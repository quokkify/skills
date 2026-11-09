# md-to-html-page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A hub skill that renders one Markdown file into one self-contained, offline, genre-aware
`.html` page and refuses to emit it unless an independent fidelity and offline gate passes.

**Architecture:** `mdpage.sh` owns the venv and the render → check → atomic-move pipeline.
`render.py` turns markdown-it-py tokens into a page with component transforms and inlined assets;
`check.py` re-derives the reference text with a plain CommonMark parser and compares it to the
rendered HTML; `mermaid_view.py` builds a derived text view of flowcharts.

**Tech Stack:** Python ≥ 3.10, POSIX `sh`, markdown-it-py, mdit-py-plugins, linkify-it-py, mdurl,
Pygments; stdlib `unittest` and `html.parser`.

**Spec:** `docs/superpowers/specs/2026-11-09-md-to-html-page-design.md`

## Global Constraints

- Skill directory: `skills/software-development/md-to-html-page/`; frontmatter `name: md-to-html-page` (must equal the directory name).
- Pins in `scripts/requirements.txt`, exactly: `markdown-it-py==4.2.0`, `mdit-py-plugins==0.6.1`, `linkify-it-py==2.2.0`, `mdurl==0.1.2`, `Pygments==2.21.0`.
- Venv path: `${XDG_CACHE_HOME:-$HOME/.cache}/md-to-html-page/<first 12 hex of sha256(requirements.txt)>`; every Python call uses `-I`.
- Output: no `<script src>`, no remote `<link>`/`<img>`/`<iframe>`/`<object>`, no `@import`, no `url(http`, no web fonts; CSP meta exactly `default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'`.
- Deterministic: no timestamps, random values, absolute paths, or dict-order-dependent output.
- Added non-source text carries `data-chrome`; source-derived views carry `data-derived`.
- Front matter never appears in the page; only `type:` and `title:` are read.
- Exit codes: 0 pass, 1 render error or check FAIL, 2 bad arguments, 3 venv setup failure.
- Public-safe: fixtures and tests are synthetic; no employer, project, or person names, no machine paths, no real e-mail addresses. Company-name grep is a manual pre-PR step and the name list is never committed.
- Shell scripts are POSIX `sh` (no bashisms, no GNU-only flags).
- Hub tests run through `python3 -m unittest discover -s tests` (see `scripts/validate.sh`).
- Dev interpreter `$V`: for Tasks 1–4, `V="${XDG_CACHE_HOME:-$HOME/.cache}/md-to-html-page/dev"`; from Task 5 on, `V="$(dirname "$(skills/software-development/md-to-html-page/scripts/mdpage.sh --python)")/.."`. All skill tests use stdlib `unittest`.

**Spec amendment (do in Task 1):** the spec says `check.py` is "stdlib only". The order gate needs a
Markdown parser to strip markup, so `check.py` uses markdown-it-py in plain `commonmark` mode with
only `table` and `strikethrough` enabled and none of the renderer's plugins or rules. It still
shares no code with `render.py`. Edit that spec line accordingly.

## Review Focus

