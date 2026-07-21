---
name: repository-quality-gates
description: Design, implement, and review reproducible repository validators, Git hooks, and CI quality gates that inspect the exact artifact being published.
---

# Repository Quality Gates

Use this skill when adding or reviewing repository-level validators, tracked Git hooks, documentation builds, public-content checks, secret scanning, or CI gates.

## Core principle

Validate the exact artifact that will be committed, pushed, or reviewed. A green check against a mutable working tree is not evidence about a different staged snapshot or Git ref.

## Workflow

1. Inventory existing CI, hooks, security policy, contribution guidance, and tool-version conventions.
2. Define fast and full gates:
   - fast: dependency-light structural, link, and targeted boundary checks;
   - full: fast checks, regression tests, generated-document validation, pinned static tools, working-tree secret scan, and full-history secret scan.
3. Implement deterministic validators that aggregate actionable repository-relative errors.
4. Add regression tests for valid input, malformed input, bypass attempts, and host-filesystem isolation.
5. Make local hooks opt-in and refuse to overwrite an existing `core.hooksPath` without explicit force.
6. Add CI that runs the same portable validator with pinned tool versions and minimal permissions.
7. Run shell/workflow linting, tests, documentation build, diff checks, and both secret-scan scopes.
8. Review the complete diff. Create or push a focused branch and open a PR only after explicit user approval or an applicable repository policy authorizes publication.
   - For repository-layout migrations, inspect moved or renamed skill bodies even when Git reports 100% renames. Structural validation does not prove that legacy role names, tool-specific invocation language, home-directory fallbacks, or project-specific stack assumptions were removed.
   - Cross-check documentation claims against the adapter files that actually ship; a notes-only adapter must not be described as providing personas, model routing, or executable setup.
   - Search for both legacy identifiers and concrete project fingerprints such as framework versions, fixed directory conventions, and domain-rule filenames. A canonical portable skill that mandates a named role or tool without a capability-based fallback is a functional portability failure.
9. After every fix commit, re-check the exact PR head plus top-level comments, submitted reviews, inline comments, and active review threads.

## Safety requirements

- Pre-commit validation must use the staged snapshot and the validator implementation from that same snapshot.
- Pre-push validation must either validate every pushed OID independently or enforce a clean exact-`HEAD` contract and reject unsupported refs.
- Never follow repository symlinks into the host filesystem.
- Reject local links that resolve outside the repository, even when the external target exists.
- Handle malformed UTF-8 as an aggregated validation error rather than an uncaught crash.
- Verify PATH-installed tool versions before treating local output as equivalent to pinned CI output.
- Treat privacy pattern checks and Gitleaks as complements to manual review, not proof that content is safe.

## Detailed reference

See `references/repository-validation-git-hooks.md` for staged/pushed artifact patterns, validator hardening, reproducibility rules, and the minimum adversarial regression matrix.

## Completion criteria

- The same portable validation logic runs locally and in CI.
- Fast and full modes have explicit, documented scopes.
- Exact-artifact bypasses have regression coverage.
- Local and CI tool versions are reproducible.
- Working-tree and historical secret scans pass.
- Current-head CI and reviewer findings are clean or explicitly reported as pending.
