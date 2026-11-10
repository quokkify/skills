import http.server
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock
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


class AnnotateIdsTest(unittest.TestCase):
    def test_annotate_svg_node_ids_with_dashes_and_digits(self):
        svg = (
            '<svg viewBox="0 0 100 50" width="100%" style="max-width: 100px;">'
            '<g class="node default" id="d1-flowchart-node-1-0"></g>'
            '<g class="node default" id="d1-flowchart-B1-3"></g></svg>'
        )
        out, ids = mermaid_svg.annotate_svg(svg, "d1", "ch")
        self.assertEqual(ids, ["ch-node-1", "ch-B1"])
        self.assertIn('data-spot="ch-node-1"', out)
        self.assertIn('data-spot="ch-B1"', out)


def real_chrome_and_mermaid(test: unittest.TestCase) -> tuple[str, Path]:
    chrome = mermaid_svg.find_chrome()
    if chrome is None:
        test.skipTest("chrome not found")
    proc = subprocess.run(
        ["sh", str(SCRIPTS / "discuss.sh"), "--mermaid"], capture_output=True, text=True
    )
    test.assertEqual(proc.returncode, 0, f"discuss.sh --mermaid failed: {proc.stderr}")
    return chrome, Path(proc.stdout.strip())


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

    def test_regression_guard_chrome_batch_failure_falls_back_to_runtime(self):
        # a crashed, hung or missing Chrome used to turn every diagram into a code block
        failures = [
            subprocess.TimeoutExpired("chrome", 60),
            FileNotFoundError(2, "No such file or directory"),
            RuntimeError("chrome exit -11, no result; stderr: crash"),
        ]
        for exc in failures:
            with self.subTest(exc=type(exc).__name__):
                def runner(chrome, page, exc=exc):
                    raise exc

                out = mermaid_svg.render([self.JOB, DiagramJob("k2", "c", "flowchart LR\n X-->Y")], self._mjs(), "chrome", runner)
                self.assertEqual([o.mode for o in out], ["runtime", "runtime"])
                self.assertEqual([o.error for o in out], [None, None])
                self.assertTrue(out[0].warning.startswith("warning: chrome render failed, using runtime diagrams: "), out[0].warning)

    def test_regression_guard_find_chrome_skips_bad_chrome_bin(self):
        with tempfile.TemporaryDirectory() as d:
            not_exec = Path(d) / "chrome.txt"
            not_exec.write_text("x", encoding="utf-8")
            for bad in ("/nonexistent/chrome", d, str(not_exec)):
                with self.subTest(bad=bad), mock.patch.dict(os.environ, {"CHROME_BIN": bad}), \
                        mock.patch.object(mermaid_svg, "MAC_CHROME", "/nonexistent/mac"), \
                        mock.patch.object(mermaid_svg.shutil, "which", return_value="/usr/bin/chromium"):
                    os.environ.pop("DISCUSS_NO_CHROME", None)
                    self.assertEqual(mermaid_svg.find_chrome(), "/usr/bin/chromium")
            good = Path(d) / "chrome"
            good.write_text("#!/bin/sh\n", encoding="utf-8")
            good.chmod(0o755)
            with mock.patch.dict(os.environ, {"CHROME_BIN": str(good)}):
                os.environ.pop("DISCUSS_NO_CHROME", None)
                self.assertEqual(mermaid_svg.find_chrome(), str(good))

    def test_regression_guard_render_ids_cannot_clash_with_chapter_ids(self):
        # render ids d1..dN collided with a chapter slug like `d1` (H2 "D1")
        svg = '<svg id="dc-m1" viewBox="0 0 10 10"><g class="node" id="dc-m1-flowchart-A-0"></g></svg>'

        def runner(chrome, page):
            self.assertIn("'dc-m' + (k + 1)", (page.parent / "render-mermaid.html").read_text(encoding="utf-8"))
            body = json.dumps([{"key": "k1", "svg": svg, "nodes": [{"domId": "dc-m1-flowchart-A-0", "label": "A",
                                                                   "x": 0, "y": 0, "w": 1, "h": 1, "fontPx": 16}]}])
            return f'<script id="result" type="application/json">{body}</script>'

        out = mermaid_svg.render([self.JOB], self._mjs(), "chrome", runner)[0]
        self.assertEqual(out.mode, "static", out.error)
        self.assertEqual([n.spot_id for n in out.nodes], ["how-it-works-A"])
        self.assertIn('data-spot="how-it-works-A"', out.svg)

    def test_no_chrome_runtime_mode(self):
        out = mermaid_svg.render([self.JOB], self._mjs(), None)
        self.assertEqual(out[0].mode, "runtime")
        self.assertIsNone(out[0].svg)

    def _mjs(self) -> Path:
        return FIX / "sample-flowchart.svg"  # content irrelevant: only copied

    def test_chrome_no_result_error_has_code_and_stderr(self):
        fake = subprocess.CompletedProcess(["chrome"], 7, stdout="<html></html>", stderr="x" * 900 + "BOOM")
        with mock.patch.object(mermaid_svg.subprocess, "run", return_value=fake):
            out = mermaid_svg.render([self.JOB], self._mjs(), "chrome")
        self.assertEqual(out[0].mode, "runtime")
        self.assertIn("exit 7", out[0].warning)
        self.assertTrue(out[0].warning.endswith("BOOM"))
        self.assertLess(len(out[0].warning), 800)

    def test_regression_guard_render_makes_no_network_requests(self):
        hits = []

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append(self.path)
                self.send_response(404)
                self.end_headers()

            def log_message(self, *a):
                pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            chrome, mjs = real_chrome_and_mermaid(self)
            src = "flowchart LR\n  A[\"<img src='http://127.0.0.1:%d/leak.png'> pic\"] --> B" % srv.server_port
            out = mermaid_svg.render([DiagramJob("k1", "c", src)], mjs, chrome)[0]
            self.assertEqual(out.mode, "static", out.error)
        finally:
            srv.shutdown()
            srv.server_close()
        self.assertEqual(hits, [])

    def test_real_render(self):
        chrome, mjs = real_chrome_and_mermaid(self)
        out = mermaid_svg.render([DiagramJob("k1", "how-it-works", SAMPLE_SRC)], mjs, chrome)[0]
        self.assertEqual(out.mode, "static", out.error)
        self.assertEqual(len(out.nodes), 4)
        self.assertEqual(len(out.labels), 3)
        self.assertTrue(all(n.font_px >= 14 for n in out.nodes))
        self.assertEqual([n.spot_id for n in out.nodes], [f"how-it-works-{c}" for c in "ABCD"])
        self.assertIn('data-spot="how-it-works-A"', out.svg)
        self.assertRegex(out.svg, r'^<svg[^>]*\bid="dc-m1"')
        self.assertNotIn("max-width", re.search(r"<svg\b[^>]*>", out.svg).group(0))


if __name__ == "__main__":
    unittest.main()
