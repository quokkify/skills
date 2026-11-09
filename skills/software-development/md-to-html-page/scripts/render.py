#!/usr/bin/env python3
"""Render one Markdown file into one self-contained, offline HTML page.

Usage: render.py IN.md -o OUT.html [--ui auto|ru|en] [--breaks auto|on|off]

Writes the page and prints the run report to stderr: "genre: <g> (<source>)",
"transforms: <list or ->", one "unresolved: <item>" per unresolvable link and one
"warning: <text>" per warning. Exit 0 on success, 2 when the input cannot be read.

Pipeline: markdown-it-py tokens -> token passes (callouts, heading ids, links) ->
block list -> block transforms (genre components plug in here) -> HTML -> page shell
with inlined CSS/JS. Text is never rewritten; everything the page adds that is not
source text carries data-chrome, views derived from source data carry data-derived.
Shares no code with check.py on purpose.
"""
from __future__ import annotations

import argparse
import base64
import html
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import unquote

from markdown_it import MarkdownIt
from markdown_it.common.utils import escapeHtml
from markdown_it.token import Token
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.front_matter import front_matter_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

ASSETS = Path(__file__).resolve().parent.parent / "assets"
CSP = "default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'"
LIGHT_STYLE = "default"
DARK_STYLE = "github-dark"
DARK_SCOPES = (
    ('@media screen and (prefers-color-scheme: dark) {', ':root:not([data-theme="light"]) '),
    ("@media screen {", ':root[data-theme="dark"] '),
)
TOC_MIN_H2 = 3
MAX_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_MIME = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
    ".webp": "image/webp", ".svg": "image/svg+xml",
}

# Stable transform vocabulary; RenderResult.transforms is reported in this order.
TRANSFORMS = (
    "toc", "code", "callout", "image", "passport", "lede", "stepper", "compare",
    "timeline", "hypotheses", "chat", "mermaid",
)

UI: dict[str, dict[str, str]] = {
    "ru": {
        "toc": "Содержание", "copy": "Копировать", "copied": "Скопировано", "theme": "Тема",
        "note": "Заметка", "tip": "Совет", "important": "Важно", "warning": "Внимание",
        "caution": "Осторожно", "image_not_embedded": "Изображение не встроено:",
        "diagram_source": "Исходник диаграммы", "diagram_text": "Текстовый вид диаграммы",
        "genre_bug": "Баг-репорт", "genre_incident": "Инцидент", "genre_thread": "Тред",
        "genre_explainer": "Разбор", "genre_spec": "Спецификация", "genre_howto": "Инструкция",
        "genre_note": "Заметка",
    },
    "en": {
        "toc": "Contents", "copy": "Copy", "copied": "Copied", "theme": "Theme",
        "note": "Note", "tip": "Tip", "important": "Important", "warning": "Warning",
        "caution": "Caution", "image_not_embedded": "Image not embedded:",
        "diagram_source": "Diagram source", "diagram_text": "Diagram as text",
        "genre_bug": "Bug report", "genre_incident": "Incident", "genre_thread": "Thread",
        "genre_explainer": "Explainer", "genre_spec": "Specification", "genre_howto": "How-to",
        "genre_note": "Note",
    },
}

# GitHub kinds plus Obsidian aliases, folded onto the five styled kinds.
CALLOUT_KINDS = {
    "note": "note", "info": "note", "todo": "note", "abstract": "note", "summary": "note",
    "tldr": "note", "question": "note", "help": "note", "faq": "note", "example": "note",
    "quote": "note", "cite": "note", "tip": "tip", "hint": "tip", "success": "tip",
    "check": "tip", "done": "tip", "important": "important", "warning": "warning",
    "attention": "warning", "caution": "caution", "danger": "caution", "error": "caution",
    "failure": "caution", "fail": "caution", "missing": "caution", "bug": "caution",
}

