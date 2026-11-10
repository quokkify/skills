# discussion-card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A hub skill that turns one Markdown file plus an agent-written `card.yaml` into one offline, interactive HTML discussion card. Mermaid flowcharts become clickable diagrams, and the build is gated by checks.

**Architecture:**
- `discuss.sh` builds and reuses a pinned venv and a sha256-verified Mermaid cache.
- It runs `plan.py` (validate), `build.py` (page model and HTML), `mermaid_svg.py` (Mermaid rendered in headless Chrome into static SVG) and `check.py` (gates).
- A generic `engine.js`/`engine.css` provides all interactivity and reads only `#card-config` and `data-spot` elements.

**Tech Stack:** Python ≥3.10 (unittest, markdown-it-py set, PyYAML), POSIX sh, headless Chrome, `@mermaid-js/tiny` 12.3.0 (MIT), vanilla JS/CSS, Playwright 1.65.0 with `node --test` for browser tests.

**Spec:** `docs/superpowers/specs/2026-11-09-discussion-card-design.md`

## Global Constraints

- Skill dir: `skills/software-development/discussion-card/`. No runtime imports from `md-to-html-page`. Copied files keep a provenance line in `SKILL.md`.
- Python ≥3.10. Scripts run as `python -I`. Third-party Python only from the pinned `scripts/requirements.txt`: `markdown-it-py==4.2.0`, `mdit-py-plugins==0.6.1`, `linkify-it-py==2.2.0`, `mdurl==0.1.2`, `Pygments==2.21.0`, `PyYAML==6.0.3`.
- Cache root `${XDG_CACHE_HOME:-$HOME/.cache}/discussion-card/`. Venv dir `<root>/<sha256(requirements)[:12]>` with marker `.discussion-card`. `DISCUSS_VENV` overrides it; the script refuses to replace an existing dir without the marker (exit 3).
- `scripts/mermaid.lock`:
  - `version=12.3.0`
  - `url=https://cdn.jsdelivr.net/npm/@mermaid-js/tiny@12.3.0/dist/mermaid.tiny.js`
  - `sha256=c41f5236091b83f524c4940f97a16b2b14a76f21ff84aea4fd6b66421d8a2a9a`
  - Cached as `<root>/mermaid-12.3.0.js`; `DISCUSS_MERMAID` overrides the path. A sha mismatch is exit 3.
- Chrome: `CHROME_BIN`, else `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`, else `google-chrome`/`chromium` on PATH. Flags: `--headless=new --disable-gpu --allow-file-access-from-files --virtual-time-budget=15000 --dump-dom`.
- Mermaid: `securityLevel: 'strict'`, `themeVariables.fontSize: '16px'`. Rendered node DOM id is `<renderId>-flowchart-<nodeId>-<n>` (verified on 12.3.0).
- Spot ids:
  - Mermaid node: `<chapter-slug>-<nodeId>`.
  - Other spots: `<chapter-slug>-<kind>-<sha1(normalised text)[:6]>`, with collisions suffixed `-2`, `-3` in source order.
  - `kind` ∈ `p|li|tr|callout|code|intro|q`.
  - Chapter slug: ASCII, transliterated, lowercase, hyphenated, ≤40 chars.
  - Normalised text means whitespace collapsed and stripped.
- Storage key `discussion-card:<slug>:v1`. Presenter mode key `<storage key>:mode`. State shape exactly as in spec §Engine.
- Check line: `PASS words=<n> extra=<n> spots=<n> diagrams=<n>|runtime offline=ok [ids=kept|ids=-k]`, or `FAIL <gate>: <reason>` followed by up to 5 sample lines.
- Exit codes: 0 pass; 1 check fail or build error (no output written); 2 bad args or plan schema; 3 environment.
- Output `<name>.card.html` next to the source unless `-o`. An existing output is moved to `<name>.card.backup.html` before replacing.
- Diagram text ≥14px at scale 1. Diagram SVGs are never scaled down.
- No network at view time. No `innerHTML` with source or user data in `engine.js`.
- Skill files contain no machine paths (`/Users/`, `/home/`) and no e-mails except `example.com`. These are checked by the hub test.
- UI labels in `ru` and `en`; `--ui auto` picks `ru` when Cyrillic letters are the majority.

