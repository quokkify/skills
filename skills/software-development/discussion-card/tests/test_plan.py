import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import plan  # noqa: E402
from plan import PlanError, load_plan  # noqa: E402

H2 = ["How it works", "Report  example", "Open questions"]


def load(text, h2=H2):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "card.yaml"
        p.write_text(text, encoding="utf-8")
        return load_plan(p, h2)


class PlanTests(unittest.TestCase):
    def assertPlanError(self, text, fragment):
        with self.assertRaises(PlanError) as cm:
            load(text)
        self.assertIn(fragment, str(cm.exception))

    def test_minimal_plan_defaults(self):
        p = load("version: 1\nkind: retro\n")
        self.assertEqual(p.blocks, {"verdict": False, "questions": True, "actions": True})
        self.assertIsNone(p.slug)
        self.assertEqual(p.chapters, [])
        self.assertEqual(p.diagrams, {})

    def test_kind_defaults(self):
        self.assertEqual(
            load("version: 1\nkind: review\n").blocks,
            {"verdict": False, "questions": True, "actions": False},
        )
        self.assertEqual(
            load("version: 1\nkind: proposal\n").blocks,
            {"verdict": True, "questions": True, "actions": True},
        )

    def test_blocks_override(self):
        p = load("version: 1\nkind: retro\nblocks: {verdict: true, actions: false}\n")
        self.assertEqual(p.blocks, {"verdict": True, "questions": True, "actions": False})

    def test_unknown_key_errors(self):
        self.assertPlanError(
            "version: 1\nkind: retro\nchapters:\n  - {from: How it works, hide: true}\n",
            "unknown key: chapters[0].hide",
        )
        self.assertPlanError("version: 1\nkind: retro\nfoo: 1\n", "unknown key: foo")

    def test_version_2_errors(self):
        self.assertPlanError("version: 2\nkind: retro\n", "version")

    def test_kind_invalid_errors(self):
        self.assertPlanError("version: 1\nkind: party\n", "kind")

    def test_chapter_from_must_match_h2(self):
        self.assertPlanError(
            "version: 1\nkind: retro\nchapters:\n  - {from: X}\n",
            'chapters[0].from "X" matches no H2',
        )
        p = load("version: 1\nkind: retro\nchapters:\n  - {from: ' report example ', fold: true}\n")
        self.assertTrue(p.chapters[0].fold)
        self.assertIsNone(p.chapters[0].label)
        self.assertEqual(p.chapters[0].from_, " report example ")

    def test_questions_from_must_match_h2(self):
        self.assertPlanError(
            "version: 1\nkind: retro\nquestions: {from: Nope}\n",
            'questions.from "Nope" matches no H2',
        )

    def test_questions_options_keys_int(self):
        p = load('version: 1\nkind: retro\nquestions:\n  from: Open questions\n  options:\n    1: ["Yes", "No"]\n')
        self.assertEqual(p.questions.options, {1: ["Yes", "No"]})
        self.assertPlanError(
            'version: 1\nkind: retro\nquestions:\n  options:\n    first: ["Yes"]\n',
            "questions.options",
        )

    def test_diagram_split_only_subgraphs(self):
        p = load("version: 1\nkind: retro\ndiagrams:\n  3: {split: subgraphs}\n")
        self.assertEqual(p.diagrams[3].split, "subgraphs")
        self.assertPlanError(
            "version: 1\nkind: retro\ndiagrams:\n  3: {split: rows}\n",
            "diagrams[3].split",
        )

    def test_slug_ascii_only(self):
        self.assertEqual(load("version: 1\nkind: retro\nslug: deploy-approval\n").slug, "deploy-approval")
        self.assertPlanError("version: 1\nkind: retro\nslug: Деплой\n", "slug")
        self.assertPlanError("version: 1\nkind: retro\nslug: Upper\n", "slug")

    def test_intro(self):
        p = load(
            "version: 1\nkind: retro\nintro:\n  lead: hi\n  cards:\n"
            "    - {title: A, text: b}\n    - {title: C, text: d, accent: true}\n"
        )
        self.assertEqual(p.intro.lead, "hi")
        self.assertEqual([c.accent for c in p.intro.cards], [False, True])
        self.assertPlanError(
            "version: 1\nkind: retro\nintro:\n  cards:\n    - {title: A}\n",
            "intro.cards[0].text",
        )

    def test_not_a_mapping_and_bad_yaml(self):
        self.assertPlanError("- 1\n", "plan")
        self.assertPlanError("version: [\n", "invalid YAML")

    def test_full_fixture(self):
        fx = Path(__file__).resolve().parent / "fixtures" / "plan_full.yaml"
        p = load_plan(fx, ["How it works", "Report example", "Open questions"])
        self.assertEqual(p.kind, "proposal")
        self.assertEqual(len(p.intro.cards), 2)
        self.assertEqual(p.questions.options, {1: ["Yes", "No"]})
        self.assertEqual(p.diagrams[3].split, "subgraphs")

    def test_default_blocks_constant(self):
        self.assertEqual(plan.DEFAULT_BLOCKS["review"], {"questions"})


if __name__ == "__main__":
    unittest.main()