# Same per-tag rule as check.py's reference side (duplicated deliberately, see tests).
RAW_ALLOWED = re.compile(r"</?(?:b|i|u|s|em|strong|kbd|sup|sub|mark|small|del|ins|br)\s*/?>", re.I)
TASK_CHECKBOX = re.compile(
    r'<input class="task-list-item-checkbox" (?:checked="checked" )?disabled="disabled" type="checkbox">'
)
WIKILINK = re.compile(r"\[\[([^\]|\n]+)(?:\|([^\]\n]+))?\]\]")
CALLOUT_LINE = re.compile(r"^(?:[ \t]*>)+[ \t]*\[![A-Za-z][\w-]*\][+-]?")
CALLOUT_MARK = re.compile(r"^\[!([A-Za-z][\w-]*)\]([+-]?)[ \t]*")
UNRESOLVED_HREF = re.compile(r"^(?![a-z][a-z0-9+.-]*:|#|//)\S", re.I)
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:|^//", re.I)
FRONT_MATTER = re.compile(r"\A---[ \t]*\n.*?\n(?:---|\.\.\.)[ \t]*(?:\n|\Z)", re.S)
FENCE_BLOCK = re.compile(r"^ {0,3}(`{3,}|~{3,}).*?(?:^ {0,3}\1[`~]*[ \t]*$|\Z)", re.S | re.M)
CODE_SPAN = re.compile(r"(`+).+?\1", re.S)
CYRILLIC = re.compile(r"[\u0400-\u04ff]")
LATIN = re.compile(r"[A-Za-z]")
WBR_SPLIT = re.compile(r"(?<=[/_.:])(?=[^/_.:])")
PYG_RULE = re.compile(r"^\.highlight \.([\w-]+) \{([^}]*)\}")
CLASS_ATTR = re.compile(r'class="([^"]+)"')
TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class RenderResult:
    html: str
    genre: str
    genre_source: str
    transforms: tuple[str, ...]
    unresolved_links: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass
class Context:
    """Per-render state shared by token passes, block transforms and render rules."""

    md: MarkdownIt
    src: str
    lang: str
    source_dir: Path | None
    meta: dict[str, str]
    used: set[str] = field(default_factory=set)
    unresolved: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    pyg_classes: set[str] = field(default_factory=set)
    toc: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def ui(self) -> dict[str, str]:
        return UI[self.lang]

    def mark(self, name: str) -> None:
        if name not in TRANSFORMS:
            raise ValueError(f"unknown transform {name!r}")
        self.used.add(name)


@dataclass
class Block:
    """A top-level token group; a transform may replace its markup via `html`."""

    tokens: list[Token]
    html: str | None = None

    @property
    def kind(self) -> str:
        return self.tokens[0].type

    def text(self) -> str:
        return " ".join(t.content for t in self.tokens if t.type == "inline")


TokenPass = Callable[[Context, list[Token]], None]
BlockTransform = Callable[[Context, list[Block]], list[Block]]


