"""Launcher tests: argument handling and environment guards. Stdlib only."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

LAUNCHER = Path(__file__).resolve().parents[1] / "scripts" / "discuss.sh"
EXIT_BAD_ARGS = 2
EXIT_ENV = 3


def run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = dict(os.environ)
    merged.update(env or {})
    return subprocess.run(
        ["sh", str(LAUNCHER), *args], capture_output=True, text=True, env=merged, check=False, timeout=120
    )


class LauncherTest(unittest.TestCase):
    def test_no_args_exit_2(self) -> None:
        result = run()
        self.assertEqual(result.returncode, EXIT_BAD_ARGS)
        self.assertTrue(result.stderr.startswith("usage: discuss.sh"), result.stderr)

    def test_non_md_input_exit_2(self) -> None:
        result = run("x.txt", "--plan", "card.yaml")
        self.assertEqual(result.returncode, EXIT_BAD_ARGS, result.stderr)

    def test_mermaid_sha_mismatch_exit_3(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "mermaid.js"
            fake.write_text("garbage", encoding="utf-8")
            result = run("--mermaid", env={"DISCUSS_MERMAID": str(fake)})
        self.assertEqual(result.returncode, EXIT_ENV, result.stderr)
        self.assertIn("sha256 mismatch", result.stderr)

    def test_foreign_venv_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run("--python", env={"DISCUSS_VENV": tmp})
        self.assertEqual(result.returncode, EXIT_ENV, result.stderr)
        self.assertIn("not built by discuss", result.stderr)


if __name__ == "__main__":
    unittest.main()
