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

DEFAULT_REPO_URL = "https://github.com/quokkify/example"

GH_STUB = """#!/bin/sh
printf '%s\\n' "$*" >> "$GH_STUB_LOG"
if [ "$GH_STUB_FAIL" = "1" ]; then
  echo "stub: simulated gh failure" >&2
  exit 1
fi
case "$1 $2" in
  "pr view") cat "$GH_STUB_DIR/pr_view.json" ;;
  "repo view") cat "$GH_STUB_DIR/repo_url" ;;
  "pr list")
    case "$*" in
      *"--state merged"*) cat "$GH_STUB_DIR/pr_list_merged.json" ;;
      *) cat "$GH_STUB_DIR/pr_list_open.json" ;;
    esac ;;
  "api "*|"api")
    case "$*" in
      *contents/copier.yml*) cat "$GH_STUB_DIR/copier_yml" ;;
      *) cat "$GH_STUB_DIR/api_tree.json" ;;
    esac ;;
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
    (stub_dir / "repo_url").write_text(DEFAULT_REPO_URL + "\n", encoding="utf-8")
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
    def run_script(self, tmp, args, fixture="pr_view_minor.json", fail=False, repo_url=None):
        env = make_stub(tmp, {"pr_view.json": fixture}, fail=fail)
        if repo_url is not None:
            (Path(env["GH_STUB_DIR"]) / "repo_url").write_text(repo_url + "\n", encoding="utf-8")
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

    def inspect(self, fixture, mode=None, allow=None, repo_url=None):
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
            result = self.run_script(tmp, args, fixture=fixture, repo_url=repo_url)
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
        for update in out["updates"]:
            prefix = update["sourceUrl"].lower() + "/"
            self.assertTrue(update["releaseNotesUrls"], update["package"])
            for url in update["releaseNotesUrls"]:
                self.assertTrue(url.lower().startswith(prefix), (update["package"], url))

    def test_all_digit_versions_are_not_a_digest(self):
        out = self.inspect("pr_view_numeric_version.json")
        self.assertNotEqual(out["updates"][0]["updateType"], "digest")

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

    def test_regression_guard_self_dependency_is_skipped(self):
        """Regression guard: updates whose sourceUrl is the consumer repo are skipped."""
        for repo_url in (
            "https://github.com/quokkify/q4j",
            "https://github.com/Quokkify/Q4J.git/",
        ):
            for mode in ("open", "retro"):
                out = self.inspect("pr_view_self.json", mode=mode, repo_url=repo_url)
                self.assertEqual(out["verdict"], "skip", (repo_url, mode))
                self.assertEqual(out["reason"], "self dependency")
        out = self.inspect(
            "pr_view_self.json", allow=["quokkify/q4j"], repo_url="https://github.com/quokkify/q4j"
        )
        self.assertEqual(out["verdict"], "skip")
        foreign = self.inspect("pr_view_self.json", repo_url="https://github.com/quokkify/other")
        self.assertEqual(foreign["verdict"], "candidate")

    def test_regression_guard_repo_view_failure_exits_3(self):
        """Regression guard: a failing `gh repo view` is a gh failure (exit 3)."""
        with tempfile.TemporaryDirectory() as temporary:
            tmp = Path(temporary)
            env = make_stub(tmp, {"pr_view.json": "pr_view_minor.json"})
            (Path(env["GH_STUB_DIR"]) / "repo_url").unlink()
            (tmp / "repo").mkdir()
            result = subprocess.run(
                ["sh", str(SCRIPT), "inspect", "1"],
                env=env, cwd=tmp / "repo", capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 3)
            self.assertIn("gh failed", result.stderr)
            self.assertEqual(result.stdout, "")

    def test_regression_guard_pin_row_with_empty_from_parses_to(self):
        """Regression guard: a pin row ` → `sha`` keeps `to` instead of null."""
        out = self.inspect("pr_view_pin.json")
        update = out["updates"][0]
        self.assertIn(update["from"], ("", None))
        self.assertEqual(update["to"], "aa4efad")
        self.assertEqual(update["updateType"], "pin")

    def test_regression_guard_update_column_overrides_computed_type(self):
        """Regression guard: Renovate's Update column wins; unknown values fall back."""
        out = self.inspect("pr_view_update_column.json")
        self.assertEqual([u["updateType"] for u in out["updates"]], ["patch", "major"])


