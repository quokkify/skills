---
name: project-toolkit-migration
description: Apply or migrate existing repositories to project-toolkit Copier templates, diagnose failed template updates, and retain verified migration lessons. Use for template adoption, copier update conflicts, legacy answers, or project-toolkit readiness checks.
---

# Project Toolkit Migration

Maturity: **experimental**. This is an assisted migration workflow. Local diagnosis does not establish remote CI readiness or automation readiness.

## Start with durable context

Identify the consumer checkout, toolkit checkout, intended released template ref, and whether the request is diagnosis, first adoption, update, or recovery. Inspect their local instructions and dirty state. Ask only for missing inputs that affect the next action. Never infer the consumer from the current directory when it is the template repository itself.

Read [migration-checklist.md](references/migration-checklist.md) and the local learning index before a migration. In Codex, store private learning under `${CODEX_HOME:-$HOME/.codex}/migration-learning/project-toolkit/`; other runtimes use their private state directory. Create that directory when first recording a run. Keep project paths, reports and failed attempts there, outside the public hub. See [learning.md](references/learning.md) for the record and promotion contract.

Resolve the toolkit checkout from the user's location or the current repository, not a hard-coded machine path. Read its `copier.yml` and current usage guide. Treat the chosen release's actual template contract as authoritative when it differs from checkout HEAD.

## Diagnose before applying

Use the toolkit's documented Python environment (Python 3.9+ with PyYAML). If its dependencies are unavailable, report a tooling finding and use the manual checklist until resolved. Use the executable doctor from a toolkit checkout that contains it:

```sh
python3 <toolkit-checkout>/scripts/migration_doctor.py --project <consumer-checkout> --format json
```

For first adoption with proposed answers, add `--answers <answers-file>`. This is a read-only local check; it does not invoke Copier, fetch, or inspect GitHub. Exit 1 includes warnings and unknown checks; exit 2 includes blocking findings. Do not equate exit 0 with a proven migration. Do not invent the command if the checkout predates it: perform the checklist manually and report that executable diagnosis is unavailable.

Explain each finding with its evidence, remedy and responsible layer: consumer project, template, migration tooling, or missing remote evidence. Fix failures in the correct owner. A project-specific workaround is not proof that the reusable template is fixed.

## Apply and verify

1. Record the starting consumer commit and exact target release. Preserve existing uncommitted work. Rehearse in an isolated checkout before applying a migration to a working consumer.
2. Distinguish first adoption (`copier copy`) from tracked updates (`copier update`). Review the actual target template's tasks before authorizing `--trust`. Never run a rollout/fleet write across repositories based on a single-project request.
3. Preserve component IDs, names and paths, existing test/build commands, release policy, checks required by branch protection, and project-owned files. For legacy answers, derive missing topology from actual workflows and source layout; do not accept a default Python component as a reconstruction.
4. Inspect generated changes, conflict markers and rejected patches. A zero Copier exit code alone is insufficient. Run relevant local validation and, where authorized and available, inspect the consumer CI at the resulting commit. Record skipped checks explicitly.
5. Stop blind retries after the same failure repeats. Capture the evidence, classify the failing layer, and perform one discriminating check before retrying. Do not suppress a failing check or change required statuses merely to obtain green CI.
6. Rehearse a second application at the same target release in the disposable checkout to check idempotence. Record whether tracked output changes again. Do not declare success while unexplained changes remain.

Use existing toolkit helpers only after reading their side effects. `rollout_project_toolkit.sh` publishes branches and PRs; fleet `--dry-run` needs GitHub access and a token. Neither is a substitute for offline local diagnosis.

## Finish every substantive run with a learning decision

Write a private run record even when migration fails. Report: result, verification evidence, unresolved checks, and learning decision (`patch-existing`, `create-case`, or `no-change` with reason). Update the private index so the next invocation can find it. Do not end with only “migration fixed” after repeated attempts.

Keep hypotheses separate from verified lessons. Turn a confirmed failure into a minimal reproducible fixture, a doctor rule or a checklist correction in the appropriate repository. Search existing lessons first. Validate a changed diagnostic against both the failure and an unaffected case. Generalize and review before proposing shared changes; preserve existing authorization, and never assume this skill authorizes public publication or merge.

Use the [maturity criteria](references/learning.md#maturity) before changing status. Installation and passing fixture tests alone do not qualify this agent for unattended automation.
