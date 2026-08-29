---
name: init-doc
description: Use when initializing a translation project from extraction through glossary, chapter mapping, and progress tracking.
user-invocable: true
---

# Initialize Document Translation

## Overview

Initialize translation baseline from PDF extraction to chaptered docs, style decisions, glossary, progress tracker, and reusable whole-book context.

**Core principle:** Build a deterministic, verifiable baseline before any large-scale translation.

## Task Initialization (MANDATORY)

Before ANY action, create tasks using TaskCreate:
- One task per major phase (extraction, formatting, images/theme, terminology, chapter split, progress tracker, translation context)
- One task for final handoff gate
- One task for automatic translation dispatch

## Interaction Rules

- All user interaction must be Traditional Chinese (zh-TW).
- AskUserQuestion prompts must be Traditional Chinese.
- Do not use Simplified Chinese in user-facing text.

## The Process

### Step 1: Cleanup and Source Validation

Run cleanup:

```bash
uv run python scripts/clean_sample_data.py --yes
```

Then resolve source PDF from `$ARGUMENTS` or ask user in Traditional Chinese. Ensure source is under `data/pdfs/`.

Before extraction, ask user in Traditional Chinese whether to preserve PDF images in the generated docs:

```text
是否要保留 PDF 內的圖片，並在切分後的 Markdown 文件中保留對應圖片連結？
```

Record this decision as `preserve_images: true/false` for the rest of the run.

**Verification:** Source PDF exists under `data/pdfs/`; `preserve_images` decision recorded; cleanup script exited 0.

### Step 2: Create Tasks

Create TaskCreate items for:
- extraction
- formatting decisions
- image retention decision
- image and theme setup
- terminology bootstrap
- chapter mapping
- progress tracker creation
- reusable translation context
- final handoff gate
- automatic translation dispatch

**Verification:** All tasks created with correct descriptions; task list matches the phases above.

### Step 3: Extract and Validate Raw Outputs

Run:

```bash
uv run python scripts/extract_pdf.py <pdf_path> --include-images
```

If `preserve_images` is `false`, run instead:

```bash
uv run python scripts/extract_pdf.py <pdf_path> --no-include-images
```

Validate outputs:
- `data/markdown/<name>.md`
- `data/markdown/<name>_pages.md`
- `data/markdown/images/<name>/`（only when `preserve_images = true`）

**Verification:** All expected output files exist and are non-empty.

### Step 4: Cropping Review and Optional Split

Review readability and completeness.
If needed, split large source into parts and re-extract until clean.

**Verification:** Extracted markdown is readable; no garbled text or truncated sections remain.

### Step 5: Confirm Document Formatting Decisions

Summarize content to user in Traditional Chinese:

```text
書本內容概覽：
- 主要內容類型：[規則說明、範例場景、角色選項...]
- 特殊結構：[大量表格、骰表、設計者備註...]
- 建議可使用的格式化元件：[...]
```

Collect formatting choices (Traditional Chinese):
- layout profile for extraction (`auto` / `single-column` / `double-column`)
- aside mapping (`note/tip/caution/danger`) — must include a mapping for game examples (game examples should always be rendered as asides)
- card/tabs usage
- table/dice-table conventions

Persist via script:

```bash
uv run python scripts/style_decisions.py init
uv run python scripts/style_decisions.py set-document-format \
  --layout-profile "<auto|single-column|double-column>" \
  --aside-note "<note_component>" \
  --aside-tip "<tip_component>" \
  --aside-caution "<caution_component>" \
  --aside-danger "<danger_component>" \
  --cards-usage "<cards_usage_note>" \
  --tabs-usage "<tabs_usage_note>" \
  --tables-convention "<table_note>" \
  --dice-tables-convention "<dice_table_note>"
uv run python scripts/validate_style_decisions.py
```

Ask user to choose translation mode in Traditional Chinese:

```text
請選擇翻譯模式：
A. 純中文翻譯：完整翻譯所有內容，僅保留中文
B. 雙語模式：中文翻譯為主，英文原文以 blockquote 附於每段之後
```

