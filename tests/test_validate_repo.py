from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.validate_repo import validate_repository


class RepositoryValidationTests(unittest.TestCase):
    def make_repository(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        skill = root / "sample-skill" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(
            "---\n"
            "name: sample-skill\n"
            "description: A portable test skill.\n"
            "---\n\n"
            "# Sample Skill\n\nUse it safely.\n",
            encoding="utf-8",
        )
        docs = root / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("# Docs\n", encoding="utf-8")
        return temporary, root

    def test_valid_repository_passes(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            self.assertEqual(validate_repository(root), [])

    def test_duplicate_skill_name_is_rejected(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            duplicate = root / "other-skill" / "SKILL.md"
            duplicate.parent.mkdir()
            duplicate.write_text(
                "---\nname: sample-skill\ndescription: Duplicate.\n---\n\n# Duplicate\n",
                encoding="utf-8",
            )
            errors = validate_repository(root)
            self.assertTrue(any("duplicate skill name" in error for error in errors), errors)

    def test_symbolic_link_is_rejected(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            target = root / "target.txt"
            target.write_text("portable text\n", encoding="utf-8")
            link = root / "docs" / "linked.txt"
            try:
                link.symlink_to(target)
            except OSError as error:
                self.skipTest(f"symbolic links unavailable: {error}")
            errors = validate_repository(root)
            self.assertTrue(any("symbolic links are not allowed" in error for error in errors), errors)

    def test_windows_home_path_is_rejected(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            separator = chr(92)
            private_path = f"C:{separator}Users{separator}example{separator}private-file"
            (root / "docs" / "index.md").write_text(f"Do not publish {private_path}.\n", encoding="utf-8")
            errors = validate_repository(root)
            self.assertTrue(any("machine-specific Windows home path" in error for error in errors), errors)

    def test_markdown_filename_collision_is_rejected(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            (root / "docs" / "sample-skill.md").write_text("# Guide\n", encoding="utf-8")
            errors = validate_repository(root)
            self.assertTrue(any("Markdown filename collides" in error for error in errors), errors)

    def test_frontmatter_name_must_match_directory(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            skill = root / "sample-skill" / "SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8").replace("name: sample-skill", "name: renamed-skill"), encoding="utf-8")
            errors = validate_repository(root)
            self.assertTrue(any("must match directory" in error for error in errors), errors)

    def test_broken_documentation_link_is_rejected(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            (root / "docs" / "index.md").write_text("[Missing](missing.md)\n", encoding="utf-8")
            errors = validate_repository(root)
            self.assertTrue(any("broken local link" in error for error in errors), errors)

    def test_forbidden_agent_state_filename_is_rejected(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            (root / "MEMORY.md").write_text("private state\n", encoding="utf-8")
            errors = validate_repository(root)
            self.assertTrue(any("agent-local or credential-state filename" in error for error in errors), errors)

    def test_machine_specific_home_path_is_rejected(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            private_path = "/" + "home/example/private-file"
            (root / "docs" / "index.md").write_text(f"Do not publish {private_path}.\n", encoding="utf-8")
            errors = validate_repository(root)
            self.assertTrue(any("machine-specific home path" in error for error in errors), errors)

    def test_local_secret_store_path_is_rejected(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            private_path = "~/" + ".secrets/example.env"
            (root / "docs" / "index.md").write_text(f"Do not publish {private_path}.\n", encoding="utf-8")
            errors = validate_repository(root)
            self.assertTrue(any("local secret-store path" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