1. A heading whose text is inline code (e.g. ``## `FAILED` status``) at 390 px must not split the code mid-word — Task 3 test `test_heading_with_inline_code_not_flex`.
2. A document with no H1, no H2, and only a paragraph must still produce a valid page titled from the file stem — Task 2 test `test_minimal_document`.
3. A two-column table that is not first after H1 must not become a passport — Task 3 test `test_passport_only_directly_after_h1`.
4. A remote image `![alt](https://…)` must not be fetched or emitted as `<img src=http…>` and must not fail the gate — Task 2 test `test_remote_image_placeholder` and Task 1 test `test_derived_placeholder_passes`.
5. Input path containing spaces and Cyrillic (`Заметка про баг.md`) must work end to end — Task 5 test `test_path_with_spaces_and_cyrillic`.

---

### Task 1: Fidelity and offline gate (`check.py`)

**Files:**
- Create: `skills/software-development/md-to-html-page/scripts/check.py`
- Create: `skills/software-development/md-to-html-page/scripts/requirements.txt`
- Create: `skills/software-development/md-to-html-page/tests/test_check.py`
- Modify: `docs/superpowers/specs/2026-11-09-md-to-html-page-design.md` (spec amendment above)

Starting material (read, do not copy verbatim): tournament prototypes under the session scratchpad
`tournament/D-llm-structure-script-render/skill/md-to-html-page/scripts/check.py` (`Text` parser,
`reference`, `check_render`), `tournament/C-heuristic-components/skill/md-to-html-page/scripts/check_fidelity.py`
(word multiset), `tournament/B-bespoke/skill/md-to-bespoke-html/scripts/assemble.py` (offline rules).

**Interfaces:**
- Produces:
  - `check(md_text: str, html_text: str) -> CheckResult`
  - `@dataclass(frozen=True) class CheckResult: ok: bool; gate: str | None; line: str; samples: tuple[str, ...]`
  - `gate` is one of `"words" | "blocks" | "order" | "derived" | "offline" | None`.
  - CLI: `check.py <in.md> <out.html>` prints `result.line`, then each sample on its own line prefixed `  - `; exit 0 if ok else 1; exit 2 on unreadable input.
  - PASS line format: `PASS words=<n> code=<n> hrefs=<n> order=ok offline=ok`; FAIL line: `FAIL <gate>: <short reason>`.
- Reference normalisation (md side), applied before parsing: drop YAML front matter; `[!KIND][+-]?` callout markers removed; `[[target|alias]]` → `alias`, `[[target]]` → `target`; task markers `[ ]`/`[x]` removed.
- HTML side: ignore `<head>`, `<script>`, `<style>`, `<svg>` and any subtree with `data-chrome` or `data-derived`; `<wbr>` contributes nothing.

- [ ] **Step 1: Write failing tests** in `tests/test_check.py` (unittest; build HTML fixtures inline with a helper `page(body: str) -> str` that wraps `body` in a minimal document with the exact CSP meta). Tests and assertions:
  - `test_identical_passes`: md `"# T\n\nHello **world** 42.\n"` vs body `<h1>T</h1><p>Hello <strong>world</strong> 42.</p>` → `ok is True`, `line.startswith("PASS words=")`.
  - `test_changed_digit_fails`: same md vs `… 43.` → `gate == "words"`, a sample contains `42`.
  - `test_dropped_word_fails`: body without `world` → `gate == "words"`.
  - `test_swapped_cells_fails`: md table `|a|b|\n|-|-|\n|1|2|` vs HTML cells `2`,`1` → `gate == "order"`.
  - `test_punctuation_change_fails`: `42.` vs `42!` → `gate == "order"`.
  - `test_code_whitespace_fails`: fence ```` ```\na  b\n``` ```` vs `<pre><code>a b</code></pre>` → `gate == "blocks"`.
  - `test_inline_code_must_be_code`: md `` `x_y` `` rendered as plain text → `gate == "blocks"`.
  - `test_removed_href_fails`: `[t](https://example.com/a)` rendered `<a href="https://example.com/b">t</a>` → `gate == "blocks"`.
  - `test_wbr_rejoined`: `` `a/b_c` `` vs `<code>a/<wbr>b_<wbr>c</code>` → ok.
  - `test_chrome_ignored`: extra `<nav data-chrome>Содержание</nav>` → ok.
  - `test_derived_word_not_in_source_fails`: `<div data-derived>invented</div>` → `gate == "derived"`.
  - `test_derived_placeholder_passes`: md `![pic](https://example.com/p.png)` vs `<figure><span data-derived>pic https://example.com/p.png</span></figure>` → ok.
  - `test_script_src_fails`, `test_remote_link_fails`, `test_import_fails`, `test_url_http_fails`, `test_fetch_in_inline_js_fails`, `test_missing_csp_fails` → each `gate == "offline"`.
  - `test_front_matter_ignored`: md with `---\nsecret: x\n---\n` and HTML without it → ok.
  - `test_wikilink_alias`: md `[[Note|alias]]` vs `<p>alias</p>` → ok.
- [ ] **Step 2: Build the dev venv and run.** `python3 -m venv "$V" && "$V/bin/pip" install -r skills/software-development/md-to-html-page/scripts/requirements.txt` (see "Dev interpreter"), then `"$V/bin/python" -I -m unittest discover -s skills/software-development/md-to-html-page/tests -p 'test_check.py' -v`. Expected: FAIL (`ModuleNotFoundError: check`). Tests import the script via `sys.path.insert(0, <skill>/scripts)` at the top of the test module.
- [ ] **Step 3: Implement `check.py`.** Gates run in order words → blocks → order → derived → offline; the first failing gate is reported with up to 10 samples. Words: `\w+` multiset with digits listed separately in samples. Order: compare lists of non-whitespace characters with `difflib.SequenceMatcher(autojunk=False)`; samples show `md=… html=…` with 25 chars of context. Blocks: each fence/`code_block` content (rstrip `\n`) equals some `<pre>` text after `html.unescape`; each inline code span equals the text of some `<code>`; each link href from md appears as an `href` attribute. Offline: regexes over the raw HTML plus the exact CSP meta.
- [ ] **Step 4: Run** the Step 2 command. Expected: all `test_check` tests PASS.
- [ ] **Step 5: Amend the spec line** about `check.py` per "Spec amendment".
- [ ] **Step 6: Commit**
```bash
git add skills/software-development/md-to-html-page/scripts/check.py skills/software-development/md-to-html-page/scripts/requirements.txt skills/software-development/md-to-html-page/tests/test_check.py docs/superpowers/specs/2026-11-09-md-to-html-page-design.md
git commit -m "feat(md-to-html-page): add fidelity and offline gate"
```

### Task 2: Base renderer and page shell (`render.py`, assets)

**Files:**
- Create: `skills/software-development/md-to-html-page/scripts/render.py`
- Create: `skills/software-development/md-to-html-page/assets/style.css`
- Create: `skills/software-development/md-to-html-page/assets/page.js`
- Create: `skills/software-development/md-to-html-page/tests/test_render_base.py`
- Create: `skills/software-development/md-to-html-page/tests/fixtures/note.md`, `minimal.md`, `callouts.md`, `code.md`

Starting material: C's `render.py` (`make_md`, `slugify`, raw-HTML whitelist, `render_fence`,
`to_blocks`, `Renderer`, `build`), C's `style.css`/`page.js`; A's `md2html.py` Pygments CSS
(`HtmlFormatter(style=…).get_style_defs`) and `<wbr>` logic; B's `base.css` print rules.

