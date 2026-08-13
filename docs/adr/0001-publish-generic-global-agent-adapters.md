---
title: "ADR-0001: Publish generic global agent adapters"
---

# ADR-0001: Publish genericized global agent adapters instead of no global configuration

- Status: accepted
- Date: 2026-08-13

## Context

Until this decision, the repository documented a hard boundary in five places: no global `CLAUDE.md`, no sub-agent personas, no output styles, no status lines, and no project-specific commands. [The FAQ](../FAQ.md) additionally recorded that a former "global Claude configuration bundle" had been deliberately removed.

That boundary was correct for the artifact that existed at the time. The only global configuration available to publish was one user's real agent home: employer conventions, project trust lists, credentialed MCP server entries, employer-only skills, and absolute machine paths. Publishing it would have leaked private context, and it would not have helped anyone else, because almost none of it was portable.

Two things changed:

1. **The content can be genericized and the result can be checked mechanically.** `scripts/validate_repo.py` rejects machine-specific home paths, Windows home paths, local secret-store paths, agent-local and credential-state filenames, private runtime state directories, symlinks, and broken or repository-escaping Markdown links, on every tracked file. That converts "please review carefully" into a gate that fails a pull request.
2. **The runtimes converged.** Codex CLI 0.146 gained native hooks, subagents, and skills using the same hook JSON contract as Claude Code. A single runtime-neutral base plus thin per-runtime wiring is now genuinely portable, rather than a Claude-only bundle wearing a cross-runtime label.

Meanwhile the underlying need did not go away: a user who installs the portable skills still has to hand-build the global layer that decides what loads before any skill runs, and there was no reviewed starting point for it anywhere.

## Decision

Publish the global agent configuration layer as **templates and genericized defaults**, and keep every user's real configuration out.

The repository is organized in three layers:

1. **Shared portable skills** — `skills/<category>/<name>/SKILL.md`. Unchanged, and still the only source of truth for portable workflow knowledge. A skill body is never duplicated into an adapter.
2. **Genericized global adapters** — `adapters/shared/` holds a runtime-neutral global instruction base plus cross-runtime lifecycle hook scripts and git hooks. `adapters/claude/` and `adapters/codex/` hold per-runtime templates: settings and config templates, hook wiring, subagent definitions, and an injectable `CLAUDE.md` block.
3. **Private overlay** — the user's real content lives in a separate private repository and is merged over the templates at install time. It is not a directory inside this repository.

A published adapter must be *derived* from a real setup by removing everything specific to it, never a copy of one.

This supersedes the earlier "no global configuration is published" boundary. It does not restore the removed bundle: none of that content returns, and the removal decision remains correct for what it removed.

### What remains forbidden

- real credentials, tokens, and private endpoints;
- employer, client, and private-project identifiers, including internal repository, tracker, and CI paths;
- any person's name or personal identifiers;
- machine-specific home paths — use `$HOME`, `~/.claude/...`, `~/.codex/...`, or `/path/to/...`;
- session, transcript, memory, and runtime-database state, and raw agent-home snapshots;
- pinned personal model versions or one user's routing policy presented as a default;
- any user's actual private overlay, in whole or in part.

## Alternatives considered

### Keep the boundary and put the whole global layer in a private repository

- Benefits: zero leak surface; no new review obligation; nothing to keep in step.
- Costs and risks: the reusable part of the layer — hook contracts, capability-based subagent shapes, a neutral instruction base — stays invisible, so every consumer rebuilds it and the shared skills keep assuming a global layer that this project never shows.
- Why it was not selected: it protects content that does not need protecting, at the cost of the layer being unreviewable and unshared.

### Publish the real personal configuration

- Benefits: no genericization work; the published artifact is known to function end to end.
- Costs and risks: leaks employer context, trust lists, and machine paths; is unusable to others without editing; would be rejected by the existing validator and by the repository's `SECURITY.md` boundary.
- Why it was not selected: it is the exact failure the original removal was meant to prevent.

### Chosen: genericized templates in public, real overlay in private

- Benefits: the portable part is shared and reviewed; the private part keeps its trust boundary; the split is enforced by an existing mechanical gate.
- Costs and risks: two repositories must stay in step, and every future adapter edit needs a leak review.
- Why it was selected: it is the only option that makes the layer reusable without moving any private content into a public clone.

## Consequences

### Positive

- The global layer becomes a reviewed artifact with a public diff, instead of undocumented local state.
- Consumers get a working starting point for hooks, settings, and subagent definitions rather than a prohibition.
- One shared base serves both Claude Code and Codex, so a hook or instruction fix lands once.
- The public/private line is now written down as a rule an installer and a validator can both apply.

### Negative

- **Ongoing leak-review burden.** Every future adapter edit is a potential disclosure, and unlike a skill body it may carry settings values, tool names, or paths that look innocuous. Mitigation: `scripts/validate_repo.py` plus Gitleaks on every pull request and the default branch, and the adapter-boundary checklist in `shared-skill-library-maintenance`. Neither proves a file is appropriate to publish.
- **Two repositories to keep in step.** A template change can break an overlay that patched the same file. Mitigation: keep templates minimal and treat the overlay as authoritative on conflict.
- **Overwrite risk at install time.** Merging templates into a live agent home can clobber existing configuration. Mitigation: any installer must back up rather than overwrite, and must preserve managed blocks written by other tools, such as `<!-- OMC:START -->…<!-- OMC:END -->`. No installer ships with this decision; templates are copied manually until one lands.
- **Genericization can hide breakage.** A template with the specifics removed may no longer be a configuration that actually works. Mitigation: exercise the templates from a scratch agent home before claiming they install cleanly.

### Follow-up and review triggers

- The follow-up installer (`scripts/bootstrap.sh`) must implement backup-not-overwrite and foreign-managed-block preservation before it is documented as available.
- Revisit if the hook or settings contract diverges again between runtimes, which would make one shared base dishonest.
- Revisit if a leak reaches the public branch, or if template drift makes the overlay unmergeable: either signals that the split is in the wrong place.
- Supersede this record rather than editing it if the repository later decides to stop publishing the adapter layer.
