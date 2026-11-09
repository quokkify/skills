"""Load and validate a discussion-card plan (card.yaml)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

KINDS = ("proposal", "retro", "review")
BLOCK_NAMES = ("verdict", "questions", "actions")
DEFAULT_BLOCKS = {
    "proposal": {"verdict", "questions", "actions"},
    "retro": {"questions", "actions"},
    "review": {"questions"},
}
SLUG_RE = re.compile(r"^[a-z0-9-]{1,40}$")
SPLIT_VALUES = ("subgraphs",)


class PlanError(Exception):
    """Raised for any schema violation; message is `<key path>: <reason>`."""


@dataclass
class IntroCard:
    title: str
    text: str
    accent: bool = False


@dataclass
class Intro:
    lead: str | None
    cards: list[IntroCard] = field(default_factory=list)


@dataclass
class ChapterHint:
    from_: str
    label: str | None = None
    fold: bool = False


@dataclass
class QuestionsHint:
    from_: str | None
    options: dict[int, list[str]] = field(default_factory=dict)


@dataclass
class DiagramHint:
    split: str | None = None


@dataclass
class Plan:
    version: int
    kind: str
    slug: str | None
    blocks: dict[str, bool]
    intro: Intro | None
    chapters: list[ChapterHint]
    questions: QuestionsHint | None
    diagrams: dict[int, DiagramHint]


def _norm(s: str) -> str:
    return " ".join(s.casefold().split())


def _mapping(value, path: str, allowed: set[str]) -> dict:
    if not isinstance(value, dict):
        raise PlanError(f"{path}: must be a mapping")
    for key in value:
        if key not in allowed:
            name = f"{path}.{key}" if path != "plan" else str(key)
            raise PlanError(f"unknown key: {name}")
    return value


def _str(value, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PlanError(f"{path}: must be a non-empty string")
    return value


def _opt_str(m: dict, key: str, path: str) -> str | None:
    return _str(m[key], f"{path}.{key}") if m.get(key) is not None else None


def _bool(value, path: str) -> bool:
    if not isinstance(value, bool):
        raise PlanError(f"{path}: must be true or false")
    return value


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _match_h2(value: str, path: str, h2_norm: set[str]) -> None:
    if _norm(value) not in h2_norm:
        raise PlanError(f'{path} "{value}" matches no H2')


def _intro(raw) -> Intro:
    m = _mapping(raw, "intro", {"lead", "cards"})
    cards = []
    raw_cards = m.get("cards") or []
    if not isinstance(raw_cards, list):
        raise PlanError("intro.cards: must be a list")
    for i, c in enumerate(raw_cards):
        p = f"intro.cards[{i}]"
        cm = _mapping(c, p, {"title", "text", "accent"})
        for req in ("title", "text"):
            if req not in cm:
                raise PlanError(f"{p}.{req}: required")
        cards.append(
            IntroCard(
                title=_str(cm["title"], f"{p}.title"),
                text=_str(cm["text"], f"{p}.text"),
                accent=_bool(cm.get("accent", False), f"{p}.accent"),
            )
        )
    return Intro(lead=_opt_str(m, "lead", "intro"), cards=cards)


def _chapters(raw, h2_norm: set[str]) -> list[ChapterHint]:
    if not isinstance(raw, list):
        raise PlanError("chapters: must be a list")
    out = []
    for i, c in enumerate(raw):
        p = f"chapters[{i}]"
        cm = _mapping(c, p, {"from", "label", "fold"})
        if "from" not in cm:
            raise PlanError(f"{p}.from: required")
        frm = _str(cm["from"], f"{p}.from")
        _match_h2(frm, f"{p}.from", h2_norm)
        out.append(
            ChapterHint(
                from_=frm,
                label=_opt_str(cm, "label", p),
                fold=_bool(cm.get("fold", False), f"{p}.fold"),
            )
        )
    return out


def _questions(raw, h2_norm: set[str]) -> QuestionsHint:
    m = _mapping(raw, "questions", {"from", "options"})
    frm = _opt_str(m, "from", "questions")
    if frm is not None:
        _match_h2(frm, "questions.from", h2_norm)
    options: dict[int, list[str]] = {}
    raw_opts = m.get("options") or {}
    if not isinstance(raw_opts, dict):
        raise PlanError("questions.options: must be a mapping")
    for k, v in raw_opts.items():
        if not _is_int(k) or k < 1:
            raise PlanError(f"questions.options: key {k!r} must be a question number (integer >= 1)")
        if not isinstance(v, list) or not v or not all(isinstance(x, str) and x for x in v):
            raise PlanError(f"questions.options[{k}]: must be a non-empty list of strings")
        options[k] = list(v)
    return QuestionsHint(from_=frm, options=options)


def _diagrams(raw) -> dict[int, DiagramHint]:
    if not isinstance(raw, dict):
        raise PlanError("diagrams: must be a mapping")
    out = {}
    for k, v in raw.items():
        if not _is_int(k) or k < 1:
            raise PlanError(f"diagrams: key {k!r} must be a 1-based block index (integer >= 1)")
        p = f"diagrams[{k}]"
        m = _mapping(v, p, {"split"})
        split = m.get("split")
        if split is not None and split not in SPLIT_VALUES:
            raise PlanError(f"{p}.split: must be 'subgraphs'")
        out[k] = DiagramHint(split=split)
    return out


def load_plan(path: Path, h2_titles: list[str]) -> Plan:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise PlanError(f"plan: invalid YAML: {e}") from e
    except OSError as e:
        raise PlanError(f"plan: cannot read {path}: {e}") from e

    m = _mapping(
        raw, "plan", {"version", "kind", "slug", "blocks", "intro", "chapters", "questions", "diagrams"}
    )
    h2_norm = {_norm(t) for t in h2_titles}

    version = m.get("version")
    if not _is_int(version) or version != 1:
        raise PlanError(f"version: must be 1, got {version!r}")
    kind = m.get("kind")
    if kind not in KINDS:
        raise PlanError(f"kind: must be one of {', '.join(KINDS)}, got {kind!r}")

    slug = m.get("slug")
    if slug is not None and (not isinstance(slug, str) or not SLUG_RE.fullmatch(slug)):
        raise PlanError("slug: must match ^[a-z0-9-]{1,40}$")

    blocks = {b: b in DEFAULT_BLOCKS[kind] for b in BLOCK_NAMES}
    if m.get("blocks") is not None:
        bm = _mapping(m["blocks"], "blocks", set(BLOCK_NAMES))
        for k, v in bm.items():
            blocks[k] = _bool(v, f"blocks.{k}")

    return Plan(
        version=version,
        kind=kind,
        slug=slug,
        blocks=blocks,
        intro=_intro(m["intro"]) if m.get("intro") is not None else None,
        chapters=_chapters(m["chapters"], h2_norm) if m.get("chapters") is not None else [],
        questions=_questions(m["questions"], h2_norm) if m.get("questions") is not None else None,
        diagrams=_diagrams(m["diagrams"]) if m.get("diagrams") is not None else {},
    )
