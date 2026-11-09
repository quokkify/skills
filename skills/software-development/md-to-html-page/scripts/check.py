#!/usr/bin/env python3
"""Independent fidelity and offline gate for Markdown -> HTML pages.

Usage: check.py IN.md OUT.html

Prints one result line, then each sample as "  - <sample>". Exit 0 when every gate
passes, 1 when a gate fails, 2 when an input cannot be read.

Gates run in the order words -> blocks -> order -> derived -> offline; only the first
failure is reported. The Markdown side is rendered with plain CommonMark markdown-it
(table and strikethrough enabled, no plugins); this module shares no code with the
renderer.
"""
from __future__ import annotations

import difflib
import re
import sys
from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.common.utils import escapeHtml

CSP = "default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'"
MAX_SAMPLES = 10
CONTEXT = 25

GATES = ("words", "blocks", "order", "derived", "offline")

HIDDEN_TAGS = {"head", "script", "style", "svg"}
VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}
BLOCK_TAGS = {
    "address", "article", "aside", "blockquote", "br", "dd", "details", "div", "dl", "dt",
    "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6",
    "header", "hr", "li", "main", "nav", "ol", "p", "pre", "section", "summary", "table",
    "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
}
RESOURCE_TAGS = {"link", "img", "iframe", "object", "embed", "source", "video", "audio", "track"}
RESOURCE_ATTRS = ("src", "href", "data", "srcset", "poster")

FRONT_MATTER = re.compile(r"\A---[ \t]*\n.*?\n(?:---|\.\.\.)[ \t]*(?:\n|\Z)", re.S)
CALLOUT = re.compile(r"^((?:[ \t]*>)+[ \t]*)\[![A-Za-z][\w-]*\][+-]?[ \t]*", re.M)
TASK = re.compile(r"^([ \t]*(?:[-*+]|\d+[.)])[ \t]+)\[[ xX]\][ \t]?", re.M)
WIKILINK = re.compile(r"\[\[([^\]|\n]+)(?:\|([^\]\n]+))?\]\]")
FENCE_LINE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
CODE_SPAN = re.compile(r"(`+)(?:(?!\1).)+?\1(?!`)", re.S)
RAW_ALLOWED = re.compile(r"</?(?:b|i|u|s|em|strong|kbd|sup|sub|mark|small|del|ins|br)\s*/?>", re.I)
# Relative links point at files the recipient does not have; the page renders them as
# plain text, so their hrefs are not required (their text still is).
RELATIVE_HREF = re.compile(r"^(?![a-z][a-z0-9+.-]*:|#|//)\S", re.I)
WORD = re.compile(r"\w+")
JS_NETWORK = re.compile(
    r"\b(?:fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon|importScripts)\b"
    r"|\bimport\s*\(|\bimport\s+[^;\n]*\bfrom\b|\bimport\s*['\"]"
)
CSS_REMOTE_URL = re.compile(r"url\(\s*['\"]?\s*(?:https?:)?//", re.I)


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    gate: str | None
    line: str
    samples: tuple[str, ...]


