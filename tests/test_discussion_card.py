"""Checks for the discussion-card skill: its own test suites, entry point and public boundary."""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


SKILL_DIR = (
    Path(__file__).resolve().parents[1] / "skills" / "software-development" / "discussion-card"
)
LAUNCHER = SKILL_DIR / "scripts" / "discuss.sh"
VENV_SETUP_FAILED = 3
SETUP_TIMEOUT_SECONDS = 600
SUITE_TIMEOUT_SECONDS = 900
EXCLUDED_DIRS = {"__pycache__"}
MACHINE_PATHS = ("/Users/", "/home/")
# Credentials in URLs (`https://user:token@host`) and SSH remotes (`git@host:owner/repo`)
# are not e-mail addresses: the local part must not follow `:`, `/` or `@`, nor the host precede `:`.
EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+:/@-])[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)(?![A-Za-z0-9:-]|\.[A-Za-z0-9])"
)
ALLOWED_EMAIL_DOMAIN = "example.com"


def skill_text_files() -> list[Path]:
    files = []
    for path in sorted(SKILL_DIR.rglob("*")):
        rel = path.relative_to(SKILL_DIR)
        if not path.is_file() or EXCLUDED_DIRS & set(rel.parts):
            continue
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        files.append(path)
    return files


def frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return {}
    fields = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


class DiscussionCardSkillTest(unittest.TestCase):
    def test_skill_suites_pass(self) -> None:
        resolved = subprocess.run(
            [str(LAUNCHER), "--python"],
            capture_output=True,
            text=True,
            timeout=SETUP_TIMEOUT_SECONDS,
            check=False,
        )
        if resolved.returncode == VENV_SETUP_FAILED:
            self.skipTest("cannot build venv (no package index)")
        self.assertEqual(resolved.returncode, 0, resolved.stdout + resolved.stderr)
        python = resolved.stdout.strip()
        result = subprocess.run(
            [python, "-I", "-m", "unittest", "discover", "-s", str(SKILL_DIR / "tests"), "-v"],
            cwd=SKILL_DIR,
            capture_output=True,
            text=True,
            timeout=SUITE_TIMEOUT_SECONDS,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_skill_md_frontmatter(self) -> None:
        skill_md = SKILL_DIR / "SKILL.md"
        self.assertTrue(skill_md.is_file(), f"missing {skill_md}")
        fields = frontmatter(skill_md.read_text(encoding="utf-8"))
        self.assertEqual(fields.get("name"), "discussion-card")
        self.assertTrue(fields.get("description"), "empty description")

    def test_skill_has_no_machine_paths(self) -> None:
        self.assertTrue((SKILL_DIR / "SKILL.md").is_file(), f"missing {SKILL_DIR / 'SKILL.md'}")
        findings = []
        for path in skill_text_files():
            rel = path.relative_to(SKILL_DIR)
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                findings.extend(f"{rel}:{number}: {p}" for p in MACHINE_PATHS if p in line)
        self.assertEqual(findings, [])

    def test_skill_has_no_real_emails(self) -> None:
        findings = []
        for path in skill_text_files():
            rel = path.relative_to(SKILL_DIR)
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                for match in EMAIL_RE.finditer(line):
                    domain = match.group(1).casefold()
                    if domain.rsplit(".", 1)[-1].isdigit():  # `python@3.12` is a version pin
                        continue
                    if domain != ALLOWED_EMAIL_DOMAIN and not domain.endswith("." + ALLOWED_EMAIL_DOMAIN):
                        findings.append(f"{rel}:{number}: e-mail {match.group(0)}")
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
