import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build  # noqa: E402
import check  # noqa: E402
from model import Box, NodeBox, RenderedDiagram  # noqa: E402

PLAN = "version: 1\nkind: proposal\n"
PASS_RE = re.compile(r"^PASS words=\d+ extra=\d+ spots=\d+ diagrams=(\d+|runtime) offline=ok( ids=(kept|-\d+))?$")
MD = "# T\n\n## A\n\nAlpha beta gamma.\n\n- item one\n- item two\n"
FLOW = "# T\n\n## Flow\n\n```mermaid\nflowchart LR\n  A[Start] --> B[Stop]\n```\n"
SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
    '<g class="node default" id="d1-flowchart-A-0"><text>Start</text></g>'
    '<g class="node default" id="d1-flowchart-B-1"><text>Stop</text></g></svg>'
)


def box(x, y, w=50, h=20):
    return Box(x, y, w, h)


def static_renderer(font=16, b2=None, labels=()):
    def render(jobs):
        out = []
        for j in jobs:
            svg = SVG.replace('class="node default" id="d1-flowchart-A-0"', f'class="node default" id="d1-flowchart-A-0" data-spot="{j.chapter_slug}-A"')
            svg = svg.replace('class="node default" id="d1-flowchart-B-1"', f'class="node default" id="d1-flowchart-B-1" data-spot="{j.chapter_slug}-B"')
            nodes = [
                NodeBox(f"{j.chapter_slug}-A", "Start", box(0, 0), font),
                NodeBox(f"{j.chapter_slug}-B", "Stop", b2 or box(100, 0), font),
            ]
            out.append(RenderedDiagram(j.key, svg, nodes, list(labels), None, "static"))
        return out

    return render


def runtime_renderer(jobs):
    return [RenderedDiagram(j.key, None, [], [], None, "runtime") for j in jobs]


class Env:
    def __init__(self, md=MD, renderer=None, mutate=None):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.md = d / "in.md"
        self.md.write_text(md, encoding="utf-8")
        pp = d / "card.yaml"
        pp.write_text(PLAN, encoding="utf-8")
        plan = build.load_plan(pp, build.h2_titles(md))
        page = build.build_page(self.md, plan, "en", renderer or build.stub_renderer)
        self.html = d / "out.html"
        text = mutate(page.html) if mutate else page.html
        self.html.write_text(text, encoding="utf-8")
        self.meta = Path(str(self.html) + ".meta.json")
        self.meta.write_text(json.dumps(build._meta(page)), encoding="utf-8")
        self.page = page

    def run(self, **kw):
        return check.check(self.md, self.html, self.meta, **kw)

    def close(self):
        self.tmp.cleanup()


