import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "skills/repository/renovate-adoption-review/scripts/renovate_adoption.sh"
FIXTURES = Path(__file__).parent / "fixtures/renovate_adoption"

GH_STUB = """#!/bin/sh
printf '%s\\n' "$*" >> "$GH_STUB_LOG"
if [ "$GH_STUB_FAIL" = "1" ]; then
  echo "stub: simulated gh failure" >&2
  exit 1
fi
case "$1 $2" in
  "pr view") cat "$GH_STUB_DIR/pr_view.json" ;;
  "pr list")
    case "$*" in
      *"--state merged"*) cat "$GH_STUB_DIR/pr_list_merged.json" ;;
      *) cat "$GH_STUB_DIR/pr_list_open.json" ;;
    esac ;;
  "api "*|"api") cat "$GH_STUB_DIR/api_tree.json" ;;
  *) echo "stub: unsupported: $*" >&2; exit 1 ;;
esac
"""


def make_stub(tmp: Path, fixtures: dict, fail: bool = False) -> dict:
    """Create an executable gh stub; fixtures maps stub file name -> fixture file name."""
    bin_dir = tmp / "bin"
    stub_dir = tmp / "stub"
    bin_dir.mkdir()
    stub_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(GH_STUB, encoding="utf-8")
    gh.chmod(0o755)
    for name, source in fixtures.items():
        shutil.copy(FIXTURES / source, stub_dir / name)
    log = tmp / "gh.log"
    log.write_text("", encoding="utf-8")
    return {
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        "GH_STUB_DIR": str(stub_dir),
        "GH_STUB_LOG": str(log),
        "GH_STUB_FAIL": "1" if fail else "0",
        "HOME": str(tmp),
    }


