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

### 7. Analyze and Split index.md

After initial split, analyze the generated `index.md` to create proper chapter structure:

1. **Identify TOC Structure**
   - Find table of contents or major headings in index.md
   - Extract chapter/section titles and their order
   - Note heading hierarchy (H1, H2, H3)

2. **Propose Chapter Split**
   Present to user:
   ```
   找到以下章節結構：
   1. [章節名稱] - 約 XXX 字
   2. [章節名稱] - 約 XXX 字
   ...
   建議拆分為獨立檔案嗎？
   ```

3. **Execute Split**
   For each identified chapter:
   - Create new file with slug derived from title
   - Add frontmatter with `sidebar.order` to preserve TOC sequence
   - Move corresponding content from index.md
   - Update index.md to contain only overview/introduction

4. **Update chapters.json**
   Add new files to config for future reference.

5. **Frontmatter Template**
   ```yaml
   ---
   title: 章節標題
   description: 章節描述
   sidebar:
     order: N  # 保留原始目錄順序
   ---
   ```

### 8. Verify

- Check generated files in `docs/src/content/docs/`
- Verify sidebar order matches original TOC
- Preview: `cd docs && bun dev`

## Example Usage

```
/init-doc
/init-doc data/pdfs/rulebook.pdf
```
