"""Independent gate run after build: decides PASS/FAIL and prints the check line.

Gates: words, ids, diagrams, overlap, font, offline, id diff (see the design spec).
Exit codes: 0 pass; 1 check fail; 2 bad arguments or unreadable inputs; 3 environment.
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

# `python -I` omits the script directory from sys.path; sibling modules need it.
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from markdown_it import MarkdownIt
except ImportError as e:  # pragma: no cover - environment problem, reported via exit code 3
    print(f"FAIL: environment: {e}", file=sys.stderr)
    sys.exit(3)

from mermaid_parse import parse_flowchart  # noqa: E402

MIN_FONT_PX = 14
OVERLAP_EPS = 0.01
MAX_SAMPLES = 5
WORD_RE = re.compile(r"\w+")
EXTERNAL_RE = re.compile(r"^(?:[a-z][a-z0-9+.-]*://|//|mailto:)", re.I)
ANY_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)
CSS_URL_RE = re.compile(r"url\(\s*[\"']?([^\"')]*)")
CSS_IMPORT_RE = re.compile(r"@import\s+(?:url\(\s*)?[\"']?([^\"')\s;]+)", re.I)
FETCH_RE = re.compile(r"fetch\(\s*[\"'`]([^\"'`]*)")
NODE_G_RE = re.compile(r"<g\b[^>]*>")
TAG_RE = re.compile(r"<[^>]*>")
MERMAID_ENTITY_RE = re.compile(r"#(?:(\d+)|([A-Za-z][A-Za-z0-9]*));")
SKIP_TEXT_TAGS = {"script", "style"}
RELATIVE_ATTRS = ("href", "xlink:href")


@dataclass
class CheckResult:
    ok: bool
    line: str
    samples: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class CheckError(Exception):
    """Bad or unreadable input (exit code 2)."""


def words_of(text: str) -> list[str]:
    return WORD_RE.findall(text.casefold())


def _inline_words(children) -> list[str]:
    out: list[str] = []
    links: list[tuple[str, list[str]]] = []
    for c in children or []:
        shown: list[str] = []
        if c.type in ("text", "code_inline"):
            shown.append(c.content)
        elif c.type == "image":
            src = c.attrGet("src") or ""
            if not src.startswith("data:image/"):
                label = f"[image: {c.content}]" if c.content else "[image]"
                shown.append(f"{label} ({src})")
        elif c.type in ("softbreak", "hardbreak"):
            shown.append(" ")
        elif c.type == "link_open" and EXTERNAL_RE.match(c.attrGet("href") or ""):
            links.append((c.attrGet("href") or "", []))
            continue
        elif c.type == "link_close" and links:
            href, parts = links.pop()
            if "".join(parts) != href:
                shown.append(f" ({href})")
        else:
            continue
        for s in shown:
            if links:
                links[-1][1].append(s)
            out.extend(words_of(s))
    return out


def label_text(raw: str) -> str:
    """Visible text of a Mermaid label: tags removed, `#name;`/`#NNN;` and `&..;` entities decoded."""

    def ent(m: re.Match) -> str:
        if m.group(1):
            return f"&#{m.group(1)};"
        return f"&{m.group(2)};"

    return html_lib.unescape(html_lib.unescape(MERMAID_ENTITY_RE.sub(ent, TAG_RE.sub(" ", raw))))


def _flowchart_words(index: int, src: str) -> list[str] | None:
    try:
        fc = parse_flowchart(index, src)
    except ValueError:
        return None
    parts = list(fc.nodes.values())
    parts += [e.label for e in fc.edges if e.label]
    parts += [sg.title for sg in fc.subgraphs if sg.title]
    return [w for p in parts for w in words_of(label_text(p))]


def source_words(md_text: str) -> Counter:
    tokens = MarkdownIt("commonmark", {"html": False}).enable("table").parse(md_text)
    out: list[str] = []
    mermaid_n = 0
    for t in tokens:
        if t.type == "inline":
            out.extend(_inline_words(t.children))
        elif t.type == "code_block":
            out.extend(words_of(t.content))
        elif t.type == "fence":
            lang = t.info.strip().split(" ")[0] if t.info.strip() else ""
            if lang != "mermaid":
                out.extend(words_of(t.content))
                continue
            mermaid_n += 1
            src = t.content.rstrip("\n")
            kind = (src.split() or [""])[0]
            fw = _flowchart_words(mermaid_n, src) if kind.startswith(("flowchart", "graph")) else None
            out.extend(fw if fw is not None else words_of(src))
    return Counter(out)


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.spots: list[str] = []
        self.refs: list[tuple[str, str]] = []  # (kind, value) of network-capable candidates
        self.relative: list[str] = []
        self.config: dict | None = None
        self._stack: list[str] = []
        self._cfg_buf: list[str] | None = None
        self._script_buf: list[str] | None = None
        self._style_buf: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        self._stack.append(tag)
        if "data-spot" in a:
            self.spots.append(a["data-spot"])
        if tag == "script":
            if a.get("id") == "card-config":
                self._cfg_buf = []
            elif a.get("type", "") in ("", "text/javascript", "module"):
                self._script_buf = []
        if tag == "style":
            self._style_buf = []
        src = a.get("src")
        if src is not None and src != "" and not src.startswith(("data:", "#")):
            self.refs.append(("src", src))
        for k in RELATIVE_ATTRS:
            if k in a:
                v = a[k].strip()
                if EXTERNAL_RE.match(v):
                    self.refs.append((k, v))
                elif v and not v.startswith("#") and not ANY_SCHEME_RE.match(v):
                    self.relative.append(v)
        if "srcset" in a and EXTERNAL_RE.match(a["srcset"].strip()):
            self.refs.append(("srcset", a["srcset"]))
        if "style" in a:
            self._css(a["style"])

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "script":
            if self._cfg_buf is not None:
                try:
                    self.config = json.loads("".join(self._cfg_buf))
                except ValueError:
                    self.config = None
                self._cfg_buf = None
            if self._script_buf is not None:
                for m in FETCH_RE.finditer("".join(self._script_buf)):
                    if EXTERNAL_RE.match(m.group(1)):
                        self.refs.append(("fetch(", m.group(1)))
                self._script_buf = None
        if tag == "style" and self._style_buf is not None:
            self._css("".join(self._style_buf))
            self._style_buf = None
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i] == tag:
                del self._stack[i:]
                break

    def handle_data(self, data):
        if self._cfg_buf is not None:
            self._cfg_buf.append(data)
        elif self._script_buf is not None:
            self._script_buf.append(data)
        elif self._style_buf is not None:
            self._style_buf.append(data)
        elif not any(t in SKIP_TEXT_TAGS for t in self._stack):
            self.text.append(data)

    def _css(self, css: str) -> None:
        for m in CSS_URL_RE.finditer(css):
            if EXTERNAL_RE.match(m.group(1).strip()):
                self.refs.append(("url()", m.group(1).strip()))
        for m in CSS_IMPORT_RE.finditer(css):
            if EXTERNAL_RE.match(m.group(1).strip()):
                self.refs.append(("@import", m.group(1).strip()))


def _parse_page(html_text: str) -> _PageParser:
    p = _PageParser()
    p.feed(html_text)
    p.close()
    return p


def _read(path: Path, what: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise CheckError(f"cannot read {what}: {e}") from e


def _read_json(path: Path, what: str):
    try:
        return json.loads(_read(path, what))
    except ValueError as e:
        raise CheckError(f"{what} is not valid JSON: {e}") from e


def _intersects(a: dict, b: dict) -> bool:
    return (
        min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]) > OVERLAP_EPS
        and min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]) > OVERLAP_EPS
    )


def _previous_ids(previous: Path | None, state: dict | None) -> set[str] | None:
    if previous is None and state is None:
        return None
    ids: set[str] = set()
    if previous is not None:
        page = _parse_page(_read(previous, "previous page"))
        ids.update(page.spots)
        cfg_spots = (page.config or {}).get("spots")
        if isinstance(cfg_spots, list):
            ids.update(s for s in cfg_spots if isinstance(s, str))
    if state is not None:
        ids.update((state.get("spots") or {}).keys())
    return ids


def _holds_mark(entry) -> bool:
    return isinstance(entry, dict) and bool(entry.get("status") or entry.get("comments"))


def check(
    md_path: Path,
    html_path: Path,
    meta_path: Path,
    previous: Path | None = None,
    allow_drop: bool = False,
    previous_state: Path | None = None,
) -> CheckResult:
    md_text = _read(md_path, "markdown")
    page = _parse_page(_read(html_path, "page"))
    meta = _read_json(meta_path, "meta sidecar")
    state = _read_json(previous_state, "previous state") if previous_state else None
    if state is not None and not isinstance(state, dict):
        raise CheckError("previous state must be a JSON object")
    prev_ids = _previous_ids(previous, state)

    warnings: list[str] = []
    fails: list[tuple[str, str, list[str]]] = []  # (gate, reason, samples)

    # words
    src = source_words(md_text)
    have = Counter(w for chunk in page.text for w in words_of(chunk))
    missing = [(w, c - have[w]) for w, c in src.items() if have[w] < c]
    if missing:
        fails.append(("words", f"{sum(n for _, n in missing)} source word(s) missing from the page",
                      [f"missing: {w}" + (f" (x{n})" if n > 1 else "") for w, n in sorted(missing)]))
    words_n = sum(src.values())
    extra_n = int(meta.get("intro_words", 0))

    # ids
    spot_counts = Counter(page.spots)
    dups = sorted(s for s, c in spot_counts.items() if c > 1)
    if dups:
        fails.append(("ids", f"{len(dups)} duplicate data-spot", [f"duplicate: {s}" for s in dups]))
    diagrams = meta.get("diagrams", [])
    page_spots = set(page.spots)
    orphan: list[str] = []
    for d in diagrams:
        for n in d.get("nodes", []):
            if n["spot_id"] not in page_spots:
                orphan.append(f"node without spot: {d['key']}/{n['spot_id']} ({n.get('label', '')})")
    for s in meta.get("spots", []):
        if s not in page_spots and not any(f"node without spot: " in o and s in o for o in orphan):
            orphan.append(f"spot not on page: {s}")
    html_raw = _read(html_path, "page")
    for m in re.finditer(r'<svg\b.*?</svg>', html_raw, re.S):
        for g in NODE_G_RE.findall(m.group(0)):
            if re.search(r'class="[^"]*\bnode\b', g) and "data-spot=" not in g:
                orphan.append(f"mermaid node without spot: {g[:80]}")
    if orphan:
        fails.append(("ids", f"{len(orphan)} spot(s) missing", orphan))

    # diagrams
    mer_blocks = 0
    toks = MarkdownIt("commonmark", {"html": False}).enable("table").parse(md_text)
    n = 0
    for t in toks:
        if t.type == "fence" and (t.info.strip().split(" ") or [""])[0] == "mermaid":
            n += 1
            src_text = t.content.rstrip("\n")
            kind = (src_text.split() or [""])[0]
            if kind.startswith(("flowchart", "graph")):
                try:
                    parse_flowchart(n, src_text)
                    mer_blocks += 1
                except ValueError:
                    pass
    undone: list[str] = []
    if mer_blocks and not diagrams:
        undone.append(f"{mer_blocks} flowchart block(s) neither rendered nor reported")
    warn_text = "\n".join(meta.get("warnings", []))
    for d in diagrams:
        key, mode = d["key"], d.get("mode", "code")
        if mode == "static":
            ok = re.search(rf'data-diagram="{re.escape(key)}">\s*<svg\b', html_raw)
        elif mode == "runtime":
            ok = re.search(rf'data-diagram="{re.escape(key)}">\s*<pre class="mermaid-runtime"', html_raw)
        else:
            ok = f"diagram {key} shown as code" in warn_text
        if not ok:
            undone.append(f"diagram {key} ({mode}) neither rendered nor reported")
    if undone:
        fails.append(("diagrams", f"{len(undone)} diagram problem(s)", undone))

    # overlap and font
    runtime = any(d.get("mode") == "runtime" for d in diagrams)
    if runtime:
        warnings.append("warning: overlap and font gates skipped (runtime diagrams)")
    else:
        over: list[str] = []
        small: list[str] = []
        for d in diagrams:
            items = [(f"node {x['spot_id']}", x["box"]) for x in d.get("nodes", [])]
            items += [(f"label#{i}", b) for i, b in enumerate(d.get("labels", []))]
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    if _intersects(items[i][1], items[j][1]):
                        over.append(f"{d['key']}: {items[i][0]} overlaps {items[j][0]}")
            for x in d.get("nodes", []):
                if float(x["font_px"]) < MIN_FONT_PX:
                    small.append(f"{d['key']}: {x['spot_id']} font {x['font_px']}px < {MIN_FONT_PX}px")
        if over:
            fails.append(("overlap", f"{len(over)} overlapping box pair(s)", over))
        if small:
            fails.append(("font", f"{len(small)} text(s) below {MIN_FONT_PX}px", small))

    # offline
    if page.refs:
        fails.append(("offline", f"{len(page.refs)} reference(s) outside the file",
                      [f"{k}: {v}" for k, v in page.refs]))
    for href in page.relative:
        warnings.append(f"warning: relative link: {href}")

    # id diff
    ids_suffix = ""
    if prev_ids is not None:
        dropped = sorted(prev_ids - page_spots)
        for i in dropped:
            warnings.append(f"warning: dropped id: {i}")
        marked = [i for i in dropped if state and _holds_mark((state.get("spots") or {}).get(i))]
        if marked and not allow_drop:
            fails.append(("id diff", f"{len(marked)} dropped id(s) hold a mark", [f"dropped with mark: {i}" for i in marked]))
        ids_suffix = " ids=kept" if not dropped else f" ids=-{len(dropped)}"

    if fails:
        fails.sort(key=lambda f: f[0] != "offline")  # offline is reported first; sort is stable
        gate, reason, samples = fails[0]
        return CheckResult(False, f"FAIL {gate}: {reason}", samples[:MAX_SAMPLES], warnings)
    spots_n = len(page_spots)
    diag = "runtime" if runtime else str(len(diagrams))
    line = f"PASS words={words_n} extra={extra_n} spots={spots_n} diagrams={diag} offline=ok{ids_suffix}"
    return CheckResult(True, line, [], warnings)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="check.py")
    ap.add_argument("md")
    ap.add_argument("html")
    ap.add_argument("--meta")
    ap.add_argument("--previous")
    ap.add_argument("--previous-state")
    ap.add_argument("--allow-drop", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    meta = Path(args.meta) if args.meta else Path(str(args.html) + ".meta.json")
    try:
        res = check(
            Path(args.md),
            Path(args.html),
            meta,
            Path(args.previous) if args.previous else None,
            args.allow_drop,
            Path(args.previous_state) if args.previous_state else None,
        )
    except CheckError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2
    except (KeyError, TypeError, AttributeError, ValueError) as e:
        print(f"FAIL: malformed meta sidecar: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    for w in res.warnings:
        print(w, file=sys.stderr)
    print(res.line)
    for s in res.samples:
        print(s)
    return 0 if res.ok else 1


if __name__ == "__main__":
    sys.exit(main())
