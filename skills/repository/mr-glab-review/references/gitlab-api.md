# GitLab API recipes

All calls use the GitLab REST API v4 through `glab api`. Add `--hostname <host>` when the MR lives on a host other than the default `glab` host. `<skill-dir>` is the directory that contains this skill. `<scratch>` is a temporary directory for the session.

## Resolve the MR

Parse the MR URL, then fetch the MR to get `diff_refs` and the diff text.

```bash
python3 <skill-dir>/scripts/mr_glab.py parse-url https://example.gitlab.com/group/app/-/merge_requests/42
# {"host": "example.gitlab.com", "project_path": "group/app", "iid": 42, "encoded_project": "group%2Fapp"}

glab api --hostname <host> projects/<encoded>/merge_requests/<iid> > <scratch>/mr.json
glab mr diff <iid> --repo <host>/<project_path> --color=never > <scratch>/mr.diff
```

- `diff_refs` in `mr.json` holds `base_sha`, `head_sha` and `start_sha`. Extract that object to `<scratch>/refs.json`; `draft-payload` reads it:

  ```bash
  python3 -c 'import json,sys; json.dump(json.load(sys.stdin)["diff_refs"], sys.stdout)' < <scratch>/mr.json > <scratch>/refs.json
  ```

- Find the new-side line number for a snippet with `python3 <skill-dir>/scripts/mr_glab.py new-line <scratch>/mr.diff <path> <text>`. An empty list means the text is not in the diff. More than one number means the match is ambiguous; pick by context.
- Check that a line can carry an inline position with `python3 <skill-dir>/scripts/mr_glab.py in-diff <scratch>/mr.diff <path> <line>` (exit 0 = in diff, 1 = not in diff, 2 = usage or IO error).

## Draft notes

Approved comments are staged as draft notes. A draft is visible only to its author until it is published.

Build the payload, then send it as JSON:

```bash
python3 <skill-dir>/scripts/mr_glab.py draft-payload \
  --note-file <scratch>/note.md \
  --refs-file <scratch>/refs.json --path <path> --line <n> \
  --out <scratch>/draft.json

glab api --hostname <host> --method POST \
  projects/<encoded>/merge_requests/<iid>/draft_notes \
  -H 'Content-Type: application/json' --input <scratch>/draft.json
```

Endpoint reference: `POST projects/:id/merge_requests/:iid/draft_notes`. Never put `:id`-style placeholders in a command: `glab api` substitutes them from the repository in the current directory, which may be a different project. Always use `<encoded>` and `<iid>`.

Omit `--refs-file`, `--path` and `--line` for a general note.

The payload is a JSON object with a `"note"` field and, for an inline comment, a `position` object:

```json
{
  "note": "**Gist** 🧹\n\n...",
  "position": {
    "position_type": "text",
    "base_sha": "<base_sha>",
    "head_sha": "<head_sha>",
    "start_sha": "<start_sha>",
    "new_path": "<path>",
    "old_path": "<path>",
    "new_line": 12
  }
}
```

An inline position is valid only for a line present in the diff. Otherwise stage a general note that names `file:line` in its first line.

List and remove drafts:

```bash
glab api --hostname <host> projects/<encoded>/merge_requests/<iid>/draft_notes
glab api --hostname <host> --method DELETE \
  projects/<encoded>/merge_requests/<iid>/draft_notes/<draft_note_id>
```

## Publish

Publish every staged draft in one batch, only after the reviewer confirms the final list:

```bash
glab api --hostname <host> --method POST \
  projects/<encoded>/merge_requests/<iid>/draft_notes/bulk_publish
```

Afterwards list the MR discussions to confirm the notes are visible:

```bash
glab api --hostname <host> projects/<encoded>/merge_requests/<iid>/discussions
```

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
