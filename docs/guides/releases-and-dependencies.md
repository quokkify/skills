# Releases and dependency updates

This repository uses Release Please for versioning and changelog generation, and Renovate for pinned GitHub Actions updates.

## Release flow

1. Open pull requests with a Conventional Commit title. The scope is optional:

   ```text
   type(optional-scope): short summary
   ```

2. Merge the pull request into `main`. The squash commit title must remain conventional.
3. Release Please updates or opens a release pull request containing the next version and `CHANGELOG.md` entries.
4. Merge the release pull request after its checks pass.
5. Release Please creates the component-scoped `skills-vX.Y.Z` Git tag and GitHub release.

The manifest starts from a `0.0.0` baseline, while `initial-version` explicitly makes the first public release `0.1.0`. The commit recorded as `bootstrap-sha` excludes earlier repository history from the first generated changelog. The `simple` release type is used because this repository has no package manifest; `package-name` and `include-component-in-tag` still provide component-scoped tags.

Release impact follows Conventional Commits:

- `fix(scope): ...` and `perf(scope): ...` produce a patch release;
- `feat(scope): ...` produces a minor release;
- a breaking change marked with `!` produces a major release;
- `docs`, `test`, `ci`, `build`, `refactor`, and `chore` changes do not normally trigger a release by themselves, but can appear in the next generated changelog.

The `PR Title` workflow enforces the title format before merge. When squash merging, verify the final commit title in GitHub because Release Please reads merged commit history rather than the pull request body.

## Renovate flow

Root-level `renovate.json` is generated from the Copier answers and extends the shared public base and GitHub Actions presets. Renovate keeps immutable action SHAs current while preserving readable version comments.

The `Renovate Config` workflow runs:

- when `renovate.json` or its validation workflow changes;
- weekly, to detect incompatibility with newer Renovate versions;
- manually through `workflow_dispatch`.

It executes `renovate-config-validator --strict renovate.json`. Renovate pull requests must pass the normal repository checks before merge. Major dependency updates still require explicit review; do not bypass branch protection or security review for an automated update.

## Configuration files

- `release-please-config.json` — release type, baseline, and changelog sections;
- `.release-please-manifest.json` — last released version tracked by Release Please;
- `.github/workflows/release-please.yml` — release PR and GitHub release automation;
- `.github/workflows/pr-title.yml` — Conventional Commit title validation;
- `renovate.json` — Copier-managed shared Renovate preset selection;
- `.github/workflows/renovate-config.yml` — strict Renovate configuration validation.
