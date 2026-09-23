---
name: md-review
description: Use when a markdown draft or docs page must be checked for structural validity and documentation style compliance before writeback or publishing.
user-invocable: true
---

# Markdown Review

## Overview

Single-file Markdown structure and style gate for translated docs and drafts.

**Core principle:** Block writeback when structure, syntax, or documentation conventions are broken.

## Scope

Default targets:
- `docs/src/content/docs/**/*.md`
- `docs/src/content/docs/**/*.mdx`
- Draft files produced by `scripts/draft.py` for `translate` or `super-translate`

If source content is available, compare the draft against the source. Otherwise, review the target as a standalone docs page against project conventions.

## The Process

### Step 1: Resolve Context

1. Read the target markdown content.
2. If available, also read:
   - source content for the same page or draft
   - `.claude/rules/docs-conventions.md`（文件格式與翻譯風格規範）
   - `style-decisions.json`
   - `glossary.json` when proper-noun or term policy affects the judgment
3. Treat `style-decisions.json.translation_notes` as hard constraints.

**Verification:** Target content loaded; supporting context loaded when available.

### Step 2: Structural Checks

Check and report:

1. Frontmatter integrity:
   - balanced `---` delimiters
   - YAML is parseable
   - `title` and `description` exist and are non-empty
   - 側欄順序由 `_meta.yml` 驅動；頁面**不需要** `sidebar.order`，僅在刻意覆蓋自動排序時才應出現
2. Heading rules:
   - no body H1 when `frontmatter.title` already provides the title
   - no heading of any level that simply restates `frontmatter.title`
   - no skipped heading levels（例如 H2 → H4）
3. Block integrity:
   - source block order and block type are preserved when source is available
   - fenced code blocks are closed
   - tables keep consistent column counts
   - list markers and indentation are preserved; list items are not flattened into paragraphs
   - list items are not split by stray blank lines unless the Markdown construct truly requires a loose list
   - paragraphs that should be separated are not accidentally fused together by missing blank lines
   - admonitions, example blocks, lists, and code fences are not merged into surrounding prose by broken blank-line structure
4. Link and media syntax:
   - internal docs links use `/...`
   - anchor links use `#...`
   - images use project-relative asset paths such as `../../assets/...`
   - image alt text is present
5. Starlight and MDX syntax:
   - asides use valid `:::note[...]` / `:::tip` / `:::caution` / `:::danger`
   - component imports remain present when JSX or MDX components are used

### Step 3: Style Checks

Check and report:

1. Chinese prose uses Traditional Chinese punctuation:
   - 刪節號必須使用 `……`，不得使用 `...`
2. Simplified Chinese must not appear.
3. Every applicable rule in `style-decisions.json.translation_notes` is followed.
4. No invented overview heading or title-repeat heading appears.
5. If source is available, preserve non-translatable tokens, links, code, dice notation, and image links exactly.
6. If source is available, do not drop, duplicate, or reorder Markdown blocks in ways that change rendering or document structure.
7. Examples, asides, and body paragraphs must remain clearly separated blocks; do not mix them into one paragraph flow.

### Step 4: Output Contract

Return JSON only:

```json
{
  "pass": true,
  "critical": [{ "type": "...", "location": "...", "detail": "..." }],
  "important": [{ "type": "...", "location": "...", "detail": "..." }]
}
```

Pass condition: `critical` is empty.

Treat block-shape breakage as critical when it changes rendering semantics.

Only flag issues that genuinely affect rendering, navigation, project conventions, or zh-TW style compliance.

## Red Flags

| Thought | Reality |
|---------|---------|
| "The translation reviewer already looked at structure" | Translation quality and Markdown validity are separate gates. |
| "This probably renders fine" | If syntax or hierarchy is questionable, report it explicitly. |
| "Missing alt text is minor" | Project conventions require descriptive alt text. |
| "The link looks okay" | Check whether it follows project path conventions before passing it. |
| "This English punctuation is harmless" | zh-TW punctuation rules are part of style compliance. |

## When to Stop and Ask

Stop when:
- the file type or route convention is ambiguous
- a heading or block was intentionally restructured and source intent is unclear
- a style rule conflicts with an explicit user decision in `style-decisions.json`

## References

See `./reviewer-prompt.md` for the brief used when this review is delegated as a work unit.
