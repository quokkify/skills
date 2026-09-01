---
title: "ADR-0002: Reference project-toolkit by release tag"
---

# ADR-0002: Reference project-toolkit by its release tag instead of a commit digest

- Status: accepted
- Date: 2026-09-01

## Context

`.github/workflows/release.yml` is owned by the `quokkify/project-toolkit` Copier template. The template renders the reusable release workflow as an exact release tag:

```yaml
uses: quokkify/project-toolkit/.github/workflows/release-please.yml@v2.19.0
```

This repository instead held a 40-character commit digest with the tag as a trailing comment, and `tests/test_release_configuration.py` required that form. The digest never came from the template. Renovate re-pinned the rendered tag to a digest after every update, and the test encoded that side effect as a rule.

Renovate stopped doing so. The shared preset now disables Renovate for the workflow paths the template owns, `release.yml` among them, so that a project-side pin and a template-side pin cannot fight over the same line. Nothing re-pins the tag any more. Each `copier update` therefore rewrote the file to the tag form, the test rejected it, and the run ended in a conflict:

```text
[failed] quokkify/skills: Copier produced conflict files: .github/workflows/release.yml.rej
```

This repository was the only public consumer the fleet automation could no longer update; the other consumers all reference the toolkit by tag and update unattended.

The requirement the test encoded was also stricter than the contract the toolkit itself enforces. The template-owned check in `.github/workflows/validate.yml` accepts either form:

```python
pinned_release = len(reference) == 40 and all(char in "0123456789abcdef" for char in reference) and comment == answers["toolkit_version"]
if reference != answers["toolkit_version"] and not pinned_release:
    raise SystemExit(f"{path} uses toolkit {reference}, expected {answers['toolkit_version']}")
```

Two divergences travelled with the pin. The file predated the template's `release_mode` answer, so it carried a hand-written manifest configuration, a `workflow_dispatch` trigger, and a concurrency group that the rendered file did not have.

## Decision

Reference `quokkify/project-toolkit` by its exact release tag, and let the template own `release.yml` in full.

The unit test now applies the toolkit's own contract rather than a narrower one: the reference identifies the toolkit release workflow at the answered `toolkit_version`, either as that exact tag or as a full 40-character digest whose comment names that tag. Both forms pass, so a future decision to re-pin by hand does not require another test change.

`release_mode: manifest` is recorded in `.copier-answers.yml`, so the template renders this repository's manifest configuration instead of the single-version default, and the workflow is aligned with the rendered shape — the template's workflow name, trigger, and concurrency group. The template update to `v2.19.0` is applied in the same change, which consumes the one-time transition conflict; subsequent updates apply cleanly and change nothing but the version.

## Consequences

This is a real loosening of supply-chain strictness, and it is the cost of the decision rather than an oversight. A tag is mutable: whoever can move `v2.19.0` in `quokkify/project-toolkit` can change what this repository executes at release time, without a commit here. A digest cannot be moved.

What limits that exposure is ownership, not the pin. The toolkit is a first-party repository in the same organization, its release tags are never rewritten by policy, and third-party actions inside it remain digest-pinned. The tag is trusted here in the same way and to the same degree as the template that renders it, which this repository already executes on every push.

In exchange, `release.yml` stops being a file that automation and this repository take turns rewriting. Template updates land unattended, and the divergence that made every update conflict is gone rather than merely re-resolved.

## Alternatives considered

### Keep the digest and own the release workflow outright

Set `release_please: false` and maintain the release workflow under a project-owned filename, the way `q4j` does.

- Benefits: keeps the immutable pin; makes the existing divergence honest instead of leaving a template-owned file that automation keeps fighting; upstream fleet automation deliberately leaves digests in project-owned files alone rather than downgrading them.
- Costs and risks: the release workflow is maintained by hand indefinitely and stops receiving template fixes; it drifts from the five other consumers; the repository accepts permanent maintenance to protect one line.
- Why it was not selected: the strictness it buys is small next to the trust already extended to the template, and the maintenance it costs is unbounded.

### Keep the digest and re-enable Renovate for `release.yml`

- Benefits: no test change; the digest survives.
- Costs and risks: restores exactly the double ownership the shared preset was introduced to end. Renovate moves the pin, the next `copier update` lands on the moved pin, and the conflict returns in a file this repository never edited.
- Why it was not selected: it reintroduces a resolved problem to preserve a side effect.