Persist via:

```bash
uv run python scripts/style_decisions.py set-translation-mode \
  --mode "<full|bilingual>" \
  --reason "使用者在 init-doc 選擇翻譯模式"
```

**Verification:** `style-decisions.json` contains `document_format` section and `translation_mode` section; `validate_style_decisions.py` exits 0.

### Step 6: Select Images, Theme, and Homepage Content

1. If `preserve_images = true`, ask user to assign extracted images for hero/background/og.
2. If `preserve_images = true`, copy and resize where needed.
3. If `preserve_images = false`, skip extracted image assignment and continue with theme-only setup.
4. Ask theme decisions in Traditional Chinese. `custom.css` derives every interface
   layer (nav, sidebar, hairlines, inline code, surfaces) from `--bg-h` and `--bg-l`,
   so ask for those two knobs plus the accent hues — never for individual layer colors.
   - `--overlay-opacity` MUST stay `0` unless a background image is actually placed at
     `docs/public/bg.jpg`. On a flat background the overlay has nothing to mask and only
     darkens the page.
   - `--bg-l` is meaningful in the 5%-16% range (dark mode only; the layer model is additive).
5. Update `docs/src/styles/custom.css`, then persist the theme decision via:

```bash
uv run python scripts/style_decisions.py set-theme \
  --mode dark-forced \
  --bg-h "<0-360>" \
  --bg-l "<5%-16%>" \
  --overlay "<0_unless_background_image_used>" \
  --palette "<色票說明>"
```
6. Persist image retention decision via:

```bash
uv run python scripts/style_decisions.py set-images --preserve-images <true_or_false>
```
7. Ask for site meta in Traditional Chinese (all four fields):
   - **網站標題**（`site.title`）：首頁 `<title>` 及 frontmatter title，例：「Rapscallion 遊戲規則」
   - **首頁描述**（`site.description`）：SEO description，一句話
   - **副標語**（`site.tagline`）：hero 區塊顯示的一行短語
   - **內容簡介**（`site.intro`）：首頁「內容簡介」段落，一到兩句
   Persist via:

   ```bash
   uv run python scripts/style_decisions.py set-site \
     --title "<USER_INPUT>" \
     --description "<USER_INPUT>" \
     --tagline "<USER_INPUT>" \
     --intro "<USER_INPUT>"
   ```

8. Ask for copyright and credits in Traditional Chinese:
   - Copyright notice text（例：`© 2024 Author Name. All rights reserved.`）
   - Credits entries as role → name pairs（例：原作者、翻譯、美術設計等）
   - Whether to show each section on the homepage
9. Persist via:

```bash
uv run python scripts/style_decisions.py set-copyright \
  --text "<USER_INPUT>" \
  --show-on-homepage <true_or_false>
uv run python scripts/style_decisions.py set-credits \
  --entry "原作者:..." \
  --entry "翻譯:..." \
  --show-on-homepage <true_or_false>
```

10. Ask whether there are any translation-wide notes the translator must always follow.
    Persist each note via:

```bash
uv run python scripts/style_decisions.py add-translation-note \
  --key "<short_key>" \
  --topic "<optional_topic>" \
  --note "<USER_INPUT>"
```

If the note is specific to one source file or future appended document, use:

```bash
uv run python scripts/style_decisions.py add-translation-note \
  --document-key "<pdf_stem_or_doc_id>" \
  --key "<short_key>" \
  --note "<USER_INPUT>"
```

11. Run:

```bash
uv run python scripts/validate_style_decisions.py
```

`generate_nav.py` will render these as **## 版權宣告** and **## 製作名單** sections on the homepage. If neither is provided, a generic fallback disclaimer is used.

**Verification:** `validate_style_decisions.py` exits 0; `style-decisions.json` contains site meta, copyright, credits, and image decisions.

### Step 7: Build Terminology Baseline

Invoke `term-decision` skill for terminology bootstrap instead of duplicating the workflow here.

