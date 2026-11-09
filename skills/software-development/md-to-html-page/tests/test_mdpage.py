"""End-to-end tests for scripts/mdpage.sh (the entry point)."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
SCRIPT = HERE.parent / "scripts" / "mdpage.sh"
SHOOT = HERE.parent / "scripts" / "shoot.sh"
# Stand-in browser: writes the --screenshot target unless its path contains $FAKE_FAIL.
FAKE_CHROME = """#!/bin/sh
for a in "$@"; do case $a in --screenshot=*) out=${a#--screenshot=} ;; esac; done
case $out in *"$FAKE_FAIL"*) exit 1 ;; esac
printf png > "$out"
"""


def run(args, env=None, cwd=None):
    e = dict(os.environ)
    e.pop("MDPAGE_FORCE_FAIL", None)
    e.update(env or {})
    return subprocess.run(["sh", str(SCRIPT), *args], capture_output=True, text=True,
                          env=e, cwd=cwd, timeout=300)


class MdpageTest(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.tmp = Path(self._td.name)

    def put(self, fixture="bug.md", name=None):
        dst = self.tmp / (name or fixture)
        shutil.copy(FIX / fixture, dst)
        return dst

    def test_happy_path(self):
        src = self.put()
        r = run([str(src)])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("PASS"), r.stdout)
        self.assertTrue((self.tmp / "bug.html").is_file())
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["bug.html", "bug.md"])
        self.assertIn("genre: bug (detected)", r.stderr)

    def test_output_flag(self):
        src = self.put()
        out = self.tmp / "x" / "out.html"
        out.parent.mkdir()
        r = run([str(src), "-o", str(out)])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(out.is_file())
        self.assertFalse((self.tmp / "bug.html").exists())

    def test_refuses_non_md(self):
        src = self.tmp / "notes.txt"
        src.write_text("# hi\n")
        r = run([str(src)])
        self.assertEqual(r.returncode, 2)
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["notes.txt"])

    def test_refuses_output_equal_input(self):
        src = self.put()
        before = src.read_bytes()
        r = run([str(src), "-o", str(src)])
        self.assertEqual(r.returncode, 2)
        self.assertEqual(src.read_bytes(), before)

    def test_refuses_output_directory(self):
        src = self.put()
        d = self.tmp / "outdir"
        d.mkdir()
        r = run([str(src), "-o", str(d)])
        self.assertEqual(r.returncode, 2)
        self.assertEqual(list(d.iterdir()), [])

    def test_leading_dash_path_no_dirname_error(self):
        src = self.put()
        r = run(["-o", "-x/out.html", str(src)], cwd=self.tmp)
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("dirname", r.stderr)
        self.assertNotIn("illegal option", r.stderr)

    def test_venv_dir_not_a_venv_is_not_deleted(self):
        src = self.put()
        d = self.tmp / "notvenv"
        d.mkdir()
        (d / "marker.txt").write_text("keep")
        r = run([str(src)], env={"MDPAGE_VENV": str(d)})
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertEqual((d / "marker.txt").read_text(), "keep")

    def test_foreign_venv_is_not_deleted(self):
        """Regression guard: MDPAGE_VENV pointing at the user's own venv deleted and rebuilt it."""
        src = self.put()
        d = self.tmp / "project-venv"
        subprocess.run([sys.executable, "-I", "-m", "venv", "--without-pip", str(d)], check=True)
        (d / "keep.txt").write_text("keep")
        before = sorted(p.relative_to(d) for p in d.rglob("*"))
        r = run([str(src)], env={"MDPAGE_VENV": str(d)})
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn(str(d), r.stderr)
        self.assertEqual(sorted(p.relative_to(d) for p in d.rglob("*")), before)
        self.assertEqual((d / "keep.txt").read_text(), "keep")
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["bug.md", "project-venv"])

    def test_marked_venv_may_be_rebuilt(self):
        """Regression guard: a broken venv carrying mdpage's marker is still rebuilt, not refused."""
        src = self.put()
        d = self.tmp / "own-venv"
        d.mkdir()
        (d / ".md-to-html-page").write_text("")
        r = run([str(src)], env={"MDPAGE_VENV": str(d), "PIP_INDEX_URL": "http://127.0.0.1:9/",
                                 "PIP_RETRIES": "0", "PIP_TIMEOUT": "2"})
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn("venv setup failed", r.stderr)
        self.assertNotIn("refusing", r.stderr)

    def test_missing_input(self):
        r = run([str(self.tmp / "nope.md")])
        self.assertEqual(r.returncode, 2)
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_check_failure_leaves_no_file(self):
        src = self.put()
        r = run([str(src)], env={"MDPAGE_FORCE_FAIL": "1"})
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stdout.startswith("FAIL"), r.stdout)
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["bug.md"])

    def test_render_exception_exit_1(self):
        src = self.tmp / "bad.md"
        src.write_bytes(b"\xff\xfe# x")
        r = run([str(src)])
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("error: UnicodeDecodeError", r.stderr)
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["bad.md"])

    def test_venv_failure_exit_3(self):
        src = self.put()
        venv = self.tmp / "v"
        r = run([str(src)], env={"MDPAGE_VENV": str(venv),
                                 "PIP_INDEX_URL": "http://127.0.0.1:9/",
                                 "PIP_RETRIES": "0", "PIP_TIMEOUT": "2"})
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertFalse(venv.exists())
        self.assertEqual([p.name for p in self.tmp.iterdir() if p.name.startswith("v")], [])

    def test_path_with_spaces_and_cyrillic(self):
        src = self.put("bug.md", "Заметка про баг.md")
        r = run([str(src)])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.tmp / "Заметка про баг.html").is_file())

    def test_byte_identical_reruns(self):
        src = self.put()
        out = self.tmp / "bug.html"
        self.assertEqual(run([str(src)]).returncode, 0)
        first = out.read_bytes()
        out.unlink()
        self.assertEqual(run([str(src)]).returncode, 0)
        self.assertEqual(first, out.read_bytes())

    def test_python_flag(self):
        r = run(["--python"])
        self.assertEqual(r.returncode, 0, r.stderr)
        p = r.stdout.strip()
        self.assertTrue(os.path.isabs(p))
        self.assertTrue(os.access(p, os.X_OK))


