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

TOOLKIT_RELEASE_WORKFLOW = "quokkify/project-toolkit/.github/workflows/release-please.yml"
TOOLKIT_USES_MARKER = f"uses: {TOOLKIT_RELEASE_WORKFLOW}@"


def toolkit_reference(workflow: str) -> tuple[str, str] | None:
    """Return the reference and its trailing comment for the toolkit release job."""
    for line in workflow.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(TOOLKIT_USES_MARKER):
            reference = stripped[len(TOOLKIT_USES_MARKER) :].split()[0]
            return reference, line.partition("#")[2].strip()
    return None


def references_toolkit_version(workflow: str, version: str) -> bool:
    """Apply the toolkit's own pin contract, mirrored from ``.github/workflows/validate.yml``.

    The reference identifies the toolkit release workflow at ``version`` when it is
    either the exact tag, or a full 40-character digest whose comment names that tag.
    """
    parsed = toolkit_reference(workflow)
    if parsed is None:
        return False
    reference, comment = parsed
    if reference == version:
        return True
    return re.fullmatch(r"[0-9a-f]{40}", reference) is not None and comment == version


def with_toolkit_reference(workflow: str, replacement: str) -> str:
    """Rewrite the toolkit reference in place, keeping the rest of the artifact intact."""
    lines = []
    for line in workflow.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(TOOLKIT_USES_MARKER):
            indent = line[: len(line) - len(stripped)]
            line = f"{indent}{TOOLKIT_USES_MARKER}{replacement}"
        lines.append(line)
    return "\n".join(lines) + "\n"


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

    def toolkit_version(self) -> str:
        answers = ANSWERS_PATH.read_text(encoding="utf-8")
        version_match = re.search(r"^toolkit_version: (v\d+\.\d+\.\d+)$", answers, re.MULTILINE)
        self.assertIn("release_please: true", answers)
        self.assertIsNotNone(version_match)
        assert version_match is not None
        return version_match.group(1)

    def test_release_workflow_calls_the_toolkit_at_the_answered_version(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        version = self.toolkit_version()

        self.assertIsNotNone(
            toolkit_reference(workflow),
            "release.yml must call the toolkit release-please workflow",
        )
        self.assertTrue(
            references_toolkit_version(workflow, version),
            f"release.yml must reference the toolkit at {version}, as that tag or as a "
            "digest whose comment names it",
        )
        self.assertIn("mode: manifest", workflow)
        self.assertIn("config-file: .github/release-please/config.json", workflow)
        self.assertIn("manifest-file: .github/release-please/manifest.json", workflow)

    def test_pin_contract_accepts_both_forms_the_toolkit_emits(self) -> None:
        # The probes are the committed artifact with only its pin rewritten, so they
        # cannot drift from the file they mirror.
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        version = self.toolkit_version()
        digest = "0" * 40
        other_digest = "1" * 40

        accepted = {
            "exact tag": version,
            "digest carrying the version": f"{digest} # {version}",
            "bumped digest carrying the version": f"{other_digest} # {version}",
        }
        for label, replacement in accepted.items():
            with self.subTest(accepted=label):
                self.assertTrue(
                    references_toolkit_version(with_toolkit_reference(workflow, replacement), version)
                )

        rejected = {
            "mutable branch": "main",
            "another tag": "v0.0.1",
            "truncated digest": f"{digest[:-1]} # {version}",
            "digest without a version comment": digest,
            "digest naming another version": f"{digest} # v0.0.1",
        }
        for label, replacement in rejected.items():
            with self.subTest(rejected=label):
                self.assertFalse(
                    references_toolkit_version(with_toolkit_reference(workflow, replacement), version)
                )

    def test_pin_contract_requires_the_toolkit_release_workflow(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        version = self.toolkit_version()
        unrelated = workflow.replace(TOOLKIT_RELEASE_WORKFLOW, "quokkify/other/.github/workflows/x.yml")

        self.assertIsNone(toolkit_reference(unrelated))
        self.assertFalse(references_toolkit_version(unrelated, version))

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
