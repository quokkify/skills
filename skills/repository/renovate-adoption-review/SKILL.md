---
name: renovate-adoption-review
description: Review a Renovate update (open PR or a batch of merged updates) and apply grounded, cited opportunities to adopt what the new version brings in the consumer repository, via a child PR or an issue.
---

# Renovate Adoption Review

A version bump changes only the version. This skill reads a dependency update and finds places in the **consumer** repository that should change to use what the new version brings: a deprecated API, input or option replaced by its documented successor, a workaround the new version makes unnecessary, or a new option that simplifies existing configuration. Every applied change cites its source.

## When to use

- A Renovate PR (usually a major) is open and you want the consumer code to adopt the new version before or together with the merge.
- Updates were merged over a period and nobody read their release notes with the consumer code in mind.
- Not for: judging breaking-change risk, fixing a build the bump broke, editing the Renovate configuration, or adding dependencies.

Requirements: `gh` (authenticated), `jq`, `git`, a POSIX shell, and a clone of the consumer repository. Renovate must label its PRs `dependencies` (renovate `labels` option); `retro` finds PRs by that label. All helper calls below run from the consumer repository root; `<skill-dir>` is the directory holding this file.

## Modes

| Mode | Input | Delivers | Implied outward action |
|---|---|---|---|
| `review <pr>` | one open Renovate PR | child PR stacked on the Renovate branch, or a report comment on the parent | child PR and parent comment |
| `sweep` | open Renovate PRs | verdict table; changes nothing | none |
| `retro` | `--since <date\|tag\|sha>` or `--last <N>` | one issue per run titled `Adoption review: <range>` | the issue |
| `retro --apply` | as `retro` | the issue plus one PR to the default branch with `Closes #<issue>` | issue and PR |

Helper commands (`sh <skill-dir>/scripts/renovate_adoption.sh ...`):

- `inspect <pr> [--mode open|retro]` → `{pr, branch, headSha, updates[{package, sourceUrl, from, to, updateType, releaseNotesUrls}], verdict, reason}`.
- `sweep` → array of `inspect` items for open Renovate PRs.
- `retro (--since <date|tag|sha> | --last <N>)` → array of `{package, sourceUrl, from, to, updateType, prs, releaseNotesUrls, verdict, reason}`; repeated bumps of one package collapse into one interval from the earliest `from` to the latest `to`.
- `owned-paths` → array of consumer-relative paths owned by the Copier template.
- Exit codes: `0` success, `2` usage error (including an invalid allowlist or unknown `--since` ref), `3` `gh`, `jq` or network failure.

Triage: in `review`/`sweep` only majors are candidates; in `retro`, majors and minors. Digest, patch, pin, lock-file and `unknown` updates are skipped unless the package is listed in the consumer's `.github/renovate-adoption.json` (`{"allow": ["actions/setup-java"]}`; absent file means an empty list). A version change that keeps the numeric prefix but changes the suffix (for example a base-image tag moving from one variant suffix to another) classifies as `unknown` and is skipped; use the explicit-PR override below to review it. Updates whose source is the consumer repository itself (Renovate bumping the repo's own published modules) are skipped with reason `self dependency`, even when allowlisted. Renovate's own `Update` column, when present, takes precedence over the computed type. `retro` merges updates per dependency by package name and source URL.

Retro notes:

- `--last <N>` takes the N most recent Renovate PRs in the order `gh` returns them (creation order), not strictly the N most recently merged.
- The helper caps its queries at 100 open and 200 merged PRs. When the helper prints `warning: results may be truncated at <N>` on stderr, narrow the range with `--since` and say in the output that the result may be truncated.
- "Merged Renovate PRs scanned" is the number of unique PR numbers across all retro items' `prs` arrays. If it is below N for `--last N`, report the actual count; the repository may have fewer merged Renovate PRs.
- When `retro` returns an empty array it warns on stderr (usually the `dependencies` label is missing). Report the empty result to the user; never turn it into an issue.