class ShootTest(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.tmp = Path(self._td.name)
        self.page = self.tmp / "page.html"
        self.page.write_text("<!doctype html><p>x</p>\n")
        self.chrome = self.tmp / "fake-chrome"
        self.chrome.write_text(FAKE_CHROME)
        self.chrome.chmod(0o755)
        self.out = self.tmp / "shots"

    def shoot(self, fail):
        env = dict(os.environ, CHROME_BIN=str(self.chrome), FAKE_FAIL=fail)
        return subprocess.run(["sh", str(SHOOT), str(self.page), str(self.out)],
                              capture_output=True, text=True, env=env, timeout=60)

    def test_all_shots_written(self):
        r = self.shoot("no-such-name")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["dark.png", "desktop.png", "phone.png"])

    def test_stale_png_not_accepted(self):
        """Regression guard: a PNG left by an earlier run satisfied the size check after a failed shot."""
        self.out.mkdir()
        (self.out / "desktop.png").write_text("stale")
        r = self.shoot("desktop.png")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("desktop.png", r.stderr)
        self.assertFalse((self.out / "desktop.png").exists())

    def test_phone_wrapper_removed_on_failure(self):
        """Regression guard: a failed phone shot left .phone-wrapper.html behind."""
        r = self.shoot("phone.png")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["dark.png", "desktop.png"])

    def test_no_browser_exit_2(self):
        env = dict(os.environ, CHROME_BIN=str(self.tmp / "missing"))
        r = subprocess.run(["sh", str(SHOOT), str(self.page), str(self.out)],
                           capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 2)
        self.assertIn("no Chrome/Chromium found", r.stderr)


if __name__ == "__main__":
    unittest.main()
