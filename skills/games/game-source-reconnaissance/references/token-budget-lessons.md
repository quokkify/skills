# Token-budget lessons for live game source reconnaissance

Use this reference when a game-source task combines code investigation with runtime/headless/WebSocket automation.

## Common failure pattern
Long-running game-source reconnaissance can exhaust a model session quickly when it combines:

- Many model iterations on an ever-growing context.
- Repeated repository-wide content searches with large result limits and several context lines.
- Runtime/WebSocket/probe logs kept in tool outputs, then resent to the model on every later turn.
- Repeated searches over the same landmarks: command protocol, simulation core, zone/camp data, and tests.

In these workflows, accumulated tool-output JSON—especially broad search results and live runtime logs—often costs more context than dependency directories or build artifacts.

## Safer workflow
1. **Discovery pass: list paths first.**
   - Use file/path-only or match-count search output to locate likely files.
   - Record a small landmark list: command protocol, sim mechanics, zone data, tests/docs.
2. **Focused extraction pass.**
   - Read only the necessary ranges with the runtime's paginated file-reading tool.
   - Prefer narrow patterns, bounded result sets, and minimal context lines.
3. **Runtime pass.**
   - Make helper scripts print a compact JSON summary only.
   - Write full WS/probe logs to a file outside the conversation context.
   - Summaries should include only fields needed for the next decision: status, pos, HP, inventory ids, last event/error.
4. **Phase handoff.**
   - Before accumulated output becomes unwieldy, summarize discovered facts and drop raw logs/search outputs by starting a new phase or explicit handoff.

## Red flags
- Repo-root `search_files` with `output_mode="content"`, `limit >= 100`, and `context >= 3`.
- Repeating similar searches for `move`, `use`, `cast`, `trade`, `fishing`, `graveyard`, etc. after the relevant files are known.
- Streaming/printing full WebSocket snapshots, inventory dumps, process trees, or npm/node logs into terminal output.
- Letting pathfinding/probe experiments accumulate in context instead of writing them to scratch files and returning concise summaries.

## Practical target

Set output budgets appropriate to the active runtime and task. Measure returned output, summarize before context pressure affects quality, and avoid unsupported claims about a universal percentage reduction.
