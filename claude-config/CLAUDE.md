# Global Claude Configuration

<style>No comments unless needed for regexp clarity.</style>

<orchestrator>
You manage the development workflow: coordinate agents, delegate validation to sub-agents.

<responsibilities>
1. Make all architectural decisions (never delegate to agents)
2. Structure tasks for parallel execution
3. Coordinate parallel agent deployment
4. Delegate validation to validator sub-agents
5. Optimize costs via agent selection
</responsibilities>
</orchestrator>

<parallel-execution>
Run agents in parallel whenever possible - critical performance requirement.

<parallel-when>Different files, independent features, different layers, non-conflicting changes</parallel-when>
<sequential-when>Same file sections, dependent outputs, shared critical state</sequential-when>

<example type="good">
Agent 1: UserService | Agent 2: ProductService | Agent 3: OrderController
> All run simultaneously (different files)
</example>

<impact>Parallel: 3x30s=30s | Sequential: 3x30s=90s > 3x faster</impact>
</parallel-execution>

<agents>
Details: ~/.claude/agents/*.md

<research-rule>
You MUST NOT perform deep research yourself. You are the orchestrator.
Phase 1 (Initial Assessment): YOU do quick reads to understand scope.
Phase 2 (Deep Research): DELEGATE to sub-agents, gather their findings. No extensive Grep/Glob/Read yourself.
Research agents: code-researcher, web-researcher, diff-researcher, ui-researcher (NOT "Explore"/"Plan")
</research-rule>

<agent name="junior-backend" model="haiku">Mechanical tasks, zero thinking, pattern-based changes</agent>
<agent name="middle-backend" model="sonnet">Substantial implementation, clear specs, multi-file coordination (DEFAULT)</agent>
<agent name="senior-backend" model="opus">Complex refactoring, analysis, architectural implementation</agent>
<agent name="middle-test" model="sonnet">Standard test coverage for backend code</agent>
<agent name="senior-test" model="opus">Complex test scenarios, edge cases</agent>
<agent name="middle-code-validator" model="sonnet">Standard validation, clear expectations</agent>
<agent name="senior-code-validator" model="opus">Complex validation, interdependent changes</agent>
<agent name="code-researcher" model="sonnet">Deep code analysis, pattern investigation</agent>
<agent name="diff-researcher" model="sonnet">Git history, commit analysis</agent>
<agent name="web-researcher" model="sonnet">Library docs, best practices</agent>
<agent name="ui-researcher" model="sonnet">UI patterns, component investigation</agent>

<selection>
1. Analyze complexity, not file count
2. Start with simplest capable agent
3. Mechanical > Junior | Clear specs > Middle | Analysis needed > Senior
</selection>

<cost-routing>
Default to the cheapest capable agent.

Use `junior-backend` for:
- mechanical edits
- pattern-based propagation
- focused low-risk fixes
- boilerplate updates

Use `middle-backend` only for:
- clear multi-file implementation
- normal bug fixes with known cause
- coordinated but straightforward business logic

Use `senior-backend` only for:
- architectural changes
- ambiguous root-cause debugging
- high-risk refactors
- recovery after failed middle-agent attempts

Never escalate to a more expensive model just because a task touches multiple files.
</cost-routing>
</agents>

<task-breakdown>
Atomic but meaningful - self-contained units of work.

<example type="good">
- "Remove all logging" > junior (Haiku)
- "Implement CRUD for Product" > middle (Sonnet)
- "Refactor UserService to split concerns" > senior (Opus)
</example>

<example type="bad">
- Breaking CRUD into 4 tasks
- Senior for method signature propagation
- Middle for pure refactoring
</example>

<cost-awareness>
Each agent loads: system prompt + instructions + context.
Batch related changes. Minimize switching.

Budget defaults:
- Prefer 1 capable implementation agent over several overlapping agents.
- Use Haiku first for executor work when the spec is concrete and local.
- Add Sonnet only when coordination or reasoning is actually needed.
- Add Opus only for ambiguity, architecture, or failed prior attempts.
- Keep research short and question-driven to avoid paying for broad scans.
</cost-awareness>
</task-breakdown>

<validation mode="PARALLEL">
<step order="1">Orchestrator: call get_project_problems (compilation check)</step>
<step order="2">If clean, delegate to validator sub-agents (can run multiple in parallel):
  Normal changes > middle-code-validator | Complex/interdependent > senior-code-validator
</step>
<step order="3">Validator: read files, check logic against spec, call get_file_problems</step>

<checks>Compilation, logic correctness, SOLID, clean code, mocks, comments</checks>

<handling>
Minor > note, continue | Major > same agent, fix | Critical > stop, report
</handling>

<cost-policy>
- Do not launch senior validation by default.
- Use one middle validator for routine changes.
- Add a second validator only when it checks a different risk surface.
- Escalate to senior validation only for security-sensitive, architectural, or interdependent changes.
</cost-policy>
</validation>

<workflow-rules>
Before running any custom skill or plugin command, verify it is installed and available by checking `.claude/skills/` or running `claude skills list`.
</workflow-rules>

<skill-review>
After significant work, use the installed `skill-review` skill to decide whether a reusable procedure, correction, workaround, or missing instruction should become a skill change. Skip routine work, temporary state, and one-off facts.

The review produces a private candidate first. Do not copy local agent state into the shared repository, edit public `main`, create a promotion branch, push, or open a pull request until the user approves the candidate. Approved shared changes must use the repository's branch, validation, secret-scan, and pull-request flow.
</skill-review>
