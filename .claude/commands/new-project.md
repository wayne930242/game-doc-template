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

If `$ARGUMENTS` does not include project_name:
- Extract game name from PDF filename or ask user
- Suggest slug format (lowercase, hyphenated)

Example:
```
PDF: "Blades in the Dark.pdf"
建議專案名稱: blades-in-the-dark
```

### 2. Determine Paths

```bash
# Template repo (current project)
TEMPLATE_REPO="weihung/game-doc-template"

# Target directory (sibling to template)
TARGET_DIR="../<project_name>"

# PDF path (from arguments)
PDF_PATH="$ARGUMENTS[0]"
```

### 3. Clone Template

```bash
# Clone from GitHub template
gh repo create <project_name> --template $TEMPLATE_REPO --private --clone

# Or if template is local:
# cp -r . ../<project_name>
# cd ../<project_name>
# rm -rf .git
# git init
```

### 4. Create GitHub Repository

```bash
cd ../<project_name>

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
- Update `SITE_CONFIG.title` with game name

Edit `CLAUDE.md`:
- Update project description if needed

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
✓ GitHub repo: https://github.com/<username>/<project_name>
✓ PDF 已複製到: data/pdfs/<filename>

下一步：
1. cd ../<project_name>
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
