"""Checks for the mr-description helper scripts and the skill's public boundary."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "repository" / "mr-description"
RUBRIC = SKILL_DIR / "scripts" / "rubric.py"
FIXTURES = ROOT / "tests" / "fixtures" / "mr_description"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def codes(items: list[dict]) -> set[str]:
    return {item["code"] for item in items}


class RubricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.m = load_module("mr_description_rubric", RUBRIC)
        cls.profile = json.loads(fixture("profile.json"))

    def run_cli(self, profile_text: str, text: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile.json"
            draft = Path(tmp) / "draft.md"
            profile.write_text(profile_text, encoding="utf-8")
            draft.write_text(text, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(RUBRIC), "--profile", str(profile), "--text", str(draft)],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_good_fixture_passes(self) -> None:
        result = self.m.check(fixture("good.md"), self.profile)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["failures"], [])

    def test_over_word_budget_fails(self) -> None:
        text = "Summary line.\n\n## What changed\n- " + " ".join(["word"] * 130) + "\n"
        result = self.m.check(text, self.profile)
        self.assertFalse(result["ok"])
        self.assertIn("over_budget_words", codes(result["failures"]))

    def test_over_line_budget_fails(self) -> None:
        text = "Summary.\n\n## What changed\n" + "".join(f"- fact {i}\n" for i in range(12))
        result = self.m.check(text, self.profile)
        self.assertIn("over_budget_lines", codes(result["failures"]))

    def test_keep_lines_and_details_not_counted(self) -> None:
        hidden = " ".join(["detail"] * 200)
        text = (
            "Summary line.\n\n## Verification\n- `make test`: green\n\n"
            f"<details><summary>More</summary>\n\n{hidden}\n\n</details>\n\n"
            "Tracker: [CASE-1](https://tracker.example.com/cases/1)\nCloses SHOP-1\n"
        )
        result = self.m.check(text, self.profile)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["stats"]["visible_lines"], 3)

    def test_headings_count_lines_not_words(self) -> None:
        result = self.m.check("One two three.\n\n## What changed\n- four five\n", self.profile)
        self.assertEqual(result["stats"]["visible_words"], 5)
        self.assertEqual(result["stats"]["visible_lines"], 3)

    def test_dense_bullet_warns_not_fails(self) -> None:
        result = self.m.check(fixture("dense.md"), self.profile)
        self.assertTrue(result["ok"], result)
        self.assertTrue(
            {"bullet_too_long", "bullet_identifiers", "bullet_parenthetical"} <= codes(result["warnings"]),
            result["warnings"],
        )

    def test_too_many_bullets_warns(self) -> None:
        text = "Summary.\n\n## What changed\n" + "".join(f"- fact {i}\n" for i in range(8))
        profile = dict(self.profile, word_budget={"words": 120, "lines": 20})
        self.assertIn("too_many_bullets", codes(self.m.check(text, profile)["warnings"]))

    def test_empty_and_duplicate_sections_warn(self) -> None:
        text = "Summary.\n\n## What changed\n\n## Verification\n- ok\n\n## Verification\n- again\n"
        warnings = codes(self.m.check(text, self.profile)["warnings"])
        self.assertIn("empty_section", warnings)
        self.assertIn("duplicate_section", warnings)

    def test_demo_block_dropped_fails(self) -> None:
        result = self.m.check("New short description.\n\nCloses SHOP-42\n", self.profile, fixture("with_demo.md"))
        self.assertIn("marker_block_changed", codes(result["failures"]))

    def test_demo_block_edited_fails(self) -> None:
        result = self.m.check(fixture("demo_edited.md"), self.profile, fixture("with_demo.md"))
        self.assertIn("marker_block_changed", codes(result["failures"]))

    def test_demo_block_moved_passes(self) -> None:
        original = fixture("with_demo.md")
        block = original[original.index("<!-- demo:start -->") : original.index("<!-- demo:end -->") + len("<!-- demo:end -->")]
        text = f"New short description.\n\n## Verification\n- `make test`: green\n\nCloses SHOP-42\n\n{block}\n"
        result = self.m.check(text, self.profile, original)
        self.assertTrue(result["ok"], result)

    def test_demo_block_not_counted_in_budget(self) -> None:
        result = self.m.check(fixture("with_demo.md"), self.profile)
        self.assertEqual(result["stats"]["visible_lines"], 1)

    def test_unbalanced_marker_fails(self) -> None:
        text = "Summary.\n\n<!-- demo:start -->\nVideo: x\n"
        self.assertIn("marker_block_unbalanced", codes(self.m.check(text, self.profile)["failures"]))

    def test_stop_list_case_insensitive(self) -> None:
        result = self.m.check("Rotated the Internal-Token for the job.\n", self.profile)
        self.assertIn("stop_list_hit", codes(result["failures"]))

    def test_empty_description_fails(self) -> None:
        self.assertIn("empty_description", codes(self.m.check("  \n", self.profile)["failures"]))

    def test_missing_profile_keys_use_defaults(self) -> None:
        result = self.m.check(fixture("good.md"), {})
        self.assertIn("visible_words", result["stats"])

    def test_cli_ok_exit_0_and_json(self) -> None:
        proc = self.run_cli(fixture("profile.json"), fixture("good.md"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(json.loads(proc.stdout)["ok"])

    def test_cli_failure_exit_1(self) -> None:
        proc = self.run_cli(fixture("profile.json"), "   ")
        self.assertEqual(proc.returncode, 1)
        self.assertFalse(json.loads(proc.stdout)["ok"])

    def test_bad_regex_exit_2(self) -> None:
        proc = self.run_cli(json.dumps({"keep_lines": ["("]}), fixture("good.md"))
        self.assertEqual(proc.returncode, 2)
        self.assertTrue(proc.stderr.strip())
        self.assertNotIn("Traceback", proc.stderr)

    def test_bad_profile_json_exit_2(self) -> None:
        proc = self.run_cli("{", fixture("good.md"))
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
