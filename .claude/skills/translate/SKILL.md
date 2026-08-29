---
name: translate
description: Use when translating one chapter, a scoped set, or a complete rulebook with reusable whole-book context, glossary control, deterministic Markdown validation, and one semantic review.
user-invocable: true
---

# Translate Document

Translate complete Markdown chapters into Traditional Chinese. The same workflow handles focused fixes and unattended whole-book translation.

**Leading principle:** understand the whole book once, then translate every chapter in that shared context. A chapter translation is complete prose, never a summary.

## Authoritative state

| File | Responsibility |
| --- | --- |
| `data/translation-context.json` | Whole-book and per-chapter source context; no authoritative term mappings |
| `glossary.json` | The only authoritative term mappings |
| `style-decisions.json` | User-approved translation and presentation decisions |
| `data/translation-progress.json` | Chapter order and completion state |
| `.state/translate/` | Rebuildable isolated drafts |

## Process

### 1. Resolve project and scope

Require `chapters.json`, `glossary.json`, and `style-decisions.json`. Create the progress tracker when absent:

```bash
uv run python scripts/progress_edit.py --create-if-missing
```

Resolve scope without a confirmation pause:

- explicit file or pattern: process only matching entries;
- `next`: process the next pending checkpoint batch;
- no arguments or `all`: process every pending entry and continue across checkpoint batches.

Select `in_progress` before `not_started`, preserving chapter order within each status:

```bash
uv run python scripts/progress_read.py --next 5 --json
```

Resolve the optional Codex draft tier once per project using [`codex-tier.md`](./codex-tier.md). This provider preference does not change the translation or review contract.

**Complete when:** scope is known, required project state exists, and no user confirmation is pending.

### 2. Prepare or reuse whole-book context

Inspect context state:

```bash
uv run python scripts/translation_context.py status --json
```

- missing context or `full_refresh_required`: initialize and run [`context-prompt.md`](./context-prompt.md). Read every unique source, covering all chapters in `chapters.json` order, before drafting any translation. Then run the terminology candidate workflow below.
- `decision_refresh_required`: retain the source summaries; reconcile glossary/style decisions, rerun the terminology candidate workflow only when glossary content changed, and finalize again.
- `ready`: reuse the existing context without rereading the complete source corpus.

Initialize when needed:

```bash
uv run python scripts/translation_context.py init
```

The context pass must produce:

- a whole-book summary of subject, structure, tone, core rules/concepts, world information, and translation priorities;
- one summary and functional role for every chapter;
- chapter dependencies and relevant glossary term keys;
- a queue containing only genuine unresolved ambiguities.

For a new or fully refreshed context, run the existing terminology candidate workflow once against the complete corpus:

```bash
uv run python scripts/term_generate.py --min-frequency 2
uv run python scripts/term_cal_batch.py
uv run python scripts/validate_glossary.py
```

Reuse `terminology-management` to approve direct, unambiguous mappings. Ask the user only when multiple plausible readings affect mechanics, meaning, names, wordplay, cultural tone, or cross-chapter consistency. Group related questions. Persist each answer in `glossary.json` and remove it from the context's unresolved queue.

When context was created or decisions were refreshed, finalize only after context and terms are ready:

```bash
uv run python scripts/translation_context.py finalize
```

On every invocation, including reuse of a ready context, run the inexpensive terminology guards:

```bash
uv run python scripts/validate_glossary.py
uv run python scripts/term_read.py --fail-on-missing --fail-on-forbidden
```

**Complete when:** context status is `ready`, every chapter has a summary and role, and no unresolved ambiguity remains.

### 3. Build one complete chapter draft

For the next selected file:

1. Mark it `in_progress`.
2. Register and obtain its draft path through `draft.py`; do not construct a draft path manually.
3. Read only the current full source chapter plus the reusable context, glossary, style decisions, and translator style.
4. Generate the draft using [`translator-prompt.md`](./translator-prompt.md), either in the current session or through the configured Codex tier.

```bash
uv run python scripts/progress_edit.py --file <TARGET_FILE> --status in_progress
uv run python scripts/draft.py --skill translate path <TARGET_FILE>
```

Delegated work receives absolute project, target, and draft paths. The translator receives:

- the complete current source chapter;
- `book_summary`;
- the matching chapter summary, role, dependencies, and key terms;
- applicable glossary entries;
- style decisions and [`translator-style.md`](./translator-style.md).

