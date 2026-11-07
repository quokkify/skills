"""Checks for the feature-demo skill: its browser-free node suites and its public boundary."""

from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path


SKILL_DIR = (
    Path(__file__).resolve().parents[1] / "skills" / "software-development" / "feature-demo"
)
NODE_SUITES = ("stand.test.mjs", "summary.test.mjs", "publish.test.mjs")
EXCLUDED_DIRS = {"node_modules"}
EXCLUDED_FILES = {"package-lock.json"}
MACHINE_PATHS = ("/Users/", "/home/")
# Credentials in URLs (`https://user:token@host`) and SSH remotes (`git@host:owner/repo`)
# are not e-mail addresses: the local part must not follow `:`, `/` or `@`, nor the host precede `:`.
EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+:/@-])[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)(?![A-Za-z0-9:-]|\.[A-Za-z0-9])"
)
ALLOWED_EMAIL_DOMAIN = "example.com"
NODE_TIMEOUT_SECONDS = 300


def skill_text_files() -> list[Path]:
    files = []
    for path in sorted(SKILL_DIR.rglob("*")):
        rel = path.relative_to(SKILL_DIR)
        if not path.is_file() or EXCLUDED_DIRS & set(rel.parts) or path.name in EXCLUDED_FILES:
            continue
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        files.append(path)
    return files


class FeatureDemoSkillTest(unittest.TestCase):
    def test_node_suites_pass(self) -> None:
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        suites = [str(SKILL_DIR / "tests" / name) for name in NODE_SUITES]
        result = subprocess.run(
            [node, "--test", *suites],
            cwd=SKILL_DIR,
            capture_output=True,
            text=True,
            timeout=NODE_TIMEOUT_SECONDS,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_skill_has_no_machine_paths(self) -> None:
        self.assertTrue((SKILL_DIR / "SKILL.md").is_file(), f"missing {SKILL_DIR / 'SKILL.md'}")
        findings = []
        for path in skill_text_files():
            rel = path.relative_to(SKILL_DIR)
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                findings.extend(f"{rel}:{number}: {p}" for p in MACHINE_PATHS if p in line)
                for match in EMAIL_RE.finditer(line):
                    domain = match.group(1).casefold()
                    if domain != ALLOWED_EMAIL_DOMAIN and not domain.endswith("." + ALLOWED_EMAIL_DOMAIN):
                        findings.append(f"{rel}:{number}: e-mail {match.group(0)}")
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
