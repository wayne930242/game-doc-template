---
name: terminology-management
description: Use when creating, editing, validating, or enforcing glossary-driven terminology.
---

# Terminology Management

## Overview

Maintain glossary quality and enforce terminology consistency across all translated content.

**Core principle:** Glossary is the source of truth; validation must run before and after any terminology update.

## The Process

### Step 1: Load Glossary Baseline

1. Load `glossary.json`.
2. Confirm schema validity:

```bash
uv run python scripts/validate_glossary.py
```

3. Authoritative state is `glossary.json` itself, checked by `validate_glossary.py` and `term_read.py`. If a task-tracking tool is available in this session, create items for candidate generation, decisions, and verification.

### Step 2: Generate and Classify Candidates

Before running candidate generation, inspect the extracted source markdown for high-signal terminology sources:
- glossary / terminology sections
- index pages
- appendix reference lists
- summary tables that define recurring mechanics terms

Use those sections to complete a first-pass glossary bootstrap:
- approve obvious terms first
- collect ambiguous terms for user discussion

Run:

```bash
uv run python scripts/term_generate.py --min-frequency 2
```

Then **immediately** pre-calculate evidence for all candidates in one pass:

```bash
uv run python scripts/term_cal_batch.py
```

This scans the corpus once and caches counts + context for every candidate.
Subsequent `term_edit.py` calls hit the cache; no re-scanning needed.

Classify each candidate as:
- managed game term
- normal prose (not managed)

If `proper_nouns.mode != keep_original`, repeated proper nouns (`>=2`) must be managed.

### Step 3: Edit Glossary Safely

For unmanaged terms, evidence is read from cache (populated by `term_cal_batch.py`):

```bash
uv run python scripts/term_edit.py --term "<TERM>" --set-zh "<ZH_TERM>" --status approved --mark-term
```

When `translation.term_gloss` in `style-decisions.json` names a language other than the source text's, record a term's original-language form for its gloss once it is known from the original work or an approved source:

```bash
uv run python scripts/term_edit.py --term "<TERM>" --set-original-term "<ORIGINAL_TERM>"
```

To inspect evidence for a single term without editing:

```bash
uv run python scripts/term_edit.py --term "<TERM>" --cal
```

If the corpus changed since the last batch run, re-run `term_cal_batch.py` to refresh the cache.

### Step 4: Validate Usage Across Docs

Run:

```bash
uv run python scripts/term_read.py --fail-on-forbidden
```

Check for:
- missing managed terms
- inconsistent variants
- unintended untranslated residual English terms

### Step 5: Apply Fixes and Recheck

1. Apply approved replacements where needed.
2. Re-run `term_read.py` until clean.

## Progress Sync Contract (Required)

1. Each term candidate's authoritative state is its entry in `glossary.json`; if using task tracking, track each candidate and decision with it too.
2. Mark a term (and its item, if using task tracking) complete only after `term_read.py` is clean for that change.

## When to Stop and Ask for Help

Stop when:
- glossary policy conflicts are unresolved
- a term has culturally nuanced ambiguity affecting tone/mechanics
- bulk changes risk unintended semantic shifts

## When to Revisit Earlier Steps

Return to Step 2 when:
- corpus changes significantly
- proper noun policy changes

## Red Flags

Never:
- bypass glossary schema validation
- leave inconsistent managed terms unresolved

## Next Step

Continue with `/check-consistency`, `/translate`, or `/super-translate`.
