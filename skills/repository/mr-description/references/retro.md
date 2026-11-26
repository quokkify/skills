# Retro

Each retro names one bottleneck and changes one rule. Changing several rules at once hides which one helped.

## Bottleneck tags

`mr_log.py record` accepts only these tags. Tag what the author changed in the draft:

| Tag | The author… |
|---|---|
| `length` | shortened the text |
| `main-point-not-first` | rewrote or moved the first sentence |
| `jargon` | replaced a term or removed an identifier |
| `density` | split a bullet into several |
| `mechanism-not-outcome` | replaced "how it was done" with "what changed" |
| `noise` | deleted a whole section |
| `missing-context` | added context the draft lacked |
| `no-ask` | added the "needs from you" line |

## Steps

1. `python3 <skill-dir>/scripts/mr_log.py stats --state-dir <state_dir> --last 10`.
2. Optionally read reviewer questions on the logged MRs ("what is this?", "why?"). Show each to the author and count only the ones the author confirms as caused by the description.
3. Name the most frequent tag. Ties: prefer the one that also appears in confirmed reviewer questions.
4. For each entry carrying that tag, read `<state_dir>/<entry texts>/draft.md` and `final.md` (the `texts` field of the entry). Propose **one** rule that would have produced the author's final text, with a before/after taken from those pairs.
5. The author accepts, edits or rejects it. On accept, write it to the caller's `style_rules`. The file holds at most 12 rules: a new rule replaces or merges an old one.
6. `python3 <skill-dir>/scripts/mr_log.py mark-retro --state-dir <state_dir>`.

## Signals of success and of over-correction

- Success: `accepted_unedited_share` goes up across retros, and `avg_final_words` does not.
- Over-compression: `missing-context` becomes frequent. Raise the word budget instead of adding rules.

## Promotion

A rule that survived two retros and contains no organisation details can become a candidate for the shared default rules through the library's skill-review process, after the author approves.
