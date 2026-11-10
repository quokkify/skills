"""Render Mermaid flowchart DiagramJobs to static SVG in headless Chrome."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from model import Box, DiagramJob, NodeBox, RenderedDiagram  # noqa: E402,F401

PAGE = Path(__file__).resolve().parent.parent / "assets" / "render-mermaid.html"
MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CHROME_FLAGS = [
    "--headless=new",
    "--disable-gpu",
    "--allow-file-access-from-files",
    "--virtual-time-budget=15000",
    "--dump-dom",
]
TIMEOUT_S = 60
RENDER_ID = "dc-m{k}"  # engine-owned prefix: cannot equal a chapter id such as `d1`
CHROME_FAILED = "warning: chrome render failed, using runtime diagrams: {reason}"

ChromeRunner = Callable[[str, Path], str]


def find_chrome() -> str | None:
    if os.environ.get("DISCUSS_NO_CHROME") == "1":  # test hook: force the runtime fallback
        return None
    env = os.environ.get("CHROME_BIN")
    if env and os.path.isfile(env) and os.access(env, os.X_OK):
        return env
    if os.path.isfile(MAC_CHROME) and os.access(MAC_CHROME, os.X_OK):
        return MAC_CHROME
    for name in ("google-chrome", "chromium"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _node_id(dom_id: str, render_id: str) -> str:
    s = re.sub(r"^" + re.escape(render_id) + r"-flowchart-", "", dom_id)
    return re.sub(r"-\d+$", "", s)


def annotate_svg(svg: str, render_id: str, chapter_slug: str) -> tuple[str, list[str]]:
    """Mark each g.node as a clickable spot and unlock the SVG's natural width."""
    ids: list[str] = []

    def repl(m: re.Match) -> str:
        tag = m.group(0)
        if not re.search(r'class="[^"]*\bnode\b', tag):
            return tag
        dom_id = re.search(r'\bid="([^"]*)"', tag)
        if not dom_id:
            return tag
        spot = f"{chapter_slug}-{_node_id(dom_id.group(1), render_id)}"
        ids.append(spot)
        return tag[:-1] + f' data-spot="{spot}" tabindex="0" role="button">'

    svg = re.sub(r"<g\b[^>]*>", repl, svg)

    def fix_root(m: re.Match) -> str:
        tag = m.group(0)
        tag = re.sub(r'\sstyle="[^"]*"', lambda s: "" if "max-width" in s.group(0) else s.group(0), tag)
        vb = re.search(r'viewBox="([^"]*)"', tag)
        if vb:
            parts = vb.group(1).replace(",", " ").split()
            if len(parts) == 4:
                w = parts[2]
                if re.search(r'\swidth="', tag):
                    tag = re.sub(r'\swidth="[^"]*"', f' width="{w}"', tag, count=1)
                else:
                    tag = tag[:-1] + f' width="{w}">'
        return tag

    svg = re.sub(r"<svg\b[^>]*>", fix_root, svg, count=1)
    return svg, ids


def _run_chrome(chrome: str, page: Path) -> str:
    cmd = [chrome, *CHROME_FLAGS, page.as_uri()]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S, check=False)
    if 'id="result"' not in proc.stdout:
        raise RuntimeError(f"chrome exit {proc.returncode}, no result; stderr: {proc.stderr[-500:]}")
    return proc.stdout


def _box(d: dict) -> Box:
    return Box(float(d["x"]), float(d["y"]), float(d["w"]), float(d["h"]))


def _parse(dom: str) -> list[dict]:
    m = re.search(r'<script id="result" type="application/json">(.*?)</script>', dom, re.S)
    if not m:
        raise RuntimeError("no result in chrome output")
    return json.loads(m.group(1))


def render(
    jobs: list[DiagramJob],
    mermaid_js: Path,
    chrome: str | None,
    runner: ChromeRunner | None = None,
) -> list[RenderedDiagram]:
    if not jobs:
        return []
    if chrome is None:
        return [RenderedDiagram(j.key, None, [], [], None, "runtime") for j in jobs]
    run = runner or _run_chrome
    with tempfile.TemporaryDirectory(prefix="discuss-mermaid-") as d:
        tmp = Path(d)
        shutil.copyfile(mermaid_js, tmp / "mermaid.js")
        shutil.copyfile(PAGE, tmp / "render-mermaid.html")
        payload = [{"key": j.key, "source": j.source} for j in jobs]
        (tmp / "jobs.js").write_text(
            "window.JOBS = " + json.dumps(payload).replace("<", "\\u003c") + ";", encoding="utf-8"
        )
        try:
            results = _parse(run(chrome, tmp / "render-mermaid.html"))
        except (RuntimeError, ValueError, subprocess.SubprocessError, OSError) as e:
            msg = CHROME_FAILED.format(reason=f"{type(e).__name__}: {e}")
            return [RenderedDiagram(j.key, None, [], [], None, "runtime", msg) for j in jobs]
    by_key = {r.get("key"): r for r in results}
    batch_err = results[0].get("error") if results and results[0].get("key") is None else None
    out: list[RenderedDiagram] = []
    for k, j in enumerate(jobs, start=1):
        r = by_key.get(j.key)
        err = (r or {}).get("error") or batch_err
        if r is None or err or not r.get("svg"):
            out.append(RenderedDiagram(j.key, None, [], [], err or "no result for diagram", "code"))
            continue
        render_id = RENDER_ID.format(k=k)
        svg, _ = annotate_svg(r["svg"], render_id, j.chapter_slug)
        nodes = [
            NodeBox(f"{j.chapter_slug}-{_node_id(n['domId'], render_id)}", n["label"], _box(n), float(n["fontPx"]))
            for n in r.get("nodes", [])
        ]
        labels = [_box(b) for b in r.get("labels", [])]
        out.append(RenderedDiagram(j.key, svg, nodes, labels, None, "static"))
    return out
