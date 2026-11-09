# md-to-html-page — design

Date: 2026-11-09
Status: draft, awaiting review

## Problem

Write-ups shared with teammates in chat (bug reports, incident notes, explainers, specs, how-tos,
exported threads) are authored as Markdown. Raw `.md` attachments read poorly in a browser or chat
preview; designed HTML pages read much better, but hand-designing each page costs time and tokens
and risks altering the content.

## Goal

A skill that turns one Markdown file into one self-contained, good-looking static `.html` file that
can be attached to a chat message, downloaded, and opened offline — with a hard guarantee that the
text is not lost, altered, or invented.

Success criteria:

- A typical bug report renders with recognisable components (fact cards, summary lede, numbered
  steps, expected/actual side by side, timeline) without any manual markup.
- Any other Markdown renders as clean typography with TOC, callouts, and highlighted code.
- The output opens with no network access and makes no network requests.
- Rendering is deterministic (same input + pinned versions → byte-identical output), costs no LLM
  tokens for the content, and takes well under a second per document.
- The fidelity gate fails the run on any content difference.

## Non-goals (YAGNI)

- No LLM-authored or LLM-annotated layout path (Claude never edits the HTML or rewrites the source).
- No `:::` directive language.
- No inlined Mermaid library; diagrams get a text view.
- No tabs, glossary, quiz, search, or multi-file sites.
- No publishing or uploading; the user attaches the file themselves.

## Decisions taken during brainstorming

