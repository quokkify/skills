# Adapter Boundary Checklist

Use this before moving legacy agent configuration into a shared repository layout.

## Classify Each Candidate

### Portable skill

- Uses standard `SKILL.md` frontmatter and tool-neutral instructions.
- Describes a reusable procedure rather than a model persona or one repository.
- Keeps support material under its own `references/`, `templates/`, `scripts/`, or `assets/`.

### Thin adapter

- Exists only because an agent has a distinct configuration or instruction format.
- Points to canonical skills or supplies minimal tool-specific setup.
- Does not copy skill bodies, prescribe private project paths, or overwrite global state without explicit action.

### Genericized global template

The global layer a runtime loads before any skill runs may be published, but only as a template. Publishable when all of these hold:

- it is *derived* from a real setup by removing the specifics, not copied from one;
- it contains no credentials, tokens, private endpoints, employer or client identifiers, personal names, or private tool names;
- every path is portable (`$HOME`, `~/.claude/...`, `~/.codex/...`, `/path/to/...`), never a machine home path;
- roles are selected by capability; no pinned model version, no hard-coded junior/middle/senior tier, no one user's routing policy presented as a default;
- values a user must supply are visibly placeholders rather than working defaults borrowed from someone's setup;
- it carries no session, transcript, memory, or runtime-database state;
- applying it is non-destructive: back up before writing, preserve managed blocks owned by other tools such as `<!-- OMC:START -->…<!-- OMC:END -->`, and never silently clobber existing configuration.

### Never publishable: real personal/employer/machine state

Keep outside the shared library when any of these appear:

- any user's actual global `CLAUDE.md`, settings file, or agent-home tree, and any part of a private overlay;
- employer conventions, project trust or allowlist entries, credentialed MCP server definitions, employer-only skills;
- fixed IDE/MCP tool names unavailable to other users;
- machine home paths, local secret-store paths, personal aliases;
- personal status lines, themes, or output styles that encode a specific environment or identity;
- package namespaces, modules, stack versions, domain paths, client terminology;
- commands meaningful only inside one project.

### Telling them apart

Apply these tests to the exact file, not to its category:

1. **Stranger test** — could an unrelated user install this file unchanged and get sane behavior? If it only makes sense for its author, it is state, not a template.
2. **Substitution test** — replace every placeholder with a different value. If the file stops making sense, a real value was baked in.
3. **Attribution test** — does any line identify a person, employer, client, repository, tracker, host, or machine? One such line disqualifies the file until it is removed.
4. **Durability test** — does it pin a model version, dated tier, or version-specific tool name? Genericize to a capability, or the template rots into bad advice.
5. **Origin test** — was this written as a template, or pasted from a working setup and then edited? Pasted files need a line-by-line read; the mechanical validator catches paths and filenames, not context.

A validator pass and a clean secret scan are necessary and not sufficient. Both are silent about employer context, private conventions, and pinned personal preferences.

## Dependency Closure After Removing Personas

Deleting a global persona bundle is incomplete if a canonical workflow still requires its names, tools, or model tiers. Review every portable `SKILL.md` and support file for:

- mandatory named roles such as `code-researcher` when the active backend may not define them;
- hard requirements for Claude-only mechanisms such as a `task` tool;
- fallback reads from removed global agent directories;
- delegation-only rules that make a workflow impossible when native subagents are unavailable;
- fixed assumptions about parallel speedups or cheapest-model tiers.

Rewrite these as capability-based role selection through the active environment. Prefer native delegation when it adds value, but provide a bounded orchestrator fallback when no suitable backend exists. Conceptual fallback role names are guidance, not a promise that the harness exposes them.

## Searches After Cleanup

Search documentation, scripts, tests, examples, canonical skills, and skill support files for:

- retired installer/script names;
- old source directories and consumer discovery paths;
- deleted persona names and global-agent fallbacks;
- mandatory tool/model/role wording unsupported by another target agent;
- machine-specific home paths;
- package namespaces, stack versions, module names, fixed `backend/**` or `frontend/**` ownership paths, and domain-document names from private projects;
- claims that configuration migration is mandatory without implementation evidence;
- docs that still advertise routing or adapter capabilities removed by the cleanup.

## Capability and Terminology Audit

Path cleanup is not enough; compare every documentation promise with the files that survive:

- distinguish a skill that a user *can invoke* from an adapter that *automatically prompts* for it;
- distinguish installation/discovery notes from configuration that actually changes runtime behavior;
- distinguish a published template from a shipped installer: describe copying as manual until the installer exists, and do not link adapter files that a concurrent change has not yet created;
- verify claims about model routing, personas, commands, hooks, status lines, and post-task actions against the surviving adapter contents;
- use current official tool names in canonical workflows (for example, a renamed delegation tool), and mention legacy names only as explicit compatibility aliases;
- after each finding-driven patch, search the entire repository for equivalent wording and review the new exact commit rather than only the originally reported lines.

## Behavioral Verification

- Run the repository validator and dependency-free tests.
- Build documentation and validate links.
- Invoke available agent/skills CLIs in list or dry-run mode to prove nested discovery.
- Smoke-test remaining installers in temporary homes/projects, including paths with spaces.
- Run shell syntax/ShellCheck and tree plus full-history secret scans.
- Re-query CI and automated review on the final exact head after every fix push.

## Review Triage

For large move diffs, distinguish:

1. New defects introduced by the layout.
2. Pre-existing content exposed by rename detection.
3. Pre-existing content whose new location now falsely endorses it as portable/shared.

Category 3 is actionable during the migration: delete or relocate it rather than mechanically preserving it.
