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
        self.assertEqual([q["id"] for q in qs], ["q1", "q2", "q3"])
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
        self.assertEqual(ids_, ["pipeline-path", "pipeline-path-1", "pipeline-path-2", "pipeline-path-3"])

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
        md = "# T\n\n## A\n\n```mermaid\nflowchart\n```\n"
        page = make(md_text=md)
        self.assertEqual(kind_count(page, "code"), 1)
        self.assertTrue(any("block 1" in w for w in page.warnings))

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


if __name__ == "__main__":
    unittest.main()
