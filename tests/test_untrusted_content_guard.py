"""Regression guard: skills that read third-party text and then act on it must say that text is data."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


SKILLS = Path(__file__).resolve().parents[1] / "skills"

# Skills that read text written by someone else (release notes, MR or PR descriptions, review
# comments, CI logs, page text) and then edit, run, commit, push, or post on the strength of it.
GUARDED_SKILLS = (
    "repository/renovate-adoption-review",
    "repository/repository-quality-gates",
    "repository/mr-glab-review",
    "software-development/feature-demo",
)

REQUIRED_RULES = {
    "data, not instructions": r"data[^.\n]*,\s*never instructions",
    "no quoted commands": r"[Nn]ever run a command quoted in",
    "cited edits only": r"cite to a specific",
    "stop on out-of-scope requests": r"outside this task[^.\n]*,\s*stop",
}


def guard_section(text: str) -> str:
    match = re.search(r"^## Untrusted content\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else ""


class UntrustedContentGuardTests(unittest.TestCase):
    def test_guarded_skills_state_every_rule_in_a_dedicated_section(self) -> None:
        for skill in GUARDED_SKILLS:
            text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
            section = guard_section(text)
            with self.subTest(skill=skill):
                self.assertTrue(section, f"{skill}: missing '## Untrusted content' section")
                for rule, pattern in REQUIRED_RULES.items():
                    self.assertRegex(section, pattern, f"{skill}: guard lacks rule '{rule}'")

    def test_guard_comes_before_the_workflow(self) -> None:
        for skill in GUARDED_SKILLS:
            text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
            headings = re.findall(r"^## (.+)$", text, re.MULTILINE)
            with self.subTest(skill=skill):
                self.assertIn("Untrusted content", headings)
                index = headings.index("Untrusted content")
                self.assertLessEqual(index, 2, f"{skill}: the guard must be near the top, found at heading {index}")


if __name__ == "__main__":
    unittest.main()
