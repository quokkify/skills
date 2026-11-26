# Description shape

Headings and language come from the profile; the defaults are shown here.

## Template

```markdown
<One sentence: what changed and for whom, why included. No class names.>

> <Optional: stacked on !N / merge after release X.>

## What changed
- <one fact>

## Verification
- `<command or job>`: <result>

## Needs from you
<One line: what to look at or do. Omit the section when nothing is asked.>

<foreign marker blocks, unchanged>

<keep_lines: tracker links, closing keywords, quick actions>
```

## Rules

1. **Order.** Outcome first, then the list, then verification. The "why" goes into the first sentence, not into its own section.
2. **Budget.** Visible text within the profile budget (default 120 words / 12 lines). Headings count as lines, not words. `keep_lines`, marker blocks and `<details>` content do not count. Over budget: move detail into one `<details>`.
3. **Size.** Small MR (one or two files): first sentence and `Verification`; no `What changed`. Medium: the full template, 2–5 bullets. Large: the template plus one `<details>`; more than 7 bullets means suggest splitting the MR.
4. **Bullets.** One fact, at most 20 words, at most one backticked identifier, no parenthetical asides.
5. **Words.** Spell out a term the reader may not know at its first use. One term means one thing throughout.
6. **Verification.** Only what actually ran, as `command or job: result`.
7. **Drop.** Static template checklists, file-by-file walkthroughs, the history of attempts, bot summaries, marketing words, closing recaps, and every section the profile lists in `drop_sections`.

## Examples

Small MR:

```markdown
The report "amount less than" filter is now tested with values from 1: at 0 the report is always empty, so the test always failed.

## Verification
- `ReportAmountFilterTest` locally: 4/4 green
- MR pipeline: green

Closes SHOP-101
```

Medium MR with a demo block:

```markdown
The admin orders page got a CSV export button. Tests check that the file downloads and lists every order on the page.

## What changed
- New test for exporting from the orders list.
- New test for exporting with a status filter.
- The "download and read CSV" step moved to the shared steps class.

## Verification
- `OrdersExportTest` on the stand: 6/6 green
- MR pipeline: green

## Needs from you
Look at the shared CSV step: other reports will use it.

<!-- demo:start -->
## Demo
Video: https://example.com/demo.mp4
<!-- demo:end -->

Tracker: [CASE-1](https://tracker.example.com/cases/1), [CASE-2](https://tracker.example.com/cases/2)
Closes SHOP-102
```
