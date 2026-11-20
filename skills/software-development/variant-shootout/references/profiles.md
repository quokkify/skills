# Example profiles

Two fictional profiles that show the contract from [`SKILL.md`](../SKILL.md#profile). The repositories, hosts, variables and environments are invented; a real profile lives in the caller's private wrapper, never in this repository. Fields left out keep their defaults.

The commands are illustrative; check them against the CLI versions in use.

Placeholders the skill fills in: `{worktree}`, `{results_dir}`, `{tests}`, `{ref}`, `{environment}`, `{seq}`; `<run_id>` is the id extracted from the trigger's output as `runner.ci.run_id` describes. `runner.ci.status` must print exactly one of `running`, `success`, `failed`, `canceled`.

## GitHub Actions + pytest

A Python service on a GitHub Enterprise host `github.example.com`, repository `example-org/example-app`, with a `workflow_dispatch` workflow `shootout.yml`. Its inputs `tests`, `reruns`, `notify` and `run_tag` are passed to the job, and it uploads `reports/` as the artifact `results`.

```yaml
baseline_ref: main
tests: "tests/api/test_orders.py"
runner:
  local: >-
    cd {worktree} && python -m pytest {tests} -p no:randomly
    --junitxml={results_dir}/TEST-pytest.xml
  force_env:
    PYTEST_ADDOPTS: "-p no:rerunfailures"
    NOTIFY: "false"
  expected_minutes: 12
  ci:
    trigger: >-
      GH_HOST=github.example.com gh workflow run shootout.yml -R example-org/example-app
      --ref {ref} -f tests="{tests}" -f reruns=0 -f notify=false -f run_tag=shootout-{seq}
      && sleep 10
      && GH_HOST=github.example.com gh run list -R example-org/example-app
      --workflow shootout.yml --branch {ref} --limit 20 --json databaseId,url,displayTitle
    run_id: >-
      From the JSON list, take the entry whose displayTitle contains "shootout-{seq}"
      (the workflow sets run-name from run_tag): <run_id> = databaseId, <run_url> = url.
    status: >-
      GH_HOST=github.example.com gh run view <run_id> -R example-org/example-app
      --json status,conclusion --jq 'if .status != "completed" then "running"
      elif .conclusion == "success" then "success"
      elif .conclusion == "cancelled" then "canceled" else "failed" end'
    fetch: >-
      GH_HOST=github.example.com gh run download <run_id> -R example-org/example-app
      -n results -D {results_dir}
    poll_seconds: 60
    timeout_minutes: 40
results:
  format: junit
environments: [ci]
max_parallel: 2
variant_branch_pattern: "shootout/<slug>"
language: en
report_template: "## Performance evidence"
```

Notes:

- Retries off reaches CI only through the trigger (`-f reruns=0 -f notify=false`); `force_env` covers local runs. Both are present, so proof mode may start and `analyze.py` gets `--retries off`.
- `gh workflow run` prints no run id. The unique `run_tag` lets `run_id` find this dispatch even when `max_parallel: 2` puts two runs on one branch at once.
- `gh run view ... --json headSha` gives the run's `observed_sha`.
- `max_parallel: 2` is safe only because each workflow run uses its own database container; with a shared test database it would be `1`.

## GitLab CI + Maven

A Java multi-module service on `gitlab.example.org`, project id `123`. Its pipeline accepts the variables `TESTS`, `TARGET_ENV`, `RERUNS`, `ALLURE_UPLOAD` and `CHAT_NOTIFY`, and keeps every module's `target/surefire-reports` and `target/allure-results` as artifacts of the job `tests`. Three identical staging environments share nothing with each other.

```yaml
baseline_ref: develop
tests: "OrderApiTest,PaymentApiTest"
runner:
  local: >-
    cd {worktree} && mvn -q -B test -Dtest='{tests}' -Dsurefire.rerunFailingTestsCount=0
    ; mkdir -p {results_dir}
    && tar cf - */target/surefire-reports */target/allure-results | tar xf - -C {results_dir}
  force_env:
    ALLURE_UPLOAD: "false"
    CHAT_NOTIFY: "false"
  expected_minutes: 25
  ci:
    trigger: >-
      glab api --hostname gitlab.example.org -X POST projects/123/pipeline
      -f ref={ref}
      -f 'variables[][key]=TESTS' -f 'variables[][value]={tests}'
      -f 'variables[][key]=TARGET_ENV' -f 'variables[][value]={environment}'
      -f 'variables[][key]=RERUNS' -f 'variables[][value]=0'
      -f 'variables[][key]=ALLURE_UPLOAD' -f 'variables[][value]=false'
      -f 'variables[][key]=CHAT_NOTIFY' -f 'variables[][value]=false'
    run_id: "The response is JSON: <run_id> = id, <run_url> = web_url; its sha is the observed_sha."
    status: >-
      glab api --hostname gitlab.example.org projects/123/pipelines/<run_id>
      | python3 -c 'import json,sys; s=json.load(sys.stdin)["status"];
      print({"success":"success","failed":"failed","canceled":"canceled","skipped":"canceled"}.get(s,"running"))'
    fetch: >-
      job=$(glab api --hostname gitlab.example.org projects/123/pipelines/<run_id>/jobs
      | python3 -c 'import json,sys; print(next(j["id"] for j in json.load(sys.stdin) if j["name"] == "tests"))')
      && glab api --hostname gitlab.example.org projects/123/jobs/$job/artifacts > {results_dir}/artifacts.zip
      && unzip -o {results_dir}/artifacts.zip -d {results_dir}
    poll_seconds: 60
    timeout_minutes: 75
results:
  format: both
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

- `RERUNS=0`, `ALLURE_UPLOAD=false` and `CHAT_NOTIFY=false` travel as pipeline variables in the trigger; `force_env` only reaches local Maven runs, where `-Dsurefire.rerunFailingTestsCount=0` turns retries off.
- `fetch` downloads the artifacts of this pipeline's `tests` job, not the latest artifacts of the branch, because many pipelines run on one variant branch. The archive keeps its module folders; `collect.py` searches `results_dir` recursively, so two modules' `TEST-*.xml` files with the same name do not collide.
- `status` maps GitLab's `created`, `pending`, `running` and similar to `running`, and `skipped` to `canceled`. A pipeline that failed in its build stage has no test results and becomes `infra_error`.
- 30 runs per variant over three environments are 10 + 10 + 10; with `max_parallel: 1` each environment waits for its pipeline before triggering the next.
- `results_label: tms` keeps the Allure TMS link per test, which the `impact` hook uses. Its output is an *inferred* extrapolation and the block says so.
