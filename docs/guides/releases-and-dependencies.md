# Releases and dependency updates

This repository uses Release Please for versioning and changelog generation, and Renovate for pinned GitHub Actions updates. The workflows rendered by the `quokkify/project-toolkit` Copier template are the exception: the toolkit owns the versions inside them and delivers them through `copier update`.

## Release flow

1. Open pull requests with a Conventional Commit title. The scope is optional:

   ```text
   type(optional-scope): short summary
   ```

2. Merge the pull request into `main`. The squash commit title must remain conventional.
3. Release Please updates or opens a release pull request containing the next version and `CHANGELOG.md` entries.
4. Merge the release pull request after its checks pass.
5. Release Please creates the organization-standard `vX.Y.Z` Git tag and GitHub release.

The manifest records the latest released version. The `bootstrap-sha` marks the `0.7.1` release commit as the migration boundary from historical `skills-vX.Y.Z` tags to the organization-standard `vX.Y.Z` format, without retagging past releases. The `simple` release type is used because this repository has no package manifest.

Release impact follows Conventional Commits:

- `fix(scope): ...` and `perf(scope): ...` produce a patch release;
- `feat(scope): ...` produces a minor release;
- a breaking change marked with `!` produces a major release;
- `docs`, `ci`, `build`, `refactor`, `test`, and `chore` do not create a release by themselves.

The `PR Title` workflow enforces the title format before merge. When squash merging, verify the final commit title in GitHub because Release Please reads merged commit history rather than the pull request body.

## Renovate flow

`.github/renovate.json` was generated from the Copier answers and is owned by this repository from then on; the template does not rewrite it. It extends the shared public base and GitHub Actions presets, which is how toolkit-owned Renovate policy reaches this repository. Renovate keeps immutable action SHAs current while preserving readable version comments.

Renovate is disabled for the workflow paths the template owns, including `.github/workflows/release.yml`. Without that exclusion the same pin has two owners: Renovate moves it, the next `copier update` lands on the moved pin, and the update conflicts in a file this repository never edited. Versions inside those files change only when the template is updated.

The `Renovate Config` workflow runs:

- when `.github/renovate.json` or its validation workflow changes;
- weekly, to detect incompatibility with newer Renovate versions;
- manually through `workflow_dispatch`.

It executes `renovate-config-validator --strict .github/renovate.json`. Renovate pull requests must pass the normal repository checks before merge. Major dependency updates still require explicit review; do not bypass branch protection or security review for an automated update.

## Toolkit references

Every workflow that calls `quokkify/project-toolkit` references it at the version recorded as `toolkit_version` in `.copier-answers.yml`, in one of two accepted forms:

- the exact release tag, for example `@v2.19.0` — what the template renders, and what every consumer that calls the toolkit's release workflow uses;
- a full 40-character commit digest carrying that tag as a comment, for example `@7bc13e13… # v2.19.0`.

The template-owned check in `.github/workflows/validate.yml` enforces this across every workflow, and `tests/test_release_configuration.py` asserts it for the release caller. A tag is mutable and a digest is not, so the digest form remains available for a deliberate, hand-maintained pin. It is not the default here: [ADR-0002](../adr/0002-reference-project-toolkit-by-release-tag.md) records why this repository references the toolkit by tag and what that trades away.

## Configuration files

- `.github/release-please/config.json` — release type, migration boundary, and tag convention;
- `.github/release-please/manifest.json` — last released version tracked by Release Please;
- `.github/workflows/release.yml` — template-owned caller for the toolkit's reusable release workflow;
- `.github/workflows/pr-title.yml` — Conventional Commit title validation;
- `.github/renovate.json` — project-owned Renovate configuration extending the shared presets;
- `.github/workflows/renovate-config.yml` — strict Renovate configuration validation.
