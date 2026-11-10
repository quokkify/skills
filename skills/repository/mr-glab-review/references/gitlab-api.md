# GitLab API recipes

All calls use the GitLab REST API v4 through `glab api`. Add `--hostname <host>` when the MR lives on a host other than the default `glab` host. `<skill-dir>` is the directory that contains this skill. `<scratch>` is a temporary directory for the session, used only for disposable files (diff, payloads). The resume state file lives elsewhere: `<state_dir>/<host>__<encoded_project>__<iid>.json`, where `<state_dir>` is the profile `state_dir` or `${XDG_STATE_HOME:-~/.local/state}/mr-glab-review`.

## Resolve the MR

Parse the MR URL, then fetch the MR to get `diff_refs` and the diff text.

```bash
python3 <skill-dir>/scripts/mr_glab.py parse-url https://example.gitlab.com/group/app/-/merge_requests/42
# {"host": "example.gitlab.com", "project_path": "group/app", "iid": 42, "encoded_project": "group%2Fapp"}

glab api --hostname <host> projects/<encoded>/merge_requests/<iid> > <scratch>/mr.json
glab mr diff <iid> --repo https://<host>/<project_path> --color=never > <scratch>/mr.diff
```

The diff must come from `glab mr diff`: the line helpers expect its unified format and its paths.

- `diff_refs` in `mr.json` holds `base_sha`, `head_sha` and `start_sha`. Extract that object to `<scratch>/refs.json`; `draft-payload` reads it:

  ```bash
  python3 -c 'import json,sys; json.dump(json.load(sys.stdin)["diff_refs"], sys.stdout)' < <scratch>/mr.json > <scratch>/refs.json
  ```

- Compare the number of files in `mr.diff` (`grep -c '^diff --git' <scratch>/mr.diff`) with `changes_count` in `mr.json`, and check its `overflow` flag; a missing `overflow` field means `false`. If files are missing, or `overflow` is `true`, tell the reviewer which files the review cannot see before going on.
- Get the reviewer's username and the existing discussions, so findings the reviewer already raised are not duplicated. Quote the URL in the shell; if exactly 100 entries come back, fetch `&page=2`, `&page=3`, ... and merge the arrays into one JSON list before using it (do not use `--paginate`: its output may be several concatenated arrays):

  ```bash
  glab api --hostname <host> user    # "username" is the reviewer
  glab api --hostname <host> 'projects/<encoded>/merge_requests/<iid>/discussions?per_page=100' > <scratch>/discussions.json
  ```

  Each discussion holds `notes[]` with `author.username`, `system`, `body`, `resolved` and, for inline notes, `position`.

- Find the new-side line number for a snippet with `python3 <skill-dir>/scripts/mr_glab.py new-line <scratch>/mr.diff <path> <text>`. An empty list means the text is not in the diff. More than one number means the match is ambiguous; pick by context.
- Check that a line can carry an inline position with `python3 <skill-dir>/scripts/mr_glab.py in-diff <scratch>/mr.diff <path> <line>` (exit 0 = in diff, 1 = not in diff, 2 = usage or IO error).
- Get the full position of a new-side line with `python3 <skill-dir>/scripts/mr_glab.py position <scratch>/mr.diff <path> <new_line>`. It prints `{"new_path", "old_path", "new_line", "old_line"}`; `old_path` differs from `new_path` for a renamed file, and `old_line` is `null` for an added line and set for an unchanged context line. Exit 1 means the line is not in the diff; exit 2 is a usage or IO error.

## Draft notes

Approved comments are staged as draft notes. A draft is visible only to its author until it is published.

Fill the payload flags from the `position` output: `--path` = `new_path`, `--old-path` = `old_path`, `--line` = `new_line`, and `--old-line` = `old_line` only when it is not `null`. GitLab needs only `new_line` for an added line but both lines for an unchanged one.

Build the payload, send it as JSON and save the response, then record it in the state file:

