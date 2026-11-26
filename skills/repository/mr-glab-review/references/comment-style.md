# Comment style

Review comments should read as a colleague's helpful note, not a verdict. From the first two lines the author should know what the comment is about, whether it blocks the merge, and what to do. Acting on it should take one step, and it should never read as a wall of text.

## Structure

Every comment has the same shape, in this order. Only the headline and the action line are mandatory. Separate them with a blank line: Markdown joins lines that are not separated by one, so the action would render glued to the headline.

```
<severity> <label> · **<gist>** <marker>

👉 <action: one sentence that starts with a verb>

<why: one sentence, or at most two bullets with one fact each>

<one suggestion block, or one short code block>

<details><summary><what is inside, with a count></summary> … </details>

<acknowledgement: one short, specific sentence>
```

1. **First line (headline).** The severity emoji, the severity [label](#severity), a middle dot, the gist in bold, then at most one topic [marker](#markers). The gist names the thing and the change ("Assertion can use `isSorted()`") in at most 12 words. Severity appears only here: do not repeat "not a blocker" at the end. Notifications and collapsed threads show this line first, so it must make sense on its own.
2. **Action line.** Its own paragraph after the headline, starting with `👉`: one concrete step. Offer at most one alternative, joined with "or". For an uncertain finding the action is the question, plus what to do for each answer (two branches at most). Together with the headline it forms a two-line version of the comment.
3. **Why.** The evidence the author needs to agree, not every fact you found: one sentence, or two bullets at most.
4. **Code.** Prefer a one-click fix:
   - An inline comment whose fix only touches lines of this diff hunk uses a `suggestion` block (`suggestion:-N+M`), at most about 15 lines, one per comment. The range replaces exactly the lines it rewrites. The block is the complete replacement text: no placeholders, no "rest unchanged", and only identifiers that already exist on the source branch (when a new one is needed, the action line says where to add it). Do not add "apply it with the button".
   - A fix that spans other files or lines outside the hunk uses a plain code block of at most 10 lines, or goes under `<details>`.
   - A fix that needs two suggestion blocks in different places: post the second as its own short comment whose headline points to the first ("Second part of the suggestion above").
5. **Details.** Everything only some readers need goes under `<details><summary>`: longer code, evidence tables, logs, a list of more than three items, links to in-repo examples beyond the first, the reasoning behind a non-obvious choice. The summary says what is inside and how much ("Unused methods (7)", "Why not plain locators").
6. **Acknowledgement.** One short sentence about something specific that is right, last in the comment. It closes on a friendly note without delaying the action. Skip it rather than write a generic one.

**One finding per comment.** A second, unrelated point is a separate comment. Related small points (for example the same fix in three places) stay in one comment, with the places under `<details>`.

**Short form.** When the fix is a suggestion block and the gist already says why, the comment can be just the headline, the action line and the suggestion.

**Prescribe the outcome, not the exact shape.** When the fix is a refactor the author will design (a new method, a new class), name the target and point to an in-repo example; do not dictate a signature unless a convention requires it.

Tone:

- Phrase uncertain points as a request to double-check, never as a fact.
- Avoid reviewer jargon ("nit", "smell"), capital letters for emphasis, and exclamation marks.
- Do not open with praise followed by "but"; the acknowledgement goes last.

## Severity

Severity uses the same scale as the reviewer summary, so the reviewer approves exactly what the author will see. The profile may translate the labels; the emoji stay.

| Emoji | Label | Use when | Merge |
| --- | --- | --- | --- |
| 🔴 | Before merge | The test checks nothing or the wrong thing, fails, or breaks other tests | Blocks until fixed |
| 🟠 | Should fix | Mismatch with the requirement or an agreed team rule | Fix in this MR, or agree otherwise in the thread |
| 🟡 | Not a blocker | Simplification, cleanup, reuse, ideas; also new code repeating an issue that older neighbouring code has | Merge is fine; a follow-up MR is fine |
| ❔ | Question | The finding is *uncertain* or the code may be intentional | Blocks only if the answer confirms a 🔴 or 🟠 |

A 🔴 or 🟠 comment names its evidence in the why part: a requirement, a `file:line`, or an observed result. Without evidence it is a ❔.

A label may carry one short qualifier after a comma, for example "Not a blocker, fine as a follow-up MR".

## Markers

The topic marker is optional, at most one, placed after the gist.

| Marker | Meaning |
| --- | --- |
| 🔍 | Possible hidden problem |
| 🧹 | Cleanup |
| ✂️ | Simplify |
| 🔀 | Mismatch with requirement or neighbours |
| 💡 | Idea |
| 🔄 | Process |

## Checklist

Before showing a comment to the reviewer, check each line; a failed check means redraft:

- [ ] Line 1 matches `<emoji> <label> · **<gist>**` with an optional single marker; the emoji is one of 🔴 🟠 🟡 ❔ and equals the severity in the reviewer summary.
- [ ] The gist is at most 12 words and names both the subject and the change or question.
- [ ] Line 2 is blank and line 3 starts with `👉` and holds one action, with at most one "or" alternative.
- [ ] Severity wording appears only in line 1.
- [ ] Visible text, excluding the headline, the action line, code blocks and `<details>`, is at most 60 words; at most two visible bullets.
- [ ] An inline comment whose fix stays inside the hunk uses a `suggestion` block; at most one per comment; it is a complete replacement with no placeholders and no identifiers missing on the source branch.
- [ ] A visible plain code block is at most 10 lines; anything longer is under `<details>`.
- [ ] Every `<details>` summary states its content and, for lists or code, the count.
- [ ] One finding per comment.
- [ ] A 🔴 or 🟠 comment names its evidence; a ❔ comment asks and says what to do for each answer.
- [ ] The acknowledgement, if present, is one specific sentence of at most 12 words, placed last.
- [ ] It does not say "wrong" or "bug" without evidence; no jargon, capitals for emphasis or exclamation marks.
- [ ] Language follows the profile; the default is the language of the MR description.

When a comment fails the word budget, move material into `<details>` or split the comment; do not delete the evidence.

## Examples

### Example 1: Dead code list

Before:

> You added a lot of methods that nobody uses. UserSteps.createGuest, UserSteps.archiveUser, UserSteps.resetPassword, OrderGenerator.withCoupon, OrderGenerator.withGift, OrderGenerator.withDelivery and OrderGenerator.bulk are never called from any test. This is dead code and should not be merged, please remove all of it.

After:

> 🟡 Not a blocker, fine as a follow-up MR · **Seven new helpers have no callers yet** 🧹
>
> 👉 Drop them from this MR, or keep the ones you plan to use next.
>
> No test calls the methods listed below.
>
> <details><summary>Methods without callers (7)</summary>
>
> - `UserSteps.createGuest`
> - `UserSteps.archiveUser`
> - `UserSteps.resetPassword`
> - `OrderGenerator.withCoupon`
> - `OrderGenerator.withGift`
> - `OrderGenerator.withDelivery`
> - `OrderGenerator.bulk`
>
> </details>
>
> The new steps follow the existing builder style nicely.

### Example 2: Mixed-up constant (one-click fix)

Before:

> The verification uses the wrong constant. MISSING_X_FIELDS is used in the assertion but EMPTY_X_FIELDS is declared right next to it and never used, so this is a bug and the test checks nothing useful.

After:

> 🟠 Should fix · **The assertion may need `EMPTY_X_FIELDS` instead of `MISSING_X_FIELDS`** 🔀
>
> 👉 Switch the assertion, or remove the unused constant if `MISSING_X_FIELDS` is intended.
>
> `EMPTY_X_FIELDS` is declared next to it and unused, and the requirement expects the empty-fields error.
>
> ````
> ```suggestion:-0+0
>     assertThat(errors).containsExactlyInAnyOrderElementsOf(EMPTY_X_FIELDS);
> ```
> ````
>
> The test covers the right scenario.

### Example 3: Test for a deleted test case (question)

Before:

> This test is for a test case that no longer exists in the tracker. It was deleted, so this test is obsolete and pointless. Remove it.

After:

> ❔ Question · **Is the linked test case still current?** 🔍
>
> 👉 Please check: if it was removed on purpose, this test can go (here or in a follow-up MR); if not, relink it to the current case.
>
> Its id no longer opens in the tracker; it looks deleted.
>
> The test itself is clear and well structured.
