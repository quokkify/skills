---
name: architecture-decision-records
description: Use when recording, reviewing, or superseding a significant architecture decision whose context, alternatives, and consequences must remain understandable after the conversation ends.
metadata:
  source: https://github.com/affaan-m/ECC/tree/5deee34c93395045b985e3baf91550e5f1ab7204/skills/architecture-decision-records
  license: MIT
---

# Architecture Decision Records

Capture decisions that shape a system, not every implementation choice. An ADR should preserve enough context for a future maintainer to understand why the selected option was reasonable and what would justify revisiting it.

## Trigger

Use this workflow when:

- a team chooses between materially different frameworks, protocols, storage models, deployment shapes, or security approaches;
- a decision creates a durable compatibility, cost, operational, or migration constraint;
- the user explicitly asks to record, review, deprecate, or supersede an architectural decision;
- a later task asks why the system uses an existing approach and an ADR may answer it.

Do not create an ADR for formatting, naming, routine dependency updates, reversible local refactors, or choices with no meaningful alternative or consequence.

## Discovery Before Writing

1. Inspect the repository's existing decision-log convention. Prefer its path, numbering, status vocabulary, and template.
2. Search existing ADRs for the same topic. Update or supersede a relevant record instead of creating a contradictory duplicate.
3. Separate verified context from assumptions. Read the relevant code, configuration, documentation, issue, and migration history when available.
4. Identify the actual decision and decision owner. Do not infer who approved a decision from commit authorship alone.
5. Gather only alternatives that were genuinely considered or remain credible. Do not invent rejected options to make the record look complete.

If no ADR convention exists, propose a lightweight location such as `docs/adr/` and ask before creating repository files.

## Record Format

Use the project's template when one exists. Otherwise use:

```markdown
# ADR-NNNN: <decision in a short active phrase>

- Status: proposed | accepted | deprecated | superseded
- Superseded by: ADR-NNNN  <!-- only when Status is superseded -->
- Date: YYYY-MM-DD
- Deciders: <people or roles, only when known>

## Context

<Problem, constraints, and forces that made a decision necessary.>

## Decision

<The chosen approach and its important boundaries.>

## Alternatives considered

### <alternative>
- Benefits:
- Costs and risks:
- Why it was not selected:

## Consequences

### Positive
- <what becomes easier or safer>

### Negative
- <trade-off or new obligation>

### Follow-up and review triggers
- <migration, metric, date, or condition that should reopen the decision>
```

Keep the record concise enough to scan quickly. Link detailed benchmarks, threat models, or migration plans instead of copying them into the ADR.

## Workflow

1. **Classify** — confirm the choice is durable and architecturally significant.
2. **Locate** — find the repository's ADR directory, index, template, and related records.
3. **Establish evidence** — capture current constraints and authoritative inputs without reconstructing business intent from code.
4. **Draft** — state one decision, credible alternatives, trade-offs, and revisit conditions.
5. **Check consistency** — verify the draft does not contradict active records, code, or documented policy without explicitly superseding them.
6. **Review before mutation** — present the draft or diff when the user requested discussion first. Do not silently initialize an ADR system or write a decision the user has not made.
7. **Write and index** — after authorization, add the record and update the existing index if the repository uses one.
8. **Verify** — validate numbering, links, status references, dates, and repository checks.

## Lifecycle

- `proposed`: under discussion and not yet authoritative;
- `accepted`: current decision;
- `deprecated`: retained for history but no longer recommended;
- `superseded`: replaced by a specific newer ADR; record the replacement in a separate `Superseded by: ADR-NNNN` field and link both records where practical.

Never rewrite an accepted ADR to pretend the original decision was different. Add a new record that supersedes it or append a clearly dated clarification according to project policy.

## Quality Checks

A useful ADR answers:

- What concrete problem required a decision?
- Which constraints were verified, and which assumptions remain?
- What exactly was selected and what is outside its boundary?
- Which credible alternatives were rejected, and why?
- What becomes easier, harder, riskier, or more expensive?
- What evidence or condition should cause the decision to be revisited?

Reject a draft that contains generic rationale such as "best practice", "more scalable", or "more secure" without a project-relevant constraint or measurable basis.

## Safety And Portability

- Do not include secrets, private endpoints, customer data, or production payloads.
- Do not name deciders unless the information is supplied or already part of the repository's public record.
- Do not mandate `docs/adr/`; follow the target repository's convention.
- Do not claim consensus, approval, benchmarks, or alternatives that were not established.
- Do not create or modify files when the user asked only for an explanation or draft.

## Completion Criteria

- The decision is significant enough to preserve.
- Context and alternatives are grounded in available evidence.
- Consequences include negative trade-offs and revisit triggers.
- Status and supersession links are internally consistent.
- The user-requested artifact is written only in the approved repository location.
- Relevant documentation and repository validation pass.
