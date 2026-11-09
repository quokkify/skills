---
title: Release checklist
visibility: internal
tags: [example]
---

# Release checklist for the sample service

This page collects the steps a maintainer follows before tagging a release.
Read the [project guide](https://example.com/guide) first, then work through the list.

## Preparation

- [x] Update the changelog
- [ ] Bump the version in `pyproject.toml`
- Ask a reviewer at reviewer@example.com

| Item | Owner | Status |
|------|-------|--------|
| Build | CI | green |
| Docs | Ann | pending |

## Verification

Run the suite locally:

```bash
make test && make lint
```

Paths like `src/sample_pkg/config.py:42` wrap on narrow screens.

> [!TIP] Small batches
> Ship small releases more often; they are easier to roll back.

## Publishing

1. Tag the commit.
2. Push the tag.
3. Announce the release with <kbd>Ctrl</kbd>+<kbd>Enter</kbd> in the chat.

### After the release

Watch the dashboards for one hour. A placeholder like <service-name> stays visible as text.
