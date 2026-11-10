import dataclasses
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build  # noqa: E402
import ui_text  # noqa: E402
from model import Box, NodeBox, RenderedDiagram  # noqa: E402
from plan import ChapterHint, load_plan  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
SAMPLE_MD = FIX / "sample.md"
SAMPLE_PLAN = FIX / "sample.card.yaml"


def make(md_text=None, plan_text=None, plan_edit=None, name="sample.md", ui="en"):
    with tempfile.TemporaryDirectory() as d:
        md = Path(d) / name
        md.write_text(md_text if md_text is not None else SAMPLE_MD.read_text(encoding="utf-8"), encoding="utf-8")
        pp = Path(d) / "card.yaml"
        pp.write_text(plan_text or SAMPLE_PLAN.read_text(encoding="utf-8"), encoding="utf-8")
        plan = load_plan(pp, build.h2_titles(md.read_text(encoding="utf-8")))
        if plan_edit:
            plan = plan_edit(plan)
        return build.build_page(md, plan, ui, build.stub_renderer)


def kind_count(page, kind):
    return len([s for s in page.spots if re.search(rf"-{kind}-[0-9a-f]{{6}}(-\d+)?$", s)])


class BuildTest(unittest.TestCase):
    def test_chapters_follow_h2_order(self):
        page = make()
        self.assertEqual(
            [c["title"] for c in page.config["chapters"]],
            ["Problem", "How it works", "Pipeline path", "Rules", "Situations", "Open questions"],
        )
        self.assertEqual(page.config["chapters"][0]["id"], "problem")

    def test_every_block_is_a_spot(self):
        page = make()
        for kind, n in [("p", 1), ("tr", 3), ("li", 4), ("callout", 1), ("intro", 3), ("q", 3)]:
            self.assertEqual(kind_count(page, kind), n, kind)
        self.assertEqual(len(page.spots), len(set(page.spots)))
        for sid in page.spots:
            self.assertIn(f'data-spot="{sid}"', page.html)

    def test_questions_from_h2_list(self):
        page = make()
        qs = page.config["questions"]
        qids = [q["id"] for q in qs]
        self.assertTrue(all(re.fullmatch(r"open-questions-q-[0-9a-f]{6}", q) for q in qids), qids)
        self.assertEqual(qids, [s for s in page.spots if "-q-" in s])
        for q in qids:
            self.assertIn(f'data-qid="{q}" data-spot="{q}"', page.html)
        self.assertEqual(qs[0]["options"], ["Yes", "No"])
        self.assertEqual(qs[1]["options"], [])
        self.assertEqual(qs[0]["text"], "Should small changes skip approval completely?")

    def test_split_diagram_yields_three_jobs(self):
        jobs = []

        def renderer(js):
            jobs.extend(js)
            return build.stub_renderer(js)

        with tempfile.TemporaryDirectory() as d:
            md = Path(d) / "sample.md"
            md.write_text(SAMPLE_MD.read_text(encoding="utf-8"), encoding="utf-8")
            plan = load_plan(SAMPLE_PLAN, build.h2_titles(md.read_text(encoding="utf-8")))
            page = build.build_page(md, plan, "en", renderer)
        self.assertEqual(len(jobs), 4)  # 1 unsplit + 3 parts
        parts = [j for j in jobs if j.chapter_slug == "pipeline-path"]
        self.assertEqual([j.title for j in parts], ["Build", "Review", "Release"])
        self.assertEqual(len({j.key for j in jobs}), 4)
        ids_ = [s["id"] for s in page.config["slides"] if s["chapter"] == "pipeline-path"]
        self.assertEqual(ids_, ["pipeline-path", "pipeline-path-d1-1", "pipeline-path-d1-2", "pipeline-path-d1-3"])

    def test_config_json(self):
        page = make()
        c = page.config
        self.assertEqual(
            set(c), {"storageKey", "ui", "labels", "chapters", "slides", "blocks", "questions", "runtimeDiagrams"}
        )
        self.assertEqual(c["storageKey"], "discussion-card:sample:v1")
        self.assertEqual(c["ui"], "en")
        self.assertEqual(c["labels"], ui_text.LABELS["en"])
        self.assertEqual(c["blocks"], {"verdict": True, "questions": True, "actions": True})
        self.assertIs(c["runtimeDiagrams"], False)
        self.assertEqual(set(c["chapters"][0]), {"id", "title", "label", "fold"})
        self.assertEqual(set(c["slides"][0]), {"id", "chapter", "title"})
        m = re.search(r'<script type="application/json" id="card-config">(.*?)</script>', page.html, re.S)
        self.assertEqual(json.loads(m.group(1)), c)

    def test_fold_chapter_rendered_as_details(self):
        def edit(plan):
            return dataclasses.replace(plan, chapters=[ChapterHint("rules", label="Rules!", fold=True)])

        page = make(plan_edit=edit)
        self.assertRegex(page.html, r'<details class="chapter"[^>]*id="rules"')
        rules = [c for c in page.config["chapters"] if c["id"] == "rules"][0]
        self.assertEqual((rules["fold"], rules["label"]), (True, "Rules!"))
        self.assertNotIn("<details", make().html)

    def test_no_h2_single_chapter(self):
        page = make(md_text="# Title\n\nJust a paragraph.\n\n- one\n- two\n")
        self.assertEqual(len(page.config["chapters"]), 1)
        self.assertEqual(kind_count(page, "p"), 1)
        self.assertEqual(kind_count(page, "li"), 2)

    def test_source_html_is_escaped(self):
        md = (
            "# T\n\n## A\n\n<img src=x onerror=alert(1)>\n\n"
            "## Open questions\n\n1. Does </script> break it?\n"
        )
        page = make(md_text=md)
        self.assertNotIn("<img src=x", page.html)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", page.html)
        self.assertIn("<\\/script>", page.html)
        self.assertEqual(page.html.count("</script>"), 2)  # config + engine only

    def test_ui_auto_detects_cyrillic(self):
        self.assertEqual(ui_text.detect_ui("Как это работает, привет abc"), "ru")
        self.assertEqual(ui_text.detect_ui("How it works, привет"), "en")
        page = make(md_text="# Заголовок\n\n## Проблема\n\nТекст про деплой.\n", ui="auto")
        self.assertEqual(page.config["ui"], "ru")

    def test_labels_have_same_keys(self):
        self.assertEqual(set(ui_text.LABELS["ru"]), set(ui_text.LABELS["en"]))

    def test_non_flowchart_mermaid_becomes_code_with_warning(self):
        md = "# T\n\n## A\n\n```mermaid\nsequenceDiagram\n  A->>B: hi\n```\n"
        page = make(md_text=md)
        self.assertIn("warning: mermaid sequenceDiagram shown as code (block 1)", page.warnings)
        self.assertEqual(kind_count(page, "code"), 1)

    def test_unparsable_flowchart_becomes_code_with_warning(self):
        md = "# T\n\n## A\n\n```mermaid\nflowchart LR\n  A e1@--> B\n```\n"
        page = make(md_text=md)
        self.assertEqual(kind_count(page, "code"), 1)
        self.assertTrue(
            any(w.startswith("warning: mermaid flowchart shown as code (block 1): edge ids") for w in page.warnings),
            page.warnings,
        )

    def test_main_writes_output_and_sidecar(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out.tmp"
            rc = build.main([str(SAMPLE_MD), "--plan", str(SAMPLE_PLAN), "-o", str(out), "--ui", "en"])
            self.assertEqual(rc, 0)
            meta = json.loads(Path(str(out) + ".meta.json").read_text(encoding="utf-8"))
            self.assertEqual(set(meta), {"spots", "intro_words", "diagrams", "warnings"})
            self.assertGreater(meta["intro_words"], 0)
            self.assertTrue(all(d_["mode"] == "code" and d_["nodes"] == [] for d_ in meta["diagrams"]))
            self.assertIn("<!DOCTYPE html>", out.read_text(encoding="utf-8"))

    def test_main_bad_plan_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.yaml"
            p.write_text("version: 2\nkind: proposal\n", encoding="utf-8")
            rc = build.main([str(SAMPLE_MD), "--plan", str(p), "-o", str(Path(d) / "o.tmp")])
            self.assertEqual(rc, 2)


SPLIT_PLAN = (
    "version: 1\nkind: proposal\nintro:\n  cards:\n    - {title: a, text: b}\n"
    "diagrams:\n  1: {split: subgraphs}\n  2: {split: subgraphs}\n"
)
TWO_FLOWS = (
    "## Flow\n\n```mermaid\nflowchart TD\n subgraph S1\n A-->B\n end\n subgraph S2\n C-->D\n end\n```\n\n"
    "```mermaid\nflowchart TD\n subgraph X1\n E-->F\n end\n subgraph X2\n G-->H\n end\n```\n\n"
    "## Flow 1\n\ntext\n\n## Intro\n\nhello\n\n## Flow\n\nagain\n"
)


def all_ids(page):
    return re.findall(r' id="([^"]+)"', page.html)


class RegressionGuards(unittest.TestCase):
    def test_regression_guard_unique_element_and_slide_ids(self):
        page = make(md_text=TWO_FLOWS, plan_text=SPLIT_PLAN)
        slides = [s["id"] for s in page.config["slides"]]
        self.assertEqual(len(slides), len(set(slides)))
        ei = all_ids(page)
        self.assertEqual(len(ei), len(set(ei)))
        self.assertIn("card-intro", ei)
        self.assertIn("flow-d2-1", slides)

    def test_regression_guard_repeated_node_ids_get_suffix(self):
        def renderer(jobs):
            out = []
            for j in jobs:
                nb = NodeBox(f"{j.chapter_slug}-A", "A", Box(0, 0, 1, 1), 16)
                out.append(RenderedDiagram(
                    j.key, f'<svg><g data-spot="{nb.spot_id}"></g></svg>', [nb], [], None, "static"))
            return out

        with tempfile.TemporaryDirectory() as d:
            md = Path(d) / "s.md"
            md.write_text("## F\n\n```mermaid\nflowchart TD\n A-->B\n```\n\n```mermaid\nflowchart TD\n A-->C\n```\n", encoding="utf-8")
            pp = Path(d) / "c.yaml"
            pp.write_text("version: 1\nkind: review\n", encoding="utf-8")
            page = build.build_page(md, load_plan(pp, ["F"]), "en", renderer)
        self.assertEqual(page.spots, ["f-A", "f-A-2"])
        self.assertIn('data-spot="f-A-2"', page.html)
        self.assertEqual(page.diagrams[1].nodes[0].spot_id, "f-A-2")
        self.assertTrue(any("f-A" in w for w in page.warnings))

    def test_regression_guard_no_source_text_dropped(self):
        md = (
            "# Title\n\n# Second Hone\n\n## A\n\n    indented word1\n\n![alt word4](x.png)\n\n"
            "## Open questions\n\n1. Q one\n\n   details word6\n\n   - sub word7\n2. Q two\n"
            "\n## Image ![titlealt word11](y.png) H\n\nz\n"
        )
        page = make(md_text=md)
        for w in ["Second Hone", "word1", "word4", "word6", "word7", "word11"]:
            self.assertIn(w, page.html, w)
        self.assertEqual(kind_count(page, "code"), 1)  # indented code is a code spot
        self.assertEqual(kind_count(page, "q"), 2)

    def test_regression_guard_no_network_references(self):
        md = (
            "## A\n\n![pic](https://example.org/x.png) [l](https://example.org/p) "
            "<https://example.org/auto> [m](mailto:a@example.com) [k](#a)\n"
        )
        page = make(md_text=md)
        body = page.html.split('<script type="application/json"')[0]
        self.assertEqual(re.findall(r'(?:src|href)="([^"]*)"', body), ["#a"])
        self.assertIn("[image: pic] (https://example.org/x.png)", body)
        self.assertIn("warning: remote image shown as text: https://example.org/x.png", page.warnings)
        self.assertIn("warning: external link shown as text: https://example.org/p", page.warnings)
        self.assertIn("warning: external link shown as text: https://example.org/auto", page.warnings)

    def test_regression_guard_only_top_level_blocks_are_spots(self):
        md = (
            "## A\n\n- item\n\n  second para\n\n  - nested\n\n> [!NOTE]\n> callout text\n>\n> - in callout\n"
            "\n## Open questions\n\n1. Q\n\n   - sub\n"
        )
        page = make(md_text=md)
        self.assertEqual(kind_count(page, "li"), 1)
        self.assertEqual(kind_count(page, "callout"), 1)
        self.assertEqual(kind_count(page, "q"), 1)
        self.assertEqual(kind_count(page, "p"), 0)
        self.assertEqual(page.html.count("data-spot="), 3 + kind_count(page, "intro"))  # no nested spots

    def test_regression_guard_main_reports_fail_for_bad_input_and_renderer(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad.md"
            bad.write_bytes(b"# T\n\n\xff\xfe\n")
            self.assertEqual(build.main([str(bad), "--plan", str(SAMPLE_PLAN), "-o", str(Path(d) / "o")]), 1)
            orig = build.stub_renderer

            def boom(jobs):
                raise RuntimeError("chrome exploded")

            build.stub_renderer = boom
            try:
                rc = build.main([str(SAMPLE_MD), "--plan", str(SAMPLE_PLAN), "-o", str(Path(d) / "o")])
            finally:
                build.stub_renderer = orig
            self.assertEqual(rc, 1)


MANY_FORMS = (
    "## Forms\n\n```mermaid\ngraph\n"
    "  A([Stadium]):::hot ---> B[Box]\n"
    "  B -. maybe .-> C{Choice}\n"
    "  C == sure ==> 1[Numbered]\n"
    "  1 x--x Узел[Привет]\n"
    "  Узел o--o D[(Store)]\n"
    "  subgraph grp [Group]\n"
    "    E[Inner]\n"
    "  end\n"
    "  D --> grp\n"
    "  classDef hot fill:#fee\n"
    "```\n"
)


class ManyFormsRenderTest(unittest.TestCase):
    """Regression guard: Mermaid forms the parser rejected turned the whole diagram into code."""

    def test_regression_guard_many_forms_render_static_with_node_spots(self):
        import subprocess

        import mermaid_svg
        from mermaid_parse import parse_flowchart

        chrome = mermaid_svg.find_chrome()
        if chrome is None:
            self.skipTest("chrome not found")
        launcher = Path(build.__file__).resolve().parent / "discuss.sh"
        proc = subprocess.run(["sh", str(launcher), "--mermaid"], capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        mjs = Path(proc.stdout.strip())
        with tempfile.TemporaryDirectory() as d:
            md = Path(d) / "forms.md"
            md.write_text(MANY_FORMS, encoding="utf-8")
            pp = Path(d) / "c.yaml"
            pp.write_text("version: 1\nkind: review\n", encoding="utf-8")
            page = build.build_page(
                md, load_plan(pp, ["Forms"]), "en", lambda jobs: mermaid_svg.render(jobs, mjs, chrome)
            )
        self.assertEqual([w for w in page.warnings if "shown as code" in w], [])
        self.assertEqual([d.mode for d in page.diagrams], ["static"])
        src = MANY_FORMS.split("```mermaid\n")[1].split("```")[0]
        want = {f"forms-{n}" for n in parse_flowchart(1, src).nodes}
        self.assertEqual(want, {f"forms-{n}" for n in ["A", "B", "C", "1", "Узел", "D", "E"]})
        self.assertEqual(set(page.spots), want)
        for sid in want:
            self.assertIn(f'data-spot="{sid}"', page.html)

    def test_regression_guard_split_cross_link_to_subgraph_id(self):
        md_text = (
            "## Flow\n\n```mermaid\nflowchart LR\n  X[Start] --> one\n"
            "  subgraph one [First]\n    A --> B\n  end\n  subgraph two\n    C\n  end\n  one --> two\n```\n"
        )
        page = make(md_text=md_text, plan_text="version: 1\nkind: review\ndiagrams:\n  1: {split: subgraphs}\n")
        self.assertIn("Start &rarr; First", page.html)
        self.assertIn("First &rarr; two", page.html)
        self.assertEqual(sorted(s["id"] for s in page.config["slides"]), ["flow", "flow-d1-1", "flow-d1-2", "flow-d1-3"])


class StableKeysTest(unittest.TestCase):
    def test_regression_guard_default_slug_includes_parent_dir(self):
        # two `design.md` in different folders used to share one storage key and wipe each other's marks
        with tempfile.TemporaryDirectory() as d:
            keys = []
            for team in ("teamA", "teamB"):
                md = Path(d) / team / "design.md"
                md.parent.mkdir()
                md.write_text("# D\n\n## Goal\n\nShip.\n", encoding="utf-8")
                pp = md.parent / "c.yaml"
                pp.write_text("version: 1\nkind: review\n", encoding="utf-8")
                page = build.build_page(md, load_plan(pp, ["Goal"]), "en", build.stub_renderer)
                keys.append(page.config["storageKey"])
        self.assertEqual(keys, ["discussion-card:teama-design:v1", "discussion-card:teamb-design:v1"])

    def test_default_slug_trim_and_fallbacks(self):
        self.assertEqual(build.default_slug(Path("/design.md")), "design")
        long = build.default_slug(Path("/x") / ("a" * 30) / ("b" * 30 + ".md"))
        self.assertEqual(long, "a" * 30 + "-" + "b" * 9)
        self.assertRegex(build.default_slug(Path("/x/Отдел/План работ.md")), r"^[a-z0-9-]{1,40}$")
        self.assertEqual(build.default_slug(Path("/x/team/---.md")), "team")

    def test_plan_slug_wins(self):
        page = make()
        self.assertEqual(page.config["storageKey"], "discussion-card:sample:v1")

    def test_regression_guard_question_ids_follow_text_not_position(self):
        md = lambda qs: "# Q\n\n## Open questions\n\n" + "".join(f"{i}. {q}\n" for i, q in enumerate(qs, 1))
        plan = "version: 1\nkind: review\nquestions:\n  options:\n    2: [A, B]\n"
        before = make(md_text=md(["One?", "Two?"]), plan_text=plan).config["questions"]
        after = make(md_text=md(["One?", "New?", "Two?"]), plan_text=plan).config["questions"]
        self.assertEqual(after[0]["id"], before[0]["id"])
        self.assertEqual(after[2]["id"], before[1]["id"])
        self.assertNotIn(after[1]["id"], {q["id"] for q in before})
        self.assertEqual(after[1]["options"], ["A", "B"])  # plan options still map by 1-based number


class OutputAndLicenceTest(unittest.TestCase):
    def test_regression_guard_runtime_page_carries_mermaid_licence(self):
        lock = dict(
            ln.split("=", 1) for ln in (Path(build.__file__).parent / "mermaid.lock").read_text().split("\n") if "=" in ln
        )
        banner = f"/*! @mermaid-js/tiny {lock['version']} | MIT License | Copyright (c) 2014 - 2022 Knut Sveidqvist */"

        def runtime(jobs):
            return [RenderedDiagram(j.key, None, [], [], None, "runtime") for j in jobs]

        with tempfile.TemporaryDirectory() as d:
            mjs = Path(d) / "mermaid.js"
            mjs.write_text("var mermaid = {};", encoding="utf-8")
            md = Path(d) / "s.md"
            md.write_text("## F\n\n```mermaid\nflowchart TD\n A-->B\n```\n", encoding="utf-8")
            pp = Path(d) / "c.yaml"
            pp.write_text("version: 1\nkind: review\n", encoding="utf-8")
            page = build.build_page(md, load_plan(pp, ["F"]), "en", runtime, mjs)
        self.assertIn(f'<script id="mermaid-lib">{banner}\nvar mermaid = {{}};</script>', page.html)

    def test_regression_guard_unwritable_output_is_fail_not_traceback(self):
        import contextlib
        import io

        err = io.StringIO()
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stderr(err):
            rc = build.main([str(SAMPLE_MD), "--plan", str(SAMPLE_PLAN), "-o", str(Path(d) / "missing" / "o.html")])
        self.assertEqual(rc, 1)
        self.assertTrue(err.getvalue().startswith("FAIL: "), err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_regression_guard_chrome_failure_warning_replaces_no_chrome_warning(self):
        def failed(jobs):
            return [
                RenderedDiagram(j.key, None, [], [], None, "runtime", "warning: chrome render failed, using runtime diagrams: boom")
                for j in jobs
            ]

        with tempfile.TemporaryDirectory() as d:
            md = Path(d) / "s.md"
            md.write_text("## F\n\n```mermaid\nflowchart TD\n A-->B\n```\n", encoding="utf-8")
            pp = Path(d) / "c.yaml"
            pp.write_text("version: 1\nkind: review\n", encoding="utf-8")
            page = build.build_page(md, load_plan(pp, ["F"]), "en", failed)
        self.assertIn("warning: chrome render failed, using runtime diagrams: boom", page.warnings)
        self.assertFalse(any("Chrome not available" in w for w in page.warnings), page.warnings)
        self.assertFalse(any("shown as code" in w for w in page.warnings), page.warnings)
        self.assertIn('class="mermaid-runtime"', page.html)
        self.assertEqual(page.spots, ["f-A", "f-B"])


if __name__ == "__main__":
    unittest.main()
