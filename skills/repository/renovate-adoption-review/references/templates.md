# Output templates

Fill every placeholder `<...>`. Drop a section only where marked optional; write `None.` for an empty required section. Citations are URLs, short quotes, diff hunks, or warning text.

## Child PR body (mode `review`)

```markdown
## Update

`<package>` `<from>` → `<to>` (<updateType>). Release notes: <release-notes-url>, compare: <compare-url>.
Parent: #<pr>. Merge order: this PR into `<renovate-branch>` first, then #<pr> into `<default>`.

## Applied

- **<what changed>** in `<path>`: <why>. Source: <citation>.

## Belongs in ci-kit

- **<opportunity>** in `<template-owned path>`: <why>. Source: <citation>.

## Considered, not applied

- <item>: <reason (no citation / no consumer usage / more than 10 files / checks failed: <output>)>.

## Verification

- `<command>`: <pass/fail, summary>.

## Risk

<low|medium>: <one line>.

<!-- adoption-base: <parent-head-sha> -->
```

## Parent PR comment (mode `review`)

With a child PR:

```markdown
Adoption review: <n> change(s) to adopt `<package>` `<to>` are in #<child>.
Merge order: #<child> into this branch first, then this PR.
```

Without a child PR (nothing applied or checks failed):

```markdown
Adoption review for `<package>` `<from>` → `<to>`: nothing applied.

### Considered

- <item>: <reason>. Source: <citation or "no sources">.

### Verification

- `<command>`: <result>.
```

## Retro issue (mode `retro`)

Title: `Adoption review: <range>` where `<range>` is `since <date|tag|sha>` or `last <N> updates`.

```markdown
Range: <range>. Merged Renovate PRs scanned: <count><, possibly truncated at the helper limit>.

## `<package>` `<from>` → `<to>` (<updateType>)

Source PRs: #<pr>, #<pr>. Release notes: <urls>.

- [ ] **<finding>**: source <citation>; consumer locations `<path>:<line>`; proposed change: <change>; risk <low|medium>.

## Belongs in ci-kit

- **<opportunity>** in `<template-owned path>`: source <citation>.

## Skipped

- `<package>`: <reason (triage verdict / no sources / nothing to adopt)>.
```

## Retro PR body (mode `retro --apply`)

Same sections as the child PR body, with one Update line per dependency interval and no marker:

```markdown
Closes #<issue>

## Update

- `<package>` `<from>` → `<to>` (<updateType>). Release notes: <urls>.

## Applied

- **<what changed>** in `<path>`: <why>. Source: <citation>.

## Belongs in ci-kit

- **<opportunity>** in `<path>`: source <citation>.

## Considered, not applied

- <item>: <reason>. Findings reverted after failing checks stay unchecked in #<issue> with the reason.

## Verification

- `<command>`: <result>.

## Risk

<low|medium>: <one line>.
```
