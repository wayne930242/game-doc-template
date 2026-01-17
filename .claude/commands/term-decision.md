---
name: term-decision
description: 用語權衡 - 術語選擇與全文替換
arguments:
  - name: term
    description: 要處理的術語（可選）
    required: false
---

# Terminology Decision

Use `terminology-management` skill.

## Process

### 1. Identify Term

If `$ARGUMENTS` provided, focus on that term.
Otherwise, list terms needing decisions from:
- Inconsistent usage found in docs
- Missing glossary entries
- User-flagged terms

### 2. Present Options

For each term, show:
- Original English term
- Current usage(s) in documents
- Suggested translations with rationale
- How other games translate similar terms

### 3. User Decision

Ask user to choose:
1. Translation to use
2. Any context-specific variants
3. Reason for choice

### 4. Record Decision

Update `style-decisions.json`:

```json
{
  "term_category": {
    "decision": "選擇的翻譯",
    "alternatives": ["其他選項"],
    "reason": "選擇原因"
  }
}
```

Update `glossary.json` with final term.

### 5. Batch Replace

Find all occurrences across `docs/src/content/docs/`:
- Show preview of changes
- Confirm with user
- Apply replacements

### 6. Verify

Show summary of changes made.

## Example Usage

```
/term-decision
/term-decision Move
/term-decision "Basic Move"
```