## Workflow

Steps per mode: `sweep` runs steps 1–2 and reports the verdict table. `retro` without `--apply` runs steps 1–6 and 9: no edits and no checks, findings are proposals in the issue. Local signals (source 4 in step 4: build and lint warnings) exist only in modes that run checks (`review`, `retro --apply`); in plain `retro` rely on sources 1–3. A stale local checkout is fine for plain `retro`, because usages are searched on `origin/<default>` (see step 1). `review` and `retro --apply` run every step.

1. **Preflight.** `git status --porcelain` must be empty, otherwise stop before any edit. For `review`, also check for an existing child as soon as `inspect` returns the branch name: `git ls-remote --heads origin "adopt/<name>"` and `gh pr list --head "adopt/<name>" --state all`; if either exists, the run goes through the drift path in `references/stacked-pr.md`, never a new branch. For `retro`, resolve the default branch with `git symbolic-ref --short refs/remotes/origin/HEAD` (strip the `origin/` prefix; fallback `gh repo view --json defaultBranchRef --jq .defaultBranchRef.name`) and run `git fetch origin`. Search usages without checking out: `git grep -n <pattern> origin/<default> -- <pathspec>` and `git show origin/<default>:<path>`.
2. **Helper.** Run the mode's helper command. Any non-zero exit stops the run (see Stop conditions). For `review`, apply the explicit-PR override if the verdict is `skip`. Then, before any analysis edit, switch to the working branch: for `review`, `adopt/<name>` created from `headSha` (Create) or the existing one rebased onto it (Drift), per `references/stacked-pr.md`; for `retro --apply`, follow the retro recipe in the same file. Never edit or commit on the Renovate branch or the default branch.
3. **Ownership.** Run `owned-paths` once per run and keep the list (see Guardrails).
4. **Sources per candidate dependency** (for grouped PRs, only the rows that qualify under Triage), in this order of trust; fall back to the next when one is unavailable:
   1. The Renovate PR body: release notes it already fetched and its compare link (`releaseNotesUrls`). When `releaseNotesUrls` is empty or `sourceUrl` is not a GitHub repository: (a) find the source repository from registry metadata (Maven POM `<scm><url>`, npm `repository`, PyPI `project_urls`); (b) discover the tag naming by listing tags, `gh api --paginate "repos/<o>/<r>/tags?per_page=100" --jq '.[].name' | grep -F '<version>'` (tags may be prefixed, for example `v1.2.3`, `name-1.2.3`, `module/1.2.3`); (c) fall back to the project's documentation release-notes page.
   2. GitHub Releases and the CHANGELOG between `from` and `to` (`gh api --paginate "repos/<owner>/<repo>/releases?per_page=100"`, `gh api "repos/<owner>/<repo>/contents/CHANGELOG.md?ref=<to-tag>" -H "Accept: application/vnd.github.raw"`).
   3. The tag-to-tag diff of the dependency (`gh api repos/<owner>/<repo>/compare/<from-tag>...<to-tag>`) narrowed to `action.yml`, the public API, `Dockerfile`, and migration documents (`UPGRADING`, `MIGRATION`).
   4. Local signals after the bump: deprecation warnings from the consumer's build and linters (only in modes that run checks).

   If no source yields anything, report `no sources` for that dependency and skip it.
5. **Consumer usages.** Search the consumer for every symbol, input, option or tag a source names. Use the ecosystem reference for where to look.
6. **Findings.** Pair each source item with confirmed consumer locations. Apply the grounding rules.
7. **Apply within guardrails.** On the working branch from step 2, one finding at a time, smallest edit that adopts the documented successor.
8. **Consumer checks.** Run the repository's own documented build, lint and tests. Revert any finding whose checks fail and report it with the failing output.
9. **Output.** Deliver per mode using `references/templates.md`; for `retro`, create the issue with `gh issue create --title "Adoption review: <range>" --body-file "$tmp/issue.md"`, where `$tmp` is a `mktemp -d` directory outside the repository; if the user asks for a draft or dry run, write the title and body to a temp file, show its path, and create nothing; for `review`, follow `references/stacked-pr.md` for branch, PR, marker and drift handling; for `retro --apply`, its retro recipe. Write PR and comment bodies to a temporary directory outside the repository, never into the working tree.

