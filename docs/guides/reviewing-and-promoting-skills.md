---
title: Reviewing and Promoting Skills
---

# Reviewing and Promoting Skills

The `skill-review` workflow turns reusable lessons into reviewable skill changes without publishing local agent state automatically.

## When to use it

Use the workflow after significant work when a procedure, correction, workaround, or missing instruction would help with future tasks. Skip routine operations, temporary progress, one-off facts, and project-specific rules.

## Promotion flow

```text
significant task
    -> classify the lesson
    -> search existing skills
    -> private candidate
    -> privacy and portability audit
    -> task approval or durable repository opt-in
    -> branch or worktree
    -> validation and secret scan
    -> pull request
    -> normal review and merge
```

A candidate is not a published skill. Keep it outside the shared repository until promotion is approved or an applicable durable draft-queue opt-in is verified.

## Optional rolling draft queue

A repository owner may pre-authorize completed, public-safe improvements to accumulate in a rolling draft pull request. Configure one `automation/skill-improvements/<lane>` branch per device or independently running agent and use `skill-promotion-queue` as the completion workflow.

This opt-in replaces repeated publication prompts only. It does not authorize direct pushes to the default branch, force-push, automatic merge, or publication of private runtime state. The agent must still perform the privacy and portability audit, deterministic validation, and configured secret scanning. Independent review may be deferred until the owner handles the batch.

## Decisions

Every review ends with one of three decisions:

- `patch-existing`: an existing skill already owns the workflow;
- `create-new`: the workflow is reusable and has no suitable owner;
- `no-change`: the lesson is duplicated, private, temporary, or too narrow.

Prefer patching an existing broad skill over creating a one-incident micro-skill.

## Public boundary

Before promotion:

1. Remove credentials, identities, private paths, internal URLs, infrastructure details, client context, and raw transcripts.
2. Replace real values with fictional placeholders.
3. Confirm that the procedure remains useful outside the task that produced it.
4. Review the complete diff and untracked files.
5. Run `./scripts/validate.sh --full`; it performs repository validation, builds the documentation, and scans the full Git history with Gitleaks.

See the repository [SECURITY.md](https://github.com/ylazakovich/skills/blob/main/SECURITY.md) for the complete public-content policy.

## Tool behavior

### Claude Code and Codex

Install the repository skills normally. In Claude Code, invoke the installed `skill-review` skill when significant work produces a reusable lesson; this repository publishes no global Claude prompt that does so automatically. The optional Codex `AGENTS.md` adapter adds a post-task review prompt. By default, promotion requires task-specific approval before a branch or pull request is created. A durable repository-scoped opt-in may instead route eligible changes through `skill-promotion-queue`.

### Hermes

Hermes can discover this repository through `skills.external_dirs`:

```yaml
skills:
  external_dirs:
    - /absolute/path/to/skills/skills
```

Point the setting at the canonical `skills/` directory. Restart Hermes or begin a new session after changing skill discovery settings.

External directories are not read-only. If the Hermes process can write to the checkout, skill-management tools can modify it. Treat the checkout as a shared Git source: inspect skills with `skills_list` and `skill_view`, but make approved updates in an isolated branch or worktree rather than patching the external directory in place.

If a local Hermes skill and an external skill have the same name, the local skill takes precedence. Resolve that conflict before assuming the shared version is active.

## Candidate format

The bundled `skills/skill-management/skill-review/templates/candidate.md` template records:

- the reusable trigger;
- the target skill or proposed name;
- generalized evidence;
- the proposed change;
- pitfalls and verification;
- privacy and portability checks;
- the promotion plan and approval state.

Do not commit a filled candidate merely to preserve task history. Only the approved, generalized skill change belongs in the public repository.