```bash
python3 <skill-dir>/scripts/mr_glab.py draft-payload \
  --note-file <scratch>/note.md \
  --refs-file <scratch>/refs.json --path <new_path> --old-path <old_path> \
  --line <new_line> [--old-line <old_line>] \
  --out <scratch>/draft.json

glab api --hostname <host> --method POST \
  projects/<encoded>/merge_requests/<iid>/draft_notes \
  -H 'Content-Type: application/json' --input <scratch>/draft.json > <scratch>/draft-response.json

python3 <skill-dir>/scripts/mr_glab.py record-draft \
  --state <state-file> --item <item_id> --response <scratch>/draft-response.json
```

`record-draft` needs an integer `id` in the response, sets the item's `status` to `drafted` and its `draft_id`, and rewrites the state file atomically (exit 2 on a missing item, a response without `id`, or invalid JSON).

Endpoint reference: `POST projects/:id/merge_requests/:iid/draft_notes`. Never put `:id`-style placeholders in a command: `glab api` substitutes them from the repository in the current directory, which may be a different project. Always use `<encoded>` and `<iid>`.

Omit `--refs-file`, `--path`, `--old-path`, `--line` and `--old-line` for a general note.

The payload is a JSON object with a `"note"` field and, for an inline comment, a `position` object:

```json
{
  "note": "**Gist** 🧹\n\n...",
  "position": {
    "position_type": "text",
    "base_sha": "<base_sha>",
    "head_sha": "<head_sha>",
    "start_sha": "<start_sha>",
    "new_path": "<new_path>",
    "old_path": "<old_path>",
    "new_line": 12,
    "old_line": 11
  }
}
```

`old_line` appears only for an unchanged context line. An inline position is valid only for a line present in the diff. Otherwise stage a general note that names `file:line` in its first line.

List and remove drafts. If exactly 100 drafts come back, fetch `&page=2`, ... and merge the arrays before passing them on:

```bash
glab api --hostname <host> 'projects/<encoded>/merge_requests/<iid>/draft_notes?per_page=100' > <scratch>/drafts.json
glab api --hostname <host> --method DELETE \
  projects/<encoded>/merge_requests/<iid>/draft_notes/<draft_note_id>
```

## Publish

Right before publishing, list the drafts again into `<scratch>/drafts.json` and reconcile them with the state file:

```bash
python3 <skill-dir>/scripts/mr_glab.py reconcile --state <state-file> --drafts <scratch>/drafts.json
# {"missing": [item ids whose draft is gone], "foreign": [draft ids no item references], "duplicate": [item ids sharing a draft id], "ok": true}
```

Exit 0 means `ok`; exit 1 means the sets differ (resolve `missing`, `foreign` and `duplicate` first; an id-less draft shows as `null` in `foreign`); exit 2 is a usage or IO error. Then publish every staged draft in one batch, only after the reviewer confirms the final list:

```bash
glab api --hostname <host> --method POST \
  projects/<encoded>/merge_requests/<iid>/draft_notes/bulk_publish
```

Afterwards list the MR discussions to confirm the notes are visible:

```bash
glab api --hostname <host> projects/<encoded>/merge_requests/<iid>/discussions
```

Build each thread link as `<mr web_url>#note_<note_id>`, with `web_url` from `mr.json` and the note id from the discussions list.

## Edit a note

To change a note that is already published, update it by discussion and note id. The body field here is `body`, not `note`. Write `{"body": "<new text>"}` to `<scratch>/edit.json` (escape quotes and newlines as JSON), then send it:

```bash
glab api --hostname <host> --method PUT \
  projects/<encoded>/merge_requests/<iid>/discussions/<discussion_id>/notes/<note_id> \
  -H 'Content-Type: application/json' --input <scratch>/edit.json
```

Drafts are not edited this way: delete the draft and stage a new one.

## Errors

- 429 (rate limited): back off 60 s, then 120 s, then 240 s, and retry. Send strictly one request at a time; never post drafts in parallel.
- 401 (unauthorized): run `glab api user`. If it also fails, stop and ask the user to run `glab auth login --hostname <host>`.
- 400 or 422 on an inline position: the line is probably not in the diff. Re-check with `in-diff`; if it is absent, stage a general note that names `file:line`.
- Any other error: report the status and message to the user and do not retry blindly.
