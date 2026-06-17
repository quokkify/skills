# Investigation Discipline

## Mandatory before any fix

Before claiming a root cause:
- Verify with EVIDENCE: logs, code, test runs. Do NOT fabricate hypotheses (cache TTLs, behavior assumptions).
- If no evidence exists, mark a hypothesis as "speculative" and deprioritize it.

## CI / test failures

When investigating failing CI or tests:
1. Fetch actual job logs first
2. Quote the exact error line
3. Trace it to the source code that produced it
4. State explicitly: what you VERIFIED vs what you HYPOTHESIZE
5. Only then propose a fix

## Stop conditions

If a "fix" is unrelated to the actual reported failure — STOP and re-investigate.
Do not patch a different problem to make the symptom go away.

## Rationale

Past incident: fabricated "60-second cache TTL" hypothesis for a flaky GDv1 test when the real TTL was 8h+1day in the Ruby backend. Skeptical evidence-first review prevents plausible-but-wrong fixes from reaching production.