Required handoff to `term-decision`:
1. Source is the extracted markdown from this init run.
2. First inspect high-signal terminology sources in the original book:
   - source glossary / terminology pages
   - index pages
   - appendix term lists
   - playbook / move summary tables that clearly define recurring mechanics terms
3. Complete one first-pass terminology bootstrap from those sections:
   - prefill obvious term translations into `glossary.json`
   - keep wording consistent with `style-decisions.json`
   - ask the user only about uncertain, culturally nuanced, or mechanics-ambiguous terms
4. After that first pass, generate and verify the remaining candidates with:

```bash
uv run python scripts/term_generate.py --min-frequency 2
uv run python scripts/term_cal_batch.py
uv run python scripts/validate_glossary.py
uv run python scripts/term_read.py --fail-on-missing --fail-on-forbidden
```

`init-doc` must not continue to chapter split until the `term-decision` handoff completes cleanly.

**Verification:** `validate_glossary.py` and `term_read.py --fail-on-missing --fail-on-forbidden` both exit 0.

### Step 8: Chapter Split and Navigation

Invoke `chapter-split` skill instead of duplicating split logic here.

Required handoff to `chapter-split`:
1. Source is the extracted `_pages.md` file from this init run.
2. Reuse the `preserve_images` decision from Step 1.
3. Reuse the formatting and terminology decisions already completed in Steps 5-7.
4. Generate `chapters.json`, split docs output, and regenerate navigation.
5. If `chapter-split` reports unresolved critical issues, stop `init-doc` and resolve them before continuing.

**Verification:** `chapters.json` exists; split docs generated; nav regenerated.

### Step 9: Create Translation Progress Tracker

Create `data/translation-progress.json` from `chapters.json`:

```bash
uv run python scripts/init_create_progress.py --force
```

Tracker contract:
- chapter ids derived from output file paths
- source page ranges mapped from chapter config
- initial status `not_started`
- `_meta` fields (`updated`, `total_chapters`, `completed`)

**Verification:** `data/translation-progress.json` exists; contains all chapters from `chapters.json` with status `not_started`; `_meta` fields present.

### Step 10: Persist Reusable Translation Context

Initialize the context file after chapter order and progress state are stable:

```bash
uv run python scripts/translation_context.py init
```

Use [`../translate/context-prompt.md`](../translate/context-prompt.md) to write the full-book summary and one summary, role, dependency list, and applicable term list for every chapter. Reuse the complete-source understanding already gathered during extraction, formatting, terminology, and chapter mapping; read only source sections that were not actually covered in the current run. Do not begin chapter translation here.

Record only genuine unresolved ambiguities. Resolve them through the terminology decision flow, update `glossary.json`, clear the resolved queue, and finalize:

```bash
uv run python scripts/translation_context.py finalize
uv run python scripts/translation_context.py status --require-ready
```

**Verification:** `data/translation-context.json` exists, covers every progress entry, contains no unresolved ambiguities, and reports `ready`.

### Step 11: Final Gate (Fail-Closed)

Run one-shot handoff gate:

```bash
uv run python scripts/init_handoff_gate.py
```

If any gate fails, stop and fix before completion.

**Verification:** `init_handoff_gate.py` exits 0; all initialization tasks are `completed`, and the automatic translation dispatch task is ready.

### Step 12: Automatically Start Full Translation

Only after Step 11 exits zero, read `style-decisions.json.translation_mode.mode` and dispatch the complete pending book without another confirmation prompt:

- `full` → invoke `/translate all`;
- `bilingual` → invoke `/bilingual-translate all`.

Do not dispatch either translation skill when the gate fails, the mode is absent/invalid, or the user has interrupted the run. Return the downstream translation skill's progress, completion checks, and final website result as the completion of this `init-doc` invocation; do not report initialization as the final outcome while translation is still running.

Mark the automatic translation dispatch task `completed` only after the downstream skill returns its final result.

