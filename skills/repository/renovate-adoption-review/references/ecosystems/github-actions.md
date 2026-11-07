# GitHub Actions

## Where to look in the update

- Release notes and CHANGELOG of the action between the two tags: "deprecated", "removed", "renamed", "default changed", "node", "breaking".
- Tag-to-tag diff of `action.yml` (or `action.yaml`): added, removed or renamed `inputs` and `outputs`, `deprecationMessage` on inputs, changed `default:` values, `runs.using` (node runtime), and for composite actions the `runs.steps` that changed.
- Migration documents in the action repository (`UPGRADING`, `MIGRATION`, a "v<N> changes" README section).

## Consumer files to grep

- `.github/workflows/*.yml`, `.github/workflows/*.yaml`, local composite actions under `.github/actions/**/action.yml`.
- Search for `uses: <owner>/<repo>@`, then every `with:` key and every `steps.<id>.outputs.<name>` reference to that step.
- Comments naming the old major (`# v3`) next to SHA pins.

## Local warning command

- `actionlint` over the workflows; it reports unknown inputs once the action metadata changes.
- Workflow run annotations on the Renovate PR's checks: deprecation warnings for inputs and node runtimes appear there.

## Typical adoptable patterns

- An input marked deprecated with a documented replacement input: rename it.
- A step that worked around missing behavior (manual cache step, separate setup step, shell script computing a value) that the new version now does through a documented input or by default.
- An explicit `with:` value equal to the new documented default: remove it only if the source states the default.
- An output renamed: update every `steps.<id>.outputs.<old>` reference.
- Version comments next to SHA pins naming the old version.

## Typical false positives

- Node runtime changes inside the action: no consumer edit unless the action documents a consumer-side requirement (self-hosted runner version, for example).
- New optional inputs that do not replace anything the consumer does today.
- Inputs that look similar to the consumer's but belong to another action.
- Workflows rendered by the ci-kit template: report under "Belongs in ci-kit".
- Replacing a SHA pin with a tag or the reverse: the pin policy belongs to the repository, not to this review.
