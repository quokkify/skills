# GitLab API recipes

All calls go through `glab api` (GitLab REST API v4). Add `--hostname <host>` when the MR is not on the default `glab` host. Never hardcode a project id: resolve it from the MR URL.

## Resolve the MR

From `https://<host>/<project_path>/-/merge_requests/<iid>`, URL-encode the project path:

```bash
python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' group/app
# group%2Fapp

glab api --hostname <host> projects/<encoded>/merge_requests/<iid> > <scratch>/mr.json
python3 -c 'import json,sys; print(json.load(sys.stdin)["description"] or "", end="")' < <scratch>/mr.json > <scratch>/current.md
```

`mr.json` also gives `source_branch`, `target_branch`, `sha` (head commit) and `web_url`. Use `<project_path>!<iid>` as the MR ref in the log.

## Diff and commits

```bash
glab mr diff <iid> --repo https://<host>/<project_path> --color=never > <scratch>/mr.diff
glab api --hostname <host> 'projects/<encoded>/merge_requests/<iid>/commits?per_page=100' > <scratch>/commits.json
```

In `draft` mode, before the MR exists, use `git diff <base>...HEAD` and `git log <base>..HEAD` instead.

## Publish

Only after the author's explicit yes:

```bash
glab api --hostname <host> -X PUT projects/<encoded>/merge_requests/<iid> -F description=@<scratch>/final.md > <scratch>/updated.json
```

Confirm by reading `description` from `updated.json` and comparing it with `final.md`.

## Errors

- 401: run `glab api --hostname <host> user`; if it fails too, stop and ask the author to run `glab auth login --hostname <host>`.
- 403 on publish: the author cannot edit this MR; show the final text so they can paste it.
- 429: back off 60 s, then 120 s, then retry once more.
- Any other error: report status and message; do not retry blindly.
