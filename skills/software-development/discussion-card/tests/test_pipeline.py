"""End-to-end pipeline tests: discuss.sh plan -> build -> check -> atomic move. Needs Chrome for the static path."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
LAUNCHER = SKILL / "scripts" / "discuss.sh"
BUILD = SKILL / "scripts" / "build.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
PASS_RE = re.compile(r"^PASS words=\d+ extra=\d+ spots=\d+ diagrams=(\d+|runtime) offline=ok( ids=(kept|-\d+))?$", re.M)
MERMAID_MARKER = "__esbuild_esm_mermaid_nm"
EXIT_FAIL, EXIT_BAD_ARGS = 1, 2


def run(*args: str, env: dict[str, str] | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    merged = dict(os.environ)
    merged.update(env or {})
    return subprocess.run(
        ["sh", str(LAUNCHER), *args], capture_output=True, text=True, env=merged, cwd=cwd, check=False, timeout=300
    )


class PipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.md = self.tmp / "sample.md"
        self.plan = self.tmp / "sample.card.yaml"
        shutil.copyfile(FIXTURES / "sample.md", self.md)
        shutil.copyfile(FIXTURES / "sample.card.yaml", self.plan)
        self.out = self.tmp / "out" / "card.html"
        self.out.parent.mkdir()

    def build(self, *extra: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return run(str(self.md), "--plan", str(self.plan), "-o", str(self.out), *extra, env=env)

    def leftovers(self) -> list[str]:
        return sorted(p.name for p in self.out.parent.iterdir() if p.name != self.out.name)

    def test_sample_passes(self) -> None:
        r = self.build()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, PASS_RE)
        self.assertTrue(self.out.is_file())
        self.assertEqual(self.leftovers(), [], "temp page or meta left behind")

    def test_default_output_next_to_source(self) -> None:
        r = run(str(self.md), "--plan", str(self.plan))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.tmp / "sample.card.html").is_file())

    def test_fail_writes_nothing(self) -> None:
        r = self.build(env={"DISCUSS_FORCE_FAIL": "1"})
        self.assertEqual(r.returncode, EXIT_FAIL, r.stderr)
        self.assertIn("FAIL", r.stdout)
        self.assertFalse(self.out.exists())
        self.assertEqual(self.leftovers(), [])

    def test_fail_keeps_existing_output(self) -> None:
        self.assertEqual(self.build().returncode, 0)
        before = self.out.read_bytes()
        r = self.build(env={"DISCUSS_FORCE_FAIL": "1"})
        self.assertEqual(r.returncode, EXIT_FAIL, r.stderr)
        self.assertEqual(self.out.read_bytes(), before)
        self.assertEqual(self.leftovers(), [])

    def test_rebuild_backs_up_previous(self) -> None:
        self.assertEqual(self.build().returncode, 0)
        first = self.out.read_bytes()
        r = self.build()
        self.assertEqual(r.returncode, 0, r.stderr)
        backup = self.out.parent / "card.backup.html"
        self.assertEqual(backup.read_bytes(), first)
        self.assertIn("ids=kept", r.stdout, "--previous should default to the existing output")

    def test_regression_guard_previous_defaults_with_previous_state(self) -> None:
        # --previous-state used to switch off the --previous default, hiding dropped unmarked ids
        self.assertEqual(self.build().returncode, 0)
        text = self.md.read_text(encoding="utf-8")
        self.md.write_text(text.replace("even for one-line changes.", "even for tiny changes."), encoding="utf-8")
        state = self.tmp / "state.json"
        state.write_text("{}", encoding="utf-8")
        r = self.build("--previous-state", str(state))
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("ids=-1", r.stdout)
        self.assertIn("warning: dropped id: problem-p-", r.stderr + r.stdout)

    def test_plan_error_exit_2(self) -> None:
        self.plan.write_text("version: 1\nbogus_key: 1\n", encoding="utf-8")
        r = self.build()
        self.assertEqual(r.returncode, EXIT_BAD_ARGS, r.stderr)
        self.assertFalse(self.out.exists())
        self.assertEqual(self.leftovers(), [])

    def test_runtime_fallback_inlines_mermaid(self) -> None:
        r = self.build(env={"DISCUSS_NO_CHROME": "1", "CHROME_BIN": "/nonexistent"})
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertRegex(r.stdout, PASS_RE)
        self.assertIn("diagrams=runtime", r.stdout)
        page = self.out.read_text(encoding="utf-8")
        self.assertIn(MERMAID_MARKER, page)
        self.assertEqual(page.count('<script id="mermaid-lib">'), 1)
        self.assertIn('class="mermaid-runtime"', page)
        self.assertIn('"runtimeDiagrams": true', page)

    def test_runtime_meta_spots_match_static(self) -> None:
        """Marks on diagram nodes survive a static -> runtime rebuild: both list the same spot ids."""
        python = run("--python").stdout.strip()
        mermaid = run("--mermaid").stdout.strip()
        self.assertTrue(python and mermaid)

        def meta(name: str, env: dict[str, str]) -> dict:
            out = self.tmp / "out" / f"{name}.html"
            merged = dict(os.environ)
            merged.update(env)
            r = subprocess.run(
                [python, "-I", str(BUILD), str(self.md), "--plan", str(self.plan), "-o", str(out), "--mermaid", mermaid],
                capture_output=True, text=True, env=merged, check=False, timeout=300,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            return json.loads(Path(str(out) + ".meta.json").read_text(encoding="utf-8")), out.read_text(encoding="utf-8")

        static, _ = meta("static", {})
        runtime, page = meta("runtime", {"DISCUSS_NO_CHROME": "1"})
        self.assertTrue(all(d["mode"] == "static" for d in static["diagrams"]))
        self.assertTrue(all(d["mode"] == "runtime" for d in runtime["diagrams"]))
        self.assertEqual(runtime["spots"], static["spots"])
        self.assertIn('data-node-spots="', page)


if __name__ == "__main__":
    unittest.main()