**Interfaces:**
- Consumes: `check.check` (tests assert every render passes it).
- Produces:
  - `build(src: str, *, source_dir: Path | None = None, stem: str = "document", ui: str = "auto", breaks: str = "auto") -> RenderResult`
  - `@dataclass(frozen=True) class RenderResult: html: str; genre: str; genre_source: str; transforms: tuple[str, ...]; unresolved_links: tuple[str, ...]; warnings: tuple[str, ...]`
  - `genre_source` is `"type"` or `"detected"`. Task 2 always returns `genre="note"`, `genre_source="detected"`; Task 3 fills detection.
  - `UI: dict[str, dict[str, str]]` with keys `ru`, `en` and at least: `toc`, `copy`, `copied`, `theme`, `note`, `tip`, `important`, `warning`, `caution`, `image_not_embedded`, `diagram_source`, `diagram_text`, and genre labels `genre_bug`, `genre_incident`, `genre_thread`, `genre_explainer`, `genre_spec`, `genre_howto`, `genre_note`.
  - `pick_ui(src: str, ui: str) -> str`: `ui` if `"ru"`/`"en"`, else `"ru"` when Cyrillic letters outnumber Latin letters outside code spans and fences, else `"en"`.
  - Transform names recorded in `RenderResult.transforms` (stable vocabulary used by Tasks 3–5): `toc`, `code`, `callout`, `image`, `passport`, `lede`, `stepper`, `compare`, `timeline`, `hypotheses`, `chat`, `mermaid`.
  - CLI: `render.py <in.md> -o <out.html> [--ui auto|ru|en] [--breaks auto|on|off]` writes HTML and prints the report to stderr as lines `genre: <g> (<source>)`, `transforms: <comma list or ->`, `unresolved: <item>` (one per item), `warning: <text>`.

