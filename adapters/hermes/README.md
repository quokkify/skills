# Hermes Adapter

Hermes consumes this hub read-only through `skills.external_dirs` in its `config.yaml`; see [`config.example.yaml`](config.example.yaml). Nothing here is installed by `scripts/bootstrap.sh`, and the shared lifecycle hooks are not wired into Hermes.

## Companions

Hermes requires no companion. Unlike the Claude Code and Codex adapters ([ADR-0003](../../docs/adr/0003-require-omc-and-superpowers-companions.md)), it must not load superpowers — not the `hermes plugins install obra/superpowers` plugin, and not a curated subset added through `external_dirs`. Reasons, checked against Hermes 0.22.2 and superpowers 6.4.2:

- **No gap to fill.** The bundled `software-development-lifecycle` skill already covers test-driven development, systematic debugging, code review, worktree isolation, subagent-driven development, and a verification checklist. This hub adds `agent-failure-recovery` and `ai-assisted-regression-testing`.
- **Triggers over-fire.** The skill index truncates descriptions to 60 characters (`SKILL_PROMPT_DESC_LIMIT`). A long superpowers `Use when…` description loses its qualifiers, so test-driven development fires on config edits, ops scripts, and chat turns, not only on feature work.
- **Subsets break.** `writing-plans` and `executing-plans` require `subagent-driven-development` and its scripts. A hand-picked set without it fails partway through.
- **Pins drift.** Hermes can patch skills it loads from external directories. Through a symlinked checkout, those patches edit the pinned superpowers clone in place.
- **Bootstrap fades.** The plugin injects its bootstrap only on the first turn, and Hermes has no post-compaction hook, so long messenger sessions lose it after compaction.

If one superpowers idea proves worth having, fold it into an existing Hermes skill or a hub skill with a short, specific description instead of loading the companion.

## Skill discovery

- Point `external_dirs` at this checkout's `skills/` directory. Hermes walks it recursively and follows symlinks.
- A same-named profile-local skill takes precedence over the shared copy, so make shared changes on an isolated branch or worktree.
- Start a new Hermes session after changing the discovery path; a gateway restart is not needed.
- Each profile has its own `config.yaml` and its own `external_dirs`. A profile that should see the hub needs the entry itself; an empty list there is a deliberate opt-out, not an inherited default.
- Keep the clone current with `scripts/sync-shared-skills.sh` on a schedule, for example a daily user-level systemd timer. It fast-forwards `main` only and validates the fetched snapshot before switching to it. Running sessions keep the old skills until a new session starts.
