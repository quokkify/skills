from __future__ import annotations

import fcntl
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "devops" / "linux-storage-maintenance" / "templates" / "docker-image-retention-cleanup.sh"
IMAGE_ID = "sha256:" + "a" * 64


class DockerImageRetentionCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.state_dir = self.root / "state"
        self.state_dir.mkdir()
        self.state_file = self.state_dir / "unused-images.tsv"
        self.log_file = self.root / "docker.log"
        self.fake_docker = self.root / "docker"
        self.fake_docker.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import os
                import sys

                args = sys.argv[1:]
                image = os.environ["FAKE_IMAGE_ID"]
                log = os.environ["FAKE_DOCKER_LOG"]
                if " ".join(args) == os.environ.get("FAKE_FAIL_COMMAND"):
                    raise SystemExit(42)
                if args == ["info"]:
                    raise SystemExit(0)
                if args == ["ps", "-aq"]:
                    raise SystemExit(0)
                if args == ["image", "ls", "-aq", "--no-trunc"]:
                    print(image)
                    raise SystemExit(0)
                if args == ["image", "rm", image]:
                    with open(log, "a", encoding="utf-8") as handle:
                        handle.write(image + "\\n")
                    raise SystemExit(0)
                print(f"unexpected fake docker arguments: {args!r}", file=sys.stderr)
                raise SystemExit(2)
                """
            ),
            encoding="utf-8",
        )
        self.fake_docker.chmod(0o755)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ | {
            "DOCKER_BIN": str(self.fake_docker),
            "STATE_DIR": str(self.state_dir),
            "STATE_FILE": str(self.state_file),
            "LOCK_FILE": str(self.state_dir / "lock"),
            "TMPDIR": str(self.root),
            "FAKE_IMAGE_ID": IMAGE_ID,
            "FAKE_DOCKER_LOG": str(self.log_file),
            "FAKE_FAIL_COMMAND": getattr(self, "fail_command", ""),
        }
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )

    def test_dry_run_reports_deletion_without_mutating_state(self) -> None:
        original = f"{IMAGE_ID}\t1\n"
        self.state_file.write_text(original, encoding="utf-8")

        result = self._run("--days", "1", "--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY-RUN: would delete", result.stdout)
        self.assertEqual(self.state_file.read_text(encoding="utf-8"), original)
        self.assertFalse(self.log_file.exists())
        self.assertTrue((self.state_dir / "lock").exists())
        self.assertEqual(list(self.root.glob("docker-image-retention-cleanup.*")), [])

    def test_real_run_deletes_eligible_image_and_commits_empty_state(self) -> None:
        self.state_file.write_text(f"{IMAGE_ID}\t1\n", encoding="utf-8")

        result = self._run("--days", "1")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Deleted", result.stdout)
        self.assertEqual(self.log_file.read_text(encoding="utf-8"), IMAGE_ID + "\n")
        self.assertEqual(self.state_file.read_text(encoding="utf-8"), "")

    def test_image_enumeration_failure_preserves_state_and_fails_closed(self) -> None:
        original = f"{IMAGE_ID}\t1\n"
        self.state_file.write_text(original, encoding="utf-8")
        self.fail_command = "image ls -aq --no-trunc"

        result = self._run("--days", "1")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("could not enumerate Docker images", result.stderr)
        self.assertEqual(self.state_file.read_text(encoding="utf-8"), original)
        self.assertFalse(self.log_file.exists())

    def test_dry_run_uses_same_lock_as_real_run(self) -> None:
        original = f"{IMAGE_ID}\t1\n"
        self.state_file.write_text(original, encoding="utf-8")
        lock_path = self.state_dir / "lock"
        with lock_path.open("w", encoding="utf-8") as lock_handle:
            fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self._run("--days", "1", "--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Another cleanup run is already active", result.stdout)
        self.assertNotIn("would delete", result.stdout)
        self.assertEqual(self.state_file.read_text(encoding="utf-8"), original)

    def test_malformed_state_fails_closed(self) -> None:
        original = "not-a-valid-state-line\n"
        self.state_file.write_text(original, encoding="utf-8")

        result = self._run("--days", "1")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("malformed retention state", result.stderr)
        self.assertEqual(self.state_file.read_text(encoding="utf-8"), original)

    def test_out_of_range_timestamps_fail_closed_before_arithmetic(self) -> None:
        for timestamp in ("9999999999999999999", "01721563200", "9999999999"):
            with self.subTest(timestamp=timestamp):
                original = f"{IMAGE_ID}\t{timestamp}\n"
                self.state_file.write_text(original, encoding="utf-8")
                self.log_file.unlink(missing_ok=True)

                result = self._run("--days", "1")

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("malformed retention state", result.stderr)
                self.assertEqual(self.state_file.read_text(encoding="utf-8"), original)
                self.assertFalse(self.log_file.exists())

    def test_deletion_failure_is_reported_and_retained_for_retry(self) -> None:
        original = f"{IMAGE_ID}\t1\n"
        self.state_file.write_text(original, encoding="utf-8")
        self.fail_command = f"image rm {IMAGE_ID}"

        result = self._run("--days", "1")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("keeping it tracked for retry", result.stderr)
        self.assertEqual(self.state_file.read_text(encoding="utf-8"), original)

    def test_excessive_retention_days_are_rejected_before_arithmetic(self) -> None:
        original = f"{IMAGE_ID}\t1\n"
        self.state_file.write_text(original, encoding="utf-8")

        result = self._run("--days", "18446744073709551617", "--dry-run")

        self.assertEqual(result.returncode, 2)
        self.assertIn("must not exceed", result.stderr)
        self.assertNotIn("would delete", result.stdout)
        self.assertEqual(self.state_file.read_text(encoding="utf-8"), original)
        self.assertFalse(self.log_file.exists())


if __name__ == "__main__":
    unittest.main()
