# Claude Code

Claude Code does not need a copied repository adapter. Install the canonical skills directly:

```bash
npx skills add ylazakovich/skills -a claude-code
```

The skills CLI connects them to Claude Code's supported personal skill directory. For project-only use, Claude Code also discovers skills under `.claude/skills/`.

This repository intentionally does not publish global `CLAUDE.md`, sub-agent personas, output styles, status lines, or project-specific commands. Those settings are user- or project-owned and should remain outside the portable skill library.
