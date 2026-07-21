---
name: agent-knowledge-lifecycle
description: "Use when sharing, evolving, securing, synchronizing, or backing up reusable skill libraries across multiple agent runtimes."
---

# Agent Knowledge Lifecycle

## Overview

Manage reusable agent knowledge as a curated software artifact rather than an undifferentiated runtime dump. Separate portable skills from private operational state, let multiple agent runtimes consume one canonical library, promote new knowledge through reviewable changes, and keep recovery backups private and independently restorable.

## When to Use

- Claude Code, Hermes, Codex, or another agent should share one skill library.
- The user asks whether agent configuration belongs in one repository or several.
- Agent-created skills need promotion, synchronization, review, or consolidation.
- A public skill repository must be separated from a private migration vault.
- GitHub credentials, secret scanning, or automated skill-repository maintenance are being configured.

## Core Model

Use one canonical repository for the **shared skill system**, with portable skills in a neutral `skills/<category>/<name>/SKILL.md` tree and tool-specific adapters alongside them. Treat `.claude/skills`, `.agents/skills`, Hermes external directories, and similar runtime paths as consumer discovery locations—not additional tracked sources of truth. Keep a second private repository only when it has a genuinely different role: disaster recovery for the full agent installation.

This distinction avoids two opposite failures:

- duplicating the same portable skills across agent-specific repositories until they drift;
- publishing private memory, runtime state, credentials, or client-specific context merely because the public skills need synchronization.

## Workflow

### 1. Classify the artifact

Put broadly reusable procedures, references, templates, and deterministic scripts in the shared skill repository. Put sanitized runtime configuration, memory, cron definitions, service metadata, local-only plugins, and consistent database snapshots in the private vault. Keep credentials outside both.

### 2. Establish one source of truth

Let each agent runtime consume the canonical `skills/` tree through its supported external directory, installer, generated link, plugin, or project-instruction adapter. Verify current upstream discovery conventions instead of guessing from dot-directory names: Claude Code and Codex do not use interchangeable project paths. Tool-specific files may coexist under `adapters/<runtime>/`, but portable skill bodies must not be copied there or depend on one runtime unless clearly isolated behind an adapter.

When moving an established library from root-level skills into `skills/`, treat it as an integration migration: update validators, installer sources, sync fixtures, documentation, and every runtime's configured discovery path. Prove nested discovery with the actual ecosystem CLI in list-only mode, not only with repository structure tests.

### 3. Promote rather than dump

Existing externally loaded skills may be updated in place. Newly generated skills often begin in a runtime-local directory; review them for overlap, broaden them to class-level scope, validate linked support files, and promote them through a branch/PR. Never auto-publish the entire local skill directory.

### 4. Create a gated feedback loop

After substantial work, look for repeated steps, corrected instructions, missing verification, reusable diagnostics, or overlapping skills. Skip routine work, temporary state, and one-off facts.

Classify the lesson before changing files:

- user preferences belong in the governing skill when they change how that task class should be handled;
- stable facts about the user or environment belong in memory;
- project-only conventions belong in project context;
- reusable procedures, pitfalls, verification, templates, or scripts belong in a skill.

Search the active skill catalog before proposing a target. Prefer patching a class-level umbrella or adding a support file over creating a narrow skill. Verify availability through each runtime's skill discovery mechanism; a skill name is not a shell command and must not be checked with `PATH` lookup.

Prepare a private candidate before touching the canonical repository. It should name the target, summarize the reusable lesson and supporting evidence without raw transcripts, explain the proposed change, record duplicate-search findings, and include privacy, portability, and validation checks. Use `templates/skill-improvement-candidate.md` as the starting shape. Keep filled candidates outside the public repository or present them inline.

A review trigger is not approval to publish. Do not create a promotion branch, push, or open a PR solely because a review found a lesson. Present the candidate and obtain task-specific approval first unless the repository owner has already declared a durable, repository-scoped draft-queue opt-in. After approval or verified opt-in, use an isolated branch or worktree, validate the exact diff, run the required secret scan, open or update the authorized PR, and leave merge to the human or repository policy. Use `skill-promotion-queue` when independent review is intentionally deferred into a later batch.

### 5. Secure repository automation

Use a dedicated fine-grained repository token with minimum permissions, stored outside repositories in a protected env file. Validate account and repository permission without printing the token. Do not overwrite unrelated global GitHub authentication or embed credentials in remotes.

### 6. Add layered secret protection

Begin with CI secret scanning on PRs and the default branch, then add local/pre-commit checks and repository policy only as separate reviewable steps. Pin third-party actions, scan full history where intended, disable checkout credential persistence, and keep workflow permissions minimal.

### 7. Verify restoration and synchronization

The private vault should record the canonical skill repository URL, branch, and exact revision, then reclone it during restore. Verify that local changes are pushed before backup completion. Do not treat a same-provider repository as an independent off-site backup unless a second recovery copy exists.