Ecosystem checklists: [GitHub Actions](references/ecosystems/github-actions.md), [Docker](references/ecosystems/docker.md), [Gradle and Maven](references/ecosystems/gradle-maven.md), [npm and TypeScript](references/ecosystems/npm-typescript.md), [Python](references/ecosystems/python.md).

## Grounding rules

- Every applied change cites a source: a release-note URL or quote, a diff hunk, or observed warning text.
- A finding without a citation goes to "Considered, not applied" (in the retro issue this section is distinct from "Skipped", which holds triage skips only).
- A finding without a confirmed usage in the consumer, located by search, is dropped.
- Do not infer behavior from version numbers or memory. If the source does not say it, it is not a finding.

## Guardrails

Allowed:

- Replace a deprecated API, input or option with its documented successor.
- Remove a workaround the new version makes unnecessary.
- Adopt a new option that simplifies existing configuration.
- Update comments and docs that name the old version.

Forbidden:

- New dependencies.
- Public API changes of the consumer library.
- Edits to the Renovate configuration.
- Edits to template-owned files; report them under "Belongs in ci-kit" with their citations.
- Unrelated refactors.
- Weakening or deleting tests.

Ownership rule. A consumer path `P` is template-owned when it equals an entry printed by `owned-paths`. If `owned-paths` printed a `falling back to the whole template tree` warning, `P` is also owned when an entry ends with `/P`. Any other `owned-paths` warning (a skipped non-GitHub source, a truncated template tree) means ownership is unknown for that template: stop and ask before editing any file that could be template-generated. Entries that still contain `{{` are templated file names the helper cannot render: treat every `.copier-answers*.yml` file, and any file whose name the template renders, as owned.

Size: a finding that touches more than 10 files is proposed, not applied.

Verification: a finding counts as applied only after a passing run of the consumer's checks. Commit one finding per commit and run the checks after each; revert the failing finding's commit. Never claim success without a passing run.

## Explicit-PR override

When the user names a PR for `review` and `inspect` returns verdict `skip`, report the `reason` and ask whether to proceed anyway. Proceed only on a yes; the rest of the workflow is unchanged.

## Stop conditions

- Helper exit code other than `0`: stop, quote the failing command and its stderr, and open no PR or issue. Exit `2` is a usage or allowlist problem to fix; exit `3` is a `gh`, `jq` or network failure.
- Dirty working tree or wrong branch: stop before any edit.
- Failing consumer checks: revert the failing finding; if checks still fail with no findings applied, stop and report, since the failure predates this change.
- Any `gh` write failing midway: stop and report what was created so far; no partial PR is left claiming success.

## Outward actions

Pushing branches, opening PRs or issues, and commenting need the user's go-ahead, except what the invoked mode implies:

- `review` implies the child branch push, the child PR, and the parent comment.
- `retro` without `--apply` implies only the issue.
- `retro --apply` implies the issue, the branch push, and the PR.
- `sweep` implies nothing.

Anything else, such as a ci-kit issue for "Belongs in ci-kit" findings, needs explicit approval.

## References

- [`references/stacked-pr.md`](references/stacked-pr.md): child branch, PR, marker, drift, merge order, recovery, and the `retro --apply` recipe.
- [`references/templates.md`](references/templates.md): child PR, parent comment, retro issue, retro PR.
- `references/ecosystems/`: per-ecosystem checklists linked in the Workflow.