## Review Focus

1. A source with no H2 and no Mermaid builds one chapter, with no diagram gates applied and no crash. Pinned in Task 4: `test_no_h2_single_chapter`.
2. A Mermaid block with a syntax error, or a non-flowchart type, gives a warning plus a code block, not a crash or a FAIL. Pinned in Task 5: `test_render_error_becomes_code_block`.
3. Source text holding HTML or script (`<img src=x onerror=…>`, `</script>`) is escaped in the page and in `#card-config`. Pinned in Task 4: `test_source_html_is_escaped`.
4. localStorage throws (private mode) and the page still renders and works for the session. Pinned in Task 8: `storage unavailable still works`.
5. An imported JSON with junk, foreign ids or huge strings is sanitised: unknown statuses are dropped and strings capped (comment 4000, names 80/500). Pinned in Task 8: `import sanitises junk`.

---

### Task 1: Skill scaffold, launcher and hub test

**Files:**
- Create: `skills/software-development/discussion-card/scripts/discuss.sh`, `scripts/requirements.txt`, `scripts/mermaid.lock`, `tests/__init__.py`, `tests/test_launcher.py`
- Create: `tests/test_discussion_card.py` (hub)

**Interfaces:**
- Produces:
  - `discuss.sh --python` prints the venv python path.
  - `discuss.sh --mermaid` prints the verified Mermaid JS path.
  - `discuss.sh <in.md> --plan <card.yaml> [-o out.html] [--ui auto|ru|en] [--previous old.html] [--allow-drop]` is a stub that exits 1 with `build: not implemented` until Task 7.

- [ ] **Step 1: Write failing tests** in `tests/test_launcher.py` (unittest; they run the script via `subprocess`):
  - `test_no_args_exit_2`: no args → exit 2, stderr starts with `usage: discuss.sh`.
  - `test_non_md_input_exit_2`: input `x.txt` → exit 2.
  - `test_mermaid_sha_mismatch_exit_3`: set `DISCUSS_MERMAID` to a temp file with `garbage`; `--mermaid` → exit 3, stderr contains `sha256 mismatch`.
  - `test_foreign_venv_refused`: set `DISCUSS_VENV` to a temp dir with no marker; `--python` → exit 3, stderr contains `not built by discuss`.
- [ ] **Step 2: Run** `python3 -m unittest discover -s skills/software-development/discussion-card/tests -v`. Expected: 4 failures (script missing).
- [ ] **Step 3: Implement `discuss.sh`.**
  - POSIX sh.
  - Venv handling adapted from `md-to-html-page/scripts/mdpage.sh` (marker, atomic tmp dir, concurrent-run tolerance).
  - Mermaid fetch with `curl -fsSL` into `<file>.tmp.$$`, then sha256 verify (`shasum -a 256` or `sha256sum`), then `mv`.
  - Parse `mermaid.lock` with `sed`.
  - Write `requirements.txt` and `mermaid.lock` with the Global Constraints values.
- [ ] **Step 4: Run the tests.** Expected: 4 PASS.
- [ ] **Step 5: Create the hub test** `tests/test_discussion_card.py`, modelled on the `md-to-html-page` hub test:
  - `test_skill_suites_pass` resolves the venv via `discuss.sh --python` (skip on exit 3) and runs `-m unittest discover -s <skill>/tests`.
  - `test_skill_md_frontmatter` checks `name == "discussion-card"` and a non-empty description.
  - `test_skill_has_no_machine_paths`.
  - `test_skill_has_no_real_emails`.

  Add a minimal `SKILL.md` (frontmatter `name`, `description`; body: one line "Work in progress").
- [ ] **Step 6: Run** `python3 -m unittest tests.test_discussion_card -v`. Expected: PASS.
- [ ] **Step 7: Commit** `feat(discussion-card): add launcher, pinned venv and mermaid cache`.