**Complete when:** an isolated draft contains a complete translation of every source block.

### 4. Validate structure deterministically

```bash
uv run python scripts/validate_translation_structure.py \
  <ABSOLUTE_SOURCE_PATH> \
  <ABSOLUTE_DRAFT_PATH> \
  --json
```

Repair only reported structural differences, then rerun until the command exits zero. This gate owns frontmatter, heading sequence, list nesting, table shape, fences/admonitions, images, MDX/import blocks, and block order. It does not judge translated meaning.

**Complete when:** deterministic structure validation exits zero.

### 5. Review semantics once

Dispatch one semantic reviewer using [`semantic-reviewer-prompt.md`](./semantic-reviewer-prompt.md). It checks completeness, mechanics fidelity, unsupported additions, glossary use, and natural zh-TW. It does not repeat the deterministic Markdown audit.

- pass: continue to writeback;
- fail: use [`targeted-refiner-prompt.md`](./targeted-refiner-prompt.md) to edit only reported blocks, then rerun deterministic validation;
- dispatch a second semantic review only when a reported semantic issue still requires judgment after repair;
- if a genuine source/term ambiguity remains, pause the affected chapter and ask the user; independent chapters may continue.

**Complete when:** semantic review passes or every finding is resolved with direct source evidence.

### 6. Write back and continue

Write back first and branch on its exit code:

```bash
uv run python scripts/draft.py --skill translate writeback <TARGET_FILE>
```

Only a zero exit code permits completion:

```bash
uv run python scripts/progress_edit.py --file <TARGET_FILE> --status completed
```

If the translated frontmatter changes a navigation title or description, update the matching `chapters.json` entry. At each checkpoint:

1. regenerate navigation only when its metadata changed;
2. stage only translated chapters, progress, context, glossary/style decisions, and changed navigation metadata;
3. commit `progress: X/Y`;
4. continue with the next pending checkpoint batch without asking the user.

```bash
uv run python scripts/generate_nav.py  # only when navigation metadata changed
```

A failed writeback leaves the file `in_progress` and stops completion bookkeeping for that file.

**Complete when:** source contains the reviewed draft, progress reflects the writeback, and automatic continuation has selected the next file or exhausted scope.

### 7. Verify the completed scope

After the selected scope completes:

```bash
uv run python scripts/validate_glossary.py
uv run python scripts/term_read.py --fail-on-missing --fail-on-forbidden
```

Invoke `check-consistency`. When all chapters are completed, invoke `check-completeness` once. Resolve deterministic violations directly; ask the user only when a correction requires a real translation decision.

After `check-completeness` passes and every progress entry is `completed`, run the final website handoff:

```bash
uv run python scripts/translation_completion.py --json
```

This command regenerates the final homepage and sidebar navigation, rechecks glossary/style/terminology/context state, builds `docs/dist/`, and verifies the generated search index. Require a zero exit code before reporting the whole book or website complete. Partial scopes do not run this handoff and must report only their scoped translation result.

`final-proofread` is a separate publication-readiness workflow. Report it as the next release step instead of invoking it automatically.

**Complete when:** selected chapters are completed and terminology checks pass; for a whole-book completion, completeness, final navigation, production build, and search verification also pass and `docs/dist/` exists.

## Automatic continuation and stop conditions

Continue without interaction through scope selection, checkpoint batches, passing chapters, deterministic repairs, progress updates, navigation regeneration, and the final website handoff when all chapters complete.

Stop or ask only for:

- a term or passage with multiple defensible readings that changes meaning or tone;
- a rare character, proper name, pun, or cultural adaptation without reliable evidence;
- an unrecoverable structure/writeback/tool failure;
- a semantic issue still unresolved after one targeted repair;
- an explicit user interruption.

## Compatibility

- `/super-translate` forwards to this process during its deprecation period.
- Existing progress, glossary, style, chapter, draft-manifest, and checkpoint formats remain authoritative.
- Bilingual translation retains its separate skill.

## References

- [`context-prompt.md`](./context-prompt.md)
- [`translator-prompt.md`](./translator-prompt.md)
- [`semantic-reviewer-prompt.md`](./semantic-reviewer-prompt.md)
- [`targeted-refiner-prompt.md`](./targeted-refiner-prompt.md)
- [`translator-style.md`](./translator-style.md)
- [`codex-tier.md`](./codex-tier.md)
