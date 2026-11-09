import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import mermaid_svg  # noqa: E402
from model import DiagramJob  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
SAMPLE_SRC = (
    "flowchart LR\n  A[Commit] -->|push| B[Checks]\n"
    "  B -->|green| C{Size?}\n  C -->|small| D[Auto-approve]\n"
)


def fixture_svg() -> str:
    return (FIX / "sample-flowchart.svg").read_text(encoding="utf-8")


class AnnotateTest(unittest.TestCase):
    def test_annotate_svg_adds_data_spot(self):
        svg, ids = mermaid_svg.annotate_svg(fixture_svg(), "d1", "how-it-works")
        self.assertEqual(ids, [f"how-it-works-{n}" for n in "ABCD"])
        for sid in ids:
            tag = re.search(r'<g[^>]*data-spot="%s"[^>]*>' % re.escape(sid), svg).group(0)
            self.assertIn('tabindex="0"', tag)
            self.assertIn('role="button"', tag)
            self.assertRegex(tag, r'class="[^"]*\bnode\b')

    def test_annotate_svg_removes_max_width(self):
        svg, _ = mermaid_svg.annotate_svg(fixture_svg(), "d1", "c")
        root = re.search(r"<svg\b[^>]*>", svg).group(0)
        self.assertNotIn("max-width", root)
        vb_w = re.search(r'viewBox="[\d.\-]+ [\d.\-]+ ([\d.]+) ', root).group(1)
        self.assertIn(f'width="{vb_w}"', root)
        self.assertNotIn('width="100%"', root)


class RenderTest(unittest.TestCase):
    JOB = DiagramJob("k1", "how-it-works", "flowchart LR\n A-->B")

    def test_render_error_becomes_code_block(self):
        def runner(chrome, page):
            body = json.dumps([{"key": "k1", "error": "Parse error"}])
            return f'<script id="result" type="application/json">{body}</script>'

        out = mermaid_svg.render([self.JOB], self._mjs(), "chrome", runner)
        self.assertEqual(out[0].mode, "code")
        self.assertEqual(out[0].error, "Parse error")
        self.assertIsNone(out[0].svg)

    def test_chrome_failure_becomes_code_block(self):
        def runner(chrome, page):
            raise subprocess.TimeoutExpired("chrome", 60)

        out = mermaid_svg.render([self.JOB], self._mjs(), "chrome", runner)
        self.assertEqual(out[0].mode, "code")
        self.assertTrue(out[0].error)

    def test_no_chrome_runtime_mode(self):
        out = mermaid_svg.render([self.JOB], self._mjs(), None)
        self.assertEqual(out[0].mode, "runtime")
        self.assertIsNone(out[0].svg)

    def _mjs(self) -> Path:
        return FIX / "sample-flowchart.svg"  # content irrelevant: only copied

    def test_real_render(self):
        chrome = mermaid_svg.find_chrome()
        if chrome is None:
            self.skipTest("chrome not found")
        mjs = subprocess.run(
            ["sh", str(SCRIPTS / "discuss.sh"), "--mermaid"], capture_output=True, text=True
        ).stdout.strip()
        if not mjs:
            self.skipTest("mermaid not cached")
        out = mermaid_svg.render([DiagramJob("k1", "how-it-works", SAMPLE_SRC)], Path(mjs), chrome)[0]
        self.assertEqual(out.mode, "static", out.error)
        self.assertEqual(len(out.nodes), 4)
        self.assertEqual(len(out.labels), 3)
        self.assertTrue(all(n.font_px >= 14 for n in out.nodes))
        self.assertEqual([n.spot_id for n in out.nodes], [f"how-it-works-{c}" for c in "ABCD"])
        self.assertIn('data-spot="how-it-works-A"', out.svg)
        self.assertNotIn("max-width", re.search(r"<svg\b[^>]*>", out.svg).group(0))


if __name__ == "__main__":
    unittest.main()
