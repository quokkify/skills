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

### User/project-owned state

Keep outside the shared library when any of these appear:

- global `CLAUDE.md` or equivalent personal behavior configuration;
- junior/middle/senior personas or hard-coded model tiers;
- status lines, themes, output styles, personal aliases;
- fixed IDE/MCP tool names unavailable to other users;
- package namespaces, modules, stack versions, domain paths, client terminology;
- commands meaningful only inside one project.

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