class RenovateAdoptionBatchTests(unittest.TestCase):
    def run_batch(self, args, fixtures, fail=False, setup=None, stub_files=None):
        with tempfile.TemporaryDirectory() as temporary:
            tmp = Path(temporary)
            env = make_stub(tmp, fixtures, fail=fail)
            for name, text in (stub_files or {}).items():
                (Path(env["GH_STUB_DIR"]) / name).write_text(text, encoding="utf-8")
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

    def test_regression_guard_same_short_name_different_sources_not_merged(self):
        """Regression guard: retro groups by (package, sourceUrl), not package alone."""
        result = self.run_batch(
            ["retro", "--last", "5"],
            {"pr_list_merged.json": "pr_list_merged_same_name.json"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertEqual(len(out), 2)
        docker = next(i for i in out if "docker" in i["sourceUrl"])
        maven = next(i for i in out if "redis-client" in i["sourceUrl"])
        self.assertEqual((docker["from"], docker["to"], docker["prs"]), ("8.6.0", "8.8.0", [31, 33]))
        self.assertEqual((maven["from"], maven["to"], maven["prs"]), ("0.12.1", "0.12.2", [32]))

    def test_regression_guard_retro_skips_self_dependency(self):
        """Regression guard: retro skips updates of the consumer repo itself."""
        result = self.run_batch(
            ["retro", "--last", "5"],
            {"pr_list_merged.json": "pr_list_merged_self.json"},
            stub_files={"repo_url": "https://github.com/Quokkify/q4j.git\n"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        item = json.loads(result.stdout)[0]
        self.assertEqual(item["verdict"], "skip")
        self.assertEqual(item["reason"], "self dependency")

    def test_sweep_skips_self_dependency(self):
        result = self.run_batch(
            ["sweep"],
            {"pr_list_open.json": "pr_list_open.json"},
            stub_files={"repo_url": "https://github.com/actions/github-script\n"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertEqual((out[0]["verdict"], out[0]["reason"]), ("skip", "self dependency"))

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

    def test_retro_empty_result_warns_about_dependencies_label(self):
        result = self.run_batch(
            ["retro", "--last", "5"], {}, stub_files={"pr_list_merged.json": "[]"}
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])
        self.assertIn("dependencies", result.stderr)

    def test_retro_nonempty_result_does_not_warn(self):
        _, result = self.retro()
        self.assertEqual(result.stderr, "")

    def test_retro_warns_when_result_count_hits_the_limit(self):
        prs = [{"number": n, "title": "t", "body": "", "mergedAt": "2026-01-01T00:00:00Z"}
               for n in range(200)]
        result = self.run_batch(
            ["retro", "--since", "2026-01-01"], {},
            stub_files={"pr_list_merged.json": json.dumps(prs)},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("results may be truncated at 200", result.stderr)

    def test_retro_last_mode_never_warns_about_truncation(self):
        prs = [{"number": n, "title": "t", "body": "", "mergedAt": "2026-01-01T00:00:00Z"}
               for n in range(5)]
        result = self.run_batch(
            ["retro", "--last", "5"], {},
            stub_files={"pr_list_merged.json": json.dumps(prs)},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("truncated", result.stderr)

    def test_sweep_warns_when_result_count_hits_the_limit(self):
        prs = [{"number": n, "title": "t", "body": "", "headRefName": "b", "headRefOid": "x"}
               for n in range(100)]
        result = self.run_batch(
            ["sweep"], {}, stub_files={"pr_list_open.json": json.dumps(prs)}
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("results may be truncated at 100", result.stderr)

    def test_batch_gh_failure_exits_3_with_empty_stdout(self):
        for args in (["sweep"], ["retro", "--last", "3"]):
            result = self.run_batch(args, {}, fail=True)
            self.assertEqual(result.returncode, 3, args)
            self.assertIn("gh failed", result.stderr)
            self.assertEqual(result.stdout, "")


class RenovateAdoptionOwnedPathsTests(unittest.TestCase):
    SRC = "https://github.com/quokkify/ci-kit.git"

    def run_owned(self, answers, fail=False, truncated=False, copier=None):
        """answers maps answers-file name -> (src_path, commit, extra yaml lines)."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        tmp = Path(temporary.name)
        env = make_stub(
            tmp, {"api_tree.json": "api_tree.json", "copier_yml": "copier_yml"}, fail=fail
        )
        stub_dir = Path(env["GH_STUB_DIR"])
        if truncated:
            stub = stub_dir / "api_tree.json"
            data = json.loads(stub.read_text(encoding="utf-8"))
            data["truncated"] = True
            stub.write_text(json.dumps(data), encoding="utf-8")
        if copier is not None:
            (stub_dir / "copier_yml").write_text(copier, encoding="utf-8")
        repo = tmp / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        for name, (src, commit, extra) in answers.items():
            (repo / name).write_text(
                f"# Changes here will be overwritten by Copier\n_commit: {commit}\n"
                f"_src_path: {src}\n{extra}",
                encoding="utf-8",
            )
        result = subprocess.run(
            ["sh", str(SCRIPT), "owned-paths"],
            env=env,
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        result.gh_log = Path(env["GH_STUB_LOG"]).read_text(encoding="utf-8")
        return result

    def ci_kit(self, module):
        return (self.SRC, "v3.9.0", f"module: {module}\nproject_name: demo\n")

    def test_owned_paths_honor_subdirectory_for_each_module(self):
        result = self.run_owned(
            {
                ".copier-answers.java.yml": self.ci_kit("java"),
                ".copier-answers.yml": self.ci_kit("legacy"),
            }
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertIn(".ci/modules/java.yml", out)  # java: prefix and ".jinja" stripped
        self.assertIn(".github/workflows/gitleaks.yml", out)  # legacy: template/
        self.assertIn(".github/pull_request_template.md", out)
        for foreign in ("README.md", "LICENSE", "copier.yml"):
            self.assertNotIn(foreign, out)
        self.assertFalse([p for p in out if p.startswith(("template/", "modules/"))])
        self.assertFalse([p for p in out if p.endswith(".jinja")])
        self.assertEqual(out, sorted(set(out)))

    def test_owned_paths_one_tree_call_per_repo_and_commit(self):
        result = self.run_owned(
            {
                ".copier-answers.java.yml": self.ci_kit("java"),
                ".copier-answers.yml": self.ci_kit("legacy"),
            }
        )
        calls = result.gh_log.strip().splitlines()
        tree_calls = [c for c in calls if "/git/trees/" in c]
        self.assertEqual(tree_calls, ["api repos/quokkify/ci-kit/git/trees/v3.9.0?recursive=1"])
        copier_calls = [c for c in calls if "contents/copier.yml" in c]
        self.assertEqual(len(copier_calls), 1)
        self.assertIn("?ref=v3.9.0", copier_calls[0])

    def test_owned_paths_unresolvable_variable_warns_and_falls_back_to_whole_tree(self):
        result = self.run_owned(
            {
                ".copier-answers.yml": (self.SRC, "v3.9.0", "project_name: demo\n"),
                ".copier-answers.java.yml": self.ci_kit("java"),
            }
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("unresolvable", result.stderr)
        out = json.loads(result.stdout)
        self.assertIn(".ci/modules/java.yml", out)
        self.assertIn("README.md", out)  # whole-tree fallback over-flags (safe direction)
        self.assertIn("template/.github/workflows/gitleaks.yml", out)
        self.assertNotIn("copier.yml", out)
        self.assertFalse([p for p in out if p.endswith(".jinja")])

    def test_owned_paths_plain_variable_subdirectory(self):
        result = self.run_owned(
            {".copier-answers.yml": self.ci_kit("java")},
            copier='_subdirectory: "modules/{{ module }}/template"\n_templates_suffix: .jinja\n',
        )
        self.assertEqual(
            json.loads(result.stdout), [".ci/modules/java.yml", "{{ _copier_conf.answers_file }}"]
        )

    def test_owned_paths_without_subdirectory_is_whole_tree_minus_copier_yml(self):
        result = self.run_owned(
            {".copier-answers.yml": (self.SRC, "v3.9.0", "")},
            copier="_templates_suffix: .jinja\n",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertIn("README.md", out)
        self.assertIn("template/.github/pull_request_template.md", out)
        self.assertNotIn("copier.yml", out)

    def subdir(self, raw_copier_line):
        return self.run_owned(
            {".copier-answers.yml": self.ci_kit("java")},
            copier=f"{raw_copier_line}\n_templates_suffix: .jinja\n",
        )

    def test_owned_paths_subdirectory_trailing_slash_and_dot_prefix_are_normalized(self):
        for line in ("_subdirectory: template/", "_subdirectory: ./template",
                     '_subdirectory: "./template//"'):
            result = self.subdir(line)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "", line)
            out = json.loads(result.stdout)
            self.assertIn(".github/pull_request_template.md", out, line)
            self.assertNotIn("README.md", out, line)

    def test_owned_paths_empty_or_dot_subdirectory_is_template_root(self):
        for line in ('_subdirectory: ""', "_subdirectory: .", "_subdirectory: ./"):
            result = self.subdir(line)
            self.assertEqual(result.returncode, 0, result.stderr)
            out = json.loads(result.stdout)
            self.assertIn("README.md", out, line)
            self.assertIn("template/.github/pull_request_template.md", out, line)
            self.assertNotIn("copier.yml", out, line)

    def test_owned_paths_block_scalar_subdirectory_warns_and_falls_back(self):
        for indicator in (">-", "|", ">"):
            result = self.run_owned(
                {".copier-answers.yml": self.ci_kit("java")},
                copier=f"_subdirectory: {indicator}\n  template\n_templates_suffix: .jinja\n",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("falling back to the whole template tree", result.stderr, indicator)
            self.assertIn("README.md", json.loads(result.stdout), indicator)

    def test_owned_paths_subdirectory_matching_nothing_warns_and_falls_back(self):
        result = self.subdir("_subdirectory: no/such/dir")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("falling back to the whole template tree", result.stderr)
        self.assertIn("README.md", json.loads(result.stdout))

    def test_owned_paths_accepts_gh_and_ssh_source_forms(self):
        for src in ("gh:quokkify/ci-kit", "gh:quokkify/ci-kit.git",
                    "git@github.com:quokkify/ci-kit.git", "git@github.com:quokkify/ci-kit",
                    "https://github.com/quokkify/ci-kit"):
            result = self.run_owned(
                {".copier-answers.yml": (src, "v3.9.0", "module: java\n")}
            )
            self.assertEqual(result.returncode, 0, (src, result.stderr))
            self.assertEqual(result.stderr, "", src)
            self.assertIn(".ci/modules/java.yml", json.loads(result.stdout), src)
            self.assertIn("api repos/quokkify/ci-kit/git/trees/v3.9.0?recursive=1",
                          result.gh_log, src)

    def test_owned_paths_without_answers_is_empty_list(self):
        result = self.run_owned({})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])
        self.assertEqual(result.gh_log, "")

    def test_owned_paths_non_github_source_is_skipped_with_warning(self):
        result = self.run_owned(
            {".copier-answers.yml": ("https://gitlab.example.com/group/tpl.git", "v1.0.0", "")}
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])
        self.assertIn("skipping non-GitHub", result.stderr)
        self.assertEqual(result.gh_log, "")

    def test_owned_paths_truncated_tree_warns(self):
        result = self.run_owned({".copier-answers.yml": self.ci_kit("java")}, truncated=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("truncated", result.stderr)
        self.assertTrue(json.loads(result.stdout))

    def test_owned_paths_gh_failure_exits_3_with_empty_stdout(self):
        result = self.run_owned({".copier-answers.yml": self.ci_kit("java")}, fail=True)
        self.assertEqual(result.returncode, 3)
        self.assertIn("gh failed", result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