### Task 2: Plan schema and validation

**Files:** Create `scripts/plan.py`, `tests/test_plan.py`, `tests/fixtures/plan_*.yaml`

**Interfaces:**
- Produces:
  - `class PlanError(Exception)`.
  - `@dataclass Plan(version:int, kind:str, slug:str|None, blocks:dict[str,bool], intro:Intro|None, chapters:list[ChapterHint], questions:QuestionsHint|None, diagrams:dict[int,DiagramHint])`.
  - `Intro(lead:str|None, cards:list[IntroCard(title, text, accent=False)])`.
  - `ChapterHint(from_:str, label:str|None, fold:bool)`.
  - `QuestionsHint(from_:str|None, options:dict[int,list[str]])`.
  - `DiagramHint(split:str|None)`, where `split` must be `"subgraphs"`.
  - `load_plan(path:Path, h2_titles:list[str]) -> Plan`.
  - `DEFAULT_BLOCKS = {"proposal": {"verdict","questions","actions"}, "retro": {"questions","actions"}, "review": {"questions"}}`.

- [ ] **Step 1: Failing tests.**
  - `test_minimal_plan_defaults`: `{version:1, kind:retro}` gives blocks `{verdict:False, questions:True, actions:True}`.
  - `test_blocks_override`.
  - `test_unknown_key_errors`: the message names the key path, e.g. `unknown key: chapters[0].hide`.
  - `test_version_2_errors`.
  - `test_kind_invalid_errors`.
  - `test_chapter_from_must_match_h2`: the message is `chapters[0].from "X" matches no H2`; matching is case- and whitespace-insensitive.
  - `test_questions_options_keys_int`.
  - `test_diagram_split_only_subgraphs`.
  - `test_slug_ascii_only`: must match `^[a-z0-9-]{1,40}$`.
- [ ] **Step 2: Run** the module's tests. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `load_plan` with `yaml.safe_load` and explicit allowed-key sets per mapping. Every error raises `PlanError(<path>: <reason>)`.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(discussion-card): validate card.yaml plans`.

### Task 3: Mermaid flowchart parser and subgraph split

**Files:**
- Create `scripts/mermaid_parse.py`, `tests/test_mermaid_parse.py`.
- Copy-adapt from `md-to-html-page/scripts/mermaid_view.py` and add a provenance comment at the top.

**Interfaces:**
- Produces:
  - `@dataclass Flowchart(index:int, direction:str, source:str, nodes:dict[str,str], edges:list[Edge], subgraphs:list[Subgraph])`. `nodes` maps id to label text with `<br/>` turned into a space.
  - `Edge(src, dst, label:str|None)`.
  - `Subgraph(id, title, node_ids:list[str])`.
  - `find_mermaid_blocks(tokens) -> list[tuple[int, str, str]]`, returning `(index, kind, source)`. The index is 1-based over all mermaid fences; `kind` is the first word.
  - `parse_flowchart(index, source) -> Flowchart`.
  - `split_subgraphs(fc) -> tuple[list[tuple[Subgraph, str]], list[Edge]]`, returning (part sources, cross-part edges).

