# Skills

This directory is the repository's only source of truth for portable skills.

Each skill is grouped under a category directory and must use this layout:

```text
skills/<category>/<skill-name>/SKILL.md
```

Categories currently in use: `orchestration/`, `skill-management/`, `repository/`, `software-development/`, `devops/`, and `games/`. Both the category and the skill name use lowercase kebab-case.

Optional support files belong inside the same skill under `assets/`, `references/`, `scripts/`, or `templates/`. Tool-specific configuration belongs in [`../adapters`](../adapters), not in a second copy of a skill.