For detailed repository layout, GitHub token enrollment, and the first secret-scanning PR, see `references/shared-skill-repository-and-vault.md`. For a neutral `skills/` + `adapters/` architecture, runtime discovery paths, migration checks, safe-sync compatibility, and README structure, see `references/cross-agent-library-layout.md`.

## Common Pitfalls

- Saying “one repository” without distinguishing the shared knowledge product from the full private runtime backup.
- Using a migration vault as the editable canonical skill library.
- Automatically copying `~/.hermes` or `~/.claude` into a public repository.
- Assuming external skill directories capture newly agent-created skills automatically.
- Duplicating canonical skills into snapshots instead of recording their repository revision.
- Asking the user to paste tokens into chat or storing PATs in Git remotes.
- Replacing global `gh` authentication when only one automation repository needs a scoped token.
- Trusting a secret-scanning workflow without a real baseline scan and current-head CI result.
- Leaving checkout credentials persisted in a scan-only job.
- Treating a skill name as a shell executable or checking availability through `PATH` instead of the runtime's skill catalog.
- Describing Claude, Codex, and Hermes as if they share one installation path; document each adapter separately.
- Creating `.codex/skills` by analogy; verify current runtime docs—Codex repository skills use `.agents/skills`, while Claude Code project skills use `.claude/skills`.
- Tracking duplicate native discovery trees or weakening a symlink ban to mirror one canonical skill library; use installers or generated local links instead.
- Moving skills into a nested canonical directory without updating Hermes `external_dirs`, installer sources, sync-test fixtures, and real CLI discovery checks.
- Rewriting a README for brevity by deleting useful cost-routing or ecosystem behavior instead of moving detail into guides and FAQ.
- Committing a filled review candidate that contains task evidence, raw transcripts, or private context.
- Creating a branch or PR as an automatic side effect of post-task review without task-specific approval or a durable repository-scoped draft-queue opt-in.
- Saying only “run Gitleaks” when the gate requires an explicit full-history scan.
- Passing JSON-looking array text to a scalar configuration command and assuming it became a real YAML list; use a plain path for one external directory or a supported typed/list edit, then verify the parsed value resolves to an existing directory.
- Treating a successful configuration write as discovery proof; verify the canonical skill by bare name, load one linked support file, and confirm the expected source path.
- Giving a normal documentation file the same basename as a skill; some resolution paths inspect Markdown stems beyond `SKILL.md`, so keep guide names distinct and test bare-name loading.
- Merging a generated release PR without reading its changelog; conventional inner commits and merge commits can produce duplicate entries, and generated PR references can incorrectly point to `/issues/<n>` instead of `/pull/<n>`.
- Treating an independent review of an earlier uncommitted snapshot as final review; rerun or reconcile review against the exact pushed commit after late documentation and test changes.
- Treating secret-scanner success as a complete public-boundary audit; broad legacy PRs can still expose project-specific context, stale private conventions, or broken references.

## Verification Checklist

- [ ] Shared skill repository and private vault have distinct documented responsibilities.
- [ ] Portable skills contain no personal memory, transcripts, secrets, or private project details.
- [ ] Every agent runtime resolves the same canonical skill versions.
- [ ] Portable skills live once under a documented canonical directory; adapters contain no copied skill bodies.
- [ ] Runtime-specific discovery paths were verified against current docs and with a real list-only discovery command.
- [ ] Layout migrations update external-directory configuration, installer sources, regression fixtures, README migration notes, and copied-adapter guidance.
- [ ] The currently trusted pre-migration validator can safely accept the candidate layout without executing fetched code, and the new validator enforces the stricter layout afterward.
- [ ] New local skills have a deliberate promotion path with overlap review.
- [ ] Review candidates summarize supporting evidence without raw transcripts and remain private until approved.
- [ ] Skill availability is verified through runtime discovery, not shell-command lookup.
- [ ] Promotion branches and PRs are created only after task-specific approval or a verified durable repository-scoped draft-queue opt-in.
- [ ] Vault records the canonical repository URL, branch, and exact revision.
- [ ] Repository token is fine-grained, minimally scoped, and stored outside repositories with restrictive permissions.
- [ ] Secret scanning runs on PRs and default-branch pushes with pinned actions and least privilege.
- [ ] Local and CI scans pass on the exact PR head.
- [ ] Reviewer findings are fixed or explicitly triaged before the repository is declared clean.
- [ ] External-directory configuration is parsed as the intended path/list and every directory exists.
- [ ] A canonical external skill loads by its bare name and at least one bundled reference/template loads from the expected repository path.
- [ ] Documentation filenames do not collide with canonical skill names in runtime resolution.
- [ ] Generated release notes contain one curated entry per semantic change, and release checks ran on the final edited head.
- [ ] Broad legacy changes received both secret scanning and a manual public-boundary review before merge, closure, or decomposition.
