from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPOSITORY_ROOT / ".github" / "release-please" / "config.json"
MANIFEST_PATH = REPOSITORY_ROOT / ".github" / "release-please" / "manifest.json"
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "release.yml"
ANSWERS_PATH = REPOSITORY_ROOT / ".copier-answers.yml"


class ReleaseConfigurationTests(unittest.TestCase):
    def test_manifest_configuration_uses_standard_tag_format(self) -> None:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        self.assertEqual(config["release-type"], "simple")
        self.assertFalse(config["include-component-in-tag"])
        self.assertEqual(config["changelog-path"], "CHANGELOG.md")
        self.assertEqual(
            config["bootstrap-sha"],
            "0d975dc74fbb44c39a5a087d21abab9226919cc2",
        )
        self.assertNotIn("changelog-sections", config)
        self.assertEqual(config["packages"]["."]["package-name"], "skills")
        # Assert the manifest shape, not a frozen version: release-please rewrites this
        # value on every release, so a hard-coded number breaks the suite each time.
        self.assertEqual(list(manifest), ["."])
        self.assertRegex(manifest["."], r"^\d+\.\d+\.\d+$")

    def test_release_workflow_uses_pinned_project_toolkit(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        answers = ANSWERS_PATH.read_text(encoding="utf-8")
        version_match = re.search(r"^toolkit_version: (v\d+\.\d+\.\d+)$", answers, re.MULTILINE)

        self.assertIn("release_please: true", answers)
        self.assertIsNotNone(version_match)
        assert version_match is not None
        self.assertRegex(
            workflow,
            r"uses: quokkify/project-toolkit/\.github/workflows/release-please\.yml@[0-9a-f]{40}",
        )
        self.assertIn(f"# {version_match.group(1)}", workflow)
        self.assertIn("mode: manifest", workflow)
        self.assertIn("config-file: .github/release-please/config.json", workflow)
        self.assertIn("manifest-file: .github/release-please/manifest.json", workflow)

    def test_legacy_release_files_are_absent(self) -> None:
        legacy_paths = (
            REPOSITORY_ROOT / "release-please-config.json",
            REPOSITORY_ROOT / ".release-please-manifest.json",
            REPOSITORY_ROOT / ".github" / "workflows" / "release-please.yml",
        )
        for path in legacy_paths:
            with self.subTest(path=path):
                self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