class CheckTest(unittest.TestCase):
    def env(self, *a, **kw):
        e = Env(*a, **kw)
        self.addCleanup(e.close)
        return e

    def test_pass_line_format(self):
        r = self.env().run()
        self.assertTrue(r.ok, r.samples)
        self.assertRegex(r.line, PASS_RE)

    def test_words_missing_fails(self):
        e = self.env(mutate=lambda h: h.replace("Alpha beta gamma.", "Alpha gamma."))
        r = e.run()
        self.assertFalse(r.ok)
        self.assertTrue(r.line.startswith("FAIL words:"))
        self.assertIn("missing: beta", r.samples)

    def test_samples_capped_at_five(self):
        e = self.env(md="# T\n\n## A\n\none two three four five six seven\n", mutate=lambda h: h.replace("one two three four five six seven", ""))
        self.assertEqual(len(e.run().samples), 5)

    def test_extra_counted_not_failing(self):
        e = self.env()
        meta = json.loads(e.meta.read_text())
        meta["intro_words"] = 7
        e.meta.write_text(json.dumps(meta))
        r = e.run()
        self.assertTrue(r.ok)
        self.assertIn("extra=7", r.line)

    def test_card_config_text_does_not_count_as_page_text(self):
        e = self.env(mutate=lambda h: h.replace("Alpha beta gamma.", "Alpha gamma.").replace('"ui"', '"beta": 1, "ui"'))
        self.assertFalse(e.run().ok)

    def test_external_link_and_image_transformations_pass(self):
        md = "# T\n\n## A\n\nSee [docs](https://example.com/x) and ![logo](https://example.com/l.png) and [r](other.md).\n"
        e = self.env(md=md)
        r = e.run()
        self.assertTrue(r.ok, r.samples)
        self.assertIn("warning: relative link: other.md", r.warnings)

    def test_duplicate_spot_fails(self):
        e = self.env(mutate=lambda h: h.replace("<main", '<i data-spot="dup"></i><i data-spot="dup"></i><main'))
        r = e.run()
        self.assertTrue(r.line.startswith("FAIL ids:"))
        self.assertIn("duplicate: dup", r.samples)

    def test_mermaid_node_without_spot_fails(self):
        e = self.env(md=FLOW, renderer=static_renderer(), mutate=lambda h: re.sub(r' data-spot="flow-B"', "", h))
        r = e.run()
        self.assertFalse(r.ok)
        self.assertTrue(r.line.startswith("FAIL ids:"))

    def test_static_diagram_passes(self):
        r = self.env(md=FLOW, renderer=static_renderer()).run()
        self.assertTrue(r.ok, r.samples)
        self.assertRegex(r.line, PASS_RE)
        self.assertIn("diagrams=1", r.line)

    def test_diagram_neither_rendered_nor_reported_fails(self):
        e = self.env(md=FLOW)  # stub renderer: code mode, no warning
        r = e.run()
        self.assertTrue(r.line.startswith("FAIL diagrams:"), r.line)

    def test_overlap_fails(self):
        e = self.env(md=FLOW, renderer=static_renderer(b2=box(49, 0)))
        r = e.run()
        self.assertTrue(r.line.startswith("FAIL overlap:"), r.line)

    def test_touching_boxes_do_not_overlap(self):
        self.assertTrue(self.env(md=FLOW, renderer=static_renderer(b2=box(50, 0))).run().ok)

    def test_font_below_14_fails(self):
        r = self.env(md=FLOW, renderer=static_renderer(font=13)).run()
        self.assertTrue(r.line.startswith("FAIL font:"), r.line)

    def test_runtime_mode_skips_overlap_and_font_with_reason(self):
        r = self.env(md=FLOW, renderer=runtime_renderer).run()
        self.assertTrue(r.ok, r.samples)
        self.assertIn("diagrams=runtime", r.line)
        self.assertIn("warning: overlap and font gates skipped (runtime diagrams)", r.warnings)

    def test_offline_external_src_fails(self):
        e = self.env(mutate=lambda h: h.replace("<main", '<img src="https://x.example.org/a.png"><main'))
        r = e.run()
        self.assertTrue(r.line.startswith("FAIL offline:"))
        self.assertIn("src: https://x.example.org/a.png", r.samples)

    def test_offline_other_references_fail(self):
        for frag in (
            '<a href="//cdn.example.com/x">x</a>',
            '<a href="mailto:a@example.com">m</a>',
            '<div style="background:url(http://x.example.org/a.png)"></div>',
            "<style>@import 'https://x.example.org/a.css';</style>",
            "<script>fetch('https://x.example.org/a')</script>",
        ):
            with self.subTest(frag=frag):
                r = self.env(mutate=lambda h, f=frag: h.replace("<main", f + "<main")).run()
                self.assertTrue(r.line.startswith("FAIL offline:"), r.line)

    def test_svg_namespace_allowed(self):
        r = self.env(md=FLOW, renderer=static_renderer()).run()
        self.assertTrue(r.ok, r.samples)
        self.assertIn('xmlns="http://www.w3.org/2000/svg"', Path(self.env(md=FLOW, renderer=static_renderer()).html).read_text())

    def test_data_src_and_fragment_ok(self):
        r = self.env(mutate=lambda h: h.replace("<main", '<img src="data:image/png;base64,AAAA"><a href="#x">x</a><main')).run()
        self.assertTrue(r.ok, r.samples)

    def _previous(self, e):
        prev = e.html.with_name("prev.html")
        prev.write_text(e.html.read_text().replace("<main", '<i data-spot="gone-p-111111"></i><main'), encoding="utf-8")
        return prev

    def test_id_diff_lists_dropped_marked_ids(self):
        e = self.env()
        prev = self._previous(e)
        state = e.html.with_name("state.json")
        state.write_text(json.dumps({"vote": None, "spots": {"gone-p-111111": {"status": "agree", "comments": []}}, "questions": {}, "actions": []}))
        r = e.run(previous=prev, previous_state=state)
        self.assertTrue(r.line.startswith("FAIL id diff:"), r.line)
        self.assertIn("warning: dropped id: gone-p-111111", r.warnings)
        r = e.run(previous=prev, previous_state=state, allow_drop=True)
        self.assertTrue(r.ok)
        self.assertTrue(r.line.endswith(" ids=-1"), r.line)

    def test_id_diff_unmarked_drop_only_warns(self):
        e = self.env()
        prev = self._previous(e)
        state = e.html.with_name("state.json")
        state.write_text(json.dumps({"spots": {"gone-p-111111": {"status": None, "comments": []}}}))
        r = e.run(previous=prev, previous_state=state)
        self.assertTrue(r.ok)
        self.assertRegex(r.line, PASS_RE)

    def test_ids_kept(self):
        e = self.env()
        r = e.run(previous=e.html)
        self.assertTrue(r.line.endswith(" ids=kept"), r.line)

    def test_main_exit_codes_and_streams(self):
        e = self.env()
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(check.main([str(e.md), str(e.html)]), 0)
        self.assertRegex(out.getvalue().strip(), PASS_RE)
        bad = e.html.read_text().replace("Alpha beta gamma.", "Alpha.")
        e.html.write_text(bad)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(check.main([str(e.md), str(e.html)]), 1)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(check.main([]), 2)
            self.assertEqual(check.main([str(e.md), str(e.html) + ".nope"]), 2)

    def _flow(self, label_a):
        return f'# T\n\n## Flow\n\n```mermaid\nflowchart LR\n  A["{label_a}"] --> B[Stop]\n```\n'

    def test_label_html_tags_not_counted_as_words(self):
        e = self.env(md=self._flow("<b>Start</b> bold"), renderer=static_renderer(),
                     mutate=lambda h: h.replace("<text>Start</text>", "<text>Start bold</text>"))
        r = e.run()
        self.assertTrue(r.ok, r.samples)

    def test_label_mermaid_entities_decoded(self):
        e = self.env(md=self._flow("say #quot;Start#quot; &amp; #35;"), renderer=static_renderer(),
                     mutate=lambda h: h.replace("<text>Start</text>", '<text>say "Start" &amp; #</text>'))
        r = e.run()
        self.assertTrue(r.ok, r.samples)

    def test_external_img_in_label_fails_offline_first(self):
        e = self.env(md=FLOW, renderer=static_renderer(),
                     mutate=lambda h: h.replace("<text>Start</text>", '<text>Start</text><img src="http://x.example/a.png">').replace("Stop", ""))
        r = e.run()
        self.assertTrue(r.line.startswith("FAIL offline:"), r.line)
        self.assertIn("src: http://x.example/a.png", r.samples)

    def test_script_and_style_text_not_visible(self):
        e = self.env(
            mutate=lambda h: h.replace("Alpha beta gamma.", "Alpha.").replace(
                "<main", '<script>var x="beta";</script><style>.gamma{}</style><main'))
        r = e.run()
        self.assertTrue(r.line.startswith("FAIL words:"), r.line)
        self.assertIn("missing: beta", r.samples)
        self.assertIn("missing: gamma", r.samples)

    def test_overlap_node_and_label_fails(self):
        r = self.env(md=FLOW, renderer=static_renderer(labels=[box(10, 5, 10, 10)])).run()
        self.assertTrue(r.line.startswith("FAIL overlap:"), r.line)
        self.assertTrue(any("label#0" in s for s in r.samples), r.samples)

    def test_overlap_label_and_label_fails(self):
        r = self.env(md=FLOW, renderer=static_renderer(labels=[box(200, 0, 10, 10), box(205, 5, 10, 10)])).run()
        self.assertTrue(r.line.startswith("FAIL overlap:"), r.line)
        self.assertIn("label#0 overlaps label#1", r.samples[0])

    def test_malformed_meta_exits_2_without_traceback(self):
        e = self.env(md=FLOW, renderer=static_renderer())
        meta = json.loads(e.meta.read_text())
        del meta["diagrams"][0]["nodes"][0]["spot_id"]
        e.meta.write_text(json.dumps(meta))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = check.main([str(e.md), str(e.html)])
        self.assertEqual(rc, 2)
        self.assertIn("meta", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_sample_fixture_passes(self):
        fix = Path(__file__).resolve().parent / "fixtures"
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.html"
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(build.main([str(fix / "sample.md"), "--plan", str(fix / "sample.card.yaml"), "-o", str(out)]), 0)
            r = check.check(fix / "sample.md", out, Path(str(out) + ".meta.json"))
        # stub renderer leaves diagrams as unreported code: gate must say so
        self.assertTrue(r.line.startswith("FAIL diagrams:"), r.line)


if __name__ == "__main__":
    unittest.main()
