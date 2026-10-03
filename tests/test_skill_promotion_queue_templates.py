"""Behavioural tests for the harness shell templates.

These cover the two signal-fidelity properties the templates promise and that a
`SKILL.md`-only view of a skill silently breaks: divergence confined to a support
file must still be surfaced and adoptable, and a skill whose use the signal cannot
observe must never be treated as unused.
"""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

# The templates commit on their own. Git only falls back to an identity built from the
# OS user and hostname, which a container has no reason to make valid, so a run that
# passes on a workstation fails in CI with "Author identity unknown". Supply one.
GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "harness test",
    "GIT_AUTHOR_EMAIL": "harness@example.invalid",
    "GIT_COMMITTER_NAME": "harness test",
    "GIT_COMMITTER_EMAIL": "harness@example.invalid",
}
TEMPLATES = (
    REPOSITORY_ROOT / "skills" / "skill-management" / "skill-promotion-queue" / "templates"
)
UPGRADE = TEMPLATES / "skill_upgrade.sh"
PRUNE = TEMPLATES / "skill_prune.sh"

SKILL_BODY = "---\nname: {name}\ndescription: {name} does a thing\n---\n\nBody.\n"


class TemplateFixture(unittest.TestCase):
    """A throwaway installed library, hub checkout, and lane worktree."""

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.config = self.root / "cfg"
        self.hub = self.root / "hub"
        (self.config / "skill-health").mkdir(parents=True)
        (self.hub / "skills" / "cat").mkdir(parents=True)

    def write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def install_skill(self, name: str, *, files: dict[str, str] | None = None) -> Path:
        directory = self.config / "skills" / name
        self.write(directory / "SKILL.md", SKILL_BODY.format(name=name))
        for relative, text in (files or {}).items():
            self.write(directory / relative, text)
        return directory

    def hub_skill(self, name: str, *, files: dict[str, str] | None = None) -> Path:
        directory = self.hub / "skills" / "cat" / name
        self.write(directory / "SKILL.md", SKILL_BODY.format(name=name))
        for relative, text in (files or {}).items():
            self.write(directory / relative, text)
        return directory

    def write_state(self, rows: list[tuple[str, int, str, str]]) -> None:
        """rows: (name, usage, state, hub_skill_md_path)."""
        lines = [
            "\t".join([name, str(usage), "1700000000", "installed-digest", hub_md, "hub-digest", state])
            for name, usage, state, hub_md in rows
        ]
        self.write(self.config / "skill-health" / "state.tsv", "\n".join(lines) + "\n")

    def run_template(self, script: Path, *arguments: str, extra_env: dict[str, str] | None = None):
        environment = dict(os.environ)
        environment.update(
            {
                "CLAUDE_CONFIG_DIR": str(self.config),
                "SKILL_HARNESS_MAIN": str(self.hub),
                "HOME": str(self.root),
            }
        )
        environment.update(GIT_IDENTITY)
        environment.update(extra_env or {})
        return subprocess.run(
            ["bash", str(script), *arguments],
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def read_candidate(self, pattern: str) -> str:
        matches = sorted((self.config / "skill-candidates").glob(pattern))
        self.assertTrue(matches, f"no candidate matched {pattern}")
        return matches[0].read_text(encoding="utf-8")


class SupportFileDivergenceTests(TemplateFixture):
    def test_divergence_confined_to_a_support_file_is_reported(self) -> None:
        """The case a SKILL.md-only diff cannot see: identical entry point, changed script."""
        hub = self.hub_skill("demo", files={"scripts/run.sh": "echo hub\n"})
        self.install_skill(
            "demo",
            files={"scripts/run.sh": "echo improved\n", "scripts/added.sh": "echo new\n"},
        )
        self.write_state([("demo", 0, "stale", str(hub / "SKILL.md"))])

        result = self.run_template(UPGRADE)
        self.assertEqual(result.returncode, 0, result.stderr)

        candidate = self.read_candidate("demo-upgrade-*.md")
        self.assertIn("echo improved", candidate)
        self.assertIn("added.sh", candidate)
        self.assertIn("scripts/run.sh", candidate)

    def test_generated_noise_is_excluded_from_the_diff(self) -> None:
        hub = self.hub_skill("demo", files={"scripts/run.sh": "echo hub\n"})
        self.install_skill(
            "demo",
            files={"scripts/run.sh": "echo improved\n", "__pycache__/x.pyc": "cache-junk\n"},
        )
        self.write_state([("demo", 0, "stale", str(hub / "SKILL.md"))])

        self.assertEqual(self.run_template(UPGRADE).returncode, 0)
        candidate = self.read_candidate("demo-upgrade-*.md")
        # The excluded directory may still appear inside the echoed `diff -ur -x ...`
        # header; what must not appear is the file itself or its contents.
        self.assertNotIn("cache-junk", candidate)
        self.assertNotIn("x.pyc", candidate)
        self.assertNotIn("Only in", candidate)


class AdoptDirectoryTests(TemplateFixture):
    def make_lane(self) -> Path:
        lane = self.root / "lane"
        source = self.hub / "skills" / "cat" / "demo"
        target = lane / "skills" / "cat" / "demo"
        target.mkdir(parents=True)
        for item in source.rglob("*"):
            if item.is_file():
                destination = target / item.relative_to(source)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(item.read_bytes())
        self.git(lane, "init", "-q", "-b", "automation/skill-improvements/testlane")
        self.git(lane, "add", "-A")
        self.git(lane, "commit", "-q", "-m", "seed")
        return lane

    def git(self, cwd: Path, *arguments: str) -> None:
        environment = dict(os.environ)
        environment.update(GIT_IDENTITY)
        subprocess.run(
            ["git", *arguments], cwd=cwd, env=environment, check=True, capture_output=True, text=True
        )

    def test_adopt_propagates_added_changed_and_deleted_support_files(self) -> None:
        hub = self.hub_skill(
            "demo", files={"scripts/run.sh": "echo hub\n", "scripts/obsolete.sh": "gone\n"}
        )
        self.install_skill(
            "demo", files={"scripts/run.sh": "echo improved\n", "scripts/added.sh": "echo new\n"}
        )
        self.write_state([("demo", 0, "stale", str(hub / "SKILL.md"))])
        lane = self.make_lane()

        result = self.run_template(
            UPGRADE,
            "--adopt",
            "demo",
            extra_env={
                "SKILL_HARNESS_WORKTREE": str(lane),
                "SKILL_HARNESS_LANE": "testlane",
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        adopted = lane / "skills" / "cat" / "demo" / "scripts"
        self.assertEqual((adopted / "run.sh").read_text(encoding="utf-8"), "echo improved\n")
        self.assertTrue((adopted / "added.sh").exists(), "a locally added script must be adopted")
        self.assertFalse(
            (adopted / "obsolete.sh").exists(),
            "a file deleted locally must also be dropped from the hub copy",
        )

        committed = subprocess.run(
            ["git", "show", "--stat", "--format=", "HEAD"],
            cwd=lane,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        self.assertIn("added.sh", committed)
        self.assertIn("obsolete.sh", committed)

    def test_adopt_refuses_a_hub_path_that_escapes_the_lane(self) -> None:
        """hub_path comes from an unvalidated local file and reaches `rm -rf`."""
        self.hub_skill("demo")
        self.install_skill("demo")
        victim = self.root / "victim" / "demo"
        self.write(victim / "SKILL.md", SKILL_BODY.format(name="demo"))
        self.write(victim / "precious.txt", "keep me\n")
        lane = self.make_lane()

        traversal = self.hub / "skills" / ".." / ".." / "victim" / "demo" / "SKILL.md"
        self.write_state([("demo", 0, "stale", str(traversal))])

        result = self.run_template(
            UPGRADE,
            "--adopt",
            "demo",
            extra_env={"SKILL_HARNESS_WORKTREE": str(lane), "SKILL_HARNESS_LANE": "testlane"},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("relative component", result.stderr)
        self.assertTrue(
            (victim / "precious.txt").exists(),
            "a traversing hub path must never reach the recursive delete",
        )

    def test_adopt_refuses_a_path_nested_below_the_skill_layout(self) -> None:
        self.hub_skill("demo")
        self.install_skill("demo")
        lane = self.make_lane()
        deep = self.hub / "skills" / "cat" / "extra" / "demo" / "SKILL.md"
        self.write(deep, SKILL_BODY.format(name="demo"))
        self.write_state([("demo", 0, "stale", str(deep))])

        result = self.run_template(
            UPGRADE,
            "--adopt",
            "demo",
            extra_env={"SKILL_HARNESS_WORKTREE": str(lane), "SKILL_HARNESS_LANE": "testlane"},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("nested deeper", result.stderr)

    def test_adopt_preserves_the_executable_bit_and_drops_noise(self) -> None:
        hub = self.hub_skill("demo", files={"scripts/run.sh": "echo hub\n"})
        installed = self.install_skill(
            "demo",
            files={"scripts/run.sh": "echo improved\n", "__pycache__/x.pyc": "cache-junk\n"},
        )
        (installed / "scripts" / "run.sh").chmod(0o755)
        self.write_state([("demo", 0, "stale", str(hub / "SKILL.md"))])
        lane = self.make_lane()

        result = self.run_template(
            UPGRADE,
            "--adopt",
            "demo",
            extra_env={"SKILL_HARNESS_WORKTREE": str(lane), "SKILL_HARNESS_LANE": "testlane"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        adopted = lane / "skills" / "cat" / "demo"
        self.assertTrue(
            os.access(adopted / "scripts" / "run.sh", os.X_OK),
            "an adopted script that is not executable cannot run",
        )
        self.assertFalse((adopted / "__pycache__").exists())
        self.assertEqual(
            [],
            [p for p in adopted.parent.iterdir() if p.name.startswith(".adopt-backup")]
            + [p for p in adopted.parent.iterdir() if ".adopt-backup" in p.name],
            "the backup copy must not be left behind in the lane",
        )


class UnobservableUsageTests(TemplateFixture):
    def test_skill_shipping_scripts_is_never_counted_as_unused(self) -> None:
        """Its entry point bypasses the Skill tool, so a zero count carries no information."""
        alpha = self.hub_skill("alpha")
        beta = self.hub_skill("beta")
        self.install_skill("alpha", files={"scripts/run.sh": "echo run\n"})
        self.install_skill("beta")
        self.write_state(
            [
                ("alpha", 0, "in-sync", str(alpha / "SKILL.md")),
                ("beta", 0, "in-sync", str(beta / "SKILL.md")),
            ]
        )

        result = self.run_template(PRUNE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("keep-unobservable-usage=1", result.stdout)

        report = self.read_candidate("prune-assessment-*.md")
        self.assertRegex(report, r"`alpha`\s*\|\s*`keep-unobservable-usage`")
        self.assertNotRegex(report, r"`beta`\s*\|\s*`keep-unobservable-usage`")

    def test_verdict_outranks_the_signal_window_guard(self) -> None:
        """Waiting longer can never make this skill's silence into evidence."""
        alpha = self.hub_skill("alpha")
        self.install_skill("alpha", files={"scripts/run.sh": "echo run\n"})
        self.write_state([("alpha", 0, "in-sync", str(alpha / "SKILL.md"))])

        result = self.run_template(PRUNE, extra_env={"SKILL_PRUNE_MIN_DAYS": "0"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("keep-unobservable-usage=1", result.stdout)
        self.assertIn("prune=0", result.stdout)

    def test_runnable_file_outside_scripts_also_counts(self) -> None:
        """Support files live in templates/ as often as in scripts/."""
        alpha = self.hub_skill("alpha")
        self.install_skill("alpha", files={"templates/bootstrap.sh": "echo hi\n"})
        self.write_state([("alpha", 0, "in-sync", str(alpha / "SKILL.md"))])

        result = self.run_template(PRUNE, extra_env={"SKILL_PRUNE_MIN_DAYS": "0"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("keep-unobservable-usage=1", result.stdout)

    def test_documentation_only_skill_is_still_assessed(self) -> None:
        """The guard must not swallow every skill; a prose-only skill keeps its verdict."""
        beta = self.hub_skill("beta")
        self.install_skill("beta", files={"references/notes.md": "prose\n"})
        self.write_state([("beta", 0, "in-sync", str(beta / "SKILL.md"))])

        result = self.run_template(PRUNE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("keep-unobservable-usage=0", result.stdout)


if __name__ == "__main__":
    unittest.main()
