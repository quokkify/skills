from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class AdapterInstallerTests(unittest.TestCase):
    def test_claude_installer_uses_adapter_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            environment = os.environ.copy()
            environment["HOME"] = str(home)

            subprocess.run(
                ["bash", "scripts/install-claude-config.sh"],
                cwd=REPOSITORY_ROOT,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )

            installed = home / ".claude"
            self.assertEqual(
                (installed / "CLAUDE.md").read_bytes(),
                (REPOSITORY_ROOT / "adapters" / "claude" / "CLAUDE.md").read_bytes(),
            )
            self.assertTrue((installed / "agents" / "code-researcher.md").is_file())
            self.assertTrue(os.access(installed / "statusline-command.sh", os.X_OK))

    def test_codex_installer_uses_adapter_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            subprocess.run(
                ["bash", "scripts/install-codex-agents.sh", str(target)],
                cwd=REPOSITORY_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertEqual(
                (target / "AGENTS.md").read_bytes(),
                (REPOSITORY_ROOT / "adapters" / "codex" / "AGENTS.md").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