- [ ] **Step 1: Failing tests** use the shapes from the spec. Copy the `md-to-html-page` fixture cases for `&`, chains, `subgraph X["Title"]`, `%%` comments, `;`, quoted labels with `<br/>`, and `-- "label" -->`.
  - `test_fanin_ampersand`: `C1 & C2 --> D` gives two edges.
  - `test_subgraph_membership`.
  - `test_split_keeps_internal_edges_and_returns_cross_edges`.
  - `test_split_part_source_is_valid_flowchart`: it starts with `flowchart <dir>`, holds only that part's nodes, and declares node shapes and labels exactly as the source did.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** by adapting the parser. `split_subgraphs` emits for each part `flowchart <dir>`, then each member node's original declaration line fragment, then the internal edges.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(discussion-card): parse and split mermaid flowcharts`.

### Task 4: Page model and HTML assembly

**Files:** Create `scripts/build.py`, `scripts/ids.py`, `scripts/ui_text.py`, `tests/test_build.py`, `tests/test_ids.py`, `tests/fixtures/sample.md`, `tests/fixtures/sample.card.yaml`

**Interfaces:**
- Consumes: `load_plan`, `Plan` (Task 2); `find_mermaid_blocks`, `parse_flowchart`, `split_subgraphs` (Task 3).
- Produces:
  - `ids.slugify(text:str) -> str`.
  - `ids.spot_id(chapter_slug:str, kind:str, text:str, seen:set[str]) -> str`.
  - `ids.node_spot_id(chapter_slug, node_id) -> str`.
  - `build.build_page(md_path:Path, plan:Plan, ui:str, diagram_renderer:Callable[[list[DiagramJob]], list[RenderedDiagram]]) -> Page`.
  - `@dataclass DiagramJob(key:str, chapter_slug:str, source:str, title:str|None)`.
  - `RenderedDiagram` is defined in Task 5. Here a stub renderer returns `<pre class="mermaid-src">`.
  - `@dataclass Page(html:str, spots:list[str], intro_words:int, config:dict, warnings:list[str])`.
  - `build.main(argv) -> int` handles `build.py in.md --plan p.yaml -o out.tmp --ui ru`.
  - `ui_text.LABELS: dict[str, dict[str,str]]` keyed `ru`/`en`.

- [ ] **Step 1: Write `tests/fixtures/sample.md`.** It is a fictional deploy-approval note with:
  - an H1;
  - H2 "Problem" with a paragraph;
  - H2 "How it works" with a flowchart LR of 4 nodes and edge labels;
  - H2 "Pipeline path" with a flowchart TD of 3 subgraphs;
  - H2 "Rules" with a 3-row table;
  - H2 "Situations" with an ordered list of 4;
  - a `> [!NOTE]` callout;
  - H2 "Open questions" with an ordered list of 3.

  `sample.card.yaml` sets kind `proposal`, an intro with 3 cards, options for question 1, and `diagrams: {2: {split: subgraphs}}`.
- [ ] **Step 2: Failing tests.**
  - `test_ids.py`:
    - `test_slugify_cyrillic`: `Как это работает` → `kak-eto-rabotaet`;
    - `test_spot_id_stable_on_whitespace`;
    - `test_spot_id_collision_suffix`;
    - `test_node_spot_id`.
  - `test_build.py`:
    - `test_chapters_follow_h2_order`;
    - `test_every_block_is_a_spot` (counts: 1 p, 3 tr, 4 li, 1 callout, 3 intro, 3 q);
    - `test_questions_from_h2_list` (options attached to q1);
    - `test_split_diagram_yields_three_jobs`;
    - `test_config_json` (key `discussion-card:sample:v1`, slides list, blocks);
    - `test_fold_chapter_rendered_as_details`;
    - `test_no_h2_single_chapter`;
    - `test_source_html_is_escaped` (`<img src=x onerror=alert(1)>` appears only escaped; `</script>` inside config JSON is escaped as `<\/script>`).
- [ ] **Step 3: Run.** Expected: FAIL.
- [ ] **Step 4: Implement.**
  - `ids.slugify` transliterates with a fixed Cyrillic map in-module, then lowercases, replaces non `[a-z0-9]` with `-`, and trims to 40 chars.
  - `build_page`:
    - walks markdown-it tokens and groups them by H2;
    - every paragraph, list item, table body row, callout blockquote and code fence gets `data-spot` with `tabindex="0"` and `role="button"`;
    - the questions H2 list becomes question cards with ids `q1…qN`;
    - mermaid fences become `DiagramJob`s;
    - other fences become code spots;
    - all text is escaped with `html.escape`;
    - config is embedded via `json.dumps(...).replace("</", "<\\/")`;
    - `engine.css`/`engine.js` are inlined from `assets/` (empty placeholders until Task 8).
- [ ] **Step 5: Run.** Expected: PASS.
- [ ] **Step 6: Commit** `feat(discussion-card): build page model and HTML`.

### Task 5: Build-time Mermaid render to SVG

**Files:** Create `scripts/mermaid_svg.py`, `assets/render-mermaid.html`, `tests/test_mermaid_svg.py`, `tests/fixtures/sample-flowchart.svg`, `tests/fixtures/sample-flowchart.json`

**Interfaces:**
- Consumes: `DiagramJob` (Task 4).
- Produces:
  - `@dataclass RenderedDiagram(key:str, svg:str|None, nodes:list[NodeBox], labels:list[Box], error:str|None, mode:str)`, with `mode` ∈ `"static"|"runtime"|"code"`.
  - `NodeBox(spot_id:str, label:str, box:Box, font_px:float)`.
  - `Box(x, y, w, h)`.
  - `render(jobs, mermaid_js:Path, chrome:str|None) -> list[RenderedDiagram]`.
  - `annotate_svg(svg:str, render_id:str, chapter_slug:str) -> tuple[str, list[str]]`, returning the annotated SVG and the spot ids.
  - `find_chrome() -> str|None`.

- [ ] **Step 1: Capture the fixture once (needs Chrome).** Render the sample's first flowchart through `render-mermaid.html` and save the SVG and the box JSON to `tests/fixtures/`. The JSON format is `{"nodes":[{"domId","label","x","y","w","h","fontPx"}],"labels":[{"x","y","w","h"}]}`, with numbers rounded to 1 decimal.
- [ ] **Step 2: Failing tests.** None of these need Chrome except the last.
  - `test_annotate_svg_adds_data_spot`: every `g.node` gets `data-spot="<chapter>-<nodeId>"`, `tabindex="0"` and `role="button"`; the regex strips `^<renderId>-flowchart-` and `-\d+$`.
  - `test_annotate_svg_removes_max_width`: the `style="max-width:…"` attribute is gone, and `width` is set to the viewBox width.
  - `test_render_error_becomes_code_block`: a fake chrome runner returns `{"error":"Parse error"}` → `mode=="code"` and `error` set.
  - `test_no_chrome_runtime_mode`: `chrome=None` → `mode=="runtime"` and `svg is None`.
  - `test_real_render` runs only when `find_chrome()` succeeds; it is never marked skip in CI as evidence. It checks that node count = 4 and that every `font_px >= 14`.
- [ ] **Step 3: Run.** Expected: FAIL.
- [ ] **Step 4: Implement.**
  - **`render-mermaid.html`.** It reads `jobs.json` via a `<script src="jobs.js">` that sets `window.JOBS`, which avoids `fetch` on `file://`. It initialises Mermaid with the Global Constraints settings and renders each job with id `d<k>`. For each node it collects the bbox via `getBBox()` mapped to `{x,y,width,height}` (`getBBox` does not JSON-serialise) plus the computed font size. It writes `<script id="result" type="application/json">` and sets `document.title="DONE"`.
  - **`render()`.** It writes `mermaid.js`, `jobs.js` and the page into a temp dir, runs Chrome with the Global Constraints flags via `subprocess.run(..., timeout=60)`, and parses `#result` from the dumped DOM.
  - **Runtime mode.** It returns a placeholder; Task 7 inlines the Mermaid JS for runtime mode.