class PageText(HTMLParser):
    """Extracts visible text, code, hrefs and offline-relevant facts from a page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, str | None]] = []
        self.hidden = 0
        self.derived = 0
        self.parts: list[str] = []
        self.derived_parts: list[str] = []
        self.pres: list[str] = []
        self.codes: list[str] = []
        self.hrefs: list[str] = []
        self.scripts: list[str] = []
        self.styles: list[str] = []
        self.style_attrs: list[str] = []
        self.csp: list[str] = []
        self.offline_problems: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        a = {k: (v or "") for k, v in attrs}
        self._scan_attrs(tag, a)
        if tag == "meta" and a.get("http-equiv", "").lower() == "content-security-policy":
            self.csp.append(a.get("content", ""))
        if tag == "meta" and a.get("http-equiv", "").lower() == "refresh":
            self.offline_problems.append("meta refresh")
        if tag == "base":
            self.offline_problems.append("<base> element")
        if tag == "a" and "href" in a and not self.hidden:
            self.hrefs.append(a["href"])
        if tag == "wbr":
            return
        if tag in BLOCK_TAGS and not self.hidden:
            self._emit("\n")
        if tag in VOID_TAGS:
            return
        kind = None
        if tag in HIDDEN_TAGS or "data-chrome" in a:
            kind = "hidden"
            self.hidden += 1
        elif "data-derived" in a:
            kind = "derived"
            self.derived += 1
        self.stack.append((tag, kind))
        if tag in ("pre", "code") and not self.hidden and not self.derived:
            (self.pres if tag == "pre" else self.codes).append("")
        if tag == "script":
            self.scripts.append("")
        if tag == "style":
            self.styles.append("")

    def _scan_attrs(self, tag: str, a: dict) -> None:
        if tag == "script" and "src" in a:
            self.offline_problems.append(f"<script src={a['src']!r}>")
        if tag in RESOURCE_TAGS:
            for name in RESOURCE_ATTRS:
                value = a.get(name, "").strip()
                if value and not value.lower().startswith("data:"):
                    self.offline_problems.append(f"<{tag} {name}={value[:60]!r}>")
        for name, value in a.items():
            if name.startswith("on"):
                self.offline_problems.append(f"<{tag} {name}=...> event handler")
            elif re.sub(r"[\s\x00-\x1f]", "", value).lower().startswith("javascript:"):
                self.offline_problems.append(f"<{tag} {name}> javascript: URL")
        if "style" in a:
            self.style_attrs.append(a["style"])

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_TAGS or not any(t == tag for t, _ in self.stack):
            return
        while self.stack:
            t, kind = self.stack.pop()
            if kind == "hidden":
                self.hidden -= 1
            elif kind == "derived":
                self.derived -= 1
            if t == tag:
                break
        if tag in BLOCK_TAGS and not self.hidden:
            self._emit("\n")

    def _emit(self, text: str) -> None:
        (self.derived_parts if self.derived else self.parts).append(text)

    def handle_data(self, data: str) -> None:
        open_tags = {t for t, _ in self.stack}
        if "script" in open_tags:
            self.scripts[-1] += data
            return
        if "style" in open_tags:
            self.styles[-1] += data
            return
        if self.hidden:
            return
        self._emit(data)
        if self.derived:
            return
        if "pre" in open_tags and self.pres:
            self.pres[-1] += data
        if "code" in open_tags and self.codes:
            self.codes[-1] += data


@dataclass(frozen=True)
class Reference:
    body: str
    text: str
    fences: tuple[str, ...]
    inline_codes: tuple[str, ...]
    hrefs: tuple[str, ...]


def _outside_code(text: str, fn) -> str:
    """Apply fn to the parts of text that are not fenced code or inline code spans."""
    out: list[str] = []
    chunk: list[str] = []
    fence: str | None = None

    def flush() -> None:
        if chunk:
            piece = "\n".join(chunk)
            pos, res = 0, []
            for m in CODE_SPAN.finditer(piece):
                res.append(fn(piece[pos:m.start()]))
                res.append(m.group(0))
                pos = m.end()
            res.append(fn(piece[pos:]))
            out.append("".join(res))
            chunk.clear()

    for line in text.split("\n"):
        m = FENCE_LINE.match(line)
        if fence is None and m:
            flush()
            fence = m.group(1)
            out.append(line)
        elif fence is not None:
            out.append(line)
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not line.strip(" `~"):
                fence = None
        else:
            chunk.append(line)
            continue
    flush()
    return "\n".join(out)


def normalise(md_text: str) -> str:
    body = FRONT_MATTER.sub("", md_text, count=1)

    def clean(part: str) -> str:
        part = CALLOUT.sub(r"\1", part)
        part = TASK.sub(r"\1", part)
        return WIKILINK.sub(lambda m: m.group(2) or m.group(1), part)

    return _outside_code(body, clean)


def _escape_raw(content: str) -> str:
    """Keep attribute-free allowlisted inline tags; escape every other raw HTML."""
    out, pos = [], 0
    for m in RAW_ALLOWED.finditer(content):
        out.append(escapeHtml(content[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(escapeHtml(content[pos:]))
    return "".join(out)


def build_reference(md_text: str) -> Reference:
    body = normalise(md_text)
    md = MarkdownIt("commonmark", {"html": True}).enable(["table", "strikethrough"])
    tokens = md.parse(body)
    for tok in tokens:
        for node in [tok, *(tok.children or [])]:
            if node.type in ("html_block", "html_inline"):
                node.content = _escape_raw(node.content)
    fences: list[str] = []
    inline_codes: list[str] = []
    hrefs: list[str] = []
    for tok in tokens:
        if tok.type in ("fence", "code_block"):
            fences.append(tok.content.rstrip("\n"))
        for child in tok.children or []:
            if child.type == "code_inline":
                inline_codes.append(child.content)
            elif child.type == "link_open":
                href = child.attrGet("href") or ""
                if not RELATIVE_HREF.match(href):
                    hrefs.append(href)
    page = parse_page(md.renderer.render(tokens, md.options, {}))
    return Reference(body, "".join(page.parts), tuple(fences), tuple(inline_codes), tuple(hrefs))


def parse_page(markup: str) -> PageText:
    parser = PageText()
    parser.feed(markup)
    parser.close()
    return parser


def _fail(gate: str, reason: str, samples: list[str]) -> CheckResult:
    return CheckResult(False, gate, f"FAIL {gate}: {reason}", tuple(samples[:MAX_SAMPLES]))


def _gate_words(ref_text: str, page_text: str) -> CheckResult | None:
    want, got = Counter(WORD.findall(ref_text)), Counter(WORD.findall(page_text))
    if want == got:
        return None
    missing, extra = want - got, got - want
    entries = [("missing", w, n) for w, n in missing.items()] + [("extra", w, n) for w, n in extra.items()]
    entries.sort(key=lambda e: (not e[1].isdigit(), e[0], e[1]))
    samples = [
        f"{'digits ' if w.isdigit() else ''}{kind}: {w!r}" + (f" x{n}" if n > 1 else "")
        for kind, w, n in entries
    ]
    return _fail("words", f"{sum(missing.values())} missing, {sum(extra.values())} extra", samples)


def _gate_blocks(ref: Reference, page: PageText) -> CheckResult | None:
    pres = {p.rstrip("\n") for p in page.pres}
    codes = set(page.codes)
    hrefs = set(page.hrefs)
    samples = [f"code block not verbatim: {c[:60]!r}" for c in ref.fences if c not in pres]
    samples += [f"inline code missing: {c[:60]!r}" for c in ref.inline_codes if c not in codes]
    samples += [f"href missing: {h[:80]!r}" for h in ref.hrefs if h not in hrefs]
    if not samples:
        return None
    return _fail("blocks", f"{len(samples)} code/link item(s) not preserved", samples)


def _squeeze(text: str) -> list[str]:
    return [c for c in text if not c.isspace()]


def _gate_order(ref_text: str, page_text: str) -> CheckResult | None:
    r, o = _squeeze(ref_text), _squeeze(page_text)
    if r == o:
        return None
    lo = 0
    while lo < min(len(r), len(o)) and r[lo] == o[lo]:
        lo += 1
    hi_r, hi_o = len(r), len(o)
    while hi_r > lo and hi_o > lo and r[hi_r - 1] == o[hi_o - 1]:
        hi_r -= 1
        hi_o -= 1
    base = lo
    rs, os_ = r[lo:hi_r], o[lo:hi_o]
    samples = []
    sm = difflib.SequenceMatcher(None, rs, os_, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        ctx = "".join(r[max(0, base + i1 - CONTEXT):base + i1])
        samples.append(f"md={''.join(rs[i1:i2])[:80]!r} html={''.join(os_[j1:j2])[:80]!r} after …{ctx!r}")
        if len(samples) >= MAX_SAMPLES:
            break
    return _fail("order", f"{len(samples)} difference(s) in text sequence", samples)


def _gate_derived(ref: Reference, page: PageText) -> CheckResult | None:
    known = set(WORD.findall(ref.body))
    seen = Counter(w for w in WORD.findall("".join(page.derived_parts)) if w not in known)
    if not seen:
        return None
    return _fail("derived", f"{len(seen)} derived word(s) not in source", [f"not in source: {w!r}" for w in seen])


def _gate_offline(page: PageText) -> CheckResult | None:
    samples = list(page.offline_problems)
    if CSP not in page.csp:
        samples.append("CSP meta missing or not exact")
    for css in page.styles + page.style_attrs:
        if "@import" in css:
            samples.append("@import in CSS")
        if CSS_REMOTE_URL.search(css):
            samples.append("remote url() in CSS")
    for js in page.scripts:
        for m in JS_NETWORK.finditer(js):
            samples.append(f"network API in inline JS: {m.group(0)!r}")
    if not samples:
        return None
    return _fail("offline", f"{len(samples)} problem(s)", samples)


def check(md_text: str, html_text: str) -> CheckResult:
    ref = build_reference(md_text)
    page = parse_page(html_text)
    page_text = "".join(page.parts)
    for gate in (
        lambda: _gate_words(ref.text, page_text),
        lambda: _gate_blocks(ref, page),
        lambda: _gate_order(ref.text, page_text),
        lambda: _gate_derived(ref, page),
        lambda: _gate_offline(page),
    ):
        failure = gate()
        if failure:
            return failure
    words = len(WORD.findall(ref.text))
    code = len(ref.fences) + len(ref.inline_codes)
    return CheckResult(True, None, f"PASS words={words} code={code} hrefs={len(ref.hrefs)} order=ok offline=ok", ())


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        md_text = Path(argv[1]).read_text(encoding="utf-8")
        html_text = Path(argv[2]).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"cannot read input: {exc}", file=sys.stderr)
        return 2
    result = check(md_text, html_text)
    print(result.line)
    for sample in result.samples:
        print(f"  - {sample}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
