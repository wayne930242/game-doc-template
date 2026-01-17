---
name: init-doc
description: 初次摘要 - 初始化文件翻譯專案，建立術語表與章節結構
arguments:
  - name: pdf_path
    description: PDF 檔案路徑（可選，會互動詢問）
    required: false
---

# Initialize Document Translation

Use `pdf-translation` and `terminology-management` skills.

## Process

### 1. Locate PDF

If no `$ARGUMENTS` provided, ask user for PDF location in `data/pdfs/`.

### 2. Extract Content

```bash
cd scripts
uv run python extract_pdf.py <pdf_path>
```

Review output in `data/markdown/`:
- `<name>.md` - clean version
- `<name>_pages.md` - with page markers

### 3. Identify Key Terms

Scan extracted content for:
- Capitalized game terms (Move, Playbook, Harm)
- Quoted terms
- Repeated specialized vocabulary

Present terms to user for translation confirmation.

### 4. Build Glossary

Create `glossary.json` with confirmed terms:

```json
{
  "Term": {
    "zh": "翻譯",
    "notes": "使用情境"
  }
}
```

Ask user about style preferences and record in `style-decisions.json`.

### 5. Configure Chapters

Help user set up `chapters.json`:
1. Show table of contents from PDF
2. Suggest chapter structure based on content
3. Map page ranges to output files

### 6. Split Content

```bash
uv run python split_chapters.py
```

### 7. Verify

- Check generated files in `docs/src/content/docs/`
- Preview: `cd docs && bun dev`

## Example Usage

```
/init-doc
/init-doc data/pdfs/rulebook.pdf
```
