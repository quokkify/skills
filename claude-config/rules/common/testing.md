# Testing Requirements

## Minimum Test Coverage: 80%

Test Types (ALL required):
1. **Unit Tests** - Individual functions, utilities, components
2. **Integration Tests** - API endpoints, database operations
3. **E2E Tests** - Critical user flows (framework chosen per language)

## Test-Driven Development

MANDATORY workflow:
1. Write test first (RED)
2. Run test - it should FAIL
3. Write minimal implementation (GREEN)
4. Run test - it should PASS
5. Refactor (IMPROVE)
6. Verify coverage (80%+)

## Bug Fix E2E Requirement

After fixing any bug (new or regression), write an E2E test that reproduces the original failure scenario. This is MANDATORY when the bug is user-visible (UI, API response, navigation, data display). Use a unit or integration test only when an E2E test is technically not feasible (e.g. internal utility with no UI surface), and document why.

The E2E test must:
1. Reproduce the exact flow that triggered the bug
2. Assert the correct behavior (not the broken one)
3. Be tagged to indicate it is a regression guard (e.g. comment `// regression: <short description>` or a Playwright tag)

Rationale: the `fetchRepair` trailing-slash bug and the mobile CSS cascade bug both reached production without E2E coverage. A targeted E2E test would have caught both during CI.

## Troubleshooting Test Failures

1. Use **tdd-guide** agent
2. Check test isolation
3. Verify mocks are correct
4. Fix implementation, not tests (unless tests are wrong)

## Agent Support

- **tdd-guide** - Use PROACTIVELY for new features, enforces write-tests-first
