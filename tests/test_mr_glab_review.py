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
SKILL_MD = SKILL_DIR / "SKILL.md"
SKILL_DESCRIPTION = (
    "Review a GitLab merge request together with the human reviewer: verify findings, "
    "approve each comment one by one, stage approved ones as draft notes in a light, "
    "friendly format, and publish them in one batch."
)


def github_slug(heading: str) -> str:
    """GitHub-style anchor: lowercase, drop punctuation except hyphens and spaces, spaces to hyphens."""
    kept = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return kept.replace(" ", "-")


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

    def test_blank_context_forms_keep_numbering(self) -> None:
        # Regression guard: both " " (glab) and "" blank context lines must advance the counter.
        diff = (
            "diff --git a/A.java b/A.java\n--- a/A.java\n+++ b/A.java\n"
            "@@ -1,4 +1,4 @@\n one\n \n\n+four\n-x\n"
        )
        diff = diff.replace("-x\n", "")
        diff = diff.replace("@@ -1,4 +1,4 @@", "@@ -1,3 +1,4 @@")
        lines = self.m.new_line_map(diff)["A.java"]
        self.assertEqual(lines, {1: "one", 2: "", 3: "", 4: "four"})

    def test_form_feed_and_unicode_separators_do_not_split_lines(self) -> None:
        # Regression guard: splitlines() split on \x0c, U+2028 etc. and shifted later numbers.
        diff = (
            "diff --git a/A.java b/A.java\n--- a/A.java\n+++ b/A.java\n"
            "@@ -1,2 +1,3 @@\n a\x0cb\n+c\u2028d\n last\n"
        )
        lines = self.m.new_line_map(diff)["A.java"]
        self.assertEqual(lines[2], "c\u2028d")
        self.assertEqual(lines[3], "last")

    def test_trailing_blank_lines_after_last_hunk_not_mapped(self) -> None:
        diff = (
            "diff --git a/A.java b/A.java\n--- a/A.java\n+++ b/A.java\n"
            "@@ -1 +1 @@\n-old\n+new\n\n\ndiff --git a/B.java b/B.java\n"
        )
        self.assertEqual(self.m.new_line_map(diff), {"A.java": {1: "new"}})
        self.assertFalse(self.m.in_diff(diff, "A.java", 2))

    def test_no_newline_marker_does_not_advance_counters(self) -> None:
        diff = (
            "diff --git a/A.java b/A.java\n--- a/A.java\n+++ b/A.java\n"
            "@@ -1,2 +1,2 @@\n a\n-b\n\\ No newline at end of file\n+c\n"
            "\\ No newline at end of file\n"
        )
        self.assertEqual(self.m.new_line_map(diff)["A.java"], {1: "a", 2: "c"})

    def test_new_file_lines_are_mapped(self) -> None:
        lines = self.m.new_line_map(self.diff)["src/NewHelper.java"]
        self.assertEqual(lines[3], "public class NewHelper {}")

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

    def test_references_exist_and_have_sections(self) -> None:
        expected = {
            "gitlab-api.md": ["Resolve the MR", "Draft notes", "Publish", "Edit a note", "Errors"],
            "comment-style.md": ["Structure", "Markers", "Checklist", "Examples"],
        }
        for name, headings in expected.items():
            path = SKILL_DIR / "references" / name
            self.assertTrue(path.is_file(), f"missing {name}")
            lines = path.read_text(encoding="utf-8").splitlines()
            for heading in headings:
                self.assertIn(f"## {heading}", lines, f"{name} lacks '## {heading}'")

    def test_api_recipes_use_documented_endpoints(self) -> None:
        text = (SKILL_DIR / "references" / "gitlab-api.md").read_text(encoding="utf-8")
        for needle in ("merge_requests/:iid/draft_notes", "draft_notes/bulk_publish", '"note"', "glab api"):
            self.assertIn(needle, text)

    def test_style_examples_count(self) -> None:
        text = (SKILL_DIR / "references" / "comment-style.md").read_text(encoding="utf-8")
        parts = re.split(r"^### Example", text, flags=re.M)[1:]
        self.assertEqual(len(parts), 3)
        for part in parts:
            self.assertRegex(part, r"(?m)^Before:$")
            self.assertRegex(part, r"(?m)^After:$")


    def test_skill_frontmatter(self) -> None:
        text = SKILL_MD.read_text(encoding="utf-8")
        match = re.match(r"---\n(.*?)\n---\n", text, flags=re.S)
        self.assertIsNotNone(match, "SKILL.md lacks frontmatter")
        fields = dict(line.split(": ", 1) for line in match.group(1).splitlines())
        self.assertEqual(fields.get("name"), "mr-glab-review")
        self.assertEqual(fields.get("description"), SKILL_DESCRIPTION)

    def test_skill_has_all_phases(self) -> None:
        headings = [
            line.lstrip("#").strip()
            for line in SKILL_MD.read_text(encoding="utf-8").splitlines()
            if line.startswith("#")
        ]
        for wanted in ("Phase 0", "Phase 1", "Phase 2", "Phase 3", "Phase 4", "Profile", "Resume"):
            self.assertTrue(
                any(h.startswith(wanted) for h in headings), f"SKILL.md lacks heading '{wanted}'"
            )

    def test_skill_links_resolve(self) -> None:
        text = SKILL_MD.read_text(encoding="utf-8")
        links = re.findall(r"\]\((references/[^)#\s]+)(?:#([^)\s]+))?\)", text)
        self.assertTrue(links, "SKILL.md links no references")
        for target, anchor in links:
            path = SKILL_DIR / target
            self.assertTrue(path.is_file(), f"missing link target {target}")
            if not anchor:
                continue
            slugs = {
                github_slug(line.lstrip("#"))
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.startswith("#")
            }
            self.assertIn(anchor, slugs, f"{target} has no heading for #{anchor}")

    def test_catalog_lists_skill(self) -> None:
        catalog = (ROOT / "docs" / "skill-catalog.md").read_text(encoding="utf-8")
        section = catalog.split("\n## repository\n", 1)[1].split("\n## ", 1)[0]
        self.assertIn(
            "- [`mr-glab-review`](../skills/repository/mr-glab-review/SKILL.md) — "
            "review a GitLab MR with the reviewer item by item and publish approved, "
            "friendly comments in one batch.",
            section,
        )


if __name__ == "__main__":
    unittest.main()
