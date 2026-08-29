---
name: bilingual-translate
description: Use when translating in bilingual mode — produces Chinese primary + English blockquote markdown. Single-pass, no multi-round review. Requires translation_mode=bilingual in style-decisions.json.
user-invocable: true
---

# Bilingual Translate

> 模型建議：本技能為主執行緒流程，依成本路由決策建議於 **sonnet** 會話執行；高階模型會話亦可執行，但屬超規格花費。

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

4. Resolve the project's Codex draft-tiering preference per `../translate/codex-tier.md` §1 (asked once per project, then silent).

**Verification:** Target scope is resolved; all required files and mode settings present; Codex tiering preference resolved.

### Step 2: Terminology Preflight (Fail-Closed)

```bash
uv run python scripts/validate_glossary.py
uv run python scripts/term_read.py --fail-on-missing --fail-on-forbidden
```

If preflight fails, stop and fix terminology first.

**Verification:** Both commands exit 0.

### Step 3: Prepare an Isolated Bilingual Draft Wave

Select a maximum of 3 lower-cost draft workers per wave. For each target file, determine the source English markdown path from `data/markdown/` (the `_pages.md` source referenced in `chapters.json`).

Determine the output path: `docs/src/content/docs/bilingual/<section>/<file>.md` (from `chapters.json` + `mode=bilingual`).

Register every draft path sequentially before dispatch by running `bilingual_prep.py` in chapter order to generate drafts with placeholders in `.state/bilingual-translate/drafts/`:

```bash
uv run python scripts/bilingual_prep.py <SOURCE_FILE> <DRAFT_FILE>
```

**Verification:** Draft file exists and contains `<!-- TODO: 翻譯 -->` placeholders.

### Step 4: Translate the Wave

Freeze each file's glossary/style/source input, then dispatch up to three draft workers concurrently. Each worker may edit only its assigned bilingual draft and must not modify glossary, context, progress, source, navigation, or another draft. For each target file:

1. If using task tracking, mark the item `in_progress`
2. Read draft, `glossary.json`, and `style-decisions.json`
3. For each `<!-- TODO: 翻譯 -->` placeholder: replace it with the Chinese translation of the English text in the immediately following blockquote line(s), following `../translate/translator-style.md` for register, proper-noun policy, POV, terminology glossing, and sentence structure.

   If Codex tiering is enabled and available (`../translate/codex-tier.md` §2), delegate this placeholder-filling to Codex per `../translate/codex-tier.md` §3 — the prompt MUST state that only `<!-- TODO: 翻譯 -->` placeholders may be replaced and every line starting with `>` must be left byte-for-byte untouched. On any Codex failure, use the per-chapter Claude Agent `sonnet` fallback in `../translate/codex-tier.md` §5.
4. Update frontmatter `title` to Traditional Chinese; add `bilingual: true` if not present
5. Single-pass self-review — unconditional and identical whether Codex or you filled the placeholders:
   - Any `<!-- TODO: 翻譯 -->` left untranslated?
   - Glossary violations?
   - Full-width punctuation correct in Chinese text?
   - English blockquote lines (starting with `>`) preserved exactly — no modifications?
   - Content contamination (paragraphs with no source)?
   - Native Chinese quality: any sentence that keeps English clause order/structure instead of natural Chinese syntax? Any 四字成語 or literary flourish that isn't grounded in the source's meaning? Any technical term translated where `glossary.json` or `style-decisions.json` says to keep the original English form?
6. After every worker returns, write back in chapter order to `docs/src/content/docs/bilingual/<path>`
7. Update progress:
   ```bash
   uv run python scripts/progress_edit.py --progress-file data/translation-progress-bilingual.json --file <TARGET_FILE> --status completed
   ```
8. If using task tracking, mark the item completed

One worker failure falls back only that chapter per `../translate/codex-tier.md`; successful siblings continue. Reduce later waves after repeated resource/rate-limit failures. Group shared terminology ambiguities at the wave boundary and revalidate affected drafts before writeback.

**Verification:** Self-review checklist passes; output file written; progress JSON updated.

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
| "Codex filled this, skip the self-review" | Review is unconditional regardless of who/what filled the placeholders. |

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
