"""Shared data shapes for the discussion-card build pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DiagramJob:
    key: str
    chapter_slug: str
    source: str
    title: str | None = None


@dataclass
class Box:
    x: float
    y: float
    w: float
    h: float


@dataclass
class NodeBox:
    spot_id: str
    label: str
    box: Box
    font_px: float


@dataclass
class RenderedDiagram:
    key: str
    svg: str | None
    nodes: list[NodeBox] = field(default_factory=list)
    labels: list[Box] = field(default_factory=list)
    error: str | None = None
    mode: str = "code"  # "static" | "runtime" | "code"
