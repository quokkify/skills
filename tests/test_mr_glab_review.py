"""Checks for the mr-glab-review helper script and the skill's public boundary."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "repository" / "mr-glab-review"
SCRIPT = SKILL_DIR / "scripts" / "mr_glab.py"
FIXTURE = ROOT / "tests" / "fixtures" / "mr_glab_review" / "sample.diff"
EXCLUDED_DIRS = {"__pycache__", "node_modules"}
MACHINE_PATHS = ("/Users/", "/home/")
EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+:/@-])[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)(?![A-Za-z0-9:-]|\.[A-Za-z0-9])"
)
ALLOWED_EMAIL_DOMAIN = "example.com"


def load_module():
    spec = importlib.util.spec_from_file_location("mr_glab", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["mr_glab"] = module
    spec.loader.exec_module(module)
    return module


class MrGlabTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.m = load_module()
        cls.diff = FIXTURE.read_text(encoding="utf-8")

    def test_parse_simple_url(self) -> None:
        ref = self.m.parse_mr_url("https://example.gitlab.com/group/app/-/merge_requests/42")
        self.assertEqual(ref, self.m.MrRef("example.gitlab.com", "group/app", 42))
        self.assertEqual(ref.encoded_project, "group%2Fapp")

    def test_nested_group_url(self) -> None:
        ref = self.m.parse_mr_url("https://example.gitlab.com/a/b/c/-/merge_requests/7/diffs")
        self.assertEqual(ref.project_path, "a/b/c")
        self.assertEqual(ref.iid, 7)

    def test_non_mr_url_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.m.parse_mr_url("https://example.gitlab.com/group/app/-/issues/42")

    def test_added_and_context_lines_mapped(self) -> None:
        lines = self.m.new_line_map(self.diff)["src/OrderGenerator.java"]
        self.assertEqual(lines[31], "    public Order second() {")
        self.assertEqual(lines[34], "            .currency(currency)")
        self.assertEqual(lines[35], "            .total(10)")
        self.assertEqual(lines[36], "        .build();")

    def test_removed_line_has_no_new_number(self) -> None:
        self.assertEqual(
            self.m.find_new_lines(self.diff, "src/OrderGenerator.java", ".legacy(true)"), []
        )

    def test_renamed_file_uses_new_path(self) -> None:
        mapping = self.m.new_line_map(self.diff)
        self.assertIn("src/UserSteps.java", mapping)
        self.assertNotIn("old/UserSteps.java", mapping)

    def test_ambiguous_text_returns_all_candidates(self) -> None:
        found = self.m.find_new_lines(self.diff, "src/OrderGenerator.java", ".build();")
        self.assertEqual(found, [36, 52])

    def test_line_outside_hunks_is_not_in_diff(self) -> None:
        self.assertFalse(self.m.in_diff(self.diff, "src/OrderGenerator.java", 1))
        self.assertTrue(self.m.in_diff(self.diff, "src/OrderGenerator.java", 35))

    def test_general_payload(self) -> None:
        self.assertEqual(self.m.draft_note_payload("hi"), {"note": "hi"})

    def test_inline_payload(self) -> None:
        refs = {"base_sha": "b", "head_sha": "h", "start_sha": "s"}
        payload = self.m.draft_note_payload("hi", refs, "src/A.java", 5)
        self.assertEqual(
            payload,
            {
                "note": "hi",
                "position": {
                    "position_type": "text",
                    "base_sha": "b",
                    "head_sha": "h",
                    "start_sha": "s",
                    "new_path": "src/A.java",
                    "old_path": "src/A.java",
                    "new_line": 5,
                },
            },
        )

    def test_partial_position_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.m.draft_note_payload("hi", None, "src/A.java", 5)
        with self.assertRaises(ValueError):
            self.m.draft_note_payload("hi", {"base_sha": "b"}, "src/A.java", None)

    def test_cli_new_line_outputs_json(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "new-line", str(FIXTURE),
             "src/OrderGenerator.java", ".build();"],
            capture_output=True, text=True, check=True,
        )
        self.assertEqual(json.loads(result.stdout), [36, 52])

    def test_cli_in_diff_exit_codes(self) -> None:
        def run(line: str) -> int:
            return subprocess.run(
                [sys.executable, str(SCRIPT), "in-diff", str(FIXTURE),
                 "src/OrderGenerator.java", line],
                capture_output=True, text=True,
            ).returncode
        self.assertEqual(run("35"), 0)
        self.assertEqual(run("1"), 1)

    def test_cli_draft_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            note = tmp_path / "note.md"
            refs = tmp_path / "refs.json"
            out = tmp_path / "out.json"
            note.write_text("body", encoding="utf-8")
            refs.write_text(json.dumps({"base_sha": "b", "head_sha": "h", "start_sha": "s"}))
            subprocess.run(
                [sys.executable, str(SCRIPT), "draft-payload", "--note-file", str(note),
                 "--refs-file", str(refs), "--path", "src/A.java", "--line", "5",
                 "--out", str(out)],
                check=True,
            )
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["position"]["new_line"], 5)

    def test_cli_parse_url(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "parse-url",
             "https://example.gitlab.com/group/app/-/merge_requests/42"],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(result.stdout)
        self.assertEqual(data["iid"], 42)
        self.assertEqual(data["encoded_project"], "group%2Fapp")

    def test_skill_has_no_machine_paths_or_real_emails(self) -> None:
        for path in sorted(SKILL_DIR.rglob("*")):
            rel = path.relative_to(SKILL_DIR)
            if not path.is_file() or EXCLUDED_DIRS & set(rel.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for machine_path in MACHINE_PATHS:
                self.assertNotIn(machine_path, text, f"{rel} contains {machine_path}")
            for match in EMAIL_RE.finditer(text):
                self.assertEqual(match.group(1), ALLOWED_EMAIL_DOMAIN, f"{rel}: {match.group(0)}")


if __name__ == "__main__":
    unittest.main()
