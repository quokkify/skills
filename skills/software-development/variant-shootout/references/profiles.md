# Example profiles

Two fictional profiles that show the contract from [`SKILL.md`](../SKILL.md#profile). The repositories, hosts, variables and environments are invented; a real profile lives in the caller's private wrapper, never in this repository. Fields left out keep their defaults.

The commands are illustrative; check them against the CLI versions in use.

Placeholders the skill fills in: `{worktree}`, `{results_dir}`, `{tests}`, `{ref}`; `<run_id>` stands for the id the trigger printed and is recorded in the ledger as `ci_url`.

## GitHub Actions + pytest

A Python service on a GitHub Enterprise host `github.example.com`, repository `example-org/example-app`, with a `workflow_dispatch` workflow `shootout.yml` that runs the selected tests and uploads `reports/` as the artifact `results`.

```yaml
baseline_ref: main
tests: "tests/api/test_orders.py"
runner:
  local: >-
    cd {worktree} && python -m pytest {tests} -p no:randomly -p no:rerunfailures
    --junitxml={results_dir}/TEST-pytest.xml
  ci:
    trigger: >-
      GH_HOST=github.example.com gh workflow run shootout.yml -R example-org/example-app
      --ref {ref} -f tests="{tests}" -f reruns=0 -f notify=false
      && sleep 5
      && GH_HOST=github.example.com gh run list -R example-org/example-app
      --workflow shootout.yml --branch {ref} --limit 1 --json databaseId,url
    status: >-
      GH_HOST=github.example.com gh run view <run_id> -R example-org/example-app
      --json status,conclusion,headSha
    fetch: >-
      GH_HOST=github.example.com gh run download <run_id> -R example-org/example-app
      -n results -D {results_dir}
  force_env:
    PYTEST_ADDOPTS: "-p no:rerunfailures"
    NOTIFY: "false"
results:
  format: junit
  globs: ["**/TEST-*.xml"]
environments: [ci]
max_parallel: 2
variant_branch_pattern: "shootout/<slug>"
language: en
report_template: "## Performance evidence"
```

Notes:

- `gh run list` is used because `gh workflow run` prints no run id; the `headSha` from `status` is the run's `observed_sha`. With `max_parallel` above 1, two dispatches on one branch can race for "the latest run"; dispatch with a unique input (for example the ledger `seq`) and match on it.
- `force_env` disables the rerun plugin, so proof mode may start and `analyze.py` gets `--retries off`.
- `max_parallel: 2` is safe only because each workflow run uses its own database container; with a shared test database it would be `1`.

## GitLab CI + Maven

A Java service on `gitlab.example.org`, project id `123`, whose pipeline accepts `TESTS` and `ENV` variables and keeps `target/surefire-reports` and `target/allure-results` as artifacts of the job `tests`. Three identical staging environments share nothing with each other.

```yaml
baseline_ref: develop
tests: "OrderApiTest,PaymentApiTest"
runner:
  local: >-
    cd {worktree} && mvn -q -B test -Dtest='{tests}' -Dsurefire.rerunFailingTestsCount=0
    && mkdir -p {results_dir}
    && cp target/surefire-reports/TEST-*.xml target/allure-results/*-result.json {results_dir}/
  ci:
    trigger: >-
      glab api --hostname gitlab.example.org -X POST projects/123/pipeline
      -f ref={ref} -f 'variables[][key]=TESTS' -f 'variables[][value]={tests}'
    status: >-
      glab api --hostname gitlab.example.org projects/123/pipelines/<run_id>
    fetch: >-
      job=$(glab api --hostname gitlab.example.org projects/123/pipelines/<run_id>/jobs
      | python3 -c 'import json,sys; print(next(j["id"] for j in json.load(sys.stdin) if j["name"] == "tests"))')
      && glab api --hostname gitlab.example.org projects/123/jobs/$job/artifacts > {results_dir}/artifacts.zip
      && unzip -j -o {results_dir}/artifacts.zip -d {results_dir}
  force_env:
    SUREFIRE_RERUN_COUNT: "0"
    ALLURE_UPLOAD: "false"
    CHAT_NOTIFY: "false"
results:
  format: both
  globs: ["**/TEST-*.xml", "**/*-result.json"]
results_label: tms
environments: [stage-1, stage-2, stage-3]
max_parallel: 1
variant_branch_pattern: "shootout/<slug>"
impact: >-
  For each test with a time verdict, look up its `external_id` in the suite
  inventory and multiply Δ median by the number of nightly suites that run it;
  report the serial total and divide by the suite's parallelism.
language: en
upload: "attach race.mp4 to the merge request description after the user's yes"
```

Notes:

- The trigger response carries `id`, `web_url` and `sha`; record `web_url` as `ci_url` and compare `sha` with the pin.
- `fetch` downloads the artifacts of this pipeline's `tests` job, not the latest artifacts of the branch, because many pipelines run on one variant branch.
- `unzip -j` flattens the artifact, because `collect.py` reads result files directly in `results_dir`.
- `30` runs per variant over three environments are 10 + 10 + 10; with `max_parallel: 1` each environment waits for its pipeline before triggering the next.
- `results_label: tms` keeps the Allure TMS link per test, which the `impact` hook uses. Its output is an *inferred* extrapolation and the block says so.