- [ ] **Step 1: Write failing tests** in `tests/test_render_base.py`. Each test renders a fixture via `build`, asserts `check(src, html).ok`, plus:
  - `test_minimal_document`: `minimal.md` = one paragraph, no headings; `build(src, stem="Заметка")` → `<title>Заметка</title>` present, `transforms == ()`.
  - `test_title_precedence`: front-matter `title:` beats first H1 beats `stem`.
  - `test_front_matter_hidden`: fixture with `visibility: internal` → string `visibility` absent from `html`.
  - `test_toc_threshold`: 3 H2 → `"toc" in transforms` and a `<nav data-chrome` element; 2 H2 → no `toc`.
  - `test_code_highlight_and_copy`: `code.md` with a ```` ```python ```` fence → `class="highlight"` present, copy button has `data-chrome`, only Pygments classes used in the page appear in the inlined CSS (assert `.kd` rule absent when no `kd` token is emitted).
  - `test_inline_code_wbr`: `` `a/b_c.d:e` `` → `a/<wbr>b_<wbr>c.<wbr>d:<wbr>e`.
  - `test_callouts`: `callouts.md` with `> [!WARNING] Title`, `> [!NOTE]-` (folded → `<details>`), unknown kind falls back to `note`.
  - `test_ui_auto`: Russian prose → `lang="ru"` and `Содержание`; English prose → `lang="en"` and `Contents`; `ui="en"` on Russian prose forces `Contents`.
  - `test_local_image_embedded`: image next to the fixture (write a 1×1 PNG into a `tempfile.TemporaryDirectory`) → `src="data:image/png;base64,`.
  - `test_remote_image_placeholder`: `![pic](https://example.com/p.png)` → no `<img`, `"image" in transforms`, placeholder text inside `data-derived`.
  - `test_wikilinks_plain_and_reported`: `[[Other note|see]]` and a relative Markdown link with text `x` to `./other.md` → text `see` present, no `href="./other.md"`, `unresolved_links == ("[[Other note]]", "./other.md")`.
  - `test_deterministic`: two `build` calls → identical `html`.
  - `test_offline_shell`: CSP meta present; no `http://`/`https://` in `<link`/`<script` tags; `prefers-color-scheme: dark` in CSS; `@media print` in CSS.
