---
name: game-source-reconnaissance
description: "Investigate open-source game mechanics from code: quests, item drops, fishing/crafting tables, NPCs, coordinates, and permitted automation entry points."
---

# Game Source Reconnaissance

## When to use
- User asks how to obtain an item, complete a quest, find an NPC/location, or understand a hidden mechanic in an open-source game.
- User provides a GitHub repository or says the game's source is open.
- User wants to build a permitted helper/agent/bot for their own server/account and needs to understand official/headless APIs, input commands, or deterministic simulation hooks.

## Core workflow
1. **Inspect source, not memory.** Clone or update the repo, then search code for both the user-facing name and likely internal ids:
   - case-insensitive user-facing label: `<display-name>`
   - likely internal forms: `<snake_case_name>`, `<semantic_alias>`, and related type/category terms
   - related quest/NPC names.
2. **Follow the chain from label → internal id → producer → gate.** For items/quest objects, identify:
   - item definition: display name, kind, sell/use values, quest id;
   - source: mob loot, ground pickup, vendor, crafting, fishing, dungeon, or dev command;
   - chance/count;
   - gates: active quest, completed prerequisite, level, location, party, instance, faction, or environment condition.
3. **Extract player-usable facts.** Translate code into game instructions:
   - NPC name and approximate coordinates;
   - prerequisite quest(s);
   - exact mob/object names;
   - drop chance and amount required;
   - common confusions, e.g. junk item with similar name vs quest item.
4. **Check tests/docs for behavioral confirmation.** Tests often encode cast times, failure messages, route assumptions, and intended usage even when docs are sparse.
5. **For automation/helper agents, prefer official seams.** Look for headless environments, websocket command APIs, world/client APIs, or test harnesses before considering browser DOM control.
6. **Keep safety boundaries explicit.** Help with user-owned/permitted servers/accounts and normal game inputs. Do not design stealth, anti-detection bypass, captcha bypass, ban evasion, or abuse against public services.

## Search patterns
- `(?i)<display name>|<snake_id>|<related quest>|<mob name>`
- `questId: '<id>'`, `requiresQuest`, `objectives`, `loot`, `vendorItems`, `use:`, `cmd:`
- For fishing/crafting: `completeFishing`, `RECIPES`, `profession`, `catch`, `roll`, `rng`, `useItem`.
- For automation: `headless`, `env_server`, `obs`, `ACTIONS`, `websocket`, `cmd`, `input`, `moveInput`, `useItem`.

## Output style
- Start with the direct answer: what to kill/buy/use, where, and chance.
- Include a compact table for item sources or loot outcomes.
- Mention internal ids only after user-facing names, and only when useful for disambiguation.
- If the answer depends on active quests or prerequisites, put that in a visible warning.

## Automation planning checklist
- [ ] Confirm the automation is for permitted use.
- [ ] Identify supported control surface: headless sim, websocket command protocol, or in-game API.
- [ ] Read available actions/commands instead of hardcoding assumptions.
- [ ] Build an offline/headless proof first when possible.
- [ ] Add emergency stops for death, combat, stuck movement, missing item, or unexpected state.
- [ ] Verify with real logs/counters, not just a plausible plan.

## Token-budget discipline for source/game automation
Live game reconnaissance can easily become a long loop of repo-wide searches plus WebSocket/runtime probes. Keep the model context small:
- Start discovery with file-only or count output from the available search tool; request matching content only for narrow, targeted patterns.
- Default to about 30 matches with one context line; avoid broad repository-root searches with large outputs unless explicitly justified.
- Cache the code landmarks after first discovery (e.g. command protocol, simulation file, zone data) and stop repeating broad searches over the same area.
- Read exact file ranges with the runtime's paginated file-reading tool rather than re-indexing whole files through search output.
- Keep WebSocket/probe logs out of chat context: write full logs to files, then emit only compact summaries (`OK/FAIL`, position, HP, inventory ids, last error).
- For runs longer than ~20–30 tool calls, create a compact handoff summary or start a fresh phase/session before continuing.

## References
- `references/token-budget-lessons.md` — generic token-budget discipline for source and runtime reconnaissance.

## Pitfalls
- Display names and internal IDs may differ; use clearly synthetic placeholders in reusable documentation rather than preserving a real game's content identifiers.
- Similar junk items can mask the correct quest item; verify the exact objective ID and loot entry.
- Quest drops may only roll when the relevant quest is active (`questId` on loot entries).
- Coordinates in code are approximate gameplay guidance; verify terrain/pathing before automation.
- Avoid turning a one-off finding into a hardcoded global rule. Keep game-specific facts in references, not the generic workflow.
