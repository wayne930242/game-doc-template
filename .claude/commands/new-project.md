---
name: new-project
description: 建立新專案 - 從模板建立本地專案並建立 GitHub 私人 repo
arguments:
  - name: pdf_path
    description: PDF 檔案路徑
    required: true
  - name: project_name
    description: 專案名稱（用於資料夾與 repo 名稱）
    required: false
---

# Create New Project from Template

從 game-doc-template 模板建立新的遊戲文件專案，並自動建立 GitHub 私人 repo。

## Prerequisites

- `gh` CLI 已安裝且已登入
- `git` 已設定
- PDF 檔案已準備好

## Process

### 1. Gather Information

使用 AskUserQuestion 工具一次詢問以下問題：

**問題 1: 專案路徑**
- header: "專案路徑"
- question: "要將專案建立在哪個路徑？"
- options:
  - `../` (預設，與模板同層)
  - 自訂路徑

**問題 2: 遊戲標題**
- header: "遊戲標題"
- question: "這個遊戲的繁體中文標題是什麼？"
- 從 PDF 檔名提取原文名稱作為參考
- 讓使用者輸入繁中翻譯

**問題 3: 專案名稱**（若 `$ARGUMENTS` 未提供）
- header: "專案名稱"
- question: "專案資料夾與 repo 名稱？"
- 根據 PDF 檔名建議 slug 格式（lowercase, hyphenated）

Example:
```
PDF: "Blades in the Dark.pdf"
原文標題: Blades in the Dark
繁中標題: 暗夜冷鋒 (由使用者輸入)
建議專案名稱: blades-in-the-dark
```

### 2. Determine Paths

```bash
# Template repo (current project)
TEMPLATE_REPO="weihung/game-doc-template"

# Target directory (user specified, default: ../)
TARGET_DIR="<user_specified_path>/<project_name>"

# PDF path (from arguments)
PDF_PATH="$ARGUMENTS[0]"

# Game title (user specified)
GAME_TITLE_EN="<extracted_from_pdf>"
GAME_TITLE_ZH="<user_specified>"
```

### 3. Clone Template

```bash
# Navigate to target parent directory
cd <user_specified_path>

# Clone from GitHub template
gh repo create <project_name> --template $TEMPLATE_REPO --private --clone

# Or if template is local:
# cp -r <template_path> <TARGET_DIR>
# cd <TARGET_DIR>
# rm -rf .git
# git init
```

### 4. Create GitHub Repository

```bash
cd <TARGET_DIR>

# Create private repo
gh repo create <project_name> --private --source=. --remote=origin

# Push initial commit
git add .
git commit -m "Initial commit from game-doc-template"
git push -u origin main
```

### 5. Copy PDF

```bash
# Create data directory if not exists
mkdir -p data/pdfs

# Copy PDF to new project
cp "<pdf_path>" data/pdfs/
```

### 6. Update Project Configuration

Edit `docs/astro.config.mjs`:
- Update `SITE_CONFIG.title` with `GAME_TITLE_ZH` (繁中標題)

Edit `CLAUDE.md`:
- Update project description with game name (原文 + 繁中)
- Example: `# blades-in-the-dark\n\nBlades in the Dark（暗夜冷鋒）PDF 遊戲規則翻譯專案。`

### 7. Verify Setup

```bash
# Check structure
ls -la
ls -la data/pdfs/
ls -la docs/

# Verify git remote
git remote -v
```

### 8. Next Steps

Inform user:
```
✓ 專案已建立: <project_name>
✓ 遊戲標題: <GAME_TITLE_EN>（<GAME_TITLE_ZH>）
✓ 專案路徑: <TARGET_DIR>
✓ GitHub repo: https://github.com/<username>/<project_name>
✓ PDF 已複製到: data/pdfs/<filename>

下一步：
1. cd <TARGET_DIR>
2. 執行 /init-doc 開始初始化文件
```

## Example Usage

```
/new-project ~/Downloads/Blades-in-the-Dark.pdf
/new-project ~/Downloads/game.pdf my-game-docs
```

## Error Handling

- If `gh` not installed: Provide installation instructions
- If not logged in: Run `gh auth login`
- If repo name taken: Suggest alternative name
- If PDF not found: Ask for correct path
