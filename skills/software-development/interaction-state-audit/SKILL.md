---
name: interaction-state-audit
description: Use when a UI interaction appears wired correctly but produces the wrong final state, especially after shared-state refactors, async races, effects, optimistic updates, or reports that a control does nothing.
metadata:
  source: https://github.com/affaan-m/ECC/tree/5deee34c93395045b985e3baf91550e5f1ab7204/skills/click-path-audit
  license: MIT
---

# Interaction State Audit

Trace a user interaction through every ordered state transition and side effect. This catches failures that isolated function review misses: each call works, but their composition cancels the intended behavior or leaves the interface inconsistent.

## Trigger

Use this workflow when:

- a button, form, keyboard action, gesture, or navigation control appears to do nothing;
- users report incorrect final UI state but no exception is visible;
- a shared store, reducer, context, state machine, or effect system was refactored;
- optimistic updates, concurrent requests, or route transitions can overwrite one another;
- static review and ordinary debugging confirm that handlers exist but do not explain the behavior.

Use narrower debugging for API contract failures, styling defects, or performance bottlenecks unless state composition is also implicated.

## Define The Contract First

For each interaction, state the observable promise before reading implementation details:

```text
Starting state:
User action:
Expected final state:
Expected external side effects:
Forbidden final states or side effects:
```

A label such as "Save" or "Delete" is not enough. Determine whether success means a persisted server result, local confirmation, navigation, queued work, or another observable outcome.

## Build A State-Effect Map

Inventory only the state owners touched by the flow: component state, shared stores, reducers, contexts, state machines, router state, caches, and server state.

For every relevant action record:

```text
actionName
  reads: <fields or external state>
  writes: <fields and values/transitions>
  resets: <fields cleared outside the action's apparent ownership>
  async work: <request, timer, subscription, transition>
  effects: <navigation, persistence, cache invalidation, event emission>
```

Flag broad reset operations and actions that mutate fields owned by another feature. These are common sources of sequential undo.

## Trace The Interaction In Execution Order

For each event handler:

1. Identify the event source and guard conditions.
2. Expand every direct call in order.
3. Follow dispatched actions, reducers, callbacks, effects, subscriptions, route changes, and cache updates that can run because of those calls.
4. Record each read, write, reset, and external effect.
5. Add asynchronous completion order and cancellation behavior.
6. Compute the expected and possible final states.
7. Compare them with the user-visible contract.

Use an evidence table:

```markdown
| Step | Trigger/call | Reads | Writes/resets | Async/effect | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | `openComposer()` | ... | `composer=open` | — | `file:line` |
| 2 | `clearSelection()` | ... | `composer=closed` | — | `file:line` |
```

Do not stop at the handler body when an action has hidden reducer or store side effects.

## Failure Patterns

### Sequential Undo

A later synchronous action resets a value set by an earlier action. The handler completes without error but the first transition disappears.

### Async Last-Writer Race

Two requests or callbacks write the same state and completion order is not controlled. Check abort, generation/request IDs, stale-result rejection, and idempotency.

### Stale Closure Or Snapshot

A callback uses state captured before an update. Check dependency lists, functional updates, memoization, actor snapshots, and event-handler lifetime.

### Effect Interference

An effect, watcher, subscription, route hook, or derived-state synchronizer reacts to the intended transition and reverses or replaces it.

### Missing Transition

The handler validates, toggles a local flag, or opens a confirmation surface but never performs the action promised by the UI.

### Conditional Dead Path

A guard can never be true in the reachable starting state, or an earlier transition guarantees the action branch is skipped.

### Optimistic Divergence

The UI mutates before external success but failure, timeout, retry, or navigation does not restore or reconcile state.

### Duplicate Or Re-entrant Action

Rapid input, event bubbling, retries, or rerenders invoke the transition more than once and produce duplicate requests or invalid state.

## Verify The Hypothesis

Prefer the smallest discriminating check:

- a reducer/store unit test that asserts the complete action sequence;
- a component test that exercises the user event and final visible state;
- a deterministic deferred-promise test for alternate async completion orders;
- a state-machine transition test;
- temporary structured instrumentation in a safe test environment;
- browser automation for the actual interaction, paired with state-independent observable assertions.

A test should fail before the fix when practical and assert the final contract, not only that each helper was called.

For races, cover at least both completion orders and cancellation/unmount when relevant. For optimistic updates, cover success, rejection, timeout, and repeated activation when those states are possible.

## Report Format

```markdown
## Interaction State Finding
- Interaction: <user action and location>
- Expected final state: <observable contract>
- Actual/possible final state: <result>
- Pattern: <failure pattern>
- Trace: <ordered evidence with paths/lines>
- Root cause: <the conflicting transition or missing control>
- Minimal fix: <specific change>
- Regression evidence: <test or reproducible check>
- Confidence: high | medium | low
```

Report uncertainty when runtime ordering or an external boundary has not been observed.

## Scope And Safety

- Start with one reported flow or changed state owner; full-application audits are expensive.
- Map shared actions once, then reuse that map across related interactions.
- Parallelize independent screens only after the shared state-effect map is stable.
- Do not run destructive UI journeys against production.
- Use synthetic or seeded accounts for mutating integration tests.
- Redact credentials, tokens, personal data, and screenshots before preserving evidence.

## Completion Criteria

- The user-visible contract is explicit.
- Every relevant ordered state transition and asynchronous writer is traced.
- The finding identifies the exact conflict, missing transition, or unresolved uncertainty.
- The proposed fix is bounded and does not rely on broad state resets.
- Regression evidence covers final observable state and relevant failure ordering.
