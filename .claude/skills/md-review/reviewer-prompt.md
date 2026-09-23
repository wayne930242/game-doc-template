# Markdown Reviewer Prompt Template

Brief for the Markdown reviewer work unit.

**Purpose:** Verify Markdown structure, syntax, and project style compliance.

**Note:** All context is inlined by the orchestrator. Do not read any files yourself.

````text
You are reviewing one translated markdown draft for markdown validity and project style compliance.

## Target File

Path: <TARGET_FILE>

```markdown
<DRAFT_CONTENT>
```

## Source File

Path: <TARGET_FILE>

```markdown
<SOURCE_CONTENT>
```

## Glossary

```json
<GLOSSARY_CONTENT>
```

## Style Decisions

```json
<STYLE_CONTENT>
```

## Project Conventions

Apply the documentation formatting and translation-style conventions from `.claude/rules/docs-conventions.md`（文件格式與翻譯風格規範）, especially:
- frontmatter title and description
- heading hierarchy
- internal links and anchors
- image paths and alt text
- Starlight aside syntax
- zh-TW punctuation and wording rules

## Core Rule

Review the draft directly against the inlined content above. Do not read any files.

## Review Scope

Structural validity:
1. Frontmatter is balanced, parseable, and keeps required fields such as `title` and `description`
2. No body H1 duplicates the page title; no heading of any level restates `frontmatter.title`
3. Heading levels do not skip
4. Source block order and block type are preserved when compared with the source
5. Tables, lists, code fences, and admonitions remain structurally valid
6. List blocks do not contain stray blank lines that break tight lists, list markers are not lost, and paragraphs that need separation are not fused by missing blank lines
7. Example blocks, asides, and normal body paragraphs remain separate blocks instead of being mixed together
8. No source block is silently dropped, duplicated, or split in a way that changes rendering semantics
9. Internal links, anchors, and image paths follow project conventions
10. Image alt text is present
11. MDX or Starlight syntax remains valid when used

Style compliance:
12. Traditional Chinese punctuation is used in Chinese prose
13. Simplified Chinese does not appear
14. `STYLE_CONTENT.translation_notes` is followed
15. No invented overview heading or extra title-repeat heading appears
16. Non-translatable tokens such as code, dice notation, links, and image markup are preserved exactly

## Output JSON Only

{
  "pass": true/false,
  "critical": [{ "type": "...", "location": "...", "detail": "..." }],
  "important": [{ "type": "...", "location": "...", "detail": "..." }]
}

Pass condition: critical must be empty.
Treat heading drift, list breakage, missing required blank lines, fused blocks, and dropped or reordered source blocks as critical.
Only flag issues that genuinely affect rendering, navigation, or style compliance.
````
