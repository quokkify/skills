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

This repository instead held a 40-character commit digest with the tag as a trailing comment, and `tests/test_release_configuration.py` required that form. The digest never came from the template, and it never came from Renovate either: every digest that line has ever carried was written by hand while reconciling a template update, and no automated commit has ever touched the file. The test encoded a convention that only manual reconciliation had been sustaining.

That reconciliation ended. The shared preset now disables Renovate for the workflow paths the template owns, `release.yml` among them, so that a project-side pin and a template-side pin cannot fight over the same line — and the template update automation applies the rendered file unattended rather than pausing for a human to re-pin it. Each `copier update` therefore rewrote the file to the tag form, the test rejected it, and the run ended in a conflict:

```text
[failed] quokkify/skills: Copier produced conflict files: .github/workflows/release.yml.rej
```

This repository was the last public consumer the fleet automation could not update on the current template; the consumers that call the toolkit's release workflow all reference it by tag and update unattended.

The requirement the test encoded was also stricter than the contract the toolkit itself enforces. The template-owned check in `.github/workflows/validate.yml` accepts either form:

```python
pinned_release = len(reference) == 40 and all(char in "0123456789abcdef" for char in reference) and comment == answers["toolkit_version"]
if reference != answers["toolkit_version"] and not pinned_release:
    raise SystemExit(f"{path} uses toolkit {reference}, expected {answers['toolkit_version']}")
```

Divergences travelled with the pin. The file predated the template's `release_mode` answer, so it carried a hand-written manifest configuration, and it had also drifted in its workflow name, its `workflow_dispatch` trigger, and its concurrency group.

## Decision

Reference `quokkify/project-toolkit` by its exact release tag, and let the template own `release.yml` in full.

The unit test now applies the toolkit's own contract rather than a narrower one: a reference identifies the toolkit release workflow at the answered `toolkit_version` when it is either that exact tag or a full 40-character digest whose comment names that tag. Both forms pass, so a future decision to re-pin by hand does not require another test change.

`release_mode: manifest` is recorded in `.copier-answers.yml`, so the template renders this repository's manifest configuration instead of the single-version default, and the workflow is aligned with the rendered shape in every other respect. The template update to `v2.19.0` is applied in the same change, which consumes the one-time transition conflict; subsequent updates apply cleanly and change nothing but the version.

## Alternatives considered

### Keep the digest and own the release workflow outright

Stop rendering `release.yml` from the template, and maintain the release workflow under a project-owned filename. `q4j` is the closest precedent in the organization: it keeps a project-owned `release-please.yml` and no rendered `release.yml`, though it goes further than this alternative would by calling `googleapis/release-please-action` directly rather than the toolkit's reusable workflow.

- Benefits: keeps the immutable pin; makes the existing divergence honest instead of leaving a template-owned file that automation keeps fighting; upstream fleet automation deliberately leaves digests in project-owned files alone rather than downgrading them to tags.
- Costs and risks: the release workflow is maintained by hand indefinitely and stops receiving template fixes; it drifts from the other consumers; the repository accepts unbounded maintenance to protect one line.
- Why it was not selected: the strictness it buys is small next to the trust already extended to the template, and the maintenance it costs does not end.

### Keep the digest and re-enable Renovate for `release.yml`

Restore the digest and let Renovate re-pin the rendered tag after each template update, which is the arrangement the file's history had always approximated by hand.

- Benefits: no test change; the digest survives without manual reconciliation.
- Costs and risks: creates exactly the double ownership the shared preset was introduced to prevent. Renovate moves the pin, the next `copier update` lands on the moved pin, and the conflict returns in a file this repository never edited.
- Why it was not selected: it automates the manual step that produced the problem, rather than removing the divergence.

## Consequences

This is a real loosening of supply-chain strictness, and it is the cost of the decision rather than an oversight. A tag is mutable: whoever can move `v2.19.0` in `quokkify/project-toolkit` can change what this repository executes at release time, without a commit here. A digest cannot be moved.

What limits that exposure is ownership, not the pin. The toolkit is a first-party repository in the same organization, its release tags are never rewritten by policy, and third-party actions inside it remain digest-pinned. The tag is trusted here in the same way and to the same degree as the template that renders it, which this repository already executes on every push.

In exchange, `release.yml` stops being a file that automation and this repository take turns rewriting. Template updates land unattended, and the divergence that made every update conflict is gone rather than merely re-resolved.
