---
name: ai-assisted-regression-testing
description: Use when an AI-authored change or bug fix crosses alternate paths, contracts, failure handling, generated surfaces, or multiple layers and may preserve an unverified implementation assumption that ordinary targeted tests do not expose.
metadata:
  source: https://github.com/affaan-m/ECC/tree/5deee34c93395045b985e3baf91550e5f1ab7204/skills/ai-regression-testing
  license: MIT
---

# AI-Assisted Regression Testing

Use this skill when an AI agent authored or repaired behavior across important boundaries and an independent mechanical check is needed to challenge an unverified implementation assumption.

## Core Risk

Self-review can preserve assumptions from implementation. Independent executable evidence reduces that risk: use a contract test, deterministic fixture, type check, invariant, differential test, or reproducible integration check.

This does not make AI-authored code categorically different from human-authored code. It changes where to spend verification effort: boundaries the author assumed rather than observed deserve direct tests.

Do not load this skill solely because AI wrote the change. Use the project's ordinary development and testing workflow for isolated behavior with an established contract. Use this workflow when alternate implementations, generated artifacts, failure semantics, or cross-layer propagation create a realistic assumption-divergence risk.

## Test-First Bug Repair

When practical:

1. Reproduce the reported behavior with the smallest stable test or script.
2. Confirm the new check fails for the expected reason before changing code.
3. Make the smallest fix that satisfies the contract.
4. Run the targeted test, then the relevant broader suite.
5. Keep the regression test if it protects a durable contract and is not coupled to incidental implementation.

If a pre-fix failing test cannot be created safely or economically, document the alternative evidence and its limitation.

## High-Value Boundaries

### Alternate-Path Parity

When behavior has production, mock, sandbox, fallback, feature-flag, legacy, cache-hit, or offline paths, assert the contract across every supported path affected by the change.

Compare externally meaningful properties, not necessarily byte-identical implementation data:

- required fields and types;
- status/error semantics;
- authorization and privacy boundaries;
- persistence and side effects;
- ordering, pagination, or idempotency guarantees.

A mock is not useful if it silently exposes a different contract from the real adapter.

### API And Data-Shape Contracts

Test the consumer-visible schema at the boundary. Include required, optional, nullable, and absent-field behavior. Avoid fixes that mask incomplete queries or adapters with broad selection, unsafe casts, or default values unless that is the intended contract.

### Failure And Rollback

For state-changing behavior, verify:

- partial work is not presented as success;
- optimistic UI state reconciles or rolls back;
- retries do not duplicate side effects;
- stale data is cleared or explicitly retained according to the contract;
- timeout, cancellation, and dependency failure leave a valid state.

### Generated And Derived Surfaces

When a source change feeds generated types, clients, schemas, migrations, fixtures, documentation, or caches, verify the required regeneration path and check for stale derived artifacts.

### Cross-Layer Propagation

Trace new or changed data through source, validation, persistence, serialization, client types, UI state, mock data, and tests. A field added at one layer can remain absent or semantically different at another.

## Independent Oracles

Prefer one or more of:

- an existing contract or conformance suite;
- a test derived from an authoritative specification;
- property-based or invariant testing;
- differential comparison between old/new or real/mock paths with normalized expected differences;
- schema validation at process boundaries;
- deterministic fixtures from a separate source;
- an independent reviewer who receives the contract and diff, not the author's chain of reasoning.

Do not call a second prompt to the same model an independent oracle unless it is grounded in separate executable evidence.

## Scope Selection

Regression tests should grow around durable contracts and high-consequence boundaries, not only previously observed bugs and not an arbitrary coverage percentage.

Prioritize when:

- the failure escaped earlier review;
- multiple implementations must remain compatible;
- authorization, money, persistent data, migration, or external side effects are involved;
- the bug class is easy to reintroduce;
- a fast deterministic check can prevent repeated manual diagnosis.

Skip or redesign a test that merely snapshots incidental implementation, depends on unstable external state, or costs more to maintain than the contract warrants.

## Review Checklist

- What assumption did the author and reviewer share?
- Which executable check can falsify it?
- Are alternate paths covered or explicitly out of scope?
- Does the test assert the external contract rather than helper call order?
- Are failure, retry, rollback, and stale-result cases relevant?
- Did the targeted check fail before the fix or is the limitation recorded?
- Did the relevant broader gate run after the targeted check?

## Exit Criteria

- The regression is represented by a stable observable contract.
- The check is capable of failing on the original defect or an equivalent fixture.
- Supported alternate paths and cross-layer propagation are covered where relevant.
- Failure-state behavior is verified for mutating operations.
- The report distinguishes executable evidence from reviewer judgment.
