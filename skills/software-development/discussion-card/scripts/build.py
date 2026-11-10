"""Build the discussion-card page model and assemble the offline HTML."""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from markdown_it import MarkdownIt

# `python -I` omits the script directory from sys.path; sibling modules need it.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ids  # noqa: E402
import mermaid_svg  # noqa: E402
import ui_text  # noqa: E402
from mermaid_parse import parse_flowchart, split_subgraphs  # noqa: E402
from model import Box, DiagramJob, NodeBox, RenderedDiagram  # noqa: E402
from plan import Plan, PlanError, load_plan  # noqa: E402

ASSETS = Path(__file__).resolve().parent.parent / "assets"
MERMAID_LOCK = Path(__file__).resolve().parent / "mermaid.lock"
MERMAID_BANNER = "/*! @mermaid-js/tiny {version} | MIT License | Copyright (c) 2014 - 2022 Knut Sveidqvist */\n"
STORAGE_KEY = "discussion-card:{slug}:v1"
QUESTIONS_H2 = re.compile(
    r"open questions?|questions?|to decide|decisions? needed|вопрос|нужно решить|что решить|обсудить"
)
CALLOUT_RE = re.compile(r"^\[!(\w+)\][ \t]*")
LANG_RE = re.compile(r"^[\w+-]+$")
PLACEHOLDER = "\x00D:{key}\x00"
PLACEHOLDER_RE = re.compile("\x00D:(.*?)\x00")
FALLBACK_SLUG = "section"
INTRO_ID = "card-intro"
EXTERNAL_RE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//)", re.I)

esc = html.escape


@dataclass
class Page:
    html: str
    spots: list[str]
    intro_words: int
    config: dict
    warnings: list[str]
    diagrams: list[RenderedDiagram] = field(default_factory=list)


def _norm(s: str) -> str:
    return " ".join(s.casefold().split())


def _md() -> MarkdownIt:
    return MarkdownIt("commonmark", {"html": False}).enable("table")


def plain_text(inline) -> str:
    parts = []
    for c in inline.children or []:
        if c.type in ("text", "code_inline", "image"):
            parts.append(c.content)
        elif c.type in ("softbreak", "hardbreak"):
            parts.append(" ")
    return "".join(parts).strip()


def h2_titles(md_text: str) -> list[str]:
    toks = _md().parse(md_text)
    return [plain_text(toks[i + 1]) for i, t in enumerate(toks) if t.type == "heading_open" and t.tag == "h2" and t.level == 0]


def default_slug(md_path: Path) -> str:
    """`<parent dir>-<stem>` so same-named sources in different folders get different storage keys."""
    path = Path(md_path).resolve()
    parent, stem = ids.slugify(path.parent.name), ids.slugify(path.stem)
    parent = parent[: max(0, ids.SLUG_MAX - len(stem) - 1)].strip("-")
    return "-".join(p for p in (parent, stem) if p) or FALLBACK_SLUG


def stub_renderer(jobs: list[DiagramJob]) -> list[RenderedDiagram]:
    return [
        RenderedDiagram(j.key, f'<pre class="mermaid-src">{esc(j.source)}</pre>', [], [], None, "code")
        for j in jobs
    ]


def _end(tokens, i: int) -> int:
    closing = tokens[i].type.replace("_open", "_close")
    lvl = tokens[i].level
    j = i + 1
    while not (tokens[j].type == closing and tokens[j].level == lvl):
        j += 1
    return j


