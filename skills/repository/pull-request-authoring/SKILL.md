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

1. **The type says where the change lands.** Nothing is hidden; the type only picks the section:
   - any `!` title: Breaking changes, listed first and not repeated elsewhere;
   - `feat`: New; `fix`: Fixed; `perf`: Faster; `revert`: Reverted;
   - dependency bumps: Updated (Fixed when the bump is a security fix);
   - `deps`, `chore`, `ci`, `test`, `build`, `docs`, `style`, `refactor`: a collapsed "Internal changes" list.
2. **Labels.** `release-notes: internal` demotes a `feat` or `fix` that only maintainers notice to Internal changes; the type is kept, so the version bump is unchanged. `release-notes: title-only` says the title already tells the whole story and replaces the required release note. Neither label removes a breaking change from the Breaking section or the need for `## Migration`.
3. **The title is the headline.** Format `type(scope): summary`. The scope is always required by the check, and `!` goes before the colon for a breaking change. Keep it to at most 72 characters (a warning when longer). Style advice, not enforced: lower-case subject, present or imperative tense, no trailing full stop. Say what the user notices: the new capability, or the symptom that is gone. Name things the user knows (an action, input, command, task), never files, functions, helpers, or the mechanism. Test: would a user who never saw the diff understand it?
4. **`## Release note`** is required for `feat`, `perf`, and any `!` title (a waiver label above replaces it). It is encouraged for `fix`: without it a fix is published with its title only. One paragraph of at most 300 characters: what the user can do now, or what was broken and how it showed up, plus the input, flag, or step to use. No headings, no lists, no `<details>`/`<summary>` markup, and do not repeat the title. The full note is never truncated: it is printed on one line after the title. A fenced code block inside it is lifted out and shown as an indented block under the entry.
5. **`## Migration`** is required for any `!` title, whatever the type (`chore(x)!:` included). Numbered steps the user must take. If users need to do nothing, the change is not breaking: drop the `!`.
6. **`## Usage example`** is optional: one short fenced snippet that can be copied. It is published under the entry whatever the type. A `## Migration` on a non-breaking PR is published too.
7. **Headings** must be level 2 (`## `), outside code fences. Aliases the check accepts: `## Breaking change` or `## Breaking changes` for Migration, and the legacy `## Highlight` for Release note. A repeated heading is ignored after its first use; empty sections and HTML comments do not count.
8. **Order is a convention, not checked.** The template puts the publishable sections first first (`## Release note`, `## Usage example`, `## Migration`), then reviewer sections (Summary, Design, Verification, audit tables), which are never published. Fill the publishable ones before writing the long review text.
9. **Limits are warnings, enforcement may be staged.** These only produce warnings: a title over 72 characters; a title containing a file name with an extension, `x()`, a snake_case or camelCase word; a release note over 300 characters, with more than one paragraph, or with a list; a heading in the note; `<details>`/`<summary>` markup in any published section. Missing required sections fail the check, but in warn mode they are reported as warnings and the check stays green; treat them as failures anyway. Bot-authored PRs are exempt.
10. **Fix the source, not the output.** If the release PR is regenerated from merged PRs, correct a wrong note by editing the merged PR's title, body, or labels. Never hand-edit the generated release PR.

## Before and after

All examples are fictional.

| Before (fails or describes the mechanism) | After (describes what the user notices) |
|---|---|
| `fix(report): fail when results are not at the artifact root` | `fix(report): fail instead of publishing an empty report` |
| `fix(actions): escape workflow commands in error output` | `fix(actions): stop file names from injecting workflow commands` |
| `feat: check non-empty scopes of main and test rules` (fails: no scope, and names the mechanism) | `feat(rules): run rules on modules that have no tests` |

Body for the first row:

```markdown
## Release note

Results nested below the artifact root (for example `**/build/results`) used to produce a green report with 0
tests. The publish step now fails and names the nested directories. Upload one results directory per component
at the artifact root.

## Summary

The collector globbed only the root; it now walks nested paths and errors on any match.
```

Breaking change (published under Breaking changes, with the note as the headline and the steps as the migration, whatever the type):

```markdown
fix(cli)!: require --config for every command

## Release note

Commands no longer read `./settings.toml` implicitly. Pass `--config <path>` explicitly.

## Migration

1. Add `--config settings.toml` to every scripted invocation.
2. Remove any reliance on the current working directory for configuration.
```

## Verification checklist

- Type matches the audience and the section it should land in.
- Title is at most 72 characters, has no file or function names, and reads as a user-visible headline.
- `feat`, `perf`, and `!` titles have a non-empty `## Release note` (or a waiver label); a `fix` has one when users need to know how it showed up. It is one paragraph of at most 300 characters; an HTML comment from the template does not count.
- A `!` title has numbered `## Migration` steps, even with a waiver label.
- Maintainer-only changes use a maintainer type or `release-notes: internal`.
- Publishable sections come before reviewer sections.
- Template placeholders and comments for unused sections are deleted.
- After editing a title or body, re-check that the PR-contract check re-ran against the current text.
