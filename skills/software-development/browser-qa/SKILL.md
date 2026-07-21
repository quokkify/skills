---
name: browser-qa
description: Use when a frontend change needs browser-based release evidence for rendered runtime health, critical interactions, responsive layout, visual baselines, and accessibility in an approved environment.
metadata:
  source: https://github.com/affaan-m/ECC/tree/5deee34c93395045b985e3baf91550e5f1ab7204/skills/browser-qa
  license: MIT
---

# Browser QA Release Gate

Use this skill after a frontend change is available in a local, preview, or staging environment. It verifies rendered behavior that static checks and unit tests cannot establish.

## Safety Boundary

- Default to read-only journeys.
- Run checkout, payment, deletion, mass update, invitation, email, or other mutating journeys only in an approved non-production environment.
- Use seeded test identities, not personal or production accounts.
- Never save credentials, tokens, personal data, session cookies, or sensitive payloads in screenshots, traces, console logs, or reports.
- Confirm the target URL and environment before any mutating flow.

A browser automation tool is an execution mechanism, not proof by itself. Assertions must name observable outcomes and preserve enough evidence to reproduce a failure.

## Gate 1: Smoke And Runtime Health

For each changed entry point:

1. Navigate from a clean session using a supported route.
2. Confirm the primary content renders rather than merely receiving HTTP 200.
3. Capture uncaught exceptions and relevant console errors; classify third-party noise separately.
4. Inspect failed first-party requests and unexpected redirects.
5. Check a narrow desktop and mobile viewport for blocking overflow or missing controls.

Do not claim performance thresholds from navigation timing or visual observation alone. Report Core Web Vitals only when collected by an appropriate instrument under documented conditions.

## Gate 2: Interaction Contract

For every critical changed interaction:

- define starting state, action, expected final state, and prohibited side effects;
- test valid input and the most important invalid or boundary input;
- verify loading, success, empty, and failure states when applicable;
- confirm keyboard operation and visible focus for interactive controls;
- verify navigation and browser history where the flow changes routes;
- check repeated activation or double submission when it could duplicate effects.

Assert user-visible results or stable external effects. A successful click command is not evidence that the feature worked.

For wrong final state or a control that appears inert, use `interaction-state-audit` to trace the composed state transitions.

## Gate 3: Visual Regression

1. Use the repository's existing screenshot framework and approved viewport set.
2. Compare the same route, state, data fixture, fonts, and animation policy.
3. Mask only nondeterministic regions whose content is outside the test contract.
4. Review meaningful diffs rather than automatically updating baselines.
5. Treat a missing or incompatible baseline as `INCONCLUSIVE`, not `PASS`.

Do not invent pixel thresholds. Use project-configured tolerances, and preserve the diff artifact when the tooling supports it.

## Gate 4: Accessibility

Combine automation and manual interaction:

- run the repository's configured accessibility scanner;
- inspect labels, names, roles, contrast findings, and landmark structure;
- complete the critical flow with keyboard only;
- verify focus order, focus visibility, modal focus containment, and focus restoration;
- perform a screen-reader spot check when the change affects semantic structure or a critical journey.

An automated scanner covers only part of WCAG. A clean automated report does not justify the statement "the page is accessible."

## Evidence And Verdict

Report:

```markdown
## Browser QA — <environment/URL>
- Scope: <routes and journeys>
- Build/revision: <identifier when available>
- Environment safety: read-only | approved staging mutation

### Runtime
- Console/runtime findings:
- First-party request findings:

### Interactions
- Passed:
- Failed:
- Not exercised:

### Visual
- Baseline status:
- Meaningful diffs:

### Accessibility
- Automated findings:
- Keyboard/manual findings:

### Verdict
PASS | PASS WITH NON-BLOCKING FINDINGS | FAIL | INCONCLUSIVE
```

Use `INCONCLUSIVE` whenever a required environment, identity, baseline, browser capability, or evidence source is unavailable. Do not silently downgrade untested scope to a pass.

## Exit Criteria

- The target revision and environment are identified.
- Critical changed journeys have observable assertions.
- Mutating scope stayed within the approved environment.
- Runtime, network, responsive, visual, and accessibility evidence is reported only where actually collected.
- Failures include reproduction steps and artifacts that do not expose sensitive data.
