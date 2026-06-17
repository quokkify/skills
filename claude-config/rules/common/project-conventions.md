# Project Conventions

## Java

- Use `Objects.isNull(x)` / `Objects.nonNull(x)` instead of `x == null` / `x != null`

## Skill / agent placement

- Skills and agents go in **project-local** `.claude/skills/` or `.agents/`
- Do NOT place them in the global `~/.claude/skills/` or `~/.claude/agents/` unless they are explicitly user-global
- Project-local files take precedence and keep configuration co-located with the code

## Renovate presets

- New presets affecting multiple repos must be **opt-in** (separate preset file)
- Do NOT modify shared `maven/default.json` or any shared default preset directly
- Always declare blast radius (which repos/projects are affected) before pushing
- For shared infra changes: create as DRAFT MR first, validate on a canary repo before marking ready

## Shell scripts in CI

CI runners often use Alpine/busybox, not GNU coreutils:
- Use POSIX-compatible date and shell syntax only
- No GNU-only flags (e.g., `date -d @timestamp` is GNU-only)
- Test on busybox before assuming portability
- Watch out for: `date` formatting, `find` extensions, `sed -i` syntax differences