- [ ] **Step 5: Run.** Expected: PASS (`test_real_render` runs locally).
- [ ] **Step 6: Commit** `feat(discussion-card): render mermaid to static svg at build time`.

### Task 6: Checks and check line

**Files:** Create `scripts/check.py`, `tests/test_check.py`

**Interfaces:**
- Consumes: the `Page` and `RenderedDiagram` boxes, through a sidecar JSON `<out>.tmp.meta.json` that `build.py` writes: `{spots, intro_words, diagrams:[{key,mode,nodes,labels}], warnings}`.
- Produces:
  - `check(md_path, html_path, meta_path, previous:Path|None, allow_drop:bool) -> CheckResult(ok:bool, line:str, samples:list[str])`.
  - `main(argv) -> int`.

- [ ] **Step 1: Failing tests,** one per gate, on crafted pages:
  - `test_words_missing_fails` (sample names the word);
  - `test_extra_counted_not_failing`;
  - `test_duplicate_spot_fails`;
  - `test_mermaid_node_without_spot_fails`;
  - `test_overlap_fails` (two label boxes intersect by 1px);
  - `test_font_below_14_fails`;
  - `test_offline_external_src_fails` (`<img src="https://x">`) and `test_svg_namespace_allowed`;
  - `test_id_diff_lists_dropped_marked_ids` (previous page plus a previous state JSON fixture with a mark on a now-missing id → FAIL unless `allow_drop`);
  - `test_runtime_mode_skips_overlap_and_font_with_reason` (line contains `diagrams=runtime`, warnings name the skipped gates);
  - `test_pass_line_format` (regex for the exact Global Constraints line).
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
  - **Words.** The words check tokenises the source text with markdown-it (inline text, table cells, code, Mermaid labels). It compares multisets of normalised words (casefold, `\w+`) with the page's visible text plus SVG `<text>`/`foreignObject` text.
  - **Previous marks.** The id diff reads marked ids from `--previous` by parsing that page's `#card-config` spots. Marks themselves live in the browser, so the diff reports dropped ids that existed. A dropped id fails only with `--previous-state <state.json>` (the user's JSON export) when that id holds a mark. Add this flag to `discuss.sh` in Task 7.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(discussion-card): add check gates and check line`.

### Task 7: Pipeline, sample end-to-end and screenshots

**Files:** Modify `scripts/discuss.sh`. Create `scripts/shoot.sh`, `tests/test_pipeline.py`

**Interfaces:**
- Consumes: Tasks 2–6.
- Produces: the full CLI from Global Constraints, plus `--previous-state <json>`. `shoot.sh <page.html> <out-dir> [--slides]` writes `desktop.png`, `dark.png` and `phone.png`, and with `--slides` writes `slide-<id>.png` at 1920x1080.

- [ ] **Step 1: Failing tests** in `tests/test_pipeline.py`:
  - `test_sample_passes`: `discuss.sh sample.md --plan sample.card.yaml -o tmp/out.html` → exit 0, stdout matches the PASS regex, output exists.
  - `test_fail_writes_nothing`: with `DISCUSS_FORCE_FAIL=1` (a test hook that corrupts the temp page, as `mdpage.sh` does) → exit 1, no output file.
  - `test_rebuild_backs_up_previous`.
  - `test_plan_error_exit_2`.
  - `test_runtime_fallback_inlines_mermaid`: with `CHROME_BIN=/nonexistent` → exit 0, the line has `diagrams=runtime`, and the HTML contains the Mermaid IIFE marker `__esbuild_esm_mermaid_nm`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
  - **`discuss.sh` order:** parse args → ensure venv and Mermaid → `build.py` (renderer from `mermaid_svg`) → `check.py` → on PASS, back up and `mv`; on FAIL, `rm` the tmp.
  - **Runtime mode:** `build.py` inlines the Mermaid JS and the engine renders it on load (Task 8 wires it).
  - **`shoot.sh`:** adapted from `md-to-html-page/scripts/shoot.sh`. `--slides` loads `page.html#<slide>` for each slide id from `#card-config`.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(discussion-card): wire build pipeline end to end`.

