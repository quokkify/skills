---
name: agent-harness-design
description: Use when designing or reviewing the tools, schemas, observations, permission boundaries, context behavior, and recovery contracts exposed to an autonomous agent.
metadata:
  source: https://github.com/affaan-m/ECC/tree/5deee34c93395045b985e3baf91550e5f1ab7204/skills/agent-harness-construction
  license: MIT
---

# Agent Harness Design

Use this skill when designing or reviewing the tools, observations, permissions, and recovery behavior exposed to an autonomous agent.

## Design Goal

A harness should make the correct action easy to express, unsafe action hard to invoke accidentally, and failure state easy to diagnose. Do not rely on model quality to compensate for ambiguous tools, hidden state, or an unbounded action space.

## 1. Bound The Action Space

Expose the smallest set of operations that supports the intended tasks.

- Prefer typed, task-level operations over unrestricted shell or raw API access when the domain is narrow.
- Separate read-only observation from mutation.
- Separate reversible mutation from destructive or externally visible action.
- Require explicit scope for paths, projects, accounts, environments, or task IDs.
- Avoid two tools that appear interchangeable but differ in hidden side effects.
- Keep argument names and units unambiguous.

Do not wrap a simple deterministic operation in another model call.

## 2. Make Schemas Fail Closed

For every action define:

- required and optional fields;
- accepted types, bounds, formats, and enumerations;
- defaults that do not expand scope or create side effects;
- behavior for unknown fields;
- authorization and approval requirements;
- idempotency and concurrency semantics;
- timeout, retry, and cancellation behavior.

Validate before mutation. Return actionable field-level errors rather than partially applying an invalid request.

## 3. Return Deterministic Observations

A useful response distinguishes:

- success, partial success, no-op, blocked, and failure;
- machine-readable state from human-readable explanation;
- current state from requested or predicted state;
- complete output from truncated or paginated output;
- durable handles from display-only text.

Include stable identifiers and next-page/retry information when applicable. Never require the agent to infer success from prose such as "looks good."

Redact secrets and sensitive fields before they enter model context or logs.

## 4. Expose Recovery Information

Errors should state:

- what operation failed;
- whether any side effect occurred;
- whether retry is safe;
- whether the failure is transient, invalid input, permission, policy, dependency, or capability related;
- which prerequisite or corrective action is needed;
- any durable handle required to inspect or resume work.

Do not suggest blind retry for deterministic validation or authorization failures.

For long-running actions, expose lifecycle state, liveness, cancellation, final output, and timeout behavior. Distinguish a running job from a disconnected client.

## 5. Match Permissions To Consequence

- Default to least privilege and read-only scopes.
- Place approval at the narrowest meaningful irreversible boundary.
- Make production, payment, publication, deletion, credential, and external-message actions explicit.
- Prevent path traversal, cross-tenant access, symlink escape, and confused-deputy behavior.
- Keep user-owned global state and project-owned state separate.
- Record security-relevant side effects without logging secrets.

An approval dialog is not a substitute for scope validation or idempotency.

## 6. Design For Context Efficiency

- Keep tool descriptions short but discriminative.
- Split tools by materially different safety or lifecycle semantics, not by cosmetic variants.
- Paginate or summarize large results with a way to retrieve exact details.
- Let the caller request bounded fields or ranges when output can be large.
- Return references to durable artifacts instead of repeatedly injecting bulk content.
- Avoid mandatory telemetry or observations unrelated to the active task.

## 7. Verify The Harness

Test with deterministic fixtures or a mock service:

- valid success and no-op;
- missing, malformed, oversized, and unknown fields;
- authorization and approval denial;
- dependency failure before mutation;
- timeout, cancellation, and retry;
- repeated invocation and concurrent invocation;
- partial failure and recovery;
- output truncation/pagination;
- secret redaction and tenant/path isolation;
- destructive action cannot occur after a failed prerequisite.

Exercise the interface through the same transport the agent uses. Unit-testing an internal function is not evidence that registration, serialization, or gateway behavior is correct.

## Review Checklist

- Can the model tell which tool to choose from descriptions alone?
- Can a default or omitted argument broaden scope?
- Can malformed input cause partial mutation?
- Is success machine-readable and verifiable?
- Does every error say whether retry is safe and whether side effects occurred?
- Are long-running state and cancellation observable?
- Are secrets removed before context and logs?
- Are destructive and externally visible actions separately gated?
- Are tests adversarial as well as happy-path?
- Is there a bounded fallback when a supported runtime lacks a feature?

## Exit Criteria

- Action and observation contracts are explicit.
- Read, reversible write, and destructive boundaries are distinct.
- Invalid requests fail before mutation.
- Success and partial failure can be verified from returned state or durable handles.
- Recovery and retry semantics are documented and tested.
- Transport-level tests cover safety, redaction, concurrency, and failure injection.
