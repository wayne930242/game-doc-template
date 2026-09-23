---
name: bilingual-translate
description: Use when translating in bilingual mode — produces Chinese primary + English blockquote markdown. Single-pass, no multi-round review. Requires translation_mode=bilingual in style-decisions.json.
user-invocable: true
---

# Bilingual Translate

## Overview

Single-pass bilingual translation. Produces documents where each Chinese paragraph is followed by the English original as a blockquote.

**Output format:**

```markdown
中文翻譯段落文字。

> Original English paragraph text here.
```

**Core principle:** Draft-first with bilingual_prep.py placeholders. Write directly to bilingual output dir. No multi-round review loop.

## Progress Tracking

Authoritative state lives in `data/translation-progress-bilingual.json`, kept in sync via `progress_edit.py`/`progress_read.py` at each step below — this is what later runs and other skills read, and it survives across sessions.

If a task-tracking tool is available in this session, mirror per-file progress into it for visibility (one task per target file, one for batch checkpoint, one for final verification). Treat it as optional visibility on top of the progress file, not the source of truth.

## The Process

### Step 1: Resolve Scope and Preconditions

1. Verify required files:
   - `glossary.json`
   - `style-decisions.json` with `translation_mode.mode == "bilingual"`
   - `chapters.json` with `"mode": "bilingual"`
   If any missing or mode mismatch, stop and ask user to run `/init-doc` first.

2. Resolve target files from `$ARGUMENTS` or auto-select a wave using the progress script:
   ```bash
   uv run python scripts/progress_read.py --progress-file data/translation-progress-bilingual.json --next 3 --json
   ```
   - Select `in_progress` before `not_started` and preserve chapter order.
   - If the progress file does not exist, create it first:
     ```bash
     uv run python scripts/progress_edit.py --progress-file data/translation-progress-bilingual.json --create-if-missing
     ```

3. Do not pause for scope confirmation when invoked with `all` or from `init-doc`; continue across waves automatically.

**Verification:** Target scope is resolved; all required files and mode settings present.

### Step 2: Terminology Preflight (Fail-Closed)

```bash
uv run python scripts/validate_glossary.py
uv run python scripts/term_read.py --fail-on-missing --fail-on-forbidden
```

If preflight fails, stop and fix terminology first.

**Verification:** Both commands exit 0.

### Step 3: Prepare an Isolated Bilingual Draft Wave

Select at most three files per wave. Each file is one draft work unit. For each target file, determine the source English markdown path from `data/markdown/` (the `_pages.md` source referenced in `chapters.json`).

Determine the output path: `docs/src/content/docs/bilingual/<section>/<file>.md` (from `chapters.json` + `mode=bilingual`).

Register every draft path sequentially before dispatch by running `bilingual_prep.py` in chapter order to generate drafts with placeholders in `.state/bilingual-translate/drafts/`:

```bash
uv run python scripts/bilingual_prep.py <SOURCE_FILE> <DRAFT_FILE>
```

**Verification:** Draft file exists and contains `<!-- TODO: 翻譯 -->` placeholders.

### Step 4: Translate the Wave

Freeze each file's glossary/style input, then dispatch the wave's draft units as one fan-out, each briefed with [`filler-prompt.md`](./filler-prompt.md). Each unit may edit only its assigned bilingual draft and must not modify glossary, context, progress, source, navigation, or another draft. If using task tracking, mark each item `in_progress` at dispatch.

After every unit returns, write back in chapter order. For each file:

1. Write back to `docs/src/content/docs/bilingual/<path>`
2. Update progress:
   ```bash
   uv run python scripts/progress_edit.py --progress-file data/translation-progress-bilingual.json --file <TARGET_FILE> --status completed
   ```
3. If using task tracking, mark the item completed

A failed draft unit affects only its chapter; successful siblings continue. Group shared terminology ambiguities at the wave boundary and revalidate affected drafts before writeback.

**Verification:** Every unit reports `self_review_pass: true`; output file written; progress JSON updated.

### Step 5: Batch Checkpoint Commit

After all files in the batch are processed:

1. Run `git status --short` and verify batch scope before staging.
2. Stage only files touched by this batch:
   - Translated bilingual files
   - `translation-progress-bilingual.json`
   - `glossary.json` if changed
   - `style-decisions.json` if changed
3. Commit:

```bash
git commit -m "progress (bilingual): X/Y"
```

Where X/Y is current completion from `uv run python scripts/progress_read.py --progress-file data/translation-progress-bilingual.json --json`.

**Verification:** `git log -1` shows progress commit.

### Step 6: Final Verification

```bash
uv run python scripts/validate_glossary.py
uv run python scripts/term_read.py --fail-on-missing --fail-on-forbidden
```

If using task tracking, mark the final verification item completed.

Invoke `check-consistency`. When every bilingual progress entry is completed, invoke `check-completeness`, then run:

```bash
uv run python scripts/translation_completion.py \
  --progress-file data/translation-progress-bilingual.json \
  --json
```

Require zero exit before reporting the bilingual book/site complete. Partial scopes do not run the final website handoff.

**Verification:** Both terminology commands exit 0; requested entries are completed; a whole-book run also produces `docs/dist/` and passes search verification.

## Red Flags

| Thought | Reality |
|---------|---------|
| "Modify the English blockquote lines" | Never alter `>` lines. They are source text. |
| "Skip bilingual_prep, I'll format manually" | bilingual_prep ensures consistent structure. Always use it. |
| "translation-progress-bilingual.json doesn't exist, skip tracking" | Create it with `progress_edit.py --create-if-missing`. |
| "One file done, no need for checkpoint" | Every completed batch gets a commit. |
| "Skip terminology preflight, it was fine last time" | Glossary changes between runs. Always preflight. |

## When to Stop and Ask for Help

Stop when:
- mode mismatch (style-decisions says bilingual but chapters.json doesn't)
- source markdown is missing or unreadable
- terminology conflicts block translation integrity

## Example Usage

```text
/bilingual-translate
/bilingual-translate docs/src/content/docs/bilingual/rules/combat.md
/bilingual-translate all
```
