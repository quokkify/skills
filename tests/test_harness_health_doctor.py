import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "skills/skill-management/harness-health-doctor/scripts/harness_doctor.sh"


class HarnessDoctorTests(unittest.TestCase):
    def run_doctor(self, home: Path, *, extra_env=None):
        env = {"HOME": str(home), "PATH": os.environ.get("PATH", "")}
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            ["bash", str(SCRIPT), "--offline"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_hermes_external_dirs_only_is_not_a_harness_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "Hermes User"
            home.mkdir(parents=True)
            hermes = home / ".hermes"
            hermes.mkdir()
            (hermes / "config.yaml").write_text(
                "skills:\n  external_dirs:\n    - /workspace/skills\n",
                encoding="utf-8",
            )

            result = self.run_doctor(home)

            self.assertNotIn("Harness directory missing", result.stdout)
            self.assertNotIn("Hermes: nothing wires the completion gate", result.stdout)
            self.assertIn("skills.external_dirs provides skill discovery", result.stdout)

    def test_claude_settings_path_with_spaces_is_probed_as_one_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "Claude User"
            home.mkdir(parents=True)
            claude = home / "Claude Settings"
            claude.mkdir()
            (claude / "settings.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "Stop": [{"hooks": [{"command": "completion_gate.sh"}]}],
                            "SessionStart": [
                                {"hooks": [{"command": "skill_cycle.sh"}]}
                            ],
                        }
                    }
                ),
                encoding="utf-8",
            )

            result = self.run_doctor(
                home,
                extra_env={"CLAUDE_CONFIG_DIR": str(claude)},
            )

            self.assertNotIn("is not valid JSON", result.stdout)
            self.assertIn("Claude Code: Stop hook registered", result.stdout)
            self.assertIn("Claude Code: SessionStart hook registered", result.stdout)

    def test_documentation_does_not_claim_hermes_blocks_completion(self):
        skill = SCRIPT.parents[1] / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        self.assertIn("```bash", text)
        self.assertIn("External skill discovery is read-only; it does not block turn completion.", text)
        self.assertNotIn("Whatever its configuration runs at end of turn", text)


if __name__ == "__main__":
    unittest.main()