### Task 8: Engine and browser tests

**Files:** Create `assets/engine.js`, `assets/engine.css`, `scripts/package.json`, `tests/e2e/card.test.mjs`

**Interfaces:**
- Consumes:
  - `#card-config` (Task 4): `{storageKey, ui, labels, chapters:[{id,title,label,fold}], slides:[{id,chapter,title}], blocks, questions:[{id,text,options}], runtimeDiagrams:bool}`;
  - elements `[data-spot]`, `section.chapter[data-chapter]`, `[data-slide]`.
- Produces: the user-visible behaviour in spec §Engine.

- [ ] **Step 1: Write failing browser tests** in `card.test.mjs` with `node:test` and Playwright Chromium. `before` builds the sample via `discuss.sh` into a temp dir and opens it with `file://`.
  - `spot mark and comment persist across reload`.
  - `vote question action item persist`.
  - `hot chip jumps to slide and opens drawer`.
  - `presenter keys and hash`: ArrowRight changes `location.hash`. In a tall slide (the 1280x600 viewport makes "Pipeline path" tall), the first PageDown scrolls (`scrollY` grows, hash unchanged) and a later one advances.
  - `P toggles mode and is remembered`.
  - `markdown export contains comment and verdict`: capture via `page.on('download')`.
  - `phone 390 has no horizontal page scroll`: `document.documentElement.scrollWidth <= 390`.
  - `dark theme tokens apply`.
  - `storage unavailable still works`: an init script makes `localStorage.getItem` throw; marking still works in the session and a toast is visible.
  - `import sanitises junk`.
