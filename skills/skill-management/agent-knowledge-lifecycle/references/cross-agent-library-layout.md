# Cross-Agent Skill Library Layout

## Recommended repository shape

Use a neutral canonical directory and keep runtime-specific files outside it:

```text
skills/
  <category>/
    <skill-name>/
      SKILL.md
      references/
      templates/
      scripts/
adapters/
  claude/
  codex/
  hermes/
docs/
scripts/
tests/
```

`skills/` is the only source of truth for portable skill bodies. `adapters/` contains only configuration or instructions that cannot be portable; never copy full skill bodies there.

## Runtime discovery paths

Verify current upstream documentation before changing paths. As of the validated layout:

- Claude Code project skills: `.claude/skills`; personal skills: `~/.claude/skills`.
- Codex repository skills: `.agents/skills`; personal skills: `$HOME/.agents/skills`. Do not invent `.codex/skills` as a project skill location.
- Hermes: point `skills.external_dirs` directly at the canonical `skills/` directory.

These are consumer discovery locations, not additional tracked sources of truth. Prefer the runtime's installer or locally generated links. If repository policy rejects symlinks, do not weaken it merely to track native discovery directories.

## Migration checklist

A root-level-to-`skills/` move is an integration migration even when file contents are unchanged:

1. Move each skill to `skills/<category>/<name>/SKILL.md` without changing its body in the same commit unless required.
2. Move tool-specific files to `adapters/<runtime>/` and update installer source paths.
3. Make the validator reject `SKILL.md` outside the canonical `skills/<category>/<name>/SKILL.md` layout (wrong depth, missing category grouping, or extra nesting) and canonical directories missing uppercase `SKILL.md`.
4. Update test fixtures used by sync/security tests; otherwise the validator change can make unrelated safety tests fail for the wrong reason.
5. Add installer regression tests using temporary HOME/target directories so real user configuration is untouched.
6. Run the actual ecosystem discovery command in list-only mode and assert the exact skill count; structural validation alone does not prove installer discovery.
7. Update Hermes from `<checkout>` to `<checkout>/skills`, verify the parsed configuration, start a fresh session, and load a skill plus one support file from the expected path.
8. Document the one-time migration and clarify that copied adapter files require their installer to be rerun.
9. Build docs, check local links, run staged-snapshot validation, ShellCheck, and redacted full-history secret scanning on the exact final head.
10. Treat a pre-1.0 layout migration as a feature/minor release rather than hiding it in an incidental patch.

## Safe-sync compatibility

A fail-closed updater may validate a new layout using the currently trusted validator from the old checkout. Before merge, prove that the old validator accepts the candidate layout enough to complete the update, while the new validator enforces the stricter invariant after migration. Do not solve compatibility by executing fetched validation code.

The updater must continue to:

- validate one exact fetched OID with a preserved trusted validator;
- avoid executing fetched scripts or hooks;
- allow fast-forward only;
- recheck branch, clean state, and exact OID around update;
- fail rather than claim success after concurrent movement.

## Documentation structure

Keep the main README scan-friendly:

1. one-sentence purpose;
2. canonical repository tree;
3. quick start per runtime;
4. available skills;
5. safe update and migration note;
6. validation/security summary;
7. links to detailed guides.

Move cost-routing details, ecosystem-specific orchestration, and extended troubleshooting into guides/FAQ instead of deleting useful information.

## Release and review details

- Inspect generated changelog links: references to pull requests must use `/pull/<number>`, not `/issues/<number>`.
- Verify the release PR's exact final head after any changelog correction.
- Use an independent review against the exact commit, not only an earlier uncommitted snapshot.
- Keep architecture migration, release generation, and unrelated runtime installation in separate focused PRs.
