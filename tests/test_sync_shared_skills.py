from __future__ import annotations

import shutil
import subprocess
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

        skill = seed / "sample-skill" / "SKILL.md"
        skill.parent.mkdir()
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

    def publish(self, remote: Path, relative_path: str, content: str) -> str:
        publisher = remote.parent / "publisher"
        if publisher.exists():
            shutil.rmtree(publisher)
        subprocess.run(["git", "clone", "-q", str(remote), str(publisher)], check=True)
        self.configure_identity(publisher)
        target = publisher / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.run_git("add", relative_path, cwd=publisher)
        self.run_git("commit", "-q", "-m", "test: publish", cwd=publisher)
        self.run_git("push", "-q", "origin", "main", cwd=publisher)
        return self.run_git("rev-parse", "HEAD", cwd=publisher).stdout.strip()

    def run_sync(self, consumer: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "scripts/sync-shared-skills.sh"],
            cwd=consumer,
            text=True,
            capture_output=True,
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

    def test_rejects_fetched_tree_when_candidate_ci_fails(self) -> None:
        temporary, remote, consumer = self.make_fixture()
        with temporary:
            original = self.run_git("rev-parse", "HEAD", cwd=consumer).stdout.strip()
            self.publish(remote, "scripts/validate.sh", "#!/usr/bin/env bash\nexit 1\n")
            result = self.run_sync(consumer)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.run_git("rev-parse", "HEAD", cwd=consumer).stdout.strip(), original)

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


if __name__ == "__main__":
    unittest.main()
