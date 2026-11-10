"""Regression guards for documentation accuracy and source hygiene. Stdlib only."""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
SKILL_MD = SKILL / "SKILL.md"
PROVENANCE = "adapted from the md-to-html-page skill in this hub"
ADAPTED_FILES = ("SKILL.md", "scripts/mermaid_parse.py", "scripts/discuss.sh", "scripts/shoot.sh")


def _unused_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    lines = path.read_text(encoding="utf-8").splitlines()
    imported: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if "F401" in lines[node.lineno - 1] or (isinstance(node, ast.ImportFrom) and node.module == "__future__"):
                continue
            for alias in node.names:
                imported[(alias.asname or alias.name).split(".")[0]] = node.lineno
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    used |= {n.value.id for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
    return [f"{path.name}:{line}: {name}" for name, line in imported.items() if name not in used]


class DocsTest(unittest.TestCase):
    def test_regression_guard_no_unused_imports(self):
        found = [u for p in sorted(SCRIPTS.glob("*.py")) for u in _unused_imports(p)]
        self.assertEqual(found, [])

    def test_regression_guard_provenance_names_source_skill(self):
        for rel in ADAPTED_FILES:
            with self.subTest(file=rel):
                text = " ".join((SKILL / rel).read_text(encoding="utf-8").split())
                self.assertIn(PROVENANCE, text.replace("# ", ""))

    def test_regression_guard_skill_md_plan_rules(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertRegex(text, r"`version` and `kind` are required")
        self.assertIn("^[a-z0-9-]{1,40}$", text)
        self.assertRegex(text, r"(?i)unique `slug`")
        self.assertIn("<parent dir>-<stem>", text)

    def test_regression_guard_skill_md_documents_warnings_and_exits(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("warning: mermaid flowchart shown as code (block N): <reason>", text)
        self.assertIn("warning: chrome render failed, using runtime diagrams: <reason>", text)
        self.assertRegex(text, r"not UTF-8[^\n]*exit 1|exit 1[^\n]*not UTF-8|\| 1 \|[^\n]*not UTF-8")

    def test_documented_env_and_flags_exist_in_launcher(self):
        launcher = (SCRIPTS / "discuss.sh").read_text(encoding="utf-8")
        text = SKILL_MD.read_text(encoding="utf-8")
        for name in sorted(set(re.findall(r"`(DISCUSS_[A-Z_]+)", text))):
            with self.subTest(env=name):
                self.assertIn(name, launcher + (SCRIPTS / "mermaid_svg.py").read_text(encoding="utf-8"))
        for flag in sorted(set(re.findall(r"\| `(--?[a-z-]+)` \|", text))):
            with self.subTest(flag=flag):
                self.assertIn(f"{flag})", launcher)


if __name__ == "__main__":
    unittest.main()
