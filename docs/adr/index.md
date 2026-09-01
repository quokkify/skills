---
title: Decision Records
---

# Decision Records

Durable architecture decisions for this repository. Each record keeps its context, the alternatives that were genuinely considered, and the consequences — including the negative ones — readable after the discussion that produced it has been forgotten.

The format follows the in-repo `architecture-decision-records` skill. A decision is never rewritten to pretend it was different; it is superseded by a newer record.

| ADR | Status | Decision |
| --- | --- | --- |
| [ADR-0001](0001-publish-generic-global-agent-adapters.md) | accepted | Publish genericized global agent adapters, and keep every user's real configuration in a private overlay |
| [ADR-0002](0002-reference-project-toolkit-by-release-tag.md) | accepted | Reference `quokkify/project-toolkit` by its exact release tag and let the template own `release.yml` in full |
