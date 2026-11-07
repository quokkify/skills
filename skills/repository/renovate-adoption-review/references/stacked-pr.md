# Stacked child PR (mode `review`)

The child PR carries the adoption changes on top of the Renovate branch without touching that branch. Placeholders: `<pr>` parent PR number, `<renovate-branch>` its head branch (from `inspect`), `<head>` its head SHA (`headSha`), `<default>` the default branch.

## Branch naming

- Child branch: `adopt/<renovate-branch without the renovate/ prefix>`, for example `renovate/actions-setup-java-5.x` → `adopt/actions-setup-java-5.x`.
- Never create it under Renovate's `branchPrefix`. Renovate deletes branches under its prefix that it considers stale when `pruneStaleBranches` is enabled (the default): <https://docs.renovatebot.com/configuration-options/#prunestalebranches>.
- If `adopt/<...>` already exists locally or on the remote, reuse it through the drift path below. Never create a second branch or PR for the same parent.

## Create

```sh
git fetch origin "<renovate-branch>"
git switch -c "adopt/<name>" "<head>"
# apply findings, run consumer checks, commit
git push -u origin "adopt/<name>"
gh pr create --base "<renovate-branch>" --head "adopt/<name>" \
  --title "Adopt <package> <to>" --body-file child-body.md
gh pr comment "<pr>" --body-file parent-comment.md
```

- The child body (see `templates.md`) ends with the hidden marker `<!-- adoption-base: <head> -->`, the parent head SHA at creation.
- Both PRs state the merge order: child into parent, then parent into `<default>`.
- If nothing applies or checks fail, create no branch and no PR: post only the report comment on the parent.

## Why the Renovate branch stays untouched

Nothing is pushed to `<renovate-branch>` while the child is open, so Renovate keeps rebasing it. Merging the child makes the branch "modified" and Renovate stops committing to it; merging the parent is the next step anyway. Configuring `gitIgnoredAuthors` (<https://docs.renovatebot.com/configuration-options/#gitignoredauthors>) is not required for this flow.

## Drift: the parent head moved

On re-running `review <pr>` when a child already exists:

```sh
old=$(gh pr view "adopt/<name>" --json body --jq '.body' \
  | sed -n 's/.*<!-- adoption-base: \([0-9a-f]*\) -->.*/\1/p')
new=$(gh pr view "<pr>" --json headRefOid --jq '.headRefOid')
git fetch origin "<renovate-branch>" "adopt/<name>"
git switch "adopt/<name>"
git reset --hard "origin/adopt/<name>"
git rebase --onto "$new" "$old"
# re-run consumer checks; revert failing findings
git push --force-with-lease origin "adopt/<name>"
gh pr view "adopt/<name>" --json body --jq '.body' \
  | sed "s/<!-- adoption-base: $old -->/<!-- adoption-base: $new -->/" > child-body.md
gh pr edit "adopt/<name>" --body-file child-body.md
```

- If the marker is missing, stop and ask: the base cannot be determined safely.
- If `old` equals `new`, skip the rebase; re-run only the review and checks.
- Conflicts during the rebase: abort (`git rebase --abort`), report, and leave the child as it was.

## Parent merged or closed first

This includes Renovate autoclosing a superseded parent and deleting its branch.

- Child still open: retarget and rebase onto the default branch, then update the marker.

  ```sh
  gh pr edit "adopt/<name>" --base "<default>"
  git fetch origin "<default>"
  git rebase --onto "origin/<default>" "$old"
  # re-run consumer checks
  git push --force-with-lease origin "adopt/<name>"
  ```

- Child already closed by GitHub (its base branch was deleted): open a new PR from the same branch to `<default>` and link the closed one in its body (`Supersedes #<old-child>`).

  ```sh
  gh pr create --base "<default>" --head "adopt/<name>" --body-file child-body.md
  ```

## Recovery checklist

- `gh` failure midway: report which of push, PR, comment succeeded; re-running `review <pr>` resumes through the drift path.
- Wrong base on an existing child: `gh pr edit --base` to the correct branch, then rebase as above.
