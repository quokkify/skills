# Deploy approval

## Problem

Every deploy waits for a manual approval, even for one-line changes.

## How it works

```mermaid
flowchart LR
  A[Commit] -->|push| B[Checks]
  B -->|green| C{Size?}
  C -->|small| D[Auto-approve]
```

## Pipeline path

```mermaid
flowchart TD
  subgraph Build
    B1[Compile] --> B2[Test]
  end
  subgraph Review
    R1[Risk score] --> R2[Approve]
  end
  subgraph Release
    L1[Deploy] --> L2[Verify]
  end
  B2 --> R1
  R2 --> L1
```

## Rules

| Change size | Approval | Window |
|---|---|---|
| Small | Automatic | Any time |
| Medium | One reviewer | Work hours |
| Large | Two reviewers | Work hours |

## Situations

1. A hotfix lands on Friday evening.
2. A dependency bump touches many files.
3. A config change has no tests.
4. Two small changes touch the same service.

> [!NOTE]
> Medium and large changes keep the current manual flow.

## Open questions

1. Should small changes skip approval completely?
2. Who owns the risk score thresholds?
3. How long do we keep the audit trail?