class _Ctx:
    def __init__(self, md: MarkdownIt, plan: Plan, seen: set[str], warnings: list[str]):
        self.md = md
        self.plan = plan
        self.seen = seen
        self.warnings = warnings
        self.spots: list = []  # str ids, or ("diagram", key) sentinels
        self.jobs: list[DiagramJob] = []
        self.slug = ""
        self.mermaid_n = 0
        self.part_slides: list[dict] = []
        self.chapter_title = ""
        self.reserved: set[str] = {INTRO_ID}
        self.diagram_n = 0
        self.nest = 0  # >0 while rendering the content of a spot

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def alloc(self, base: str) -> str:
        cand, n = base, 1
        while cand in self.reserved:
            n += 1
            cand = f"{base}-{n}"
        self.reserved.add(cand)
        return cand

    def inline(self, tok) -> str:
        children = self._no_external(tok.children or [])
        return self.md.renderer.renderInline(children, self.md.options, {})

    def _no_external(self, children):
        """Turn external links and images into text so no network reference reaches the output."""
        from markdown_it.token import Token

        def text(content: str):
            t = Token("text", "", 0)
            t.content = content
            return t

        out, pending = [], []  # pending: (index in out, href) for open external links
        for c in children:
            if c.type == "image":
                src = c.attrGet("src") or ""
                if src.startswith("data:image/"):
                    out.append(c)
                    continue
                alt = c.content
                label = f"[image: {alt}]" if alt else "[image]"
                out.append(text(f"{label} ({src})"))
                kind = "remote" if EXTERNAL_RE.match(src) else "local"
                self.warn(f"warning: {kind} image shown as text: {src}")
            elif c.type == "link_open" and EXTERNAL_RE.match(c.attrGet("href") or ""):
                pending.append((len(out), c.attrGet("href")))
            elif c.type == "link_close" and pending:
                start, href = pending.pop()
                shown = "".join(x.content for x in out[start:])
                if shown != href:
                    out.append(text(f" ({href})"))
                self.warn(f"warning: external link shown as text: {href}")
            else:
                out.append(c)
        return out

    def spot(self, kind: str, text: str) -> str:
        if self.nest:
            return ""
        sid = ids.spot_id(self.slug, kind, text, self.seen)
        self.spots.append(sid)
        return f' data-spot="{esc(sid)}" tabindex="0" role="button"'


def _inlines(tokens) -> list:
    return [t for t in tokens if t.type == "inline"]


