"""Parse Mermaid flowcharts and split them into one valid source per subgraph.

Provenance: adapted from `md-to-html-page/scripts/mermaid_view.py` (same hub, branch
feat/md-to-html-page). The node/edge grammar is reused; this module keeps the node ids,
original node declarations, edges and subgraph membership instead of rendering HTML.
There is no runtime import from `md-to-html-page`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

ID_RE = re.compile(r"\w(?:\w|-(?![-.]))*")
# (opener, closer), longest openers first so `([` wins over `(` and `(((` over `((`.
SHAPES = (
    ("(((", ")))"), ("([", "])"), ("[[", "]]"), ("[(", ")]"), ("((", "))"), ("{{", "}}"),
    ("[/", "/]"), ("[/", "\\]"), ("[\\", "\\]"), ("[\\", "/]"),
    ("[", "]"), ("(", ")"), ("{", "}"), (">", "]"),
)
CLASS_RE = re.compile(r":::[\w-]+")
ARROW = r"[<xo]?(?:-{2,}[->xo]|-\.+-[>xo]?|={2,}[=>xo])|~{3,}"
TEXT = r'"[^"]*"|.+?'
EDGE = (
    r"\s*(?:"
    rf"(?P<sp>[<xo]?)--\s+(?P<sl>{TEXT})\s+(?P<sc>-{{2,}}[->xo])"
    rf"|(?P<dp>[<xo]?)-\.\s+(?P<dl>{TEXT})\s+(?P<dc>\.+-[>xo]?)"
    rf"|(?P<tp>[<xo]?)==\s+(?P<tl>{TEXT})\s+(?P<tc>={{2,}}[=>xo])"
    rf"|(?P<arrow>{ARROW})(?:\s*\|(?P<pl>[^|]*)\|)?"
    r")\s*"
)
RE_EDGE = re.compile(r"^" + EDGE)
RE_EDGE_ID = re.compile(r"^\s*\w+@")
RE_HEAD = re.compile(r"^(flowchart|graph)(?:\s+(LR|RL|TD|TB|BT))?\s*$")
DEFAULT_DIRECTION = "TB"
RE_BR = re.compile(r"<br\s*/?>", re.I)
RE_SKIP = re.compile(r"^(?:style|classDef|class|linkStyle|click|direction)(?:\s|$)")
RE_END = re.compile(r"^end$")
RE_SUBGRAPH = re.compile(r"^subgraph(?:\s+(.*))?$")
RE_AMP = re.compile(r"^\s*&\s*")


@dataclass(frozen=True)
class NodeMatch:
    id: str
    shaped: bool
    raw_label: str
    decl: str
    end: int


def match_node(text: str, pos: int = 0) -> NodeMatch | None:
    """Match one node reference at `pos`: id, optional shape with label, optional `:::class`."""
    m = ID_RE.match(text, pos)
    if not m:
        return None
    nid, i = m.group(0), m.end()
    if text.startswith("@{", i):
        raise ValueError("node `@{ ... }` shapes are not supported")
    j = i
    while j < len(text) and text[j] in " \t":
        j += 1
    shaped, raw, decl_end = False, "", i
    for opener, closer in SHAPES:
        if not text.startswith(opener, j):
            continue
        k = j + len(opener)
        while k < len(text) and text[k] in " \t":
            k += 1
        if k < len(text) and text[k] == '"':
            q = text.find('"', k + 1)
            if q < 0:
                continue
            c = q + 1
            while c < len(text) and text[c] in " \t":
                c += 1
            if not text.startswith(closer, c):
                continue
        else:
            c = text.find(closer, k)
            if c < 0:
                continue
        shaped, raw, decl_end = True, text[j + len(opener) : c], c + len(closer)
        break
    end = decl_end
    cm = CLASS_RE.match(text, end)
    if cm:
        end = cm.end()
    return NodeMatch(nid, shaped, raw, text[pos:decl_end], end)


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

    def label_of(self, nid: str) -> str:
        """Label of a node, or the title of a subgraph used as an edge endpoint."""
        if nid in self.nodes:
            return self.nodes[nid]
        return next((sg.title or sg.id for sg in self.subgraphs if sg.id == nid), nid)


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
    m = match_node(rest) if rest else None
    if m and m.end == len(rest):
        return m.id, (_label(m.raw_label) if m.shaped else "") or m.id
    label = _label(rest)
    return label, label


def _edge(em: re.Match) -> tuple[str | None, str]:
    """(label, arrow written in pipe-label form) for one matched link."""
    if em.group("sc"):
        return _label(em.group("sl")) or None, em.group("sp") + em.group("sc")
    if em.group("dc"):
        return _label(em.group("dl")) or None, em.group("dp") + "-" + em.group("dc")
    if em.group("tc"):
        return _label(em.group("tl")) or None, em.group("tp") + em.group("tc")
    return _label(em.group("pl") or "") or None, em.group("arrow")


def parse_flowchart(index: int, source: str) -> Flowchart:
    lines = [ln.strip().rstrip(";").strip() for ln in source.strip().splitlines()]
    lines = [ln for ln in lines if ln and not ln.startswith("%%")]
    head = RE_HEAD.match(lines[0]) if lines else None
    if not head:
        raise ValueError("not a flowchart header")
    labels: dict[str, str] = {}
    decls: dict[str, str] = {}
    root = Subgraph("", "")
    stack = [root]
    owner: dict[str, Subgraph] = {}
    subgraphs: list[Subgraph] = []
    edges: list[Edge] = []

    def node(m: NodeMatch) -> str:
        nid = m.id
        cur = stack[-1]
        if nid not in labels:
            labels[nid] = decls[nid] = nid
            owner[nid] = cur
            cur.node_ids.append(nid)
        elif owner[nid] is root and cur is not root:
            root.node_ids.remove(nid)
            cur.node_ids.append(nid)
            owner[nid] = cur
        if m.shaped:
            labels[nid] = _label(m.raw_label) or nid
            decls[nid] = m.decl.strip()
        return nid

    def node_group(ln: str, pos: int):
        m = match_node(ln, pos)
        if not m:
            return None
        ids, pos = [node(m)], m.end
        while True:
            am = RE_AMP.match(ln[pos:])
            if not am:
                return ids, pos
            pos += am.end()
            m = match_node(ln, pos)
            if not m:
                return None
            ids.append(node(m))
            pos = m.end

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
            if RE_EDGE_ID.match(ln[pos:]):
                raise ValueError(f"edge ids (`e1@-->`) are not supported: {ln}")
            em = RE_EDGE.match(ln[pos:])
            if not em:
                raise ValueError(f"cannot parse line: {ln}")
            lab, arrow = _edge(em)
            pos += em.end()
            got = node_group(ln, pos)
            if got is None:
                raise ValueError(f"cannot parse line: {ln}")
            cur, pos = got
            edges.extend(Edge(a, b, lab, arrow) for a in prev for b in cur)
            prev = cur
    if len(stack) != 1:
        raise ValueError("unclosed subgraph")
    # An edge endpoint naming a subgraph links to the cluster; it is not a node of its own.
    for sid in {sg.id for sg in subgraphs} & set(labels):
        del labels[sid], decls[sid]
        owner.pop(sid).node_ids.remove(sid)
    return Flowchart(index, head.group(2) or DEFAULT_DIRECTION, source, labels, edges, subgraphs, decls)


def split_subgraphs(fc: Flowchart) -> tuple[list[tuple[Subgraph, str]], list[Edge]]:
    """Return (part sources, cross-part edges).

    Nodes outside every subgraph form a leading synthetic part `Subgraph("", None, ...)`.
    An edge whose endpoint is a subgraph id is a cross-part edge, never part of a part source.
    """
    home = {nid: sg.id for sg in fc.subgraphs for nid in sg.node_ids}
    sg_ids = {sg.id for sg in fc.subgraphs}
    home.update({sid: sid for sid in sg_ids})
    root_ids = [nid for nid in fc.nodes if nid not in home]
    groups = list(fc.subgraphs)
    if root_ids:
        groups.insert(0, Subgraph("", None, root_ids))
        home.update({nid: "" for nid in root_ids})
    cross: list[Edge] = []
    internal: dict[str, list[Edge]] = {sg.id: [] for sg in groups}
    for e in fc.edges:
        if home[e.src] != home[e.dst]:
            cross.append(e)
        elif e.src not in sg_ids and e.dst not in sg_ids:
            internal[home[e.src]].append(e)
    parts: list[tuple[Subgraph, str]] = []
    for sg in groups:
        lines = [f"flowchart {fc.direction}"]
        lines += [f"  {fc.decls[nid]}" for nid in sg.node_ids]
        for e in internal[sg.id]:
            arrow = f"{e.arrow}|{e.label}|" if e.label else e.arrow
            lines.append(f"  {e.src} {arrow} {e.dst}")
        parts.append((sg, "\n".join(lines)))
    return parts, cross