| Decision | Choice |
|---|---|
| Delivery | single `.html` file attached to a chat message, opened offline |
| Rendering mode | deterministic renderer only (tournament winner "C": genre-aware heuristics) |
| UI chrome language | auto by document script (Cyrillic majority → `ru`, else `en`), `--ui` overrides |
| Output location | next to the source as `<name>.html`; `-o` overrides; never overwrites the `.md` |
| Front matter | always hidden from the page; only `type:` and `title:` are read |
| Genre override | optional front-matter `type:` (`bug`, `incident`, `thread`, `explainer`, `spec`, `howto`, `note`) |
| Mermaid | collapsed source plus a derived text view of nodes and edges |
| Wikilinks, relative links | rendered as plain text (target not resolvable on the recipient's machine), listed in the run report |
| Skill category | `skills/software-development/md-to-html-page/` |

Prior art checked (llmrt/llm-report-templates, Phuker/md2html, mdsone, catalog md-to-html skills,
pandoc + embedded CSS): none combines genre components, a fidelity gate, and a strict offline
guarantee; several load CDN assets. llmrt's front-matter `type` selector is the one idea adopted.

## Architecture

```
mdpage.sh <in.md> [-o out.html] [--breaks auto|on|off] [--ui auto|ru|en]
   │  creates/reuses pinned venv in ${XDG_CACHE_HOME:-~/.cache}/md-to-html-page
   ├─ python -I render.py   in.md → out.html.tmp   (+ transforms report on stderr)
   ├─ python -I check.py    in.md  out.html.tmp     (fidelity + offline gates)
   └─ on PASS: mv out.html.tmp out.html; print the check line; exit 0
      on FAIL: keep no output file, print the check line with samples; exit 1
```

### Skill directory

```
skills/software-development/md-to-html-page/
  SKILL.md
  scripts/
    mdpage.sh          entry point: venv, render, check, atomic move
    render.py          Markdown → HTML with component transforms
    mermaid_view.py    Mermaid flowchart → derived text view
    check.py           independent fidelity + offline gate (stdlib only)
    shoot.sh           optional headless-Chrome screenshots (desktop, dark, 390 px)
    requirements.txt   pinned: markdown-it-py, mdit-py-plugins, linkify-it-py, mdurl, Pygments
  assets/
    style.css          tokens, light/dark, components, print
    page.js            theme toggle, copy buttons, TOC highlight (optional enhancement)
  tests/
    fixtures/*.md      synthetic, generic documents, one per genre, plus expected-transform lists
    test_render.py     transforms fire / do not fire as expected; determinism
    test_check.py      mutation tests that must FAIL
```

### Units

**`mdpage.sh`** — only orchestration. Validates the input path exists and ends in `.md`, refuses an
output path equal to the input, builds the venv on first run from `requirements.txt`, runs render
then check, and moves the temp file into place only on PASS.

**`render.py`** — markdown-it-py (CommonMark + GFM tables, strikethrough, task lists, footnotes,
front matter; raw HTML limited to attribute-free inline formatting tags; schema-only linkify). Works
on the token stream, then on block groups:

| Transform | Trigger | Output |
|---|---|---|
| Passport | first block after H1 is a 2-column table (empty header row allowed) | fact cards |
| Lede | H2 `Кратко` / `TL;DR` / `Summary` | highlighted lead paragraph |
| Stepper | ordered list under H2 starting `Шаги` / `Steps` | numbered stepper |
| Compare | adjacent H2 `Ожидаемый…` + `Фактический…` / `Expected…` + `Actual…` | side-by-side cards |
| Timeline | table whose first column is all times/timestamps | vertical timeline |
| Hypotheses | ordered list under H2 containing `гипотез` / `hypothes` | numbered cards |
| Callouts | `> [!NOTE]` / `[!WARNING]` / `[!TIP]` / … (GitHub and Obsidian, with `+`/`-` fold) | callouts |
| Chat log | paragraphs starting `**Name** (HH:MM):` or thread-export shape | chat bubbles, per-author hue |
| Mermaid | ```` ```mermaid ```` | collapsed source + derived text view |
| Code | fenced code | Pygments highlighting, copy button |
| Inline code | always | `<wbr>` after `/ _ . :` for phone wrapping |
| TOC | 3+ H2 headings | sticky sidebar on desktop, collapsed on phone |
| Genre badge | `type:` or detected genre | badge + accent colour in the header |

Keyword lists live in one table at the top of `render.py` so they are easy to extend. Every element
the renderer adds that is not source text carries `data-chrome` (UI labels) or `data-derived`
(views built from source data, e.g. the Mermaid text view). Genre detection: front-matter `type:`
wins; otherwise score headings (bug: compare + steps; thread: chat-log shape; incident: timeline +
root-cause headings) with `note` as the fallback. `--breaks auto` turns soft line breaks into `<br>`
only for the `thread` genre. Local images under the source's directory are embedded as data URIs;
remote images are never fetched and render as a labelled placeholder with the URL as text.
Output contains no timestamps or random values.

**`check.py`** — independent of `render.py` (uses stdlib `html.parser` and its own Markdown-side
normalisation). All gates must pass:

1. Word multiset: source words vs visible HTML text (excluding `data-chrome`, `data-derived`),
   with `<wbr>` splits rejoined and block boundaries separated; digit tokens reported separately.
2. Exact blocks: every fenced code block byte-for-byte inside a `<pre>`; every inline code span
   present as a `<code>`; every link href present.
3. Order: the in-order non-whitespace character sequence of source content equals that of the HTML
   content (catches punctuation changes and swapped values the multiset misses).
4. Derived content: every word inside `data-derived` occurs in the source.
5. Offline: no `<script src>`, no remote `<link>`/`<img>`/`<iframe>`/`<object>`, no `@import`, no
   `url(http…)`, no `fetch`/`XMLHttpRequest`/`WebSocket`/`EventSource` in inline JS; the CSP meta
   `default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'` present.

Output: one line `PASS words=N code=N hrefs=N order=ok offline=ok` or `FAIL <gate>: …` with up to
10 samples of missing/extra items.

**`assets/style.css`, `page.js`** — system font stacks with Cyrillic coverage; colour tokens on
`:root` with `prefers-color-scheme` dark plus a manual toggle (`localStorage` wrapped in try/catch);
layouts use `minmax(0,1fr)` grids; tables and code scroll inside their card; headings are never
flex rows (avoids splitting inline code at 390 px); print forces the light palette, hides TOC and
buttons, expands `<details>`. The page is complete with JavaScript disabled.

**`shoot.sh`** — optional visual check: auto-detects Chrome/Chromium, writes desktop, dark, and
390 px (iframe wrapper) screenshots into a directory given as an argument.

### What Claude does when the skill runs

1. Resolve the input path; state the output path.
2. Run `mdpage.sh`.
3. Quote the check line verbatim. On FAIL, report it and stop; never patch the HTML.
4. Summarise the transforms report: which components fired, detected genre, unresolved links.
5. If an obvious pattern did not fire (e.g. a differently worded heading), say so and suggest either
   renaming the heading in the source or adding `type:`.
6. Optionally run `shoot.sh` and look at the screenshot when the user asks for a visual check.

## Error handling

- Missing input, non-`.md` input, output equal to input → exit 2 with a message, nothing written.
- Venv creation fails (no network on first run) → exit 3 with the pip error; no partial venv kept.
- Render exception → exit 1, temp file removed, traceback summary printed.
- Check FAIL → exit 1, no output file, samples printed.
- Unknown `type:` value → warning, falls back to detection.

## Testing

- Fixtures are synthetic and generic (no employer or project content): one per genre plus edge
  cases (empty-header table, setext heading in a list, long log lines, nested callout with code,
  Cyrillic + identifiers, no H2 at all).
- `test_render.py`: each fixture's expected transforms fire and others do not; two runs are
  byte-identical; output passes `check.py`; offline grep is clean.
- `test_check.py` mutation tests, each must FAIL: changed digit, dropped word, swapped table cells,
  altered code whitespace, removed href, injected `<script src>`, `data-derived` word not in source.
- Hub gate before the PR: `./scripts/validate.sh --full` and a grep for company/project names.

## Starting material

Tournament prototypes (local, not committed; they were run against private documents):
contestant C's `render.py`, `mermaid_view.py`, `check_fidelity.py`, `style.css`, `page.js` as the
base; contestant A's Pygments/`<wbr>`/theme-toggle code and pinned requirements; contestant D's
order gate and per-author hues; contestant B's offline gate and print rules. Code is re-applied
into the hub files; no sample document or render is copied.

## Risks

- Heuristics fire rarely outside bug reports; most notes will get "good typography + TOC +
  callouts". Expectation is set in SKILL.md.
- Keyword triggers are Russian/English wordings; other wordings miss (mitigated by `type:` and an
  easy-to-extend keyword table). False positive: any 2-column table right after H1 becomes a
  passport.
- Checker blind spots: lost emphasis, a component misrepresenting meaning. Covered partly by the
  order gate and fixture tests.
- First run needs PyPI access; determinism holds only with pinned versions.