def escape_raw(content: str) -> str:
    out, pos = [], 0
    for m in RAW_ALLOWED.finditer(content):
        out.append(escapeHtml(content[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(escapeHtml(content[pos:]))
    return "".join(out)


def pick_ui(src: str, ui: str) -> str:
    if ui in UI:
        return ui
    prose = CODE_SPAN.sub(" ", FENCE_BLOCK.sub(" ", FRONT_MATTER.sub("", src, count=1)))
    return "ru" if len(CYRILLIC.findall(prose)) > len(LATIN.findall(prose)) else "en"


def slugify(text: str, seen: dict[str, int]) -> str:
    base = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    base = re.sub(r"[\s_]+", "-", base)[:60].strip("-") or "section"
    n = seen.get(base, 0)
    seen[base] = n + 1
    return base if n == 0 else f"{base}-{n}"


def plain_text(inline: Token) -> str:
    parts = []
    for child in inline.children or []:
        if child.type in ("text", "code_inline"):
            parts.append(WIKILINK.sub(lambda m: m.group(2) or m.group(1), child.content))
        elif child.type in ("softbreak", "hardbreak"):
            parts.append(" ")
    return "".join(parts).strip()


def read_front_matter(tokens: list[Token]) -> dict[str, str]:
    meta: dict[str, str] = {}
    for tok in tokens:
        if tok.type != "front_matter":
            continue
        for line in tok.content.splitlines():
            m = re.match(r"^(type|title):[ \t]*(.*?)[ \t]*$", line)
            if m and m.group(2):
                meta[m.group(1)] = m.group(2).strip("\"'")
    return meta


# ---------- token passes ----------

def pass_callouts(ctx: Context, tokens: list[Token]) -> None:
    lines = ctx.src.split("\n")
    for i, tok in enumerate(tokens):
        if tok.type != "blockquote_open" or i + 2 >= len(tokens) or tokens[i + 1].type != "paragraph_open":
            continue
        para, inline = tokens[i + 1], tokens[i + 2]
        if not para.map or not CALLOUT_LINE.match(lines[para.map[0]]):
            continue
        children = inline.children or []
        m = CALLOUT_MARK.match(children[0].content) if children and children[0].type == "text" else None
        if not m:
            continue
        children[0].content = children[0].content[m.end():]
        brk = next((k for k, c in enumerate(children) if c.type in ("softbreak", "hardbreak")), len(children))
        title, body = children[:brk], children[brk + 1:]
        inline.children = body
        if not body:
            para.hidden = tokens[i + 3].hidden = True
        close = next(t for t in tokens[i + 1:] if t.type == "blockquote_close" and t.level == tok.level)
        info = {"kind": CALLOUT_KINDS.get(m.group(1).lower(), "note"), "fold": m.group(2), "title": title}
        tok.meta["callout"] = close.meta["callout"] = info


def pass_headings(ctx: Context, tokens: list[Token]) -> None:
    seen: dict[str, int] = {}
    for i, tok in enumerate(tokens):
        if tok.type != "heading_open":
            continue
        text = plain_text(tokens[i + 1])
        sid = slugify(text, seen)
        tok.attrSet("id", sid)
        if tok.level == 0 and tok.tag in ("h2", "h3"):
            ctx.toc.append((tok.tag, sid, text))


def pass_links(ctx: Context, tokens: list[Token]) -> None:
    for tok in tokens:
        open_link: Token | None = None
        for child in tok.children or []:
            if child.type == "text":
                ctx.unresolved.extend(f"[[{m.group(1).strip()}]]" for m in WIKILINK.finditer(child.content))
            elif child.type == "link_open":
                href = child.attrGet("href") or ""
                if UNRESOLVED_HREF.match(href):
                    child.meta["unresolved"] = True
                    open_link = child
                    ctx.unresolved.append(href)
            elif child.type == "link_close" and open_link is not None:
                child.meta["unresolved"] = True
                open_link = None


# pass_links runs first: pass_callouts moves title children out of the inline token.
TOKEN_PASSES: list[TokenPass] = [pass_links, pass_callouts, pass_headings]
BLOCK_TRANSFORMS: list[BlockTransform] = []


# ---------- render rules ----------

def _ctx(env: dict) -> Context:
    return env["ctx"]


def rule_text(self, tokens, idx, options, env) -> str:
    content, out, pos = tokens[idx].content, [], 0
    for m in WIKILINK.finditer(content):
        out.append(escapeHtml(content[pos:m.start()]))
        out.append(f'<span class="wikilink">{escapeHtml(m.group(2) or m.group(1))}</span>')
        pos = m.end()
    out.append(escapeHtml(content[pos:]))
    return "".join(out)


def rule_raw(self, tokens, idx, options, env) -> str:
    content = tokens[idx].content
    return content if TASK_CHECKBOX.fullmatch(content) else escape_raw(content)


def rule_code_inline(self, tokens, idx, options, env) -> str:
    parts = WBR_SPLIT.split(tokens[idx].content)
    return "<code>" + "<wbr>".join(escapeHtml(p) for p in parts) + "</code>"


def highlight_code(ctx: Context, code: str, lang: str) -> tuple[str, bool]:
    try:
        lexer = get_lexer_by_name(lang, stripnl=False, ensurenl=False) if lang else None
    except ClassNotFound:
        lexer = None
    if lexer is not None:
        body = highlight(code, lexer, HtmlFormatter(nowrap=True))
        if body.endswith("\n") and not code.endswith("\n"):
            body = body[:-1]
        if html.unescape(TAG.sub("", body)) == code:
            for classes in CLASS_ATTR.findall(body):
                ctx.pyg_classes.update(classes.split())
            return body, True
    return escapeHtml(code), False


def rule_fence(self, tokens, idx, options, env) -> str:
    ctx, tok = _ctx(env), tokens[idx]
    info = tok.info.strip() if tok.type == "fence" else ""
    lang = info.split(maxsplit=1)[0].lower() if info else ""
    code = tok.content[:-1] if tok.content.endswith("\n") else tok.content
    body, lit = highlight_code(ctx, code, lang)
    ctx.mark("code")
    label = f'<span class="lang">{escapeHtml(lang)}</span>' if lang else ""
    pre_cls = ' class="highlight"' if lit else ""
    code_cls = f' class="language-{escapeHtml(lang)}"' if lang else ""
    return (
        f'<figure class="code"><figcaption data-chrome>{label}'
        f'<button type="button" class="copy" data-chrome data-copied="{escapeHtml(ctx.ui["copied"])}" hidden>'
        f'{escapeHtml(ctx.ui["copy"])}</button></figcaption>'
        f"<pre{pre_cls}><code{code_cls}>{body}</code></pre></figure>\n"
    )


def rule_link_open(self, tokens, idx, options, env) -> str:
    tok = tokens[idx]
    if tok.meta.get("unresolved"):
        return '<span class="xref">'
    return self.renderToken(tokens, idx, options, env)


def rule_link_close(self, tokens, idx, options, env) -> str:
    return "</span>" if tokens[idx].meta.get("unresolved") else "</a>"


def rule_image(self, tokens, idx, options, env) -> str:
    ctx, tok = _ctx(env), tokens[idx]
    src = tok.attrGet("src") or ""
    alt = self.renderInlineAsText(tok.children or [], options, env)
    ctx.mark("image")
    data, reason = embed_image(ctx.source_dir, src)
    if data:
        return f'<img src="{data}" alt="{escapeHtml(alt)}">'
    if reason:
        ctx.warnings.append(f"image not embedded: {src} ({reason})")
    shown = " ".join(x for x in (alt, ctx.md.normalizeLinkText(src)) if x)
    return (
        f'<span class="img-ph"><span data-chrome>{escapeHtml(ctx.ui["image_not_embedded"])}</span> '
        f"<span data-derived>{escapeHtml(shown)}</span></span>"
    )


def embed_image(source_dir: Path | None, src: str) -> tuple[str | None, str | None]:
    """Return (data URI, None), or (None, reason); remote sources give (None, None)."""
    if not src or SCHEME.match(src):
        return None, None
    if source_dir is None:
        return None, "no source directory"
    root = source_dir.resolve()
    try:
        path = (root / unquote(src)).resolve()
        path.relative_to(root)
    except (ValueError, OSError):
        return None, "outside the source directory"
    mime = IMAGE_MIME.get(path.suffix.lower())
    if mime is None:
        return None, "unsupported image type"
    if not path.is_file():
        return None, "file not found"
    if path.stat().st_size > MAX_IMAGE_BYTES:
        return None, "file too large"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}", None


def rule_blockquote_open(self, tokens, idx, options, env) -> str:
    ctx, info = _ctx(env), tokens[idx].meta.get("callout")
    if not info:
        return "<blockquote>\n"
    ctx.mark("callout")
    kind = info["kind"]
    title = self.renderInline(info["title"], options, env).strip()
    if not title:
        title = f"<span data-chrome>{escapeHtml(ctx.ui[kind])}</span>"
    head = f'<span class="c-icon" data-chrome aria-hidden="true"></span><span class="c-text">{title}</span>'
    if info["fold"]:
        opened = " open" if info["fold"] == "+" else ""
        return (f'<details class="callout c-{kind}"{opened}><summary class="c-title">{head}</summary>'
                f'<div class="c-body">\n')
    return f'<aside class="callout c-{kind}"><div class="c-title">{head}</div><div class="c-body">\n'


def rule_blockquote_close(self, tokens, idx, options, env) -> str:
    info = tokens[idx].meta.get("callout")
    if not info:
        return "</blockquote>\n"
    return "</div></details>\n" if info["fold"] else "</div></aside>\n"


def make_md() -> MarkdownIt:
    md = (
        MarkdownIt("commonmark", {"html": True, "linkify": True, "typographer": False, "xhtmlOut": False})
        .enable(["table", "strikethrough", "linkify"])
        .use(front_matter_plugin)
        .use(footnote_plugin)
        .use(tasklists_plugin)
    )
    md.linkify.set({"fuzzy_link": False, "fuzzy_email": False, "fuzzy_ip": False})
    rules = {
        "text": rule_text, "html_inline": rule_raw, "html_block": rule_raw,
        "code_inline": rule_code_inline, "fence": rule_fence, "code_block": rule_fence,
        "link_open": rule_link_open, "link_close": rule_link_close, "image": rule_image,
        "blockquote_open": rule_blockquote_open, "blockquote_close": rule_blockquote_close,
        "table_open": lambda self, t, i, o, e: '<div class="tbl"><table>\n',
        "table_close": lambda self, t, i, o, e: "</table></div>\n",
    }
    for name, fn in rules.items():
        md.add_render_rule(name, fn)
    return md


def to_blocks(tokens: list[Token]) -> list[Block]:
    blocks, cur, depth = [], [], 0
    for tok in tokens:
        cur.append(tok)
        depth += tok.nesting
        if depth == 0:
            blocks.append(Block(cur))
            cur = []
    if cur:
        blocks.append(Block(cur))
    return blocks


def render_blocks(ctx: Context, blocks: list[Block], env: dict) -> str:
    md = ctx.md
    return "".join(b.html if b.html is not None else md.renderer.render(b.tokens, md.options, env) for b in blocks)


# ---------- page shell ----------

def pygments_css(classes: set[str]) -> str:
    def rules(style: str) -> dict[str, str]:
        found = {}
        for line in HtmlFormatter(style=style).get_style_defs(".highlight").splitlines():
            m = PYG_RULE.match(line.strip())
            if m and m.group(1) in classes:
                found[m.group(1)] = m.group(2).strip()
        return found

    light, dark = rules(LIGHT_STYLE), rules(DARK_STYLE)
    used = sorted(classes)
    out = [f".highlight .{c} {{ {light[c]} }}" for c in used if c in light]
    for media, scope in DARK_SCOPES:
        body = [f"  {scope}.highlight .{c} {{ {dark.get(c, 'color: inherit')} }}" for c in used if c in light or c in dark]
        if body:
            out += [media, *body, "}"]
    return "\n".join(out)


def toc_html(ctx: Context) -> str:
    if sum(1 for tag, _, _ in ctx.toc if tag == "h2") < TOC_MIN_H2:
        return ""
    ctx.mark("toc")
    items = "".join(f'<li class="t-{tag}"><a href="#{escapeHtml(sid)}">{escapeHtml(text)}</a></li>'
                    for tag, sid, text in ctx.toc)
    label = escapeHtml(ctx.ui["toc"])
    return (f'<nav data-chrome class="toc" aria-label="{label}"><details open><summary>{label}</summary>'
            f"<ol>{items}</ol></details></nav>\n")


def page_shell(ctx: Context, title: str, chrome_title: str, body: str, toc: str) -> str:
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    js = (ASSETS / "page.js").read_text(encoding="utf-8")
    pyg = pygments_css(ctx.pyg_classes)
    heading = f'<h1 class="doc-title" data-chrome>{escapeHtml(chrome_title)}</h1>\n' if chrome_title else ""
    layout = "page has-toc" if toc else "page"
    theme = escapeHtml(ctx.ui["theme"])
    return f"""<!doctype html>
<html lang="{ctx.lang}">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{escapeHtml(title)}</title>
<style>
{css}{pyg}
</style>
</head>
<body>
<div class="bar" data-chrome><button type="button" class="theme-toggle" data-chrome aria-label="{theme}" hidden>{theme}</button></div>
<div class="{layout}">
{toc}<main class="doc">
{heading}{body}</main>
</div>
<script>
{js}</script>
</body>
</html>
"""


def build(src: str, *, source_dir: Path | None = None, stem: str = "document", ui: str = "auto",
          breaks: str = "auto") -> RenderResult:
    md = make_md()
    tokens = md.parse(src)
    meta = read_front_matter(tokens)
    tokens = [t for t in tokens if t.type != "front_matter"]
    ctx = Context(md=md, src=src, lang=pick_ui(src, ui), source_dir=source_dir, meta=meta)
    for token_pass in TOKEN_PASSES:
        token_pass(ctx, tokens)
    blocks = to_blocks(tokens)
    for transform in BLOCK_TRANSFORMS:
        blocks = transform(ctx, blocks)

    genre, genre_source = "note", "detected"
    md.options["breaks"] = breaks == "on" or (breaks == "auto" and genre == "thread")
    env = {"ctx": ctx}
    body = render_blocks(ctx, blocks, env)

    h1 = next((plain_text(tokens[i + 1]) for i, t in enumerate(tokens)
               if t.type == "heading_open" and t.tag == "h1" and t.level == 0), "")
    title = meta.get("title") or h1 or stem
    chrome_title = meta.get("title", "") if not h1 else ""
    page = page_shell(ctx, title, chrome_title, body, toc_html(ctx))
    return RenderResult(
        html=page,
        genre=genre,
        genre_source=genre_source,
        transforms=tuple(n for n in TRANSFORMS if n in ctx.used),
        unresolved_links=tuple(dict.fromkeys(ctx.unresolved)),
        warnings=tuple(dict.fromkeys(ctx.warnings)),
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render Markdown into one offline HTML page.")
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--ui", choices=("auto", "ru", "en"), default="auto")
    ap.add_argument("--breaks", choices=("auto", "on", "off"), default="auto")
    args = ap.parse_args(argv)
    try:
        src = args.input.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"cannot read input: {exc}", file=sys.stderr)
        return 2
    result = build(src, source_dir=args.input.parent, stem=args.input.stem, ui=args.ui, breaks=args.breaks)
    args.output.write_text(result.html, encoding="utf-8")
    report = [f"genre: {result.genre} ({result.genre_source})",
              f"transforms: {', '.join(result.transforms) or '-'}"]
    report += [f"unresolved: {u}" for u in result.unresolved_links]
    report += [f"warning: {w}" for w in result.warnings]
    print("\n".join(report), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
