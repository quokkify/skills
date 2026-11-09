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
RE_SKIP = re.compile(r"^(?:style|classDef|class|linkStyle|click|direction)(?:\s|$)")
RE_END = re.compile(r"^end$")
RE_SUBGRAPH = re.compile(r"^subgraph(?:\s+(.*))?$")
RE_AMP = re.compile(r"^\s*&\s*")


def _label(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        raw = raw[1:-1]
    return " ".join(RE_BR.sub(" ", raw).split())


def _group_label(rest: str) -> str:
    m = RE_NODE.match(rest)
    if m and m.end() == len(rest) and m.group(2):
        return _label(m.group(3)) or m.group(1)
    return _label(rest)


def parse(src: str):
    """Return (labels by id, item tree, edges) or None.

    The tree is a list of ("node", id) and ("group", label, subtree) items.
    """
    lines = [ln.strip().rstrip(";").strip() for ln in src.strip().splitlines()]
    lines = [ln for ln in lines if ln and not ln.startswith("%%")]
    if not lines or not RE_HEAD.match(lines[0]):
        return None
    labels: dict[str, str] = {}
    root: list = []
    stack = [root]
    home: dict[str, list] = {}
    edges: list[tuple[str, str, str]] = []

    def node(m) -> str:
        nid, opener, text = m.group(1), m.group(2), m.group(3)
        if nid not in labels:
            labels[nid] = nid
            stack[-1].append(("node", nid))
            home[nid] = stack[-1]
        elif home[nid] is root and stack[-1] is not root:
            root.remove(("node", nid))
            stack[-1].append(("node", nid))
            home[nid] = stack[-1]
        if opener:
            labels[nid] = _label(text) or nid
        return nid

    def node_group(ln: str, pos: int):
        m = RE_NODE.match(ln[pos:])
        if not m:
            return None
        ids, pos = [node(m)], pos + m.end()
        while True:
            am = RE_AMP.match(ln[pos:])
            if not am:
                return ids, pos
            pos += am.end()
            m = RE_NODE.match(ln[pos:])
            if not m:
                return None
            ids.append(node(m))
            pos += m.end()

    for ln in lines[1:]:
        if RE_SKIP.match(ln):
            continue
        sm = RE_SUBGRAPH.match(ln)
        if sm:
            group: list = []
            stack[-1].append(("group", _group_label(sm.group(1) or ""), group))
            stack.append(group)
            continue
        if RE_END.match(ln):
            if len(stack) == 1:
                return None
            stack.pop()
            continue
        got = node_group(ln, 0)
        if got is None:
            return None
        prev, pos = got
        while pos < len(ln):
            em = RE_EDGE.match(ln[pos:])
            if not em:
                return None
            edge_label = _label(em.group(1) or em.group(2) or "")
            pos += em.end()
            got = node_group(ln, pos)
            if got is None:
                return None
            cur, pos = got
            edges.extend((a, b, edge_label) for a in prev for b in cur)
            prev = cur
    if not edges or len(stack) != 1:
        return None
    return labels, root, edges


def render(src: str) -> str | None:
    parsed = parse(src)
    if parsed is None:
        return None
    labels, tree, edges = parsed

    def node_html(nid: str) -> str:
        outs = "".join(
            ('<li class="fl-labelled">' if lab else "<li>")
            + (f'<span class="fl-edge">{html.escape(lab)}</span> ' if lab else "")
            + f'<span class="fl-to">{html.escape(labels[dst])}</span></li>'
            for s, dst, lab in edges if s == nid
        )
        return (
            f'<li><span class="fl-label">{html.escape(labels[nid])}</span>'
            + (f'<ul class="fl-out">{outs}</ul>' if outs else "")
            + "</li>"
        )

    def items_html(items: list) -> str:
        out = []
        for item in items:
            if item[0] == "node":
                out.append(node_html(item[1]))
            else:
                heading = f'<span class="fl-group-label">{html.escape(item[1])}</span>' if item[1] else ""
                out.append(f'<li class="fl-group">{heading}<ol class="flow">{items_html(item[2])}</ol></li>')
        return "".join(out)

    return f'<div class="mermaid-view" data-derived><ol class="flow">{items_html(tree)}</ol></div>'
