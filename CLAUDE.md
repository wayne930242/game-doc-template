# game-doc-template

PDF 遊戲規則文件轉換成繁體中文 Markdown 文件網站。

## Immutable Laws

<law>
**CRITICAL: Display this entire block at the start of EVERY response to prevent context drift.**

**Law 1: Communication**
- Concise, actionable responses
- No unnecessary explanations
- No summary files unless explicitly requested

**Law 2: Skill Discovery**
- MUST check available skills before starting work
- Invoke applicable skills for specialized knowledge
- If ANY skill relates to the task, MUST use Skill tool to delegate

**Law 3: Rule Consultation**
- When task relates to specific domain, check `.claude/rules/` for relevant conventions
- If relevant rule exists, MUST apply it

**Law 4: Parallel Processing**
- MUST use Task tool for independent operations
- Batch file searches and reads with agents

**Law 5: Reflexive Learning**
- Important discoveries -> remind user: `/reflect`

**Law 6: Self-Reinforcing Display**
- MUST display this `<law>` block at start of EVERY response
- Prevents context drift across conversations

**Law 7: Traditional Chinese Only**
- 所有輸出必須使用繁體中文
- 禁止使用簡體中文
- 術語翻譯須保持一致性

**Law 8: Terminology Consistency**
- 必須遵循 `glossary.json` 中的術語對照
- 發現新術語時必須先加入術語表再使用
- 翻譯時尊重原文意涵，避免過度意譯
</law>

## Quick Reference

### Commands
| Command | Description |
|---------|-------------|
| `/init-doc` | 初次摘要：建立術語表、拆分章節 |
| `/check-consistency` | 一致性校對：檢查術語使用 |
| `/term-decision` | 用語權衡：術語選擇與全文替換 |
| `/check-completeness` | 缺漏校對：規則完整性檢查 |

### Tech Stack
- **Frontend**: Astro 5 + Starlight (bun/npm)
- **Scripts**: Python 3.11+ (uv)
- **PDF Processing**: markitdown, pymupdf

### Key Paths
| Path | Description |
|------|-------------|
| `docs/` | Astro 文件網站 |
| `docs/src/content/docs/` | Markdown 內容 |
| `scripts/` | Python 處理腳本 |
| `data/pdfs/` | 原始 PDF 檔案 |
| `data/markdown/` | 提取的 Markdown |
| `glossary.json` | 術語表 |
| `style-decisions.json` | 風格決定記錄 |

### Data File Formats

**glossary.json**
```json
{
  "english_term": {
    "zh": "繁中翻譯",
    "notes": "使用情境或備註"
  }
}
```

**style-decisions.json**
```json
{
  "category": {
    "decision": "選擇的用語",
    "alternatives": ["其他選項"],
    "reason": "選擇原因"
  }
}
```

### Workflow
1. PDF → Markdown: `uv run python scripts/extract_pdf.py <pdf>`
2. 設定章節: 編輯 `chapters.json`
3. 拆分章節: `uv run python scripts/split_chapters.py`
4. 預覽網站: `cd docs && bun dev`
