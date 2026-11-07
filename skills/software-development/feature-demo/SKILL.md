---
name: feature-demo
description: Use when the user explicitly asks to record a demo video of a feature for a merge or pull request; drafts a captioned scenario for approval, records it with Playwright on an isolated compose stand, and publishes the video to a `demos` branch with a `## Demo` block in the request.
---

# Feature Demo Video

Record a short captioned video of a web-app feature from a merge or pull request (MR), so a non-technical product owner can decide whether the feature behaves as intended. The video, the scenario, and a summary go to an orphan `demos` branch; the MR description gets a `## Demo` block with the link, what is shown, open questions, and what is not shown.

Run this skill only on an explicit request. It never runs on its own after a push, and it re-records an existing demo only when asked.

## Prerequisites

- Node.js 20 or newer, then `npm ci` in this skill's `scripts/` directory (installs the pinned `playwright`).
- A Chromium build: `CHROME_BIN`, else the newest Chrome for Testing under `~/.cache/selenium/chrome/`, else Playwright's own browser (`npx playwright install chromium` in `scripts/`).
- Docker with Compose v2 (`up --wait`), `ffmpeg` and `ffprobe`, `git`, and `bash`.
- `gh` (GitHub) or `glab` (GitLab) authenticated for the repository; `git push` to `origin` must work with the identity configured for that repository.
- `gh` and `glab` must act as the identity that should author the MR edits and comments. When that differs from the CLI's own login, export `GH_TOKEN` or `GITLAB_TOKEN` for this repository before publishing (in the shell, never in global configuration). On GitHub, `publish.sh` uses only the REST API (`gh api`).
- A project adapter `demo.config.mjs` (see [Adapter contract](#adapter-contract)), its seed and reset steps, and synthetic fixture files. Start from `templates/demo.config.mjs`.

Below, `$SKILL` is this skill's directory.

## Adapter contract

The project owns `demo.config.mjs`; its default export is:

| Key | Contract |
| --- | --- |
| `compose.files` | Compose files, relative to the worktree root. |
| `compose.env` | Variables written to `<worktree>/.env` with the chosen ports. Synthetic values only. |
| `compose.ports` | Base ports by variable name. The whole set shifts by 10, at most twice, until every port is free on `0.0.0.0`, `127.0.0.1`, and `::` (when IPv6 is available). |
| `baseUrl({ ports })` | Returns the app URL for the chosen ports. |
| `seed`, `reset` | Either `{ service, script, run }` (the script, relative to the directory of `demo.config.mjs`, is piped to `run` inside the compose service) or `{ command: [...] }` (a host command run in the worktree). `seed` loads baseline demo data; `reset` returns it to that state before every recording. |
| `login(page, { baseUrl })` | Signs the demo user in before the recording starts; it is not filmed. Use a synthetic account and read any password from the environment. |
| `captionsLang` | `en` or `ru`. Write captions and scenario text in this language, and pass it to `publish.sh` as `--lang` so the summary and MR block labels match. |
| `viewport` | `{ width, height }` for the browser and the recording. |
| `fixtures` | Absolute directory of upload files, reached through `kit.fixture(name)`. |

## Scenario contract

One `scenario.mjs` per demo, written by you and approved by the owner. Start from `templates/scenario.mjs`.

| Export | Contract |
| --- | --- |
| `title` | Video title; shown as the opening chapter and the summary heading. |
| `covers` | Object: acceptance criterion id to the step that shows it. |
| `notShown` | Array: criteria or behavior the video does not show, each with the reason. |
| `questions` | Array: open product questions for the reviewer. |
| `steps({ page, kit })` | The recorded journey. Locate elements with `getByRole` and `getByLabel`. |

`kit` provides `caption(text, holdMs = 3500)` (one persistent caption, inserted as text; `caption('')` clears it), `chapter(title, description)`, `shot(name)` (screenshot to `<out>/shots/<name>.png`, then a secret check), `fixture(name)`, and `hold(ms)`. The recorder signs in, then starts the recording and runs `steps`; clicks and typing are highlighted automatically.

Never type a secret inside `steps`: while actions are shown, `fill()` draws its value as the action title into the video, and the secret check reads only page text, so it cannot catch that.

`title`, `covers`, `notShown`, and `questions` become `scenario.json`, from which `summary.md` and the MR block are built.

## Procedure

1. **Context.** Resolve the MR (by number or from the current branch) and its head SHA. Read the MR description, the linked issue, the spec, and the diff; write down the acceptance criteria.
   If the MR description already has a `<!-- demo:start -->` block, compare the 12-character commit recorded in it with the MR head. When they differ, warn the user that the existing demo is out of date before going further; record again only if they ask.
2. **Stand.** Create a dedicated worktree of the head SHA outside the main checkout, named `demo-<MR>` under the workspace's worktree directory. Never reuse or touch another stand.
   Take `--config` from a checkout that contains the adapter: the default branch, or the adapter's own branch until it is merged; never from the MR worktree, whose head may not have it. Seed and reset scripts are resolved next to that config, but they run against the MR head's schema; if the MR changes the models they touch, adjust them first.
   ```bash
   node $SKILL/scripts/stand.mjs up --config <abs path to demo.config.mjs> --worktree <worktree> --project <repo>-demo-<MR>
   ```
   `up` picks free ports, writes `<worktree>/.env`, runs `docker compose up -d --build --wait`, and prints `{"project", "ports", "baseUrl"}`; keep `baseUrl`. Add `--dry-run` to see the plan without side effects.
3. **Data.** `stand.mjs seed` with the same flags. Feature-specific data belongs in the scenario itself.
4. **Reconnaissance.** Visit the screens the scenario needs; take screenshots and read `innerText`; choose role- and label-based locators.
5. **Scenario for approval.** Write `scenario.mjs` and show the owner the steps with their captions, the `covers` mapping, `notShown`, and draft `questions`.
   **Hard stop:** do not record until the owner explicitly approves this scenario. Changes to it go back to the owner.
6. **Recording.**
   ```bash
   node $SKILL/scripts/stand.mjs reset --config <...> --worktree <worktree> --project <repo>-demo-<MR>
   node $SKILL/scripts/record.mjs --config <demo.config.mjs> --scenario <scenario.mjs> --base-url <baseUrl> --out <out> --secrets-file <worktree>/.env
   ```
   Keep `<out>` outside the worktree. It receives `raw.webm`, `scenario.json`, and `shots/`. The secret check covers the values in `--secrets-file` and every environment variable whose name contains `PASSWORD`, `TOKEN`, `SECRET`, or `API_KEY`, when the value has at least 6 characters. Look at the key shots, and confirm through the API or the database that the actions in the video really took effect.
7. **Render and check.**
   ```bash
   bash $SKILL/scripts/render.sh <out>/raw.webm <out>/demo.mp4
   ```
   One JSON line per encoding attempt; the last line (`durationSec`, `bytes`, `crf`, `scaled`) is the result. Then run the [verification checklist](#verification-checklist).
8. **Publication.** No further confirmation is needed once the scenario is approved.
   ```bash
   cp <scenario.mjs> <out>/scenario.mjs
   bash $SKILL/scripts/publish.sh --repo <worktree> --mr <MR> --sha <recorded head SHA> --dir <out> --duration <durationSec> --lang <captionsLang>
   ```
   It first reads the MR description (an unknown MR stops it before any git write), then commits `demos/<MR>/<sha12>/{demo.mp4, scenario.json, scenario.mjs, summary.md}` on top of `origin/demos` (or as its first, orphan commit) in a detached temporary worktree, pushes it to `demos` without force and without creating a local `demos` branch, and replaces or appends the block in the MR description. When an existing block was replaced by a new commit, it also comments on the MR (`Demo updated: <url>`, in the `--lang` language) so the reviewer is notified. An identical re-publish commits nothing and posts no comment. It prints the video URL: a raw-file link, so one click downloads the mp4 for the reviewer. Forges serve repository files as downloads, so the video does not play in the browser.
   To preview first, add `--dry-run --body-file <current MR body>`: it prints the file list, the URL, and the new body, and writes nothing.
9. **Cleanup, also after any failure.** `stand.mjs down` (runs `docker compose down -v`), then `git worktree remove --force <worktree>`. Copy `demo.mp4` to the user's downloads directory and report the video URL, the SHA, and the questions in chat.

`<sha12>` is the first 12 characters of the SHA. `--duration` is optional; without it `publish.sh` reads the duration with `ffprobe`.

### MR block

```md
<!-- demo:start -->
## Demo

Video: https://forge.example.com/acme/app/raw/demos/demos/42/0123456789ab/demo.mp4
Commit: `0123456789ab`
Duration: 1:47

### Shown
- AC-1: step 2: Export button on the orders list

### Open questions
- Should the export include cancelled orders?

### Not shown
- AC-3 (export of more than 10 000 rows): not reproducible with demo data
<!-- demo:end -->
```

With `--note <text>`, the note is one extra line directly under `Duration:`. With `--lang ru`, the labels are `Видео`, `Коммит`, `Длительность`, `Показано`, `Открытые вопросы`, `Не показано`. `summary.md` has the same content under a `# <title>` heading. The markers are exact; everything between them is replaced on the next publish, and text outside them is kept. Empty sections are omitted.

## Script exit codes

| Script | Codes |
| --- | --- |
| `stand.mjs` | `0` ok; `2` compose failed (the last 50 log lines go to stderr); `64` usage or missing seed/reset step. A failing `{ command }` step exits with that command's status; another non-zero code is a config or free-port error. |
| `record.mjs` | `0` ok; `1` scenario or browser failure (stderr has the stack and up to 500 characters of page text; `<out>/error.png` is saved); `4` a secret value is visible on the page; `64` usage. |
| `render.sh` | `0` ok; `1` `ffmpeg` or `ffprobe` missing or failed; `3` over the duration limit, or over the size limit after all fallbacks; `64` usage. |
| `publish.sh` | `0` ok; `1` MR not found, origin unreachable, or another tool failure; `5` push of `demos` failed (git's output is on stderr); `64` usage. |

## Failure handling

| Situation | Action |
| --- | --- |
| `stand.mjs` exits 2 | Put the compose log tail in the report and stop. |
| `record.mjs` exits 1 (locator not found or step failed) | Read the error, `error.png`, and page text; redo reconnaissance and fix the scenario. After the second failure, stop and report. |
| `record.mjs` exits 4 | Delete the whole `<out>` directory (shots and `raw.webm` may contain the secret) and never publish it. Fix the data or the scenario, then record again. |
| `render.sh` exits 3 | Duration over 180 s: the scenario must get shorter; ask the owner what to drop. Size over 15 MiB after CRF 22, CRF 28, and CRF 28 scaled to fit 1280×800: stop and ask the owner. Never cut the scenario silently. |
| MR not found, `publish.sh` exits 1 or 5 | Stop and report. Re-run after the cause is fixed; a failed run leaves no local branch behind. The publisher never force-pushes and never creates an MR; neither do you. |
| MR head moved during recording | Publish anyway with `--sha` of the recorded commit and `--note "Recorded at <sha12>; MR head is now <sha12>"`, and tell the user the demo predates the new head. |

## Verification checklist

Before publishing, confirm for `<out>/demo.mp4`:

- `ffprobe` shows codec `h264`, pixel format `yuv420p`, duration at most 180 s, and size at most 15 MiB (15 728 640 bytes);
- the first and the last frame are not blank (extract them with `ffmpeg` and look);
- captions are readable on the key frames;
- every acceptance criterion in `covers` is actually shown, and every criterion not shown is listed in `notShown`.

## Test-only switch

`DEMO_SKIP_FORGE=1` makes `publish.sh` commit and push `demos` but skip every `gh` and `glab` call. It exists for the skill's tests only; never set it in a real run.

## Out of scope

Voice-over, running in CI, mobile viewports, automatic re-recording on new pushes, and delivery outside the repository.

## Prior art

Ideas, not code, come from [`dxdleady/playwright-demo-video`](https://github.com/dxdleady/playwright-demo-video) (MIT): Safari-friendly mp4 encoding and checking data state before and after the recording.
