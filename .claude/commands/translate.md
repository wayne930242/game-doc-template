---
name: translate
description: 開始翻譯 - 翻譯指定章節或檔案
arguments:
  - name: target
    description: 翻譯目標（檔案路徑/章節名稱/all）
    required: false
---

# Translate Document

Use `pdf-translation` and `terminology-management` skills.

## Prerequisites

- `glossary.json` exists with key terms
- Files exist in `docs/src/content/docs/`
- Run `/init-doc` first if not done

## Process

### 0. Select Translation Mode

Read `style-decisions.json` and check `translation_mode.mode`:

**If mode is null (not set):**
- Use AskUserQuestion tool to ask user:
  - **全文翻譯**: 完整翻譯所有內容，保留原文結構與細節
  - **摘要翻譯**: 精簡翻譯，提取重點規則，省略範例與冗長說明
- Update `style-decisions.json` with user's choice:
  - Set `translation_mode.mode` to `"full"` or `"summary"`
  - Set `translation_mode.reason` to user's reason (if provided)

**If mode is already set:**
- Show current mode setting
- Ask if user wants to change (optional)

### 1. Select Target

If no `$ARGUMENTS`:
- List available files in `docs/src/content/docs/`
- Ask user which to translate

Scope options:
- Single file: `docs/src/content/docs/rules/basic.md`
- Section: `rules` (all files in section)
- All: `all`

### 2. Load Resources

Read:
- `glossary.json` - term mappings
- `style-decisions.json` - style choices

### 3. Translate Content

For each target file:

1. **Read source** - Load current content
2. **Identify segments** - Paragraphs, lists, tables
3. **Apply glossary** - Use consistent terminology
4. **Translate** - Convert to natural 繁體中文
5. **Preserve structure** - Keep frontmatter, markdown syntax

### Translation Rules

| Element | Handling |
|---------|----------|
| Frontmatter | Translate `title`, `description`; keep `sidebar` structure |
| Headings | Translate, maintain hierarchy |
| Lists | Preserve formatting, translate content |
| Tables | Keep structure, translate cells |
| Code blocks | Keep unchanged |
| Bold/Italic | Preserve markers |
| Links | Translate text, keep URLs |
| Game terms | Apply glossary strictly |

### Mode-Specific Rules

**全文翻譯模式 (full):**
- 翻譯所有段落，包含範例與說明
- 保留原文結構不做刪減
- 適合需要完整參考的規則書

**摘要翻譯模式 (summary):**
- 提取核心規則與機制
- 省略冗長範例，改用精簡說明
- 合併重複概念
- 使用條列式整理重點
- 適合快速查閱的規則摘要

### 4. New Terms

When encountering unknown terms:

1. Pause and report to user
2. Ask for translation
3. Add to `glossary.json`
4. Continue with new term

### 5. Write Output

Replace source file with translated version.

### 6. Progress Tracking

After each file:
- Report: `✓ translated: <path>`
- Show next file or completion

## Example Usage

```
/translate
/translate docs/src/content/docs/rules/basic.md
/translate rules
/translate all
```

## Output

Translated files in place, ready for `/check-consistency`.