**Verification:** the selected translation skill receives `all`, no manual command is required between initialization and translation, and the dispatch task closes only after downstream completion.

## Flowchart

```dot
digraph init_doc {
    rankdir=TB;
    cleanup [label="Cleanup &\nsource validation", shape=box];
    tasks [label="Create tasks", shape=box];
    extract [label="Extract PDF", shape=box];
    img_decision [label="Preserve\nimages?", shape=diamond];
    extract_img [label="Extract with\n--include-images", shape=box];
    extract_noimg [label="Extract with\n--no-include-images", shape=box];
    crop [label="Cropping review\n& optional split", shape=box];
    format [label="Formatting\ndecisions", shape=box];
    theme [label="Images, theme\n& homepage", shape=box];
    term [label="Terminology\nbaseline\n(term-decision)", shape=box];
    term_ok [label="Term validation\npasses?", shape=diamond];
    split [label="Chapter split\n(chapter-split)", shape=box];
    split_ok [label="Split\nsucceeded?", shape=diamond];
    progress [label="Create progress\ntracker", shape=box];
    context [label="Persist reusable\ntranslation context", shape=box];
    gate [label="Final handoff\ngate", shape=box];
    gate_ok [label="Gate\npasses?", shape=diamond];
    mode [label="Translation\nmode", shape=diamond];
    translate [label="translate all", shape=box];
    bilingual [label="bilingual-translate all", shape=box];
    done [label="Translated site\ncomplete", shape=box];
    fix [label="Fix & retry", shape=box];

    cleanup -> tasks -> extract;
    extract -> img_decision;
    img_decision -> extract_img [label="yes"];
    img_decision -> extract_noimg [label="no"];
    extract_img -> crop;
    extract_noimg -> crop;
    crop -> format -> theme -> term;
    term -> term_ok;
    term_ok -> split [label="yes"];
    term_ok -> fix [label="no"];
    fix -> term;
    split -> split_ok;
    split_ok -> progress [label="yes"];
    split_ok -> fix [label="no"];
    progress -> context -> gate;
    gate -> gate_ok;
    gate_ok -> mode [label="yes"];
    mode -> translate [label="full"];
    mode -> bilingual [label="bilingual"];
    translate -> done;
    bilingual -> done;
    gate_ok -> fix [label="no"];
}
```

## Progress Sync Contract (Required)

1. Keep tasks updated via TaskUpdate at every step.
2. Mark blockers immediately and include failing command/context.
3. Close initialization tasks only after the final gate passes; close automatic translation dispatch only after the downstream translation skill returns.

## When to Stop and Ask for Help

Stop when:
- source extraction repeatedly fails
- `chapter-split` cannot produce a usable config
- glossary validation cannot be resolved safely
- docs build fails with unclear root cause

## When to Revisit Earlier Steps

Return to earlier steps when:
- user changes formatting/theme policy
- user changes proper noun strategy
- source markdown changes enough to invalidate page mapping

## Red Flags

| Thought | Reality |
|---------|---------|
| "Validation failed but it's probably fine, keep going" | Fail-closed means stop. Fix the failure before proceeding. |
| "Skip chapter-split handoff and split manually" | Chapter-split skill ensures deterministic structure. Never bypass. |
| "User didn't answer about proper nouns, I'll just pick one" | User confirmation is required for formatting and proper noun policy. |
| "Progress tracker can be created later" | Tracker must be initialized before handoff. No exceptions. |
| "Skip terminology baseline, we can add terms during translation" | Terminology drift across chapters is costly. Bootstrap first. |
| "I'll reuse the old glossary without re-validating" | Glossary changes between runs. Always validate. |
| "One quick formatting change doesn't need style-decisions.json" | All formatting decisions must be persisted. No ad-hoc overrides. |

## Next Step

If `style-decisions.json` has `translation_mode.mode == "bilingual"`, continue with `/bilingual-translate`.
Otherwise, continue with `/translate` or `/super-translate`.

## Example Usage

```text
/init-doc
/init-doc data/pdfs/rulebook.pdf
```
