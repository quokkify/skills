---
name: pull-request-authoring
description: Use before opening or editing any pull request in a Conventional Commits repository or one that builds release notes from merged PRs, to write a user-facing title and a publishable Release note section.
---

# Pull Request Authoring

When a repository generates release notes from merged pull requests, the title and a few named body sections are published. Everything else is for reviewers. Write the publishable parts for someone who never sees the diff.

## When to load

- Before every `gh pr create`, `gh pr edit`, or equivalent forge action.
- When retitling or fixing a merged PR whose release note reads badly.
- When a PR-contract or title check fails.

## Precedence

Read the repository's PR template, contribution guide, and agent instructions first. If they define release sections, labels, or length limits, they win over the defaults below.

## Rules

1. **The type says who the change is for.** `feat`, `fix`, `perf`, and `revert` are visible to users and appear in release notes. `deps`, `chore`, `ci`, `test`, `build`, `docs`, `style`, and `refactor` are for maintainers and are collapsed or hidden. A `fix` that only maintainers notice keeps its type (it still bumps the version); add the repository's escape-hatch label (commonly `release-notes: internal`) instead of changing the type.
2. **The title is the headline.** Format `type(scope): summary`, at most 72 characters, lower case, present or imperative tense, no trailing full stop. Keep a scope if the repository requires one. Say what the user notices: the new capability, or the symptom that is gone. Name things the user knows (an action, input, command, task), never files, functions, or helpers, and never the mechanism. Test: would a user who never saw the diff understand it?
3. **`## Release note`** is required for `feat`, `fix`, and `perf`, and optional otherwise. One paragraph of at most 300 characters: what the user can do now, or what was broken and how it showed up, plus the input, flag, or step to use. No headings, no lists, and do not repeat the title.
4. **`## Migration`** is required when the title has `!`. Numbered steps the user must take. "Opt-in, no action needed" is not a migration; say that in the release note.
5. **`## Usage example`** is optional for `feat`: one short fenced snippet that can be copied.
6. **Order matters.** Put the publishable sections first (`## Release note`, `## Usage example`, `## Migration`), then reviewer sections (Summary, Design, Verification, audit tables). Fill the publishable ones before writing the long review text.
7. **Fix the source, not the output.** If the release PR is regenerated from merged PRs, correct a wrong note by editing the merged PR's title, body, or labels. Never hand-edit the generated release PR.

## Before and after

All examples are fictional.

| Before (describes the mechanism) | After (describes what the user notices) |
|---|---|
| `fix(report): fail when results are not at the artifact root` | `fix(report): fail instead of publishing an empty report` |
| `fix(actions): escape workflow commands in error output` | `fix(actions): stop file names from injecting workflow commands` |
| `feat: check non-empty scopes of main and test rules` | `feat(rules): run rules on modules that have no tests` |

Body for the first row:

```markdown
## Release note

Results nested below the artifact root (for example `**/build/results`) used to produce a green report with 0
tests. The publish step now fails and names the nested directories. Upload one results directory per component
at the artifact root.

## Summary

The collector globbed only the root; it now walks nested paths and errors on any match.
```

Breaking change:

```markdown
fix(cli)!: require --config for every command

## Release note

Commands no longer read `./settings.toml` implicitly. Pass `--config <path>` explicitly.

## Migration

1. Add `--config settings.toml` to every scripted invocation.
2. Remove any reliance on the current working directory for configuration.
```

## Verification checklist

- Type matches the audience; maintainer-only changes use a maintainer type or the escape-hatch label.
- Title is at most 72 characters, has no file or function names, and reads as a user-visible headline.
- `feat`, `fix`, and `perf` have a non-empty `## Release note` of one paragraph and at most 300 characters (an HTML comment from the template does not count).
- A `!` title has numbered `## Migration` steps.
- Publishable sections come before reviewer sections.
- Template placeholders and comments for unused sections are deleted.
- After editing a title or body, re-check that the PR-contract check re-ran against the current text.
