---
name: repository-quality-gates
description: Design, implement, and review reproducible repository validators, Git hooks, and CI quality gates that inspect the exact artifact being published.
---

# Repository Quality Gates

Use this skill when adding or reviewing repository-level validators, tracked Git hooks, documentation builds, public-content checks, secret scanning, or CI gates.

## Core principle

Validate the exact artifact that will be committed, pushed, or reviewed. A green check against a mutable working tree is not evidence about a different staged snapshot or Git ref.

## Workflow

1. Inventory existing CI, hooks, security policy, contribution guidance, and tool-version conventions.
2. Define fast and full gates:
   - fast: dependency-light structural, link, and targeted boundary checks;
   - full: fast checks, regression tests, generated-document validation, pinned static tools, working-tree secret scan, and full-history secret scan.
3. Implement deterministic validators that aggregate actionable repository-relative errors.
4. Add regression tests for valid input, malformed input, bypass attempts, and host-filesystem isolation.
5. Make local hooks opt-in and refuse to overwrite an existing `core.hooksPath` without explicit force.
6. Add CI that runs the same portable validator with pinned tool versions and minimal permissions.
7. Run shell/workflow linting, tests, documentation build, diff checks, and both secret-scan scopes.
8. Review the complete diff. Create or push a focused branch and open a PR only after explicit user approval or an applicable repository policy authorizes publication.
   - For a staged-diff review, fingerprint the index, export it, run checks from the exported directory, and re-fingerprint immediately before the verdict. If the index changed, restart scope analysis instead of mixing stale findings into the current review.
   - For repository-layout migrations, inspect moved or renamed skill bodies even when Git reports 100% renames. Structural validation does not prove that legacy role names, tool-specific invocation language, home-directory fallbacks, or project-specific stack assumptions were removed.
   - Cross-check documentation claims against the adapter files that actually ship; a notes-only adapter must not be described as providing personas, model routing, or executable setup.
   - Search for both legacy identifiers and concrete project fingerprints such as framework versions, fixed directory conventions, and domain-rule filenames. A canonical portable skill that mandates a named role or tool without a capability-based fallback is a functional portability failure.
   - Treat operational scripts, service units, and copy-paste runbooks as executable interfaces. Probe dependency failures, concurrency/locking, state preservation, required environment wiring, destructive-command gates, and secret-safe backup permissions—not only syntax and happy paths.
   - In a worktree shared with delegated agents, stage explicit paths and inspect untracked files before committing: tool runs such as `uv run` or editable installs leave virtualenvs, lockfiles, and build metadata that `git add -A` would publish.
9. After every fix commit, re-check the exact PR head plus top-level comments, submitted reviews, inline comments, and active review threads.
   - When a check, report, or bot comment is stale for the current head, read the annotations of cancelled runs for "higher priority waiting request" before changing the posting logic; the message names the colliding concurrency group.
   - When the default branch fails after a merge in a step the change does not touch, confirm the external dependency (for example, that the reported packages resolve) and rerun only the failed jobs before treating it as a regression.
   - When a bot-opened PR (default workflow token) has required checks stuck as "action required", confirm its head is the expected bot branch in the same repository, approve the pending runs (`POST /repos/<owner>/<repo>/actions/runs/<id>/approve`), then wait for the checks. Never approve fork runs this way.
   - Merge-on-green automation must re-read, on every poll, a clean merge state, no failed or cancelled check (required or not), and no pending check; merge with `--match-head-commit <evaluated-sha>`, then audit every merged PR's checks once more.

## Reusable CI migration gates

When moving a consumer repository onto a shared CI toolkit, compare the committed workflow files with the template metadata and the toolkit's latest released workflow/action contract before editing. Treat metadata as declared intent, not proof of adoption. Map ownership of triggers, permissions, secrets, artifacts, and project-specific checks; remove local setup/report/upload steps only when the reusable contract preserves their paths and failure semantics. Keep production references on immutable released tags, validate the workflow and dependency-bot configuration with the same linters CI uses, and send the exact resulting revision through an independent read-only review.

