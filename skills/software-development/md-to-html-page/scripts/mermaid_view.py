"""Deterministic text view of simple Mermaid flowcharts (no JS, no layout engine).

`render` lists every node, in source order, with its outgoing transitions and edge
labels. It returns None for anything it does not fully understand, so the caller
shows only the verbatim source.
"""
from __future__ import annotations

import html
import re

NODE = (
    r'([A-Za-z_][\w-]*)\s*(?:(\[\[|\[\(|\(\(|\[|\(|\{\{|\{|>)\s*'
    r'("[^"]*"|[^\]\)\}]*?)\s*(\]\]|\)\]|\)\)|\]|\)|\}\}|\}))?'
)
EDGE = r'\s*(?:--\s+("[^"]*"|.+?)\s+-->|-->\s*\|([^|]*)\|\s*|-\.->|==>|-->|---)\s*'
RE_NODE = re.compile(r"^" + NODE)
RE_EDGE = re.compile(r"^" + EDGE)
RE_HEAD = re.compile(r"^(flowchart|graph)\s+(LR|RL|TD|TB|BT)\s*$")
RE_BR = re.compile(r"<br\s*/?>", re.I)
UNSUPPORTED = ("classDef", "class ", "linkStyle", "click ", "subgraph", "end", "direction", "style ")


def _label(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        raw = raw[1:-1]
    return " ".join(RE_BR.sub(" ", raw).split())


def parse(src: str):
    """Return (labels by id, ids in first-seen order, edges) or None."""
    lines = [ln.strip() for ln in src.strip().splitlines()]
    lines = [ln for ln in lines if ln and not ln.startswith("%%")]
    if not lines or not RE_HEAD.match(lines[0]):
        return None
    labels: dict[str, str] = {}
    order: list[str] = []
    edges: list[tuple[str, str, str]] = []

    def node(m) -> str:
        nid, opener, text = m.group(1), m.group(2), m.group(3)
        if nid not in labels:
            labels[nid] = nid
            order.append(nid)
        if opener:
            labels[nid] = _label(text) or nid
        return nid

    for ln in lines[1:]:
        if ln.startswith(UNSUPPORTED):
            return None
        m = RE_NODE.match(ln)
        if not m:
            return None
        prev, pos = node(m), m.end()
        while pos < len(ln):
            em = RE_EDGE.match(ln[pos:])
            if not em:
                return None
            edge_label = _label(em.group(1) or em.group(2) or "")
            pos += em.end()
            nm = RE_NODE.match(ln[pos:])
            if not nm:
                return None
            cur = node(nm)
            pos += nm.end()
            edges.append((prev, cur, edge_label))
            prev = cur
    if not edges:
        return None
    return labels, order, edges


def render(src: str) -> str | None:
    parsed = parse(src)
    if parsed is None:
        return None
    labels, order, edges = parsed
    items = []
    for nid in order:
        outs = "".join(
            ('<li class="fl-labelled">' if lab else "<li>")
            + (f'<span class="fl-edge">{html.escape(lab)}</span> ' if lab else "")
            + f'<span class="fl-to">{html.escape(labels[dst])}</span></li>'
            for s, dst, lab in edges if s == nid
        )
        items.append(
            f'<li><span class="fl-label">{html.escape(labels[nid])}</span>'
            + (f'<ul class="fl-out">{outs}</ul>' if outs else "")
            + "</li>"
        )
    return f'<div class="mermaid-view" data-derived><ol class="flow">{"".join(items)}</ol></div>'
