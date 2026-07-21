---
name: codebase-onboarding
description: Use when entering an unfamiliar repository and producing a concise, evidence-backed map of its purpose, architecture, entry points, conventions, data flow, and safe verification commands.
metadata:
  source: https://github.com/affaan-m/ECC/tree/5deee34c93395045b985e3baf91550e5f1ab7204/skills/codebase-onboarding
  license: MIT
---

# Codebase Onboarding

Build a useful mental model of an unfamiliar repository without reading the whole tree or guessing from directory names. The result should help a developer or agent make the first safe change.

## Trigger

Use this skill when:

- opening a repository for the first time;
- onboarding a developer or agent;
- asked to explain architecture, request flow, conventions, or where a change belongs;
- creating or refreshing project instructions from verified repository facts.

Do not run the full workflow for a one-file question or when current project documentation already answers the request. Read the authoritative local instructions first in every case.

## Phase 1: Reconnaissance

Inspect independent signals in parallel when possible:

1. **Repository guidance** — `AGENTS.md`, `CLAUDE.md`, contribution, security, and development documentation.
2. **Manifests and lockfiles** — languages, supported versions, frameworks, package managers, and workspace boundaries.
3. **Entry points** — application startup, routes, commands, workers, scheduled jobs, and public interfaces.
4. **Directory shape** — a shallow tree excluding generated, dependency, cache, build, and VCS directories.
5. **Build and runtime configuration** — containers, environment examples, task runners, bundlers, deployment manifests, and service supervision.
6. **Verification surface** — tests, lint, type checks, builds, fixtures, CI workflows, and local validation scripts.
7. **History when available** — recent changes and contribution patterns. Label conclusions as unavailable when history is shallow or absent.

Use targeted file search and selective reads. Do not recursively dump the repository into context.

## Phase 2: Architecture Map

Establish these facts from code and configuration:

- primary languages and version constraints;
- application or package boundaries;
- runtime processes and their entry points;
- external interfaces: HTTP, queues, events, CLIs, scheduled tasks, or libraries;
- persistence and external-service boundaries;
- where domain logic, adapters, and presentation logic live;
- build, deployment, and environment model.

Trace at least one representative path end to end when relevant:

```text
external trigger
  -> entry point
  -> validation/authentication
  -> orchestration or domain logic
  -> persistence/external dependency
  -> response/event/side effect
```

Label a path as partial when a boundary cannot be verified. Never fill a missing step with a plausible framework default.

## Phase 3: Convention Detection

Sample multiple existing files before declaring a convention. Check:

- naming and directory placement;
- error and result handling;
- dependency boundaries and injection patterns;
- transaction, retry, and idempotency behavior;
- test placement, fixture style, and mocking boundaries;
- logging and observability conventions;
- Git and release workflow when history and documentation support a conclusion.

Distinguish:

- **documented rule** — explicitly stated by the repository;
- **observed convention** — repeated consistently in representative code;
- **local exception** — present but not a general rule;
- **unknown** — insufficient evidence.

## Phase 4: First-Change Guide

Identify the shortest safe route for common work:

- where to add or modify a user-facing feature;
- where to change an API or external contract;
- where schema or migration changes live;
- where tests matching each layer belong;
- which generated files must not be edited directly;
- which commands verify a small change and which run the full gate;
- which operations need services, credentials, containers, network access, or explicit approval.

Do not execute heavyweight builds, containers, migrations, paid calls, or production operations merely to complete onboarding. Report prerequisites and ask or follow project policy first.

## Output

Default to a concise conversation summary:

```markdown
# Repository Onboarding: <name>

## Purpose
<What it does and who or what consumes it.>

## Stack and boundaries
- <language/framework/runtime>
- <applications/packages/services>

## Architecture and request flow
<compact diagram or trace>

## Key entry points
- `<path>` — <role>

## Conventions
- Documented: <rule + source>
- Observed: <pattern + evidence>

## Verification
- Fast: `<command>`
- Full: `<command>`
- Prerequisites: <services/tools/approval>

## First-change map
- I want to ... -> start at `<path>`

## Unknowns and risks
- <what could not be established>
```

Create or update an onboarding document, `AGENTS.md`, or `CLAUDE.md` only when requested. Preserve existing instructions, describe the proposed changes, and use the repository's established file rather than creating duplicate agent-specific sources of truth.

## Anti-Patterns

- Reading every file instead of sampling by responsibility.
- Copying the README without validating it against code and configuration.
- Treating a dependency as an actively used architecture component merely because it appears in a manifest.
- Inferring business requirements, ownership, SLAs, or compliance obligations from names in code.
- Inventing test, build, migration, or deployment commands.
- Presenting a framework's conventional structure as this repository's verified structure.
- Writing verbose project instructions that duplicate durable documentation.

## Completion Criteria

- The map cites concrete repository paths and commands.
- At least one important flow is traced or explicitly marked unresolved.
- Documented rules and observed conventions are distinguished.
- Unknowns and prerequisites are visible.
- No source file or project instruction is modified unless requested.
- The result is concise enough to guide a first safe change.