- [ ] **Step 2: Run** `"$V/bin/python" -I -m unittest discover -s skills/software-development/md-to-html-page/tests -p 'test_render_base.py' -v`. Expected: FAIL (`ModuleNotFoundError: render`).
- [ ] **Step 3: Implement** `render.py` base: markdown-it `commonmark` + `table`, `strikethrough`, tasklists, footnotes, front matter (mdit-py-plugins), linkify with schema-only fuzzy settings off; raw HTML limited to attribute-free inline tags (C's `SAFE_TAGS`), everything else escaped. Pygments: light style `default`, dark style `github-dark`, CSS generated per page and filtered to used classes, dark rules under both `@media (prefers-color-scheme: dark) :root:not([data-theme="light"])` and `:root[data-theme="dark"]`. Inline `style.css` and `page.js` into the shell; `page.js` wraps `localStorage` in try/catch and the page is complete without it. Headings are block elements (never `display:flex`).
- [ ] **Step 4: Run** the Step 2 command, then the full skill test dir. Expected: all PASS.
- [ ] **Step 5: Commit**
```bash
git add skills/software-development/md-to-html-page
git commit -m "feat(md-to-html-page): add base renderer and offline page shell"
```

### Task 3: Genre components and detection

**Files:**
- Modify: `skills/software-development/md-to-html-page/scripts/render.py`
- Modify: `skills/software-development/md-to-html-page/assets/style.css`
- Create: `skills/software-development/md-to-html-page/tests/test_components.py`
- Create: `skills/software-development/md-to-html-page/tests/fixtures/bug.md`, `bug-en.md`, `incident.md`, `thread.md`, `howto.md`

Starting material: C's `Renderer` transforms, `RE_*` keyword regexes, `detect_genre`; D's `hue()`.

**Interfaces:**
- Consumes: Task 2 `build`, `RenderResult`, transform vocabulary.
- Produces:
  - `KEYWORDS: dict[str, re.Pattern]` at the top of `render.py` with keys `lede`, `steps`, `expected`, `actual`, `hypotheses`, `time_head`; start from C's `RE_TLDR`, `RE_STEPS`, `RE_EXPECTED`, `RE_ACTUAL`, `RE_HYPO`, `RE_TIME_HEAD`.
  - `GENRES = ("bug", "incident", "thread", "explainer", "spec", "howto", "note")`.
  - `detect_genre(fm_type: str | None, headings: list[str], blocks_signal: set[str]) -> tuple[str, str, str | None]` → `(genre, source, warning)`; unknown `fm_type` → detection plus warning `unknown type '<v>', using detection`.
  - `author_hue(name: str) -> int`: `int(sha256(name.encode()).hexdigest()[:8], 16) % 360` (deterministic, no `hash()`).

- [ ] **Step 1: Write failing tests** in `tests/test_components.py`; every test also asserts `check(src, html).ok`:
  - `test_bug_report_components`: `bug.md` (synthetic Russian bug report: H1, 2-column empty-header table, `## Кратко`, `## Шаги воспроизведения` with ordered list, `## Ожидаемый результат`, `## Фактический результат`, a `| Время (UTC) | Событие |` table, `## Гипотезы` ordered list) → `transforms` contains, in this order, `passport`, `lede`, `stepper`, `compare`, `timeline`, `hypotheses`; `genre == "bug"`, `genre_source == "detected"`; badge text `Баг-репорт` inside `data-chrome`.
  - `test_bug_report_english`: `bug-en.md` with `Summary`, `Steps to reproduce`, `Expected`, `Actual` → same transform set, badge `Bug report`.
  - `test_passport_only_directly_after_h1`: a 2-column table placed after a paragraph → `"passport" not in transforms`.
  - `test_compare_needs_adjacent_pair`: `Ожидаемый` H2 followed by an unrelated H2 → no `compare`.
  - `test_timeline_requires_all_time_cells`: one non-time cell in the first column → no `timeline`.
  - `test_thread_chat_and_breaks`: `thread.md` with `**Ann** (10:01):` lines and soft line breaks → `"chat" in transforms`, `genre == "thread"`, `<br>` present for soft breaks; two authors get different `--hue` values equal to `author_hue(name)`.
  - `test_breaks_off_overrides`: `breaks="off"` on `thread.md` → no `<br>` from soft breaks.
  - `test_type_override`: front matter `type: howto` on `bug.md` → `genre == "howto"`, `genre_source == "type"`; `type: banana` → detected `bug` plus warning `unknown type 'banana', using detection`.
  - `test_heading_with_inline_code_not_flex`: rendered CSS has no `display:flex` / `display: flex` on `h1`–`h4` selectors, and `h2 code` has `overflow-wrap: anywhere`.
  - `test_incident_timeline`: `incident.md` with a timestamp table and a `## Root cause` heading → `genre == "incident"`, `timeline` in transforms.
  - `test_note_fallback`: `note.md` from Task 2 → `genre == "note"`, none of the genre components fire.
- [ ] **Step 2: Run** `"$V/bin/python" -I -m unittest discover -s skills/software-development/md-to-html-page/tests -p 'test_components.py' -v`. Expected: FAIL on component assertions.
- [ ] **Step 3: Implement** transforms over the block list (C's approach) and detection scoring: `bug` ← `compare` + `stepper`; `thread` ← `chat`; `incident` ← `timeline` + heading matching `причин|root cause|инцидент|incident`; `howto` ← `stepper` with ≥ 3 fenced shell blocks; `spec` ← headings matching `требован|requirements|scope|non-goals`; `explainer` ← ≥ 5 H2 and none of the above; else `note`. Components keep source order; added labels carry `data-chrome`. Add component CSS (fact cards, lede, stepper, compare grid with `minmax(0,1fr)`, timeline, hypothesis cards, chat bubbles using `hsl(var(--hue) …)`), all readable at 390 px.
- [ ] **Step 4: Run** the full skill test dir. Expected: all PASS.
- [ ] **Step 5: Commit**
```bash
git add skills/software-development/md-to-html-page
git commit -m "feat(md-to-html-page): add genre detection and components"
```

### Task 4: Mermaid text view

**Files:**
- Create: `skills/software-development/md-to-html-page/scripts/mermaid_view.py`
- Modify: `skills/software-development/md-to-html-page/scripts/render.py` (fence rule for `mermaid`)
- Create: `skills/software-development/md-to-html-page/tests/test_mermaid.py`
- Create: `skills/software-development/md-to-html-page/tests/fixtures/explainer.md`

Starting material: C's `mermaid_view.py` (`parse`, `render`, `RE_NODE`, `RE_EDGE`).

**Interfaces:**
- Produces: `mermaid_view.render(src: str) -> str | None` — HTML fragment wrapped in `<div class="mermaid-view" data-derived>` listing nodes and labelled edges in source order; `None` for anything that is not a `flowchart`/`graph` with a direction.
- In `render.py`: a ```` ```mermaid ```` fence becomes `<details><summary data-chrome>…</summary>` (summary text `UI[ui]["diagram_source"]`) with the verbatim source in `<pre><code>`, plus the derived view when `render` returns non-`None`; records `mermaid` in transforms.

- [ ] **Step 1: Write failing tests**: `test_flowchart_view` (`flowchart LR\n A[Start] --> B{Check}\n B -->|yes| C[Done]` → contains `Start`, `Check`, `yes`, `Done` in that order, root has `data-derived`); `test_unsupported_returns_none` (`sequenceDiagram` → `None`); `test_explainer_page` (`explainer.md` with one flowchart and 5+ H2 → `check` ok, `genre == "explainer"`, `mermaid` in transforms, verbatim source inside a `<pre>`).
- [ ] **Step 2: Run** `"$V/bin/python" -I -m unittest discover -s skills/software-development/md-to-html-page/tests -p 'test_mermaid.py' -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `mermaid_view.py` and the fence rule.
- [ ] **Step 4: Run** the full skill test dir. Expected: all PASS.
- [ ] **Step 5: Commit**
```bash
git add skills/software-development/md-to-html-page
git commit -m "feat(md-to-html-page): add mermaid text view"
```

### Task 5: Entry point and screenshot helper

**Files:**
- Create: `skills/software-development/md-to-html-page/scripts/mdpage.sh` (executable)
- Create: `skills/software-development/md-to-html-page/scripts/shoot.sh` (executable)
- Create: `skills/software-development/md-to-html-page/tests/test_mdpage.py`

Starting material: A's `render.sh`, D's `mdpage.sh`, B's `shoot.sh` (390 px iframe trick).

**Interfaces:**
- Consumes: `render.py` CLI and `check.py` CLI from Tasks 1–2.
- Produces:
  - `mdpage.sh <in.md> [-o out.html] [--breaks auto|on|off] [--ui auto|ru|en]`: default output `<dir of in>/<stem>.html`; writes `<out>.tmp`, runs check, `mv` on PASS, deletes tmp on FAIL; stdout: the check line; stderr: render report.
  - `mdpage.sh --python`: ensures the venv and prints the absolute path of its `python` (used by hub tests).
  - Env `MDPAGE_VENV` overrides the venv directory (tests use a temp dir only for the failure case).
  - `shoot.sh <page.html> <out-dir>`: finds Chrome via `CHROME_BIN`, then `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`, then `google-chrome`, `chromium`, `chromium-browser` on `PATH`; writes `desktop.png` (1280 wide), `dark.png` (`--force-dark-mode`), `phone.png` (390 px via a temporary iframe wrapper inside `<out-dir>`); exit 2 if no browser.

- [ ] **Step 1: Write failing tests** in `tests/test_mdpage.py` (subprocess, `tempfile.TemporaryDirectory`, copy fixtures in):
  - `test_happy_path`: `bug.md` → exit 0, stdout starts `PASS`, `bug.html` exists next to it, no `.tmp` left, stderr contains `genre: bug (detected)`.
  - `test_output_flag`: `-o <tmp>/x/out.html` (dir pre-created) → file there.
  - `test_refuses_non_md` → exit 2, nothing written.
  - `test_refuses_output_equal_input` (`-o bug.md`) → exit 2, `bug.md` unchanged.
  - `test_missing_input` → exit 2.
  - `test_check_failure_leaves_no_file`: set env `MDPAGE_FORCE_FAIL=1` read by `mdpage.sh` only to corrupt the tmp file before the check (test hook; document it in a comment) → exit 1, stdout starts `FAIL`, no output file.
  - `test_render_exception_exit_1`: input `.md` containing invalid UTF-8 bytes (`b"\xff\xfe# x"`) → exit 1, stderr has a one-line error summary (no full traceback), no output or `.tmp` file.
  - `test_venv_failure_exit_3`: `MDPAGE_VENV=<tmp>/v` with `PIP_INDEX_URL=http://127.0.0.1:9/` → exit 3, `<tmp>/v` removed.
  - `test_path_with_spaces_and_cyrillic`: input `Заметка про баг.md` → exit 0, `Заметка про баг.html` exists.
  - `test_byte_identical_reruns`: two runs → identical bytes.
  - `test_python_flag`: `--python` → prints an existing executable path.
- [ ] **Step 2: Run** `"$V/bin/python" -I -m unittest discover -s skills/software-development/md-to-html-page/tests -p 'test_mdpage.py' -v`. Expected: FAIL.
- [ ] **Step 3: Implement** both scripts in POSIX `sh`; quote every path; venv built into a temp sibling dir and renamed on success so a failed build leaves nothing.
- [ ] **Step 4: Run** the full skill test dir, then `sh -n` on both scripts and, if available, `shellcheck -s sh`. Expected: all PASS, no shellcheck errors.
- [ ] **Step 5: Commit**
```bash
git add skills/software-development/md-to-html-page
git commit -m "feat(md-to-html-page): add mdpage entry point and screenshot helper"
```

### Task 6: SKILL.md, hub wiring, acceptance

**Files:**
- Create: `skills/software-development/md-to-html-page/SKILL.md`
- Create: `tests/test_md_to_html_page.py`
- Modify: `docs/skill-catalog.md` (entry under `## software-development`)

**Interfaces:**
- Consumes: `mdpage.sh` and `mdpage.sh --python` from Task 5.

- [ ] **Step 1: Write failing hub test** `tests/test_md_to_html_page.py`, modelled on `tests/test_feature_demo.py`:
  - `test_skill_suites_pass`: run `scripts/mdpage.sh --python`; if it exits 3, `skipTest("cannot build venv (no package index)")`; else run `<python> -I -m unittest discover -s <skill>/tests -v` and assert exit 0.
  - `test_skill_has_no_machine_paths` and `test_skill_has_no_real_emails`: same rules as `test_feature_demo.py` (`/Users/`, `/home/`, e-mails outside `example.com`).
  - `test_skill_md_frontmatter`: `name: md-to-html-page`, non-empty `description`.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_md_to_html_page -v`. Expected: FAIL (missing `SKILL.md`).
- [ ] **Step 3: Write `SKILL.md`**: frontmatter `name: md-to-html-page`, `description:` starting "Use when the user wants a Markdown file turned into a self-contained static HTML page to share as a file…". Body: prerequisites (Python ≥ 3.10, network on first run), the procedure from the spec's "What Claude does" (6 steps, verbatim intent), flags table, transform vocabulary with triggers, `type:` values, expectation-setting note (most notes get typography + TOC + callouts; components fire on recognisable patterns), troubleshooting by exit code. Add a catalog line in the same format as its neighbours under `## software-development`, linking to the new `SKILL.md`, with the summary "render a Markdown file into one offline, genre-aware HTML page with a fidelity gate."
- [ ] **Step 4: Run** `python3 -m unittest tests.test_md_to_html_page -v` and `./scripts/validate.sh --full`. Expected: PASS / `Repository validation: ok` and the docs build succeeds.
- [ ] **Step 5: Acceptance on real documents (local only, nothing committed).** Render the seven tournament samples (list in the session's workflow script; outputs into the session scratchpad via `-o`), quote each check line, run `shoot.sh` on the bug report, thread, and explainer, and look at the screenshots in light, dark, and phone widths. Expected: 7× `PASS`; bug report shows passport, lede, stepper, compare, timeline, hypotheses; thread shows chat bubbles with preserved line breaks; no front-matter keys visible.
- [ ] **Step 6: Pre-PR privacy grep (manual, list not committed):** grep the skill directory and the spec/plan for employer, project, and teammate names used in the samples. Expected: no matches.
- [ ] **Step 7: Commit**
```bash
git add skills/software-development/md-to-html-page/SKILL.md tests/test_md_to_html_page.py docs/skill-catalog.md
git commit -m "feat(md-to-html-page): add skill entry point and hub wiring"
```
