"""Parse Mermaid flowcharts and split them into one valid source per subgraph.

Provenance: adapted from `md-to-html-page/scripts/mermaid_view.py` (same hub, branch
feat/md-to-html-page). The node/edge grammar is reused; this module keeps the node ids,
original node declarations, edges and subgraph membership instead of rendering HTML.
There is no runtime import from `md-to-html-page`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

NODE = (
    r'([A-Za-z_](?:\w|-(?![-.]))*)\s*(?:(\[\[|\[\(|\(\(|\[|\(|\{\{|\{|>)\s*'
    r'("[^"]*"|[^\]\)\}]*?)\s*(\]\]|\)\]|\)\)|\]|\)|\}\}|\}))?'
)
EDGE = (
    r'\s*(?:--\s+("[^"]*"|.+?)\s+-->|(<-->|-\.->|==>|-->|--x|--o|---)\s*(?:\|([^|]*)\|)?)\s*'
)
RE_NODE = re.compile(r"^" + NODE)
RE_EDGE = re.compile(r"^" + EDGE)
RE_HEAD = re.compile(r"^(flowchart|graph)\s+(LR|RL|TD|TB|BT)\s*$")
RE_BR = re.compile(r"<br\s*/?>", re.I)
RE_SKIP = re.compile(r"^(?:style|classDef|class|linkStyle|click|direction)(?:\s|$)")
RE_END = re.compile(r"^end$")
RE_SUBGRAPH = re.compile(r"^subgraph(?:\s+(.*))?$")
RE_AMP = re.compile(r"^\s*&\s*")


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    label: str | None = None
    arrow: str = "-->"


@dataclass
class Subgraph:
    id: str
    title: str | None
    node_ids: list[str] = field(default_factory=list)


@dataclass
class Flowchart:
    index: int
    direction: str
    source: str
    nodes: dict[str, str]
    edges: list[Edge]
    subgraphs: list[Subgraph]
    decls: dict[str, str] = field(default_factory=dict)


def find_mermaid_blocks(tokens) -> list[tuple[int, str, str]]:
    out = []
    for tok in tokens:
        if tok.type != "fence" or tok.info.strip().split(" ")[0] != "mermaid":
            continue
        src = tok.content.rstrip("\n")
        words = src.split()
        out.append((len(out) + 1, words[0] if words else "", src))
    return out


def _label(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        raw = raw[1:-1]
    return " ".join(RE_BR.sub(" ", raw).split())


def _subgraph_head(rest: str) -> tuple[str, str]:
    rest = rest.strip()
    m = RE_NODE.match(rest)
    if m and m.end() == len(rest):
        sid = m.group(1)
        return sid, (_label(m.group(3)) if m.group(2) else "") or sid
    label = _label(rest)
    return label, label


def parse_flowchart(index: int, source: str) -> Flowchart:
    lines = [ln.strip().rstrip(";").strip() for ln in source.strip().splitlines()]
    lines = [ln for ln in lines if ln and not ln.startswith("%%")]
    head = RE_HEAD.match(lines[0]) if lines else None
    if not head:
        raise ValueError("not a flowchart with a direction")
    labels: dict[str, str] = {}
    decls: dict[str, str] = {}
    root = Subgraph("", "")
    stack = [root]
    owner: dict[str, Subgraph] = {}
    subgraphs: list[Subgraph] = []
    edges: list[Edge] = []

    def node(m) -> str:
        nid = m.group(1)
        cur = stack[-1]
        if nid not in labels:
            labels[nid] = decls[nid] = nid
            owner[nid] = cur
            cur.node_ids.append(nid)
        elif owner[nid] is root and cur is not root:
            root.node_ids.remove(nid)
            cur.node_ids.append(nid)
            owner[nid] = cur
        if m.group(2):
            labels[nid] = _label(m.group(3)) or nid
            decls[nid] = m.group(0).strip()
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
            sg = Subgraph(*_subgraph_head(sm.group(1) or ""))
            subgraphs.append(sg)
            stack.append(sg)
            continue
        if RE_END.match(ln):
            if len(stack) == 1:
                raise ValueError("`end` without subgraph")
            stack.pop()
            continue
        got = node_group(ln, 0)
        if got is None:
            raise ValueError(f"cannot parse line: {ln}")
        prev, pos = got
        while pos < len(ln):
            em = RE_EDGE.match(ln[pos:])
            if not em:
                raise ValueError(f"cannot parse line: {ln}")
            lab = _label(em.group(1) or em.group(3) or "") or None
            arrow = em.group(2) or "-->"
            pos += em.end()
            got = node_group(ln, pos)
            if got is None:
                raise ValueError(f"cannot parse line: {ln}")
            cur, pos = got
            edges.extend(Edge(a, b, lab, arrow) for a in prev for b in cur)
            prev = cur
    if len(stack) != 1:
        raise ValueError("unclosed subgraph")
    return Flowchart(index, head.group(2), source, labels, edges, subgraphs, decls)


def split_subgraphs(fc: Flowchart) -> tuple[list[tuple[Subgraph, str]], list[Edge]]:
    """Return (part sources, cross-part edges).

    Nodes outside every subgraph form a leading synthetic part `Subgraph("", None, ...)`.
    """
    home = {nid: sg.id for sg in fc.subgraphs for nid in sg.node_ids}
    root_ids = [nid for nid in fc.nodes if nid not in home]
    groups = list(fc.subgraphs)
    if root_ids:
        groups.insert(0, Subgraph("", None, root_ids))
        home.update({nid: "" for nid in root_ids})
    cross: list[Edge] = []
    internal: dict[str, list[Edge]] = {sg.id: [] for sg in groups}
    for e in fc.edges:
        if home[e.src] == home[e.dst]:
            internal[home[e.src]].append(e)
        else:
            cross.append(e)
    parts: list[tuple[Subgraph, str]] = []
    for sg in groups:
        lines = [f"flowchart {fc.direction}"]
        lines += [f"  {fc.decls[nid]}" for nid in sg.node_ids]
        for e in internal[sg.id]:
            arrow = f"{e.arrow}|{e.label}|" if e.label else e.arrow
            lines.append(f"  {e.src} {arrow} {e.dst}")
        parts.append((sg, "\n".join(lines)))
    return parts, cross
