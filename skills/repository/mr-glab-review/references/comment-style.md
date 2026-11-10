# Comment style

Review comments should read as a colleague's helpful note, not a verdict. Keep them light, specific and easy to act on.

## Structure

1. A bold one-line gist, ending with a marker. This line must make sense on its own.
2. "What I noticed": one to three bullets, one fact each.
3. "Suggestion": a concrete action. When there are two options, join them with "or".
4. Optionally, a short code block (about 10 lines at most) and a pointer to an existing in-repo example.

Tone:

- Acknowledge what is right first.
- Mark non-blockers explicitly, for example "not a blocker, fine as a follow-up MR".
- Phrase uncertain points as a request to double-check.
- Avoid reviewer jargon ("nit", "smell"), capital letters for emphasis and exclamation marks.
- Put lists longer than five items under `<details><summary>`.

## Markers

| Marker | Meaning |
| --- | --- |
| 🔍 / 🙂 | Please double-check |
| 🧹 | Cleanup |
| ✂️ | Simplify |
| 🔀 | Mismatch |
| 💡 | Idea, non-blocker |
| 🔄 | Process |

## Checklist

Before showing a comment to the reviewer:

- The first line stands alone.
- It is at most about 120 words, excluding code and `<details>`.
- A concrete suggestion is present.
- It does not say "wrong" or "bug" without evidence.
- Language follows the profile; the default is the language of the MR description.

## Examples

### Example 1: Dead code list

Before:

> You added a lot of methods that nobody uses. UserSteps.createGuest, UserSteps.archiveUser, UserSteps.resetPassword, OrderGenerator.withCoupon, OrderGenerator.withGift, OrderGenerator.withDelivery and OrderGenerator.bulk are never called from any test. This is dead code and should not be merged, please remove all of it.

After:

> **Several new helpers have no callers yet** 🧹
>
> The new steps look tidy and follow the existing builder style.
>
> **What I noticed**
> - No test calls the methods listed below.
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
> **Suggestion**
> Drop them from this MR, or keep the ones you plan to use in the next MR. Not a blocker.

### Example 2: Mixed-up constant

Before:

> The verification uses the wrong constant. MISSING_X_FIELDS is used in the assertion but EMPTY_X_FIELDS is declared right next to it and never used, so this is a bug and the test checks nothing useful.

After:

> **The assertion may use a different constant than intended** 🔀
>
> The test covers the right scenario.
>
> **What I noticed**
> - The verification uses `MISSING_X_FIELDS`.
> - `EMPTY_X_FIELDS` sits right next to it and is not used anywhere.
>
> **Suggestion**
> Please double-check which of the two the response should contain. If `EMPTY_X_FIELDS` is the intended one, switch the assertion to it; otherwise remove the unused constant.
>
> ```java
> assertThat(errors).containsExactlyInAnyOrderElementsOf(EMPTY_X_FIELDS);
> ```

### Example 3: Test for a deleted test case

Before:

> This test is for a test case that no longer exists in the tracker. It was deleted, so this test is obsolete and pointless. Remove it.

After:

> **This test may belong to a test case that was removed in the tracker** 🔍
>
> The test itself is clear and well structured.
>
> **What I noticed**
> - The linked test case id no longer opens in the tracker; it looks deleted.
>
> **Suggestion**
> Please double-check whether the case was removed on purpose. If so, this test can go in this MR, or in a follow-up MR if you prefer to keep this one focused.
