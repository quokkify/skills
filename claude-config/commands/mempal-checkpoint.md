---
description: Quick MemPalace checkpoint — saves session progress, decisions, open issues, and next steps for the current project.
---

Save a session checkpoint to MemPalace for the current project. Follow these steps exactly.

## Step 1 — Identify project

Run in bash (silent, best-effort):
```
git remote get-url origin 2>/dev/null || basename "$(pwd)"
```
Use the repo name from the remote URL (e.g. `owner/repo`) or the directory name as fallback.

## Step 2 — Check existing checkpoints

Call `mempalace_search` with the project name as query. Note what's already stored so you don't duplicate.

## Step 3 — Collect from session context

Review this conversation and extract only facts that are evident:

| Field | Content |
|-------|---------|
| **Done** | What was actually completed or fixed |
| **Decisions** | Key choices made and the reason (skip if none) |
| **Incomplete** | Work started but not finished |
| **Risks / Don't forget** | Tricky parts, caveats, potential issues |
| **Next steps** | Logical continuation |

Rules:
- Do NOT invent facts.
- If something is unclear, mark it as `[assumption]` or `[open question]`.
- Omit sections that have no evidence in the conversation.

## Step 4 — Write checkpoint

Call `mempalace_diary_write` with:
- **title**: `Checkpoint: <project-name>`
- **content**: structured Markdown using the fields from Step 3

## Step 5 — Confirm

Reply to the user in 2–3 lines: project name, what sections were saved, date. Nothing else.