When the new layout moves hand-edited generated jobs into data (declarations, a plan output, or a matrix), do not require byte equality with the template render, and do not accept the file wholesale. Compare the regenerated parts (triggers, permissions, the shared contract job) structurally against the render. For every job that moves into data, prove effective-input equivalence: the called workflow's declared defaults overlaid with the old `with:` must equal the defaults overlaid with the new entry as the real fill step produces it. Refuse what data cannot reproduce: job keys beyond the call itself (`if`, `needs`, `secrets`, `strategy`), refs other than the pinned release, undeclared inputs, wrongly typed values such as a YAML float version, and `${{ }}` expressions, which matrix data passes as literal strings. Roll back on any mismatch. Derive the old required-check names exactly (`<caller job name> / <called job id>`), not by prefix, and move project-specific steps into a project-owned workflow with its own required check before migrating so protection never weakens in between.

## Safety requirements

- Pre-commit validation must use the staged snapshot and the validator implementation from that same snapshot.
- Pre-push validation must either validate every pushed OID independently or enforce a clean exact-`HEAD` contract and reject unsupported refs.
- Never follow repository symlinks into the host filesystem.
- Reject local links that resolve outside the repository, even when the external target exists.
- Handle malformed UTF-8 as an aggregated validation error rather than an uncaught crash.
- Verify PATH-installed tool versions before treating local output as equivalent to pinned CI output.
- Clear or pin CI-provided environment variables (event name, run URL parts) inside tests whose output depends on them, and also run the suites locally with CI-like values set; otherwise a test passes locally and fails only in CI.
- Make polling and merge scripts portable and fail closed: BSD `grep` has no `-P` (parse tab-separated CLI output with `awk -F'\t'`), zsh ties a variable named `path` to `PATH`, and a guard that errors must block the merge rather than read as "no failures".
- Key every `cancel-in-progress` concurrency group by each dimension of an independent stream: triggering workflow, configured source or scope, head repository, and branch. A group keyed only by branch lets a sibling trigger, or a sibling call of the same reusable workflow, cancel the run that owns the current head's result. Never add a run ID or commit SHA to the key; that disables cancellation of superseded runs. Test the rendered group expressions, not only their presence.
- Never pass optional reusable-workflow inputs from data through `${{ x || 'default' }}`: an explicit `false` becomes the default `true` and an explicit `""` becomes the default, a silent behavior change that keeps CI green. Fill every data entry upstream from the called workflow's declared `inputs.*.default`, pass `${{ matrix.<entry>.<field> }}` unchanged, keep any copied default table under a sync test against the workflow, and test that `false` and `""` survive.
- Authenticate CI steps whose CLIs query the forge API; unauthenticated calls share the hosted runner's anonymous per-IP rate limit and fail intermittently. Treat a rate-limit failure as transient and rerun the failed jobs before changing code.
- Treat privacy pattern checks and Gitleaks as complements to manual review, not proof that content is safe.
- Assert a pinned dependency by its stable identity, and enforce digest immutability as a separate check. A validator that compares against one specific digest reports the guard as missing on every legitimate bump.
- Treat executable snippets and operational runbooks as code: test failure ordering, malformed persistent state, repeated execution, and rollback paths rather than relying on syntax checks alone.
- Bound and normalize untrusted decimal strings before Bash arithmetic; regression-test values beyond the shell integer range, leading-zero forms, and future or otherwise out-of-range timestamps.
- For destructive or state-replacing recipes, require idempotent second-run tests and failure injection proving a failed prerequisite cannot trigger the following mutation.

## Detailed reference

See `references/repository-validation-git-hooks.md` for staged/pushed artifact patterns, validator hardening, reproducibility rules, and the minimum adversarial regression matrix.

## Completion criteria

- The same portable validation logic runs locally and in CI.
- Fast and full modes have explicit, documented scopes.
- Exact-artifact bypasses have regression coverage.
- Local and CI tool versions are reproducible.
- Working-tree and historical secret scans pass.
- Current-head CI and reviewer findings are clean or explicitly reported as pending.
