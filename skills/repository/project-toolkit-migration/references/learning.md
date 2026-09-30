# Durable learning

The private learning store is an index plus one Markdown record per substantive run. It is read on subsequent invocations; no background process or model training is implied.

Maintain `index.md` with the current maturity, links to run records, verified reusable lessons, unresolved hypotheses and any proposed shared patches. Use unique run filenames. Preserve earlier evidence when correcting a lesson; mark it superseded and explain why.

If the private store is outside the active sandbox or a write is denied, return the exact pending record to the orchestrator and mark learning **not persisted**. The orchestrator may write it through the normal authorized filesystem operation. Do not claim durable capture until the write succeeds, and do not redirect private records into a public repository as a workaround.

## Run record

Record these fields in a private Markdown file:

- Date and mode: diagnose / adopt / update / recover.
- Consumer starting commit, target template ref, toolkit diagnostic revision and skill revision if known.
- Intended outcome and relevant environment/tool versions.
- Findings: check ID, observed evidence, suspected owner, confirmed owner if known.
- Attempts: action, observable result, and whether any mutation occurred.
- Verification: checks passed, failed or not performed; CI commit/run when applicable; second-application result.
- Outcome: diagnosed / migrated / blocked / failed. A diagnostic-only run is never counted as a successful migration.
- Lesson: verified / hypothesis / superseded, applicable conditions, remedy, and counterexample or limitation.
- Learning decision: patch-existing / create-case / no-change, with reason and proposed target.
- Follow-up: links to minimal fixtures or reviewed patches. Keep private evidence in this store.

Record evidence concisely; do not copy raw transcripts, credentials or full environment dumps. A raw doctor report can expose local file names, so treat it as private by default.

## Promotion

A reusable lesson should become executable where possible: a diagnostic rule or failing fixture in project-toolkit, or a workflow correction in the shared skill. Project-specific configuration stays with its project. Never silently edit the installed skill copy as the canonical source.

Search the index and existing repository fixtures before adding another lesson. A shared patch contains generalized conditions and a minimal public-safe example, not the original private record. Publication follows the user's existing authorization and the repository contribution rules. Local learning does not require public publication.

## Maturity

Initial state: **experimental**, with zero verified real consumer migrations unless records establish otherwise.

Advance to **validated** only with recorded successful first adoption and managed update on representative real consumers, idempotence evidence, and regression cases for encountered failures. Specify the supported stacks and conditions; do not generalize success to untested stacks.

Advance to **automation-ready** only for an explicit supported scope after repeated independent successful runs, no unexplained manual intervention, observed failure/recovery behavior, and a defined rollback procedure. The owner reviews the evidence before enabling unattended mutation. This is an evidence-based decision, not a fixed success counter.

A new unresolved regression returns the affected scope to experimental. Keep diagnostic-only automation separate from mutation automation: a scheduled doctor can be useful much earlier.
