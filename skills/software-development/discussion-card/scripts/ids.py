"""Stable ids for chapters and discussion spots."""
from __future__ import annotations

import hashlib
import re

SLUG_MAX = 40
KINDS = ("p", "li", "tr", "callout", "code", "intro", "q")

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya", "і": "i", "ї": "yi", "є": "ye", "ґ": "g",
}


def slugify(text: str) -> str:
    out = "".join(_TRANSLIT.get(ch, ch) for ch in text.lower())
    out = re.sub(r"[^a-z0-9]+", "-", out)
    return out[:SLUG_MAX].strip("-")


def normalise(text: str) -> str:
    return " ".join(text.split())


def spot_id(chapter_slug: str, kind: str, text: str, seen: set[str]) -> str:
    digest = hashlib.sha1(normalise(text).encode("utf-8")).hexdigest()[:6]
    base = f"{chapter_slug}-{kind}-{digest}"
    cand, n = base, 1
    while cand in seen:
        n += 1
        cand = f"{base}-{n}"
    seen.add(cand)
    return cand


def node_spot_id(chapter_slug: str, node_id: str) -> str:
    return f"{chapter_slug}-{node_id}"
