# Stacked child PR and retro apply

The child PR carries the adoption changes on top of the Renovate branch without touching that branch. Placeholders: `<pr>` parent PR number, `<renovate-branch>` its head branch (from `inspect`), `<head>` its head SHA (`headSha`), `<default>` the default branch.

## Branch naming

- Child branch: `adopt/<renovate-branch without the renovate/ prefix>`, for example `renovate/actions-setup-java-5.x` → `adopt/actions-setup-java-5.x`.
- Never create it under Renovate's `branchPrefix`. Renovate deletes branches under its prefix that it considers stale when `pruneStaleBranches` is enabled (the default): <https://docs.renovatebot.com/configuration-options/#prunestalebranches>.
- If `adopt/<...>` already exists locally or on the remote, reuse it through the drift path below. Never create a second branch or PR for the same parent.

## Create

Use this path only when preflight found no `adopt/<name>` branch (local or remote) and no PR from it. Switch to the child branch before any edit:

```sh
git fetch origin "<renovate-branch>"
git switch -c "adopt/<name>" "<head>"
```

Then apply findings, run consumer checks, and commit on `adopt/<name>`. Bodies go to a temporary directory, never into the repository:

```sh
tmp=$(mktemp -d)
# write the "Child PR body" and "Parent PR comment" templates from templates.md,
# filled in, to "$tmp/child-body.md" and "$tmp/parent-comment.md";
# the child body's last line is: <!-- adoption-base: <head> -->
git push -u origin "adopt/<name>"
gh pr create --base "<renovate-branch>" --head "adopt/<name>" \
  --title "Adopt <package> <to>" --body-file "$tmp/child-body.md"
gh pr comment "<pr>" --body-file "$tmp/parent-comment.md"
rm -r "$tmp"
```

- The child body (see `templates.md`) ends with the hidden marker `<!-- adoption-base: <head> -->`, the parent head SHA at creation.
- Both PRs state the merge order: child into parent, then parent into `<default>`.
- If nothing applies or checks fail: do not push, switch back (`git switch "<renovate-branch>"`), delete the local child (`git branch -D "adopt/<name>"`), and post only the report comment on the parent (body from `templates.md`, written to `"$tmp"`).

## Why the Renovate branch stays untouched

