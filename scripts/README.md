# 內容處理腳本

本資料夾包含 PDF 提取與章節拆分工具。

## 安裝

使用 [uv](https://github.com/astral-sh/uv)（推薦）：

```bash
cd scripts
uv sync
```

或使用 pip：

```bash
pip install markitdown pymupdf
```

## 工作流程

### 1. 提取 PDF 內容

```bash
# 將 PDF 放入 data/pdfs/ 目錄
mkdir -p ../data/pdfs
cp your-rulebook.pdf ../data/pdfs/

# 執行提取
uv run python extract_pdf.py ../data/pdfs/your-rulebook.pdf
```

輸出：
- `data/markdown/your-rulebook.md` — 純文字版本
- `data/markdown/your-rulebook_pages.md` — 含頁碼標記（用於章節拆分）
- `data/markdown/images/your-rulebook/` — 提取的圖片

### 2. 設定章節結構

```bash
# 產生範例設定檔
uv run python split_chapters.py --init
```

編輯 `chapters.json`，設定章節結構與頁碼範圍：

```json
{
    "source": "data/markdown/your-rulebook_pages.md",
    "output_dir": "docs/src/content/docs",
    "chapters": {
        "rules": {
            "title": "核心規則",
            "files": {
                "index": {
                    "title": "規則總覽",
                    "description": "遊戲規則概述",
                    "pages": [1, 20]
                }
            }
        }
    }
}
```

### 3. 拆分章節

```bash
uv run python split_chapters.py
```

這會根據 `chapters.json` 的設定，將內容拆分到 `docs/src/content/docs/` 目錄。

## 設定檔說明

### chapters.json

| 欄位 | 說明 |
|------|------|
| `source` | 來源 Markdown 檔案（使用 `_pages.md` 版本） |
| `output_dir` | 輸出目錄 |
| `clean_patterns` | 要移除的正規表達式陣列 |
| `chapters` | 章節定義 |

### 章節定義

```json
{
    "section-slug": {
        "title": "章節標題",
        "order": 1,
        "files": {
            "filename": {
                "title": "頁面標題",
                "description": "SEO 描述",
                "pages": [起始頁, 結束頁],
                "order": 0
            }
        }
    }
}
```

## 提示

1. **先預覽 PDF 頁碼**：在設定 `chapters.json` 前，先打開 PDF 確認各章節的頁碼範圍

2. **清理模式**：使用 `clean_patterns` 移除不需要的內容（如頁首、頁尾、浮水印）

3. **手動調整**：自動提取的內容可能需要手動修正格式