class RenovateAdoptionInspectTests(unittest.TestCase):
    def run_script(self, tmp, args, fixture="pr_view_minor.json", fail=False):
        env = make_stub(tmp, {"pr_view.json": fixture}, fail=fail)
        cwd = tmp / "repo"
        cwd.mkdir(exist_ok=True)
        return subprocess.run(
            ["sh", str(SCRIPT), *args],
            env=env,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )

    def inspect(self, fixture, mode=None, allow=None):
        with tempfile.TemporaryDirectory() as temporary:
            tmp = Path(temporary)
            repo = tmp / "repo"
            repo.mkdir()
            if allow is not None:
                subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
                (repo / ".github").mkdir()
                (repo / ".github/renovate-adoption.json").write_text(
                    json.dumps({"allow": allow}), encoding="utf-8"
                )
            args = ["inspect", "1"]
            if mode:
                args += ["--mode", mode]
            result = self.run_script(tmp, args, fixture=fixture)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)

    def test_major_action_is_candidate(self):
        out = self.inspect("pr_view_major.json")
        self.assertEqual(out["verdict"], "candidate")
        self.assertEqual(out["updates"][0]["updateType"], "major")
        self.assertTrue(out["updates"][0]["sourceUrl"].startswith("https://github.com/"))
        self.assertTrue(
            all(
                u.startswith("https://github.com/")
                for u in out["updates"][0]["releaseNotesUrls"]
            )
        )
        self.assertTrue(out["updates"][0]["releaseNotesUrls"])

    def test_output_shape_matches_contract(self):
        out = self.inspect("pr_view_grouped.json")
        self.assertEqual(
            set(out), {"pr", "branch", "headSha", "updates", "verdict", "reason"}
        )
        for update in out["updates"]:
            self.assertEqual(
                set(update),
                {"package", "sourceUrl", "from", "to", "updateType", "releaseNotesUrls"},
            )

    def test_digest_is_skipped(self):
        out = self.inspect("pr_view_digest.json")
        self.assertEqual(out["verdict"], "skip")
        self.assertIn("digest", out["reason"])

    def test_minor_open_mode_skipped_retro_mode_candidate(self):
        opened = self.inspect("pr_view_minor.json", mode="open")
        self.assertEqual(opened["verdict"], "skip")
        self.assertIn("minor", opened["reason"])
        retro = self.inspect("pr_view_minor.json", mode="retro")
        self.assertEqual(retro["verdict"], "candidate")

    def test_allowlisted_minor_is_candidate(self):
        out = self.inspect(
            "pr_view_minor.json",
            allow=["com.diffplug.spotless:spotless-plugin-gradle"],
        )
        self.assertEqual(out["verdict"], "candidate")
        self.assertIn("allowlisted", out["reason"])

    def test_grouped_pr_any_major_makes_candidate(self):
        out = self.inspect("pr_view_grouped.json", mode="open")
        self.assertEqual(len(out["updates"]), 3)
        self.assertEqual(out["verdict"], "candidate")
        types = [u["updateType"] for u in out["updates"]]
        self.assertEqual(types, ["minor", "major", "digest"])

    def test_docker_suffix_classified_by_numeric_prefix(self):
        out = self.inspect("pr_view_docker.json")
        self.assertEqual(out["updates"][0]["updateType"], "major")
        self.assertEqual(out["verdict"], "candidate")

    def test_zero_major_minor_bump_is_major(self):
        out = self.inspect("pr_view_zero_minor.json")
        self.assertEqual(out["updates"][0]["updateType"], "major")

    def test_body_without_table_is_skip_not_crash(self):
        out = self.inspect("pr_view_no_table.json")
        self.assertEqual(out["verdict"], "skip")
        self.assertEqual(out["reason"], "no updates table")
        self.assertEqual(out["updates"], [])

    def test_gh_failure_exits_3_with_stderr(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = self.run_script(Path(temporary), ["inspect", "1"], fail=True)
            self.assertEqual(result.returncode, 3)
            self.assertIn("gh failed", result.stderr)
            self.assertEqual(result.stdout, "")

    def test_missing_pr_argument_exits_2(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = self.run_script(Path(temporary), ["inspect"])
            self.assertEqual(result.returncode, 2)
            self.assertIn("usage", result.stderr.lower())

    def test_invalid_mode_exits_2(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = self.run_script(Path(temporary), ["inspect", "1", "--mode", "x"])
            self.assertEqual(result.returncode, 2)


class RenovateAdoptionBatchTests(unittest.TestCase):
    def run_batch(self, args, fixtures, fail=False, setup=None):
        with tempfile.TemporaryDirectory() as temporary:
            tmp = Path(temporary)
            env = make_stub(tmp, fixtures, fail=fail)
            repo = tmp / "repo"
            repo.mkdir()
            if setup:
                setup(repo)
            result = subprocess.run(
                ["sh", str(SCRIPT), *args],
                env=env,
                cwd=repo,
                capture_output=True,
                text=True,
                check=False,
            )
            result.gh_log = Path(env["GH_STUB_LOG"]).read_text(encoding="utf-8")
            return result

    def retro(self, args=("--last", "5")):
        result = self.run_batch(["retro", *args], {"pr_list_merged.json": "pr_list_merged.json"})
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout), result

    def test_sweep_lists_every_open_pr_with_verdict(self):
        result = self.run_batch(["sweep"], {"pr_list_open.json": "pr_list_open.json"})
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        expected = json.loads((FIXTURES / "pr_list_open.json").read_text(encoding="utf-8"))
        self.assertEqual(len(out), len(expected))
        self.assertEqual([i["pr"] for i in out], [p["number"] for p in expected])
        self.assertTrue(all(i["verdict"] in ("candidate", "skip") for i in out))
        self.assertEqual(out[0]["verdict"], "candidate")
        self.assertIn("--state open", result.gh_log)
        self.assertIn("--author app/renovate", result.gh_log)

    def test_retro_aggregates_repeated_bumps(self):
        out, _ = self.retro()
        item = next(i for i in out if i["package"] == "actions/setup-java")
        self.assertEqual((item["from"], item["to"], item["prs"]), ("v4.1.0", "v4.5.0", [12, 19]))
        self.assertEqual(item["updateType"], "minor")
        self.assertEqual(item["verdict"], "candidate")
        self.assertEqual(
            set(item),
            {"package", "sourceUrl", "from", "to", "updateType", "prs",
             "releaseNotesUrls", "verdict", "reason"},
        )
        self.assertEqual(len(item["releaseNotesUrls"]), 2)
        patch = next(i for i in out if i["package"] == "actions/cache")
        self.assertEqual(patch["verdict"], "skip")

    def test_retro_since_tag_resolves_to_commit_date(self):
        def setup(repo):
            env = {**os.environ, "GIT_COMMITTER_DATE": "2026-01-15T10:00:00+0000",
                   "GIT_AUTHOR_DATE": "2026-01-15T10:00:00+0000"}
            for cmd in (
                ["git", "init", "-q"],
                ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                 "commit", "-q", "--allow-empty", "-m", "init"],
                ["git", "tag", "v1.0.0"],
            ):
                subprocess.run(cmd, cwd=repo, env=env, check=True)

        result = self.run_batch(
            ["retro", "--since", "v1.0.0"],
            {"pr_list_merged.json": "pr_list_merged.json"},
            setup=setup,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.gh_log, r"merged:>=2026-01-15T10:00:00(Z|\+00:00)")
        self.assertIn("--state merged", result.gh_log)

    def test_retro_since_date_used_verbatim(self):
        result = self.run_batch(
            ["retro", "--since", "2026-02-01"],
            {"pr_list_merged.json": "pr_list_merged.json"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("merged:>=2026-02-01", result.gh_log)

    def test_retro_unknown_ref_exits_2(self):
        result = self.run_batch(
            ["retro", "--since", "no-such-ref"],
            {"pr_list_merged.json": "pr_list_merged.json"},
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown ref", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_retro_last_n_passes_limit(self):
        _, result = self.retro(("--last", "5"))
        self.assertIn("--limit 5", result.gh_log)

    def test_retro_requires_exactly_one_range_flag(self):
        fx = {"pr_list_merged.json": "pr_list_merged.json"}
        for args in ([], ["--since", "2026-01-01", "--last", "3"], ["--last", "x"]):
            result = self.run_batch(["retro", *args], fx)
            self.assertEqual(result.returncode, 2, args)
            self.assertIn("usage", result.stderr.lower())

    def test_batch_gh_failure_exits_3_with_empty_stdout(self):
        for args in (["sweep"], ["retro", "--last", "3"]):
            result = self.run_batch(args, {}, fail=True)
            self.assertEqual(result.returncode, 3, args)
            self.assertIn("gh failed", result.stderr)
            self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
