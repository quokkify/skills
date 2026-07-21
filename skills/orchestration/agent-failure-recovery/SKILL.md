---
name: agent-failure-recovery
description: Use when an agent repeats failed actions, burns context without reducing uncertainty, drifts from the task, or needs a bounded recovery from tool, environment, state, policy, or coordination failures.
metadata:
  source: https://github.com/affaan-m/ECC/tree/5deee34c93395045b985e3baf91550e5f1ab7204/skills/agent-introspection-debugging
  license: MIT
---

# Agent Failure Recovery

Use this skill when an agent repeatedly retries, consumes context without reducing uncertainty, drifts from the task, or encounters recoverable environment/tool failures.

## Recovery Loop

### 1. Stop And Capture

Stop automatic repetition before another retry. Preserve only the evidence needed to diagnose, and redact it before it enters logs, durable notes, or a handoff:

- original objective and current sub-goal;
- last successful state-changing step;
- failing tool, command, or boundary;
- exact error and the minimum relevant output, with sensitive values removed;
- recent repeated actions;
- assumed workspace, branch, files, services, ports, credential availability/source/status (never credential values), and permissions;
- whether the failure is deterministic, transient, policy-blocked, or unknown.

Redact tokens, cookies, authorization headers, credential values, private URLs, personal data, and sensitive command output. Do not dump the entire transcript into a handoff. Record a compact, redacted failure packet.

### 2. Classify

Choose the most likely class:

- **logic** — the hypothesis or implementation is wrong;
- **state** — filesystem, branch, process, cache, or external state differs from expectation;
- **environment** — dependency, service, network, port, runtime, or resource mismatch;
- **interface** — malformed tool arguments, stale API contract, parsing, or output truncation;
- **policy/capability** — permission, approval, credential, sandbox, or unavailable action;
- **coordination** — stale handoff, conflicting writers, unmet dependency, or wrong task owner;
- **transient** — rate limit, temporary network/service failure, or eventual consistency.

A classification is a hypothesis, not a verdict.

### 3. Run One Discriminating Probe

Choose the smallest safe observation that separates likely causes. Examples:

- verify actual cwd, branch, status, and file existence;
- run one failing test rather than the full suite;
- inspect service health and the exact configured endpoint;
- compare expected and actual tool schema or API response;
- check whether the prerequisite task or artifact exists;
- perform one bounded retry with explicit backoff for a confirmed transient failure.

Do not make another broad edit merely to see what happens.

### 4. Recover Containably

Prefer actions that are reversible or isolated:

- correct one path, argument, assumption, or fixture;
- narrow work to one file, test, or service boundary;
- restart only the affected disposable process after checking impact;
- refresh a stale observation;
- create a fresh worktree or copy from known backed-up state without overwriting the current dirty state;
- hand off to a capable owner with the compact failure packet;
- block and surface the missing human decision or credential.

Before any reset, checkout, restore, or overwrite that could discard work, inspect and preserve uncommitted changes and obtain explicit approval for the destructive boundary.

Never claim to reset agent state, repair configuration, change models, or restart services unless the runtime exposes that action and it was actually performed.

### 5. Verify And Resume

Repeat the discriminating probe, then the smallest affected verification. Resume the original plan after the result confirms or materially changes the diagnosis and the smallest affected verification passes.

If two recovery cycles fail to reduce uncertainty, stop broad retries and escalate or redesign the diagnostic approach. A third restatement of the same hypothesis is not progress.

## Common Patterns

| Symptom | Likely causes | First probe |
| --- | --- | --- |
| Same tool call repeats | missing exit condition, ignored error, stale observation | compare the last actions and expected state change |
| File missing after write | wrong cwd/worktree, failed write, cleanup, race | inspect actual path, cwd, status, and tool result |
| Tests still fail after a fix | wrong hypothesis or incomplete contract | isolate the first relevant failure and reproduce it |
| Connection refused/timeout | service down, wrong port/URL, network boundary | inspect config plus a bounded health check |
| Rate limit | retry storm or missing backoff | count attempts and timing; honor provider guidance |
| Conflicting diffs | parallel ownership overlap or stale branch | inspect worktrees, branch heads, and current diff |
| Context quality degrades | repeated logs/plans or task drift | restate objective and compact evidence into a handoff |

## Failure Packet

```markdown
## Agent Failure Packet
- Objective:
- Current sub-goal:
- Last successful step:
- Failure and redacted exact evidence:
- Verified environment state:
- Repeated pattern:
- Classification hypothesis:
- Discriminating probe and result:
- Recovery attempted:
- Current status: recovered | partial | blocked
- Next safe action or needed decision:
```

## Prevention Capture

After recovery, preserve a reusable lesson only when it is stable and general:

- a missing prerequisite check;
- a tool-interface pitfall;
- a bounded retry/backoff rule;
- a workspace or branch invariant;
- a verification step that would have caught the drift earlier.

Keep task progress, one-off failures, IDs, and stale environment state out of reusable skills or durable memory.

## Exit Criteria

- Blind retries stopped.
- World state was re-observed rather than assumed.
- At least one probe discriminated between plausible causes.
- Recovery was bounded and reversible, or the task was honestly blocked.
- Evidence supports the resumed plan or escalation.
