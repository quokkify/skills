from __future__ import annotations

import os
import re
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "skills" / "devops" / "vps-reverse-proxy-operations" / "references" / "caddy-vps-reverse-proxy-runbook.md"


class CaddyRunbookSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = RUNBOOK.read_text(encoding="utf-8")
        self.blocks = re.findall(r"```bash\n(.*?)```", self.text, re.DOTALL)

    def test_backup_block_is_restrictive_and_fails_closed(self) -> None:
        block = next(item for item in self.blocks if "backup_tree()" in item)

        self.assertIn("set -Eeuo pipefail", block)
        self.assertIn("umask 077", block)
        self.assertIn("install -d -m 0700", block)
        self.assertNotRegex(block, r"tar[^\n]*\|\|\s*true")
        self.assertIn("[[ ! -d", block)

    def test_restart_policy_round_trip_preserves_on_failure_retry_count(self) -> None:
        block = next(item for item in self.blocks if "ORIGINAL_RESTART_POLICY=" in item)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_docker = root / "docker"
            fake_docker.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import sys

                    args = sys.argv[1:]
                    joined = " ".join(args)
                    if "RestartPolicy.Name" in joined:
                        print("on-failure")
                    elif "MaximumRetryCount" in joined:
                        print("5")
                    elif args and args[0] == "inspect":
                        print("name=/fixture image=fixture restart=on-failure ports={}")
                    else:
                        raise SystemExit(2)
                    """
                ),
                encoding="utf-8",
            )
            fake_docker.chmod(0o700)
            env = os.environ | {
                "PATH": f"{root}:{os.environ['PATH']}",
                "B": str(root),
                "CONFLICTING_CONTAINER": "fixture-container",
            }
            result = subprocess.run(
                ["bash", "-Eeuo", "pipefail", "-c", block],
                env=env,
                text=True,
                capture_output=True,
                timeout=20,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            rollback = (root / "conflicting-container-rollback.txt").read_text(encoding="utf-8")
            self.assertEqual(rollback, "fixture-container\non-failure:5\n")

    def test_rollback_without_container_conflict_does_not_call_docker(self) -> None:
        block = next(item for item in self.blocks if "ROLLBACK_METADATA=" in item)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_sudo = root / "sudo"
            fake_sudo.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
            fake_sudo.chmod(0o700)
            env = os.environ | {
                "PATH": f"{root}:{os.environ['PATH']}",
                "B": str(root),
            }

            result = subprocess.run(
                ["bash", "-Eeuo", "pipefail", "-c", block],
                env=env,
                text=True,
                capture_output=True,
                timeout=20,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((root / "conflicting-container-rollback.txt").exists())

    def test_rollback_does_not_start_container_when_policy_restore_fails(self) -> None:
        block = next(item for item in self.blocks if "ROLLBACK_METADATA=" in item)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "conflicting-container-rollback.txt").write_text(
                "fixture-container\non-failure:5\n", encoding="utf-8"
            )
            fake_sudo = root / "sudo"
            fake_sudo.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
            fake_sudo.chmod(0o700)
            fake_docker = root / "docker"
            fake_docker.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env sh
                    printf '%s\\n' "$*" >> "$FAKE_DOCKER_LOG"
                    [ "$1" != update ]
                    """
                ),
                encoding="utf-8",
            )
            fake_docker.chmod(0o700)
            log_file = root / "docker.log"
            env = os.environ | {
                "PATH": f"{root}:{os.environ['PATH']}",
                "B": str(root),
                "FAKE_DOCKER_LOG": str(log_file),
            }

            result = subprocess.run(
                ["bash", "-c", block],
                env=env,
                text=True,
                capture_output=True,
                timeout=20,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            calls = log_file.read_text(encoding="utf-8").splitlines()
            self.assertEqual(calls, ["update --restart=on-failure:5 fixture-container"])


if __name__ == "__main__":
    unittest.main()
