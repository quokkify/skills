"""Checks for the variant-shootout skill: its own test suite, frontmatter and public boundary."""

from __future__ import annotations

import re
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "variant-shootout"
SKILL_DIR = ROOT / "skills" / "software-development" / SKILL_NAME
SPEC = ROOT / "docs" / "superpowers" / "specs" / "2026-11-20-variant-shootout-design.md"
SUITE_TIMEOUT_SECONDS = 900
EXCLUDED_DIRS = {"__pycache__", "node_modules"}
MACHINE_PATHS = ("/Users/", "/home/")
STOP_WORDS_ENV = "SKILL_PRIVATE_STOP_WORDS"
URL_HOST_RE = re.compile(r"https?://([A-Za-z0-9.-]+)")
ALLOWED_HOST_DOMAINS = ("example.com", "example.org")
PUBLIC_TOOL_HOSTS = ("registry.npmjs.org",)
# Credentials in URLs (`https://user:token@host`) and SSH remotes (`git@host:owner/repo`)
# are not e-mail addresses: the local part must not follow `:`, `/` or `@`, nor the host precede `:`.
EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+:/@-])[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)(?![A-Za-z0-9:-]|\.[A-Za-z0-9])"
)
ALLOWED_EMAIL_DOMAINS = ("example.com", "example.org")


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


def boundary_files() -> list[Path]:
    return skill_text_files() + [SPEC]


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


def allowed_email_domain(domain: str) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in ALLOWED_EMAIL_DOMAINS)


def allowed_host(host: str) -> bool:
    return host in PUBLIC_TOOL_HOSTS or any(
        host == d or host.endswith("." + d) for d in ALLOWED_HOST_DOMAINS
    )


def private_stop_words() -> list[str]:
    raw = os.environ.get(STOP_WORDS_ENV, "")
    return [w.strip().casefold() for w in raw.split(",") if w.strip()]


class VariantShootoutSkillTest(unittest.TestCase):
    def test_skill_suite_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", str(SKILL_DIR / "tests"), "-v"],
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
        self.assertEqual(fields.get("name"), SKILL_DIR.name)
        self.assertTrue(fields.get("description"), "empty description")

    def test_spec_exists(self) -> None:
        self.assertTrue(SPEC.is_file(), f"missing {SPEC}")

    def test_no_private_stop_words(self) -> None:
        words = private_stop_words()
        if not words:
            self.skipTest(f"{STOP_WORDS_ENV} is not set; private stop-word scan skipped")
        findings = []
        for path in boundary_files():
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                folded = line.casefold()
                findings.extend(f"{rel}:{number}: stop word #{i + 1}" for i, w in enumerate(words) if w in folded)
        self.assertEqual(findings, [])

    def test_only_example_or_public_tool_hosts(self) -> None:
        self.assertTrue((SKILL_DIR / "SKILL.md").is_file(), f"missing {SKILL_DIR / 'SKILL.md'}")
        findings = []
        for path in boundary_files():
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                for match in URL_HOST_RE.finditer(line):
                    host = match.group(1).casefold().rstrip(".")
                    if not allowed_host(host):
                        findings.append(f"{rel}:{number}: host {host}")
        self.assertEqual(findings, [])

    def test_no_machine_paths(self) -> None:
        self.assertTrue((SKILL_DIR / "SKILL.md").is_file(), f"missing {SKILL_DIR / 'SKILL.md'}")
        findings = []
        for path in boundary_files():
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                findings.extend(f"{rel}:{number}: {p}" for p in MACHINE_PATHS if p in line)
        self.assertEqual(findings, [])

    def test_no_real_emails(self) -> None:
        self.assertTrue((SKILL_DIR / "SKILL.md").is_file(), f"missing {SKILL_DIR / 'SKILL.md'}")
        findings = []
        for path in boundary_files():
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                for match in EMAIL_RE.finditer(line):
                    domain = match.group(1).casefold()
                    if domain.rsplit(".", 1)[-1].isdigit():  # `python@3.12` is a version pin
                        continue
                    if not allowed_email_domain(domain):
                        findings.append(f"{rel}:{number}: e-mail {match.group(0)}")
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