def _render(ctx: _Ctx, tokens, in_spot: bool = False) -> str:
    out: list[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.type == "paragraph_open":
            inl = tokens[i + 1]
            body = ctx.inline(inl)
            if t.hidden:
                out.append(body)
            elif in_spot or ctx.nest:
                out.append(f"<p>{body}</p>")
            else:
                out.append(f"<p{ctx.spot('p', inl.content)}>{body}</p>")
            i += 3
        elif t.type in ("bullet_list_open", "ordered_list_open"):
            j = _end(tokens, i)
            out.append(_list(ctx, tokens[i : j + 1]))
            i = j + 1
        elif t.type == "table_open":
            j = _end(tokens, i)
            out.append(_table(ctx, tokens[i : j + 1]))
            i = j + 1
        elif t.type == "blockquote_open":
            j = _end(tokens, i)
            out.append(_quote(ctx, tokens[i : j + 1]))
            i = j + 1
        elif t.type == "fence":
            out.append(_fence(ctx, t))
            i += 1
        elif t.type == "code_block":
            out.append(_code_spot(ctx, t.content))
            i += 1
        elif t.type == "heading_open":
            inl = tokens[i + 1]
            out.append(f"<{t.tag}>{ctx.inline(inl)}</{t.tag}>")
            i += 3
        elif t.nesting == 1:
            j = _end(tokens, i)
            out.append(ctx.md.renderer.render(tokens[i : j + 1], ctx.md.options, {}))
            i = j + 1
        else:
            out.append(ctx.md.renderer.render([t], ctx.md.options, {}))
            i += 1
    return "".join(out)


def _list(ctx: _Ctx, tokens) -> str:
    tag = "ol" if tokens[0].type == "ordered_list_open" else "ul"
    out = [f"<{tag}>"]
    i = 1
    while i < len(tokens) - 1:
        j = _end(tokens, i)
        item = tokens[i + 1 : j]
        inl = _inlines(item)
        text = inl[0].content if inl else ""
        attrs = ctx.spot("li", text)
        ctx.nest += 1
        body = _render(ctx, item, in_spot=True)
        ctx.nest -= 1
        out.append(f"<li{attrs}>{body}</li>")
        i = j + 1
    out.append(f"</{tag}>")
    return "".join(out)


def _table(ctx: _Ctx, tokens) -> str:
    r = ctx.md.renderer
    out = ['<div class="table-wrap">']
    in_body = False
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.type == "tbody_open":
            in_body = True
        elif t.type == "tbody_close":
            in_body = False
        if t.type == "tr_open" and in_body:
            j = _end(tokens, i)
            row = tokens[i + 1 : j]
            text = " | ".join(x.content for x in _inlines(row))
            out.append(f"<tr{ctx.spot('tr', text)}>")
            for k, c in enumerate(row):
                out.append(ctx.inline(c) if c.type == "inline" else r.renderToken(row, k, ctx.md.options, {}))
            out.append("</tr>")
            i = j + 1
            continue
        if t.type == "inline":
            out.append(ctx.inline(t))
        else:
            out.append(r.renderToken(tokens, i, ctx.md.options, {}))
        i += 1
    out.append("</div>")
    return "".join(out)


def _quote(ctx: _Ctx, tokens) -> str:
    first = tokens[2] if len(tokens) > 2 and tokens[1].type == "paragraph_open" else None
    m = CALLOUT_RE.match(first.content) if first is not None else None
    if not m:
        return "<blockquote>" + _render(ctx, tokens[1:-1]) + "</blockquote>"
    name = m.group(1)
    first.content = first.content[m.end() :]
    kids = first.children or []
    if kids and kids[0].type == "text":
        kids[0].content = CALLOUT_RE.sub("", kids[0].content, count=1)
        if not kids[0].content:
            kids.pop(0)
            if kids and kids[0].type == "softbreak":
                kids.pop(0)
    first.content = first.content.lstrip("\n")
    text = " ".join(x.content for x in _inlines(tokens))
    attrs = ctx.spot("callout", text)
    ctx.nest += 1
    body = _render(ctx, tokens[1:-1], in_spot=True)
    ctx.nest -= 1
    return (
        f'<aside class="callout callout-{esc(name.lower())}"{attrs}>'
        f'<div class="callout-title">{esc(name.title())}</div>{body}</aside>'
    )


def _code_spot(ctx: _Ctx, code: str, lang: str = "") -> str:
    cls = f' class="language-{esc(lang)}"' if lang and LANG_RE.match(lang) else ""
    return f"<pre{ctx.spot('code', code)}><code{cls}>{esc(code)}</code></pre>"


def _fence(ctx: _Ctx, t) -> str:
    lang = t.info.strip().split(" ")[0] if t.info.strip() else ""
    if lang != "mermaid":
        return _code_spot(ctx, t.content, lang)
    ctx.mermaid_n += 1
    n = ctx.mermaid_n
    src = t.content.rstrip("\n")
    words = src.split()
    kind = words[0] if words else ""
    if not kind.startswith(("flowchart", "graph")):
        ctx.warnings.append(f"warning: mermaid {kind or 'diagram'} shown as code (block {n})")
        return _code_spot(ctx, t.content)
    try:
        fc = parse_flowchart(n, src)
    except ValueError as e:
        ctx.warnings.append(f"warning: mermaid flowchart shown as code (block {n}): {e}")
        return _code_spot(ctx, t.content)
    ctx.diagram_n += 1
    dn = ctx.diagram_n
    hint = ctx.plan.diagrams.get(n)
    if hint is None or hint.split != "subgraphs":
        key = f"{ctx.slug}-d{n}"
        ctx.jobs.append(DiagramJob(key, ctx.slug, fc.source, None))
        ctx.spots.append(("diagram", key))
        return f'<figure class="diagram" data-diagram="{esc(key)}">{PLACEHOLDER.format(key=key)}</figure>'
    parts, cross = split_subgraphs(fc)
    home = {nid: k for k, (sg, _) in enumerate(parts) for nid in sg.node_ids}
    home.update({sg.id: k for k, (sg, _) in enumerate(parts) if sg.id})
    out = []
    for k, (sg, part_src) in enumerate(parts, start=1):
        key = f"{ctx.slug}-d{n}-{k}"
        pid = ctx.alloc(f"{ctx.slug}-d{dn}-{k}")
        title = sg.title or None
        ctx.jobs.append(DiagramJob(key, ctx.slug, part_src, title))
        ctx.spots.append(("diagram", key))
        ctx.part_slides.append({"id": pid, "chapter": ctx.slug, "title": title or f"{ctx.chapter_title} ({k})"})
        cap = f"<figcaption>{esc(title)}</figcaption>" if title else ""
        out.append(
            f'<div class="diagram-part" id="{esc(pid)}" data-slide>{cap}'
            f'<figure class="diagram" data-diagram="{esc(key)}">{PLACEHOLDER.format(key=key)}</figure></div>'
        )
        for e in cross:
            if home[e.src] == k - 1:
                lab = f" ({esc(e.label)})" if e.label else ""
                out.append(
                    f'<div class="diagram-link" aria-hidden="true">&darr; {esc(fc.label_of(e.src))} &rarr; '
                    f"{esc(fc.label_of(e.dst))}{lab}</div>"
                )
    return f'<div class="diagram-split">{"".join(out)}</div>'


def _questions(ctx: _Ctx, tokens, hint_options: dict[int, list[str]]):
    """Split a questions section: render its first list as question cards."""
    out: list[str] = []
    questions: list[dict] = []
    i, done = 0, False
    while i < len(tokens):
        t = tokens[i]
        if not done and t.type in ("bullet_list_open", "ordered_list_open"):
            j = _end(tokens, i)
            cards = []
            k = i + 1
            while k < j:
                e = _end(tokens, k)
                item = tokens[k + 1 : e]
                inl = _inlines(item)
                text = " ".join(plain_text(x) for x in inl[:1]) if inl else ""
                n = len(questions) + 1
                attrs = ctx.spot("q", inl[0].content if inl else "")
                qid = ctx.spots[-1]  # keyed by text, not position, so answers follow the question
                questions.append({"id": qid, "text": text, "options": list(hint_options.get(n, []))})
                ctx.nest += 1
                body = _render(ctx, item, in_spot=True)
                ctx.nest -= 1
                cards.append(
                    f'<article class="question" data-qid="{esc(qid)}"{attrs}>'
                    f'<div class="question-text">{body}</div></article>'
                )
                k = e + 1
            out.append(f'<div class="questions">{"".join(cards)}</div>')
            done = True
            i = j + 1
            continue
        j = _end(tokens, i) if t.nesting == 1 else i
        out.append(_render(ctx, tokens[i : j + 1]))
        i = j + 1
    return "".join(out), questions


def _sections(tokens):
    """Return [(title or None, tokens)] split on level-0 H2; first entry is the preamble."""
    secs: list[list] = [[None, []]]
    seen_h1 = False
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.type == "heading_open" and t.level == 0 and t.tag in ("h1", "h2"):
            inl = tokens[i + 1]
            if t.tag == "h2":
                secs.append([plain_text(inl), []])
                i += 3
                continue
            if not seen_h1:
                seen_h1 = True
                i += 3
                continue
        secs[-1][1].append(t)
        i += 1
    return secs


def build_page(
    md_path: Path,
    plan: Plan,
    ui: str,
    diagram_renderer: Callable[[list[DiagramJob]], list[RenderedDiagram]],
    mermaid_js: Path | None = None,
) -> Page:
    text = Path(md_path).read_text(encoding="utf-8")
    if ui == "auto":
        ui = ui_text.detect_ui(text)
    md = _md()
    tokens = md.parse(text)
    h1 = next((plain_text(tokens[i + 1]) for i, t in enumerate(tokens) if t.type == "heading_open" and t.tag == "h1" and t.level == 0), None)
    doc_slug = plan.slug or default_slug(Path(md_path))
    warnings: list[str] = []
    seen: set[str] = set()
    ctx = _Ctx(md, plan, seen, warnings)
    hints = {_norm(h.from_): h for h in plan.chapters}

    secs = _sections(tokens)
    has_h2 = len(secs) > 1
    if not secs[0][1] and has_h2:
        secs = secs[1:]
    else:
        secs[0][0] = h1 or doc_slug

    q_title = None
    if plan.blocks.get("questions"):
        if plan.questions and plan.questions.from_:
            q_title = _norm(plan.questions.from_)
        else:
            q_title = next((_norm(t) for t, _ in secs if t and QUESTIONS_H2.search(_norm(t))), None)

    parts: list[str] = []
    words = 0
    # intro
    if plan.intro and (plan.intro.lead or plan.intro.cards):
        ctx.slug = "intro"
        ib = [f'<section class="intro" id="{INTRO_ID}">']
        if plan.intro.lead:
            ib.append(f'<p class="lead">{esc(plan.intro.lead)}</p>')
            words += len(plan.intro.lead.split())
        cards = []
        for c in plan.intro.cards:
            words += len((c.title + " " + c.text).split())
            attrs = ctx.spot("intro", f"{c.title} {c.text}")
            acc = " accent" if c.accent else ""
            cards.append(f'<article class="intro-card{acc}"{attrs}><h3>{esc(c.title)}</h3><p>{esc(c.text)}</p></article>')
        ib.append(f'<div class="intro-cards">{"".join(cards)}</div></section>')
        parts.append("".join(ib))
    if plan.blocks.get("verdict"):
        parts.append('<section class="block block-verdict" data-block="verdict"></section>')

    chapters: list[dict] = []
    slides: list[dict] = []
    questions: list[dict] = []
    for title, toks in secs:
        slug = ctx.alloc(ids.slugify(title) or FALLBACK_SLUG)
        ctx.slug, ctx.chapter_title = slug, title
        ctx.part_slides = []
        ctx.diagram_n = 0
        hint = hints.get(_norm(title))
        label = (hint.label if hint and hint.label else title)
        fold = bool(hint and hint.fold)
        if q_title is not None and _norm(title) == q_title:
            body, qs = _questions(ctx, toks, plan.questions.options if plan.questions else {})
            questions.extend(qs)
        else:
            body = _render(ctx, toks)
        chapters.append({"id": slug, "title": title, "label": label, "fold": fold})
        slides.append({"id": slug, "chapter": slug, "title": title})
        slides.extend(ctx.part_slides)
        h = f"<h2>{esc(title)}</h2>"
        if fold:
            parts.append(f'<details class="chapter" id="{esc(slug)}" data-chapter><summary>{h}</summary>{body}</details>')
        else:
            parts.append(f'<section class="chapter" id="{esc(slug)}" data-chapter>{h}{body}</section>')
    if plan.blocks.get("questions") and not questions:
        warnings.append("warning: questions block enabled but no question list found")
    if plan.blocks.get("actions"):
        parts.append('<section class="block block-actions" data-block="actions"></section>')

    rendered = diagram_renderer(ctx.jobs)
    by_key = {r.key: r for r in rendered}
    for job in ctx.jobs:
        r = by_key.get(job.key)
        if r is None:
            raise RuntimeError(f"diagram renderer returned nothing for {job.key}")
        if r.error:
            warnings.append(f"warning: diagram {r.key} shown as code: {r.error}")

    node_ids: dict[str, list[str]] = {}  # runtime diagrams: Mermaid node id per r.nodes entry
    for job in ctx.jobs:
        r = by_key[job.key]
        if r.mode == "runtime" and not r.nodes:
            fc = parse_flowchart(0, job.source)
            node_ids[job.key] = list(fc.nodes)
            r.nodes = [
                NodeBox(ids.node_spot_id(job.chapter_slug, nid), label, Box(0, 0, 0, 0), 0.0)
                for nid, label in fc.nodes.items()
            ]

    for job in ctx.jobs:
        r = by_key[job.key]
        for nb in r.nodes:
            if nb.spot_id in seen:
                n = 1
                while f"{nb.spot_id}-{n + 1}" in seen:
                    n += 1
                new = f"{nb.spot_id}-{n + 1}"
                warnings.append(f"warning: diagram node id {nb.spot_id} repeated, renamed {new}")
                if r.svg is not None:
                    r.svg = r.svg.replace(f'data-spot="{nb.spot_id}"', f'data-spot="{new}"')
                nb.spot_id = new
            seen.add(nb.spot_id)

    def diagram_html(key: str) -> str:
        r = by_key[key]
        job = next(j for j in ctx.jobs if j.key == key)
        if r.svg is not None and not r.error:
            return r.svg
        if r.mode == "runtime":
            spots = dict(zip(node_ids.get(key, []), (nb.spot_id for nb in r.nodes)))
            return (
                f'<pre class="mermaid-runtime" data-diagram="{esc(key)}" '
                f'data-node-spots="{esc(json.dumps(spots, ensure_ascii=False))}">{esc(job.source)}</pre>'
            )
        return f'<pre class="mermaid-src">{esc(job.source)}</pre>'

    body_html = PLACEHOLDER_RE.sub(lambda m: diagram_html(m.group(1)), "".join(parts))
    spots: list[str] = []
    for s in ctx.spots:
        if isinstance(s, tuple):
            spots.extend(nb.spot_id for nb in by_key[s[1]].nodes)
        else:
            spots.append(s)

    runtime = any(r.mode == "runtime" for r in by_key.values())
    fallback = [r.warning for r in by_key.values() if r.mode == "runtime" and r.warning]
    for w in fallback:
        ctx.warn(w)
    if runtime and not fallback:
        warnings.append("warning: Chrome not available, diagrams render at view time (runtime Mermaid inlined)")
    config = {
        "storageKey": STORAGE_KEY.format(slug=doc_slug),
        "ui": ui,
        "labels": ui_text.LABELS[ui],
        "chapters": chapters,
        "slides": slides,
        "blocks": {k: bool(plan.blocks.get(k)) for k in ("verdict", "questions", "actions")},
        "questions": questions,
        "runtimeDiagrams": runtime,
    }
    title = h1 or doc_slug
    page_html = _assemble(title, ui, body_html, config, mermaid_js if runtime else None)
    return Page(page_html, spots, words, config, warnings, [by_key[j.key] for j in ctx.jobs])


def _config_json(config: dict) -> str:
    return json.dumps(config, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "\\u003c!--")


def _asset(name: str, closer: str) -> str:
    text = (ASSETS / name).read_text(encoding="utf-8")
    return text.replace(closer, "<\\/" + closer[2:])


def _mermaid_banner() -> str:
    for line in MERMAID_LOCK.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        if key.strip() == "version" and value.strip():
            return MERMAID_BANNER.format(version=value.strip())
    raise RuntimeError(f"no version in {MERMAID_LOCK.name}")


def _assemble(title: str, ui: str, body: str, config: dict, mermaid_js: Path | None = None) -> str:
    lib = ""
    if mermaid_js is not None:
        text = Path(mermaid_js).read_text(encoding="utf-8").replace("</script", "<\\/script")
        lib = f'<script id="mermaid-lib">{_mermaid_banner()}{text}</script>'
    return (
        f'<!DOCTYPE html>\n<html lang="{esc(ui)}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{esc(title)}</title><style>{_asset('engine.css', '</style')}</style></head>"
        f'<body><header class="card-header"><h1>{esc(title)}</h1></header>'
        f'<main id="card-main">{body}</main>'
        f'<script type="application/json" id="card-config">{_config_json(config)}</script>'
        f"{lib}<script>{_asset('engine.js', '</script')}</script></body></html>\n"
    )


def _meta(page: Page) -> dict:
    def box(b):
        return {"x": b.x, "y": b.y, "w": b.w, "h": b.h}

    return {
        "spots": page.spots,
        "intro_words": page.intro_words,
        "diagrams": [
            {
                "key": d.key,
                "mode": d.mode,
                "nodes": [
                    {"spot_id": n.spot_id, "label": n.label, "box": box(n.box), "font_px": n.font_px}
                    for n in d.nodes
                ],
                "labels": [box(b) for b in d.labels],
            }
            for d in page.diagrams
        ],
        "warnings": page.warnings,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="build.py")
    ap.add_argument("md")
    ap.add_argument("--plan", required=True)
    ap.add_argument("-o", "--out")
    ap.add_argument("--ui", choices=ui_text.UI_CHOICES, default="auto")
    ap.add_argument("--mermaid", help="cached Mermaid JS; renders diagrams with Chrome, else inlines it for view-time rendering")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    md_path = Path(args.md)
    out = Path(args.out) if args.out else md_path.with_suffix(".html")
    try:
        text = md_path.read_text(encoding="utf-8")
        plan = load_plan(Path(args.plan), h2_titles(text))
    except PlanError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2
    except UnicodeDecodeError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2
    try:
        mermaid = Path(args.mermaid) if args.mermaid else None
        renderer = stub_renderer
        if mermaid is not None:
            def renderer(jobs: list[DiagramJob]) -> list[RenderedDiagram]:
                return mermaid_svg.render(jobs, mermaid, mermaid_svg.find_chrome())
        page = build_page(md_path, plan, args.ui, renderer, mermaid)
    except Exception as e:  # noqa: BLE001 - any build failure is a reported FAIL, not a traceback
        print(f"FAIL: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    try:
        out.write_text(page.html, encoding="utf-8")
        Path(str(out) + ".meta.json").write_text(json.dumps(_meta(page), ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        print(f"FAIL: cannot write output: {e}", file=sys.stderr)
        return 1
    for w in page.warnings:
        print(w, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
