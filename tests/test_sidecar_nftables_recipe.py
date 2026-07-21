from __future__ import annotations

import os
import re
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "skills" / "devops" / "vps-reverse-proxy-operations" / "references" / "restrict-sidecar-api-ports.md"


class SidecarNftablesRecipeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        text = REFERENCE.read_text(encoding="utf-8")
        self.reference_text = text
        blocks = re.findall(r"```bash\n(.*?)```", text, re.DOTALL)
        script = next(block for block in blocks if "TABLE_NAME" in block and "#!/usr/bin/env bash" in block)
        self.script = self.root / "recipe.sh"
        self.script.write_text(script, encoding="utf-8")
        self.script.chmod(0o700)
        self.log_file = self.root / "nft.log"
        fake_nft = self.root / "nft"
        fake_nft.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import os
                import pathlib
                import sys

                args = sys.argv[1:]
                log = pathlib.Path(os.environ["FAKE_NFT_LOG"])
                if args[:2] == ["list", "table"]:
                    raise SystemExit(0 if os.environ.get("FAKE_TABLE_EXISTS") == "1" else 1)
                if args[:1] == ["-f"] and len(args) == 2:
                    log.write_text(pathlib.Path(args[1]).read_text(encoding="utf-8"), encoding="utf-8")
                    raise SystemExit(0)
                print(f"unexpected nft arguments: {args!r}", file=sys.stderr)
                raise SystemExit(2)
                """
            ),
            encoding="utf-8",
        )
        fake_nft.chmod(0o700)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _run(self, **overrides: str) -> subprocess.CompletedProcess[str]:
        env = os.environ | {
            "PATH": f"{self.root}:{os.environ['PATH']}",
            "FAKE_NFT_LOG": str(self.log_file),
            "TABLE_NAME": "restrict_example_api",
            "SUBNET": "172.18.0.0/16",
            "PORT": "12345",
        }
        env.update(overrides)
        return subprocess.run(
            ["bash", str(self.script)],
            env=env,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )

    def test_recipe_applies_expected_atomic_ruleset(self) -> None:
        result = self._run()

        self.assertEqual(result.returncode, 0, result.stderr)
        rules = self.log_file.read_text(encoding="utf-8")
        self.assertIn("add table inet restrict_example_api", rules)
        self.assertIn("ip saddr 172.18.0.0/16 accept", rules)
        self.assertIn("tcp dport 12345 drop", rules)

    def test_recipe_atomically_recreates_existing_dedicated_table(self) -> None:
        result = self._run(FAKE_TABLE_EXISTS="1")

        self.assertEqual(result.returncode, 0, result.stderr)
        rules = self.log_file.read_text(encoding="utf-8")
        self.assertIn("delete table inet restrict_example_api", rules)
        self.assertIn("add table inet restrict_example_api", rules)
        self.assertLess(
            rules.index("delete table inet restrict_example_api"),
            rules.index("add table inet restrict_example_api"),
        )
        self.assertNotIn("flush table", rules)

    def test_recipe_rejects_unsafe_table_name_before_calling_nft(self) -> None:
        result = self._run(TABLE_NAME="shared; delete table inet filter")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid TABLE_NAME", result.stderr)
        self.assertFalse(self.log_file.exists())

    def test_backup_recipe_is_private_and_does_not_require_docker_group(self) -> None:
        backup_block = next(
            block
            for block in re.findall(r"```bash\n(.*?)```", self.reference_text, re.DOTALL)
            if "BACKUP_ROOT" in block
        )

        self.assertIn("umask 077", backup_block)
        self.assertIn('install -d -m 0700 "$BACKUP_DIR"', backup_block)
        self.assertIn("sudo cat /etc/nftables.conf", backup_block)
        self.assertNotIn("sg docker", backup_block)
        self.assertIn('"${DOCKER[@]}" network inspect', backup_block)


if __name__ == "__main__":
    unittest.main()
