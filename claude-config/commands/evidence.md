You **MUST** follow `~/.claude/rules/common/investigation-discipline.md` strictly. The rule is non-negotiable.

You are debugging the failure described below. Do **NOT** propose a fix until all four steps are complete. Do **NOT** fabricate TTLs, timeouts, or behavior assumptions.

**Failure context:**
$ARGUMENTS

## Mandatory 4-step flow

### Step 1 — Fetch the actual logs

Choose the right source based on context:
- **GitLab CI / pipelines** → fetch via `glab` or curl from the job URL. Do not summarize from memory.
- **Local test failure** → re-run the failing test, capture the literal output.
- **Docker Compose / static stage** → `docker logs <container>` or read the mounted log file.
- **K8s stage** → use `/evidence:k8s` instead — it adds pod/secret/port-forward handling.
- **Production** → pull from Grafana, Loki, or app log aggregator.

If logs cannot be fetched — STOP and tell what's blocking. Do not guess.

### Step 2 — Quote the exact error line

- Paste the literal error message / stack trace / failed assertion.
- Do not paraphrase.
- If the error is a **timeout** (`ConditionTimeoutException`, `awaitility`, poll timeout) —
  the timeout is a **symptom**, not the cause. Continue to Step 3 to find why the condition
  never became true.

### Step 2.5 — Map the full data path (multi-service only)

When the bug spans more than one service (e.g. Java → API → Kafka → Consumer → DB):
- Write the chain explicitly before reading any code: `A → B → C → D`
- For each step: what is written, to what field, in what type, in what store
- For each step: what is read/queried, with what type, against what field
- **Before querying any storage:** verify field names from the model/schema definition —
  one-letter differences (`acl` vs `al`) mean completely different data.

### Step 3 — Trace to source code

- Open the file referenced in the stack trace.
- Read the surrounding code.
- Quote the line(s) that produced the failure.
- For **type / value mismatches in storage**: check both the WRITE path (what type is stored)
  and the QUERY path (what type is used). A mismatch between the two is often the root cause.

### Step 4 — Separate verified from hypothesized

```
VERIFIED:
- <fact 1 with source: file:line or log excerpt>
- <fact 2 with source>

HYPOTHESIZED:
- <speculation, explicitly marked as speculative>
```

If a hypothesis has no evidence in code or logs — mark it `speculative` and do not act on it.

---

## Hypothesis validation — closing the 2+2 gap

A partial hypothesis is not a root cause until you answer:
**"why does it fail NOW but not before?"**

If the buggy code predates the failure, something else changed. Do not stop at the symptom.

1. **Is this code new or old?**
   `git log --oneline --follow -- <file>` — if old, it is NOT the root cause alone.

2. **What changed between "was working" and "now"?**
   Find the date the test was written or last passed, then:
   `git log --oneline --after="YYYY-MM-DD" -- <relevant_service_files>`

3. **Always check dependency version changes** in that window:
   `git diff <before>..<after> -- Gemfile.lock pom.xml package.json`
   Framework upgrades silently change behavior:
   - ORM type coercion (Mongoid 8→9, Hibernate, ActiveRecord)
   - Serialization defaults (Jackson, json gem, Gson)
   - Query building (Mongoid Criteria, Spring Data)

4. **Connect the two pieces:**
   `<old buggy code>` + `<new version that stopped masking it>` = root cause.
   Neither piece alone is sufficient.

5. Do NOT conclude "it was always broken" without checking the full change window.

**Pattern:** *"This code has been broken for years, but tests only started failing after a
dependency upgrade removed implicit type coercion / fallback behavior."*

---

## Hard rules

- No fix proposals before Step 4 is complete.
- No fabricated values (cache TTLs, timeouts, retry counts, version assumptions).
- If a "fix" is unrelated to the actual failure — STOP, re-investigate from Step 1.
- After Step 4, summarize findings and **ASK** before proposing a fix.
- When adapting a test to a broken service: state clearly what coverage is lost and why the
  service-side fix is the correct long-term solution.

---

## Past incidents (do not repeat)

- **GDv1 flaky test:** fabricated "60-second cache TTL" — real value was 8h+1day in Ruby backend.
- **PAQA-4942667:** `StringifyFilter` (2022) + Mongoid 8→9 upgrade (2026-03-12) = root cause.
  Partial hypothesis (stringify bug) was correct but incomplete until git history revealed the
  upgrade that stopped masking it.
