from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.validate_repo import validate_repository


class RepositoryValidationTests(unittest.TestCase):
    def make_repository(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        skill = root / "skills" / "samples" / "sample-skill" / "SKILL.md"
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

    def test_skill_outside_canonical_skills_directory_is_rejected(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            misplaced = root / "misplaced-skill" / "SKILL.md"
            misplaced.parent.mkdir()
            misplaced.write_text(
                "---\nname: misplaced-skill\ndescription: Misplaced.\n---\n\n# Misplaced\n",
                encoding="utf-8",
            )
            errors = validate_repository(root)
            self.assertTrue(any("skills/<category>/<skill-name>/SKILL.md" in error for error in errors), errors)

    def test_flat_skill_without_category_is_rejected(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            flat = root / "skills" / "flat-skill" / "SKILL.md"
            flat.parent.mkdir(parents=True)
            flat.write_text(
                "---\nname: flat-skill\ndescription: Flat.\n---\n\n# Flat\n",
                encoding="utf-8",
            )
            errors = validate_repository(root)
            self.assertTrue(any("skills/<category>/<skill-name>/SKILL.md" in error for error in errors), errors)

    def test_over_nested_skill_is_rejected(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            nested = root / "skills" / "category" / "group" / "deep-skill" / "SKILL.md"
            nested.parent.mkdir(parents=True)
            nested.write_text(
                "---\nname: deep-skill\ndescription: Too deep.\n---\n\n# Deep\n",
                encoding="utf-8",
            )
            errors = validate_repository(root)
            self.assertTrue(any("skills/<category>/<skill-name>/SKILL.md" in error for error in errors), errors)
            self.assertFalse(any("missing SKILL.md" in error for error in errors), errors)

    def test_invalid_category_name_is_rejected(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            bad = root / "skills" / "Bad_Category" / "some-skill" / "SKILL.md"
            bad.parent.mkdir(parents=True)
            bad.write_text(
                "---\nname: some-skill\ndescription: Bad category.\n---\n\n# Some\n",
                encoding="utf-8",
            )
            errors = validate_repository(root)
            self.assertTrue(any("must use lowercase kebab-case" in error for error in errors), errors)

    def test_canonical_skill_directory_requires_uppercase_entry_point(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            misplaced = root / "skills" / "samples" / "lowercase-entry" / "skill.md"
            misplaced.parent.mkdir(parents=True)
            misplaced.write_text("# Not an entry point\n", encoding="utf-8")
            errors = validate_repository(root)
            self.assertTrue(any("missing SKILL.md" in error for error in errors), errors)

    def test_duplicate_skill_name_is_rejected(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            duplicate = root / "skills" / "samples" / "other-skill" / "SKILL.md"
            duplicate.parent.mkdir(parents=True)
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
            skill = root / "skills" / "samples" / "sample-skill" / "SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8").replace("name: sample-skill", "name: renamed-skill"), encoding="utf-8")
            errors = validate_repository(root)
            self.assertTrue(any("must match directory" in error for error in errors), errors)

    def test_broken_documentation_link_is_rejected(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            (root / "docs" / "index.md").write_text("[Missing](missing.md)\n", encoding="utf-8")
            errors = validate_repository(root)
            self.assertTrue(any("broken local link" in error for error in errors), errors)

    def test_commonmark_destinations_with_parentheses_and_spaces_are_valid(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            docs = root / "docs"
            (docs / "foo(bar).md").write_text("# Parentheses\n", encoding="utf-8")
            (docs / "my guide.md").write_text("# Spaces\n", encoding="utf-8")
            preserved_backslash = "foo" + chr(92) + "q.md"
            (docs / preserved_backslash).write_text("# Backslash\n", encoding="utf-8")
            (docs / "index.md").write_text(
                "[Nested](foo(bar).md), [escaped](foo\\(bar\\).md), "
                f"[preserved]({preserved_backslash}), and [spaced](<my guide.md>)\n",
                encoding="utf-8",
            )
            self.assertEqual(validate_repository(root), [])

    def test_multiline_broken_markdown_link_is_rejected(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            (root / "docs" / "index.md").write_text(
                "[Missing](\nmissing.md)\n", encoding="utf-8"
            )
            errors = validate_repository(root)
            self.assertTrue(any("docs/index.md:1: broken local link" in error for error in errors), errors)

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

    def test_binary_skill_asset_is_allowed(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            assets = root / "skills" / "samples" / "sample-skill" / "assets"
            assets.mkdir()
            (assets / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff")
            self.assertEqual(validate_repository(root), [])

    def test_invalid_utf8_skill_is_reported(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            (root / "skills" / "samples" / "sample-skill" / "SKILL.md").write_bytes(b"---\nname: sample-skill\n---\n\xff")
            errors = validate_repository(root)
            self.assertTrue(any("file is not valid UTF-8" in error for error in errors), errors)

    def test_invalid_utf8_markdown_is_reported(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            (root / "docs" / "index.md").write_bytes(b"# Docs\n\xff")
            errors = validate_repository(root)
            self.assertTrue(any("file is not valid UTF-8" in error for error in errors), errors)

    def test_escaping_markdown_link_is_rejected_without_echoing_target(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            private_marker = "private-client-token"
            (root / "docs" / "index.md").write_text(
                f"[Outside](../../outside.md?token={private_marker})\n", encoding="utf-8"
            )
            errors = validate_repository(root)
            self.assertTrue(any("local link escapes repository" in error for error in errors), errors)
            self.assertFalse(any(private_marker in error for error in errors), errors)

    def test_skill_support_markdown_does_not_collide(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            references = root / "skills" / "samples" / "sample-skill" / "references"
            references.mkdir()
            (references / "sample-skill.md").write_text("# Internal reference\n", encoding="utf-8")
            self.assertEqual(validate_repository(root), [])

    def test_public_boundary_checks_are_case_insensitive_and_cover_root(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            (root / "memory.md").write_text("private state\n", encoding="utf-8")
            sessions = root / "Sessions"
            sessions.mkdir()
            (sessions / "chat.txt").write_text("private transcript\n", encoding="utf-8")
            root_path = "/" + "root/private-file"
            (root / "docs" / "index.md").write_text(root_path, encoding="utf-8")
            errors = validate_repository(root)
            self.assertTrue(any("agent-local or credential-state filename" in error for error in errors), errors)
            self.assertTrue(any("private/runtime state directory" in error for error in errors), errors)
            self.assertTrue(any("machine-specific home path" in error for error in errors), errors)

    def test_gitignored_files_are_not_repository_content(self) -> None:
        temporary, root = self.make_repository()
        with temporary:
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text("ignored/\n", encoding="utf-8")
            ignored = root / "ignored"
            ignored.mkdir()
            (ignored / "MEMORY.md").write_text("local only\n", encoding="utf-8")
            (root / "memory.md").write_text("must be rejected\n", encoding="utf-8")
            errors = validate_repository(root)
            self.assertTrue(any(error.startswith("memory.md:") for error in errors), errors)
            self.assertFalse(any(error.startswith("ignored/MEMORY.md:") for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