Nothing is pushed to `<renovate-branch>` while the child is open, so Renovate keeps rebasing it. Merging the child makes the branch "modified" and Renovate stops committing to it; merging the parent is the next step anyway. Configuring `gitIgnoredAuthors` (<https://docs.renovatebot.com/configuration-options/#gitignoredauthors>) is not required for this flow.

## Drift: the parent head moved

On re-running `review <pr>` when a child already exists, and while the parent is still open (`gh pr view "<pr>" --json state --jq .state` prints `OPEN`; otherwise use the next section). Do this before any analysis edit:

```sh
tmp=$(mktemp -d)
old=$(gh pr view "adopt/<name>" --json body --jq '.body' \
  | sed -n 's/.*<!-- adoption-base: \([0-9a-f]*\) -->.*/\1/p')
new=$(gh pr view "<pr>" --json headRefOid --jq '.headRefOid')
git fetch origin "<renovate-branch>" "adopt/<name>"
git switch "adopt/<name>"
git reset --hard "origin/adopt/<name>"
git rebase --onto "$new" "$old"
# re-run the review, apply new findings, run consumer checks; revert failing findings
git push --force-with-lease origin "adopt/<name>"
gh pr view "adopt/<name>" --json body --jq '.body' \
  | sed "s/<!-- adoption-base: $old -->/<!-- adoption-base: $new -->/" > "$tmp/child-body.md"
gh pr edit "adopt/<name>" --body-file "$tmp/child-body.md"
rm -r "$tmp"
```

- If the marker is missing, stop and ask: the base cannot be determined safely.
- Branch exists but no PR (an earlier run stopped after the push): there is no marker. Use `old=$(git merge-base "origin/adopt/<name>" "origin/<renovate-branch>")` as the cut point, run the rebase, checks and push above, then open the PR as in Create (body with marker `$new`) and post the parent comment. A local-only branch from a failed run is deleted and recreated through Create.
- If `old` equals `new`, skip the rebase; re-run only the review and checks.
- Conflicts during the rebase: abort (`git rebase --abort`), report, and leave the child as it was.

## Parent merged or closed first

This includes Renovate autoclosing a superseded parent and deleting its branch. Detect it on re-run:

```sh
gh pr view "<pr>" --json state,mergedAt,headRefName
gh pr list --head "adopt/<name>" --state all --json number,state,body
```

A parent `state` of `MERGED` or `CLOSED` takes this path. Do not fetch `<renovate-branch>`: it may be deleted. Rebase first, then retarget or replace, so a squash-merged parent does not leave its commits in the child:

```sh
tmp=$(mktemp -d)
old=$(gh pr list --head "adopt/<name>" --state all --json body --jq '.[0].body' \
  | sed -n 's/.*<!-- adoption-base: \([0-9a-f]*\) -->.*/\1/p')
git fetch origin "<default>" "adopt/<name>"
new=$(git rev-parse "origin/<default>")
git switch "adopt/<name>"
git reset --hard "origin/adopt/<name>"
git rebase --onto "$new" "$old"
# re-run consumer checks; revert failing findings
git push --force-with-lease origin "adopt/<name>"
gh pr list --head "adopt/<name>" --state all --json body --jq '.[0].body' \
  | sed "s/<!-- adoption-base: $old -->/<!-- adoption-base: $new -->/" > "$tmp/child-body.md"
```

The new marker value is the default-branch SHA used as the new base. If the marker is missing, stop and ask.

- Child still open: retarget and update the body.

  ```sh
  gh pr edit "adopt/<name>" --base "<default>" --body-file "$tmp/child-body.md"
  ```

- Child already closed by GitHub (its base branch was deleted): open a new PR from the same branch to `<default>`; add `Supersedes #<old-child>` to `"$tmp/child-body.md"` first.

  ```sh
  gh pr create --base "<default>" --head "adopt/<name>" --body-file "$tmp/child-body.md"
  ```

Finish with `rm -r "$tmp"`. If the rebase leaves no commits (everything already landed), open or retarget nothing: report it and delete the remote child branch only with the user's go-ahead.

## Retro apply (mode `retro --apply`)

Branch `adopt/retro-<YYYY-MM-DD>` (run date) from the default branch. Order:

```sh
tmp=$(mktemp -d)
# 1. issue first: "Retro issue" template from templates.md -> "$tmp/issue.md"
issue_url=$(gh issue create --title "Adoption review: <range>" --body-file "$tmp/issue.md")
# 2. branch
git fetch origin "<default>"
git switch -c "adopt/retro-<YYYY-MM-DD>" "origin/<default>"
# 3. apply findings, 4. run consumer checks, 5. revert failing findings; commit
git push -u origin "adopt/retro-<YYYY-MM-DD>"
# 6. PR: "Retro PR body" template, first line "Closes #<issue>" -> "$tmp/pr.md"
gh pr create --base "<default>" --head "adopt/retro-<YYYY-MM-DD>" \
  --title "Adopt updates: <range>" --body-file "$tmp/pr.md"
# 7. update the issue: applied items checked, reverted items unchecked with their reason
gh issue edit "$issue_url" --body-file "$tmp/issue.md"
rm -r "$tmp"
```

If the branch already exists for that date, reuse it (rebase onto `origin/<default>`) instead of creating a second one. If nothing applies after checks, do not push or open a PR; delete the local branch and update the issue with the reasons.

## Recovery checklist

- `gh` failure midway: report which of push, PR, comment succeeded; re-running `review <pr>` resumes through the drift path.
- Wrong base on an existing child: `gh pr edit --base` to the correct branch, then rebase as above.