- [ ] **Step 2:** `cd scripts && npm install && npx playwright install chromium`, then `npm test`. Expected: FAIL.
- [ ] **Step 3: Implement the engine.**
  - **Starting point.** Generalise the reference page's logic (spots registry, drawer, vote, questions, actions, hot strip, TOC, presenter, export/import, theme) into a config-driven engine. The reference page is handed over out of band. It holds private content, so never commit it or copy any of its text: take only its logic.
  - **What to drop.** Content-specific text, hard-coded question lists and slide tables.
  - **Labels.** All labels come from `config.labels`.
  - **Runtime diagrams.** When `runtimeDiagrams` is set, render `pre.mermaid-runtime` blocks with the inlined Mermaid, then annotate nodes with the same id rule as `annotate_svg` before registering spots.
  - **Safety.** User text uses `textContent` only.
- [ ] **Step 4: Run** `npm test`. Expected: all PASS. Also run the Python suites. Expected: PASS.
- [ ] **Step 5:** Run `scripts/shoot.sh out.html shots --slides` on the sample and look at `desktop.png` and two slide shots. Fix visible defects once.
- [ ] **Step 6: Commit** `feat(discussion-card): add interactive engine and browser tests`.

### Task 9: SKILL.md, hub wiring and validation

**Files:**
- Modify `skills/software-development/discussion-card/SKILL.md`, `docs/skill-catalog.md`, `THIRD_PARTY_NOTICES.md`.
- Modify `tests/test_discussion_card.py`: add `test_node_suite_present`, asserting that `tests/e2e/card.test.mjs` exists and `scripts/package.json` pins `playwright` to `1.65.0`.

- [ ] **Step 1: Write `SKILL.md`.** Follow the `md-to-html-page` shape: frontmatter; Prerequisites (python, Chrome optional, network on first run); What Claude does (the 5 steps from spec §Agent procedure, including the who-writes question and the whiteboard redirect); Command and flags table; `card.yaml` reference; Checks and exit codes; Troubleshooting; Provenance (files adapted from `md-to-html-page`); Mermaid licence note.

  Description: `Use when a Markdown design note, proposal or process description should become an offline interactive card for a screen-shared discussion (retro, design review, for/against vote): clickable Mermaid diagrams, marks and comments, presenter mode, and a Markdown summary export.`
- [ ] **Step 2:** Add the catalog line under Software development, matching the neighbouring format. Add the `THIRD_PARTY_NOTICES.md` entry: `@mermaid-js/tiny` 12.3.0, MIT, downloaded at first run and inlined only in runtime-fallback pages.
- [ ] **Step 3: Run** `python3 -m unittest tests.test_discussion_card -v` and `./scripts/validate.sh --ci`. Expected: PASS. Then run `./scripts/validate.sh --full`. Expected: PASS; it needs zensical 0.0.24 via uvx and gitleaks ≥ 8.30.1, and if either is missing, report it rather than skipping silently.
- [ ] **Step 4:** Scan changed files for `TODO|TBD|skip|only(` and machine paths. Expected: none.
- [ ] **Step 5: Commit** `docs(discussion-card): document the skill and wire it into the hub`.
