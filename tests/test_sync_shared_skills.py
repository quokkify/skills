from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SYNC_SCRIPT = REPOSITORY_ROOT / "scripts" / "sync-shared-skills.sh"
VALIDATOR = REPOSITORY_ROOT / "scripts" / "validate_repo.py"


class SharedSkillSyncTests(unittest.TestCase):
    def run_git(self, *arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments], cwd=cwd, check=True, text=True, capture_output=True
        )

    def configure_identity(self, repository: Path) -> None:
        self.run_git("config", "user.name", "Sync Test", cwd=repository)
        self.run_git("config", "user.email", "sync-test@example.invalid", cwd=repository)

    def make_fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        remote = root / "remote.git"
        seed = root / "seed"
        consumer = root / "consumer"

        subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
        seed.mkdir()
        self.run_git("init", "-q", "-b", "main", cwd=seed)
        self.configure_identity(seed)

        scripts = seed / "scripts"
        scripts.mkdir()
        shutil.copy2(SYNC_SCRIPT, scripts / SYNC_SCRIPT.name)
        shutil.copy2(VALIDATOR, scripts / VALIDATOR.name)
        validate_runner = scripts / "validate.sh"
        validate_runner.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "[[ \"${1:-}\" == \"--ci\" ]]\n"
            "python3 scripts/validate_repo.py\n",
            encoding="utf-8",
        )
        validate_runner.chmod(0o755)

        skill = seed / "skills" / "sample-skill" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(
            "---\nname: sample-skill\ndescription: Portable fixture.\n---\n\n# Sample\n",
            encoding="utf-8",
        )
        docs = seed / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("# Docs\n", encoding="utf-8")

        self.run_git("add", ".", cwd=seed)
        self.run_git("commit", "-q", "-m", "test: seed", cwd=seed)
        self.run_git("remote", "add", "origin", str(remote), cwd=seed)
        self.run_git("push", "-q", "-u", "origin", "main", cwd=seed)
        self.run_git("symbolic-ref", "HEAD", "refs/heads/main", cwd=remote)
        subprocess.run(["git", "clone", "-q", str(remote), str(consumer)], check=True)
        self.configure_identity(consumer)
        return temporary, remote, consumer

    def publish(
        self, remote: Path, relative_path: str, content: str, *, executable: bool = False
    ) -> str:
        publisher = remote.parent / "publisher"
        if publisher.exists():
            shutil.rmtree(publisher)
        subprocess.run(["git", "clone", "-q", str(remote), str(publisher)], check=True)
        self.configure_identity(publisher)
        target = publisher / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        if executable:
            target.chmod(0o755)
        self.run_git("add", relative_path, cwd=publisher)
        self.run_git("commit", "-q", "-m", "test: publish", cwd=publisher)
        self.run_git("push", "-q", "origin", "main", cwd=publisher)
        return self.run_git("rev-parse", "HEAD", cwd=publisher).stdout.strip()

    def run_sync(
        self, consumer: Path, extra_environment: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        if extra_environment:
            environment.update(extra_environment)
        return subprocess.run(
            ["bash", "scripts/sync-shared-skills.sh"],
            cwd=consumer,
            text=True,
            capture_output=True,
            env=environment,
        )

    def test_fast_forwards_valid_origin_main_and_prints_session_guidance(self) -> None:
        temporary, remote, consumer = self.make_fixture()
        with temporary:
            expected = self.publish(remote, "docs/update.md", "# Update\n")
            result = self.run_sync(consumer)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.run_git("rev-parse", "HEAD", cwd=consumer).stdout.strip(), expected)
            self.assertEqual(self.run_git("rev-parse", "origin/main", cwd=consumer).stdout.strip(), expected)
            self.assertIn("start a new session", result.stdout)

    def test_rejects_dirty_checkout(self) -> None:
        temporary, _, consumer = self.make_fixture()
        with temporary:
            original = self.run_git("rev-parse", "HEAD", cwd=consumer).stdout.strip()
            (consumer / "local-note.txt").write_text("local\n", encoding="utf-8")
            result = self.run_sync(consumer)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("clean checkout", result.stderr)
            self.assertEqual(self.run_git("rev-parse", "HEAD", cwd=consumer).stdout.strip(), original)

    def test_rejects_invalid_fetched_tree_before_fast_forward(self) -> None:
        temporary, remote, consumer = self.make_fixture()
        with temporary:
            original = self.run_git("rev-parse", "HEAD", cwd=consumer).stdout.strip()
            self.publish(remote, "MEMORY.md", "private state\n")
            result = self.run_sync(consumer)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Repository validation failed", result.stderr)
            self.assertEqual(self.run_git("rev-parse", "HEAD", cwd=consumer).stdout.strip(), original)

    def test_does_not_execute_fetched_scripts_or_post_merge_hooks(self) -> None:
        temporary, remote, consumer = self.make_fixture()
        with temporary:
            script_sentinel = remote.parent / "candidate-script-ran"
            hook_sentinel = remote.parent / "post-merge-hook-ran"
            script_payload = (
                "#!/usr/bin/env bash\n"
                f"printf compromised > {shlex.quote(str(script_sentinel))}\n"
            )
            self.publish(remote, "scripts/validate.sh", script_payload, executable=True)
            hook_payload = (
                "#!/usr/bin/env bash\n"
                f"printf compromised > {shlex.quote(str(hook_sentinel))}\n"
            )
            expected = self.publish(
                remote, ".githooks/post-merge", hook_payload, executable=True
            )
            self.run_git("config", "core.hooksPath", ".githooks", cwd=consumer)
            result = self.run_sync(consumer)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.run_git("rev-parse", "HEAD", cwd=consumer).stdout.strip(), expected)
            self.assertFalse(script_sentinel.exists())
            self.assertFalse(hook_sentinel.exists())

    def test_rejects_ahead_or_diverged_main(self) -> None:
        temporary, remote, consumer = self.make_fixture()
        with temporary:
            (consumer / "local.md").write_text("# Local\n", encoding="utf-8")
            self.run_git("add", "local.md", cwd=consumer)
            self.run_git("commit", "-q", "-m", "test: local", cwd=consumer)
            original = self.run_git("rev-parse", "HEAD", cwd=consumer).stdout.strip()
            self.publish(remote, "docs/remote.md", "# Remote\n")
            result = self.run_sync(consumer)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ahead of or diverged", result.stderr)
            self.assertEqual(self.run_git("rev-parse", "HEAD", cwd=consumer).stdout.strip(), original)

    def test_rejects_concurrent_main_movement_after_candidate_validation(self) -> None:
        temporary, remote, consumer = self.make_fixture()
        with temporary:
            expected = self.publish(remote, "docs/update.md", "# Update\n")
            wrapper_directory = remote.parent / "bin"
            wrapper_directory.mkdir()
            counter = remote.parent / "python-counter"
            wrapper = wrapper_directory / "python3"
            wrapper.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "count=0\n"
                "if [[ -f \"$SYNC_COUNTER\" ]]; then read -r count < \"$SYNC_COUNTER\"; fi\n"
                "count=$((count + 1))\n"
                "printf '%s\\n' \"$count\" > \"$SYNC_COUNTER\"\n"
                "\"$SYNC_REAL_PYTHON\" \"$@\"\n"
                "if [[ \"$count\" -eq 2 ]]; then\n"
                "  git -C \"$SYNC_CONSUMER\" reset --hard -q origin/main\n"
                "  git -C \"$SYNC_CONSUMER\" commit --allow-empty -q -m 'test: concurrent move'\n"
                "fi\n",
                encoding="utf-8",
            )
            wrapper.chmod(0o755)
            result = self.run_sync(
                consumer,
                {
                    "PATH": f"{wrapper_directory}:{os.environ['PATH']}",
                    "SYNC_CONSUMER": str(consumer),
                    "SYNC_COUNTER": str(counter),
                    "SYNC_REAL_PYTHON": sys.executable,
                },
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("main changed", result.stderr)
            current = self.run_git("rev-parse", "HEAD", cwd=consumer).stdout.strip()
            self.assertNotEqual(current, expected)
            self.run_git("merge-base", "--is-ancestor", expected, current, cwd=consumer)
            self.assertNotIn("Shared skills are synchronized", result.stdout)


if __name__ == "__main__":
    unittest.main()
