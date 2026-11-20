import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
RACE = SKILL / "scripts" / "race"
sys.path.insert(0, str(SKILL / "scripts"))

from analyze import analyze  # noqa: E402


def rec(seq, variant, test, start, dur):
    return {
        "seq": seq, "variant": variant, "environment": "e1", "sha": "abc",
        "test_id": test, "name": test, "status": "passed", "retried": False,
        "start_ms": start, "stop_ms": start + dur, "duration_ms": dur,
        "failure": None, "external_id": None,
        "steps": [{"name": "setup", "start_ms": start, "stop_ms": start + dur // 2, "status": "passed"},
                  {"name": "act", "start_ms": start + dur // 2, "stop_ms": start + dur, "status": "passed"}],
    }


def build_runs():
    runs = []
    for seq in range(3):
        base = 1_000_000 * (seq + 1)
        for v, dur in (("base", 1000), ("cand", 600 + seq * 50)):
            runs.append(rec(seq * 2 + (v == "cand"), v, "t1", base, dur))
            runs.append(rec(seq * 2 + (v == "cand"), v, "t2", base + dur, dur))
    return runs


def prerequisites_missing():
    for tool in ("node", "ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            return f"{tool} not found"
    if not (RACE / "node_modules" / "playwright").is_dir():
        return "scripts/race/node_modules/playwright missing (run npm install there)"
    return None


class RaceSmokeTest(unittest.TestCase):
    def test_race_smoke(self):
        missing = prerequisites_missing()
        if missing:
            self.skipTest(missing)
        check = subprocess.run(["node", str(RACE / "race.mjs"), "--check"], capture_output=True, text=True)
        if check.returncode != 0:
            self.skipTest("browser cannot launch: " + check.stderr.strip())
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            runs = build_runs()
            (d / "runs.jsonl").write_text("\n".join(json.dumps(r) for r in runs) + "\n")
            (d / "report.json").write_text(json.dumps(analyze(runs, "base", "quick", iterations=50)))
            out = d / "race.mp4"
            p = subprocess.run(
                ["node", str(RACE / "race.mjs"), "--runs", str(d / "runs.jsonl"),
                 "--report", str(d / "report.json"), "--out", str(out), "--speed", "1000"],
                capture_output=True, text=True, timeout=240)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertTrue(out.is_file())
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(out)],
                capture_output=True, text=True)
            self.assertGreater(float(probe.stdout.strip()), 0)

    def test_lib_node_tests(self):
        if shutil.which("node") is None:
            self.skipTest("node not found")
        p = subprocess.run(["node", "--test", str(SKILL / "tests" / "race_lib.test.mjs")],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_lib_verdict_words_match_strings(self):
        if shutil.which("node") is None:
            self.skipTest("node not found")
        from strings import STRINGS
        script = ("import('" + (RACE / "lib.mjs").as_uri() + "').then((m) => console.log(JSON.stringify("
                  "{en: m.LABELS.en.verdicts, ru: m.LABELS.ru.verdicts, "
                  "q: [m.LABELS.en.quickPrefix, m.LABELS.ru.quickPrefix]})))")
        p = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        got = json.loads(p.stdout)
        for lang in ("en", "ru"):
            self.assertEqual(got[lang], STRINGS[lang]["verdicts"])
        self.assertEqual(got["q"], [STRINGS["en"]["verdict_quick_prefix"], STRINGS["ru"]["verdict_quick_prefix"]])

    def test_usage_error(self):
        if shutil.which("node") is None:
            self.skipTest("node not found")
        p = subprocess.run(["node", str(RACE / "race.mjs")], capture_output=True, text=True)
        self.assertEqual(p.returncode, 64)


if __name__ == "__main__":
    unittest.main()
