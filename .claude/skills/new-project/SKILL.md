---
name: new-project
description: Use when creating a new translation project from template and preparing repository metadata.
user-invocable: true
---

# Create New Project from Template

## Overview

Create a new game documentation project from template, configure repository metadata, and prepare source PDF for initialization.

**Core principle:** Ask once, create deterministic project state, verify immediately, then hand off.

## Task Initialization (MANDATORY)

Before ANY action, create tasks using TaskCreate:
- One task per major step (preconditions, user inputs, repo creation, PDF + config, verification)

## The Process

### Step 1: Validate Preconditions

Confirm:
- `gh` is installed and authenticated
- `git` is configured
- source PDF path exists

If any check fails, stop and report exact remediation.

**Verification:** `gh auth status` exits 0; `git config user.name` non-empty; PDF exists.

### Step 2: Ask User Inputs in Traditional Chinese

Collect via AskUserQuestion:

1. Project path
- header: `專案路徑`
- question: `請問新專案要建立在哪個路徑？`

2. Game zh-TW title
- header: `遊戲名稱`
- question: `請問這款遊戲的繁體中文名稱是什麼？`

3. Project slug (if missing from arguments)
- header: `專案代號`
- question: `請問資料夾與 GitHub repo 要使用哪個名稱？`

4. Repository visibility
- header: `儲存庫類型`
- question: `GitHub 儲存庫要設為公開還是私有？`

**Verification:** All four inputs collected and confirmed by user.

### Step 3: Resolve Variables

```bash
TEMPLATE_ROOT="<current_workspace_root>"
CLONE_SCRIPT="$TEMPLATE_ROOT/gh-clone.sh"
TARGET_DIR="<user_path>/<project_name>"
PDF_PATH="<pdf_path>"
GAME_TITLE_EN="<derived_from_pdf_filename>"
GAME_TITLE_ZH="<user_input>"
REPO_VISIBILITY="<private_or_public>"
REPO_URL="https://github.com/<username>/<project_name>"
```

**Verification:** All variables resolved to concrete values; no placeholders remain.

### Step 4: Create Repository

Preferred path:

```bash
cd <user_path>
if [ "$REPO_VISIBILITY" = "public" ]; then
  "$CLONE_SCRIPT" <project_name> --public
else
  "$CLONE_SCRIPT" <project_name>
fi
```

Fallback local-copy path:

```bash
cp -r "$TEMPLATE_ROOT" <TARGET_DIR>
cd <TARGET_DIR>
rm -rf .git
git init
gh repo create <project_name> --$REPO_VISIBILITY --source=. --remote=origin
git add .
git commit -m "Initial commit from game-doc-template"
git push -u origin main
```

**Verification:** `git remote -v` shows origin; `gh repo view` accessible.

### 清理模板範例資料（必要，不可跳過）

複製完成後立即在新專案目錄執行：

```bash
uv run python scripts/clean_sample_data.py --yes
```

此步驟會重置 `glossary.json`、`chapters.json`、`style-decisions.json`、`docs/astro.config.mjs`（標題與側欄）、刪除 `data/translation-progress*.json` 與 `plans/`，並寫入佔位首頁，確保新專案不含模板殘留。

### Step 5: Copy PDF and Apply Configuration

Copy PDF:

```bash
mkdir -p data/pdfs
cp "<pdf_path>" data/pdfs/
```

Update:
- (if public) GitHub social link in `docs/astro.config.mjs`; the site title comes from `site.title`, which `generate_nav.py` writes into `SITE_CONFIG.title`
- initialize and update `style-decisions.json` via scripts
- `CLAUDE.md` project description

Use:

```bash
uv run python scripts/style_decisions.py init
uv run python scripts/style_decisions.py set-repository \
  --slug "<project_name>" \
  --visibility "<private_or_public>" \
  --url "<REPO_URL>" \
  --show-on-homepage <true_or_false>
uv run python scripts/style_decisions.py set-site --title "$GAME_TITLE_ZH" --original-title "$GAME_TITLE_EN"
uv run python scripts/style_decisions.py set-deployment \
  --target blog \
  --base-path "/books/<project_name>"
uv run python scripts/validate_style_decisions.py
```

For the blog export, give the repo the secret that lets `Book Export` redeploy the blog. The token lives in the macOS Keychain as `blog-dispatch-token`; pipe it straight into GitHub without printing it:

```bash
security find-generic-password -s blog-dispatch-token -w | gh secret set BLOG_DISPATCH_TOKEN --repo "<username>/<project_name>"
```

If the Keychain has no entry, stop and ask the user to regenerate the `blog-dispatch` fine-grained token (Contents read/write on `wayne930242/knowledge-base` only) and store it with `security add-generic-password -U -a <username> -s blog-dispatch-token -w "$(pbpaste)"`.

Every project defaults to the blog export: the book is served at `/books/<project_name>/` inside the blog, so `generate_nav.py` writes that `base` and `fix-ref` prefixes internal links with it (see README.md「匯出到 blog（預設）」). Record `--target github-pages --base-path "/<project_name>"` or `--target root` instead only when the user asks for a standalone deployment.

**Verification:** PDF exists in `data/pdfs/`; config files updated; `style-decisions.json.deployment` is `{"target": "blog", "base_path": "/books/<project_name>"}` unless the user chose a standalone deployment; `site.original_title` is set; for the blog export, `gh secret list --repo <username>/<project_name>` shows `BLOG_DISPATCH_TOKEN`.

### Step 6: Verify and Report

Verify:

```bash
ls -la
ls -la data/pdfs/
ls -la docs/
git remote -v
```

Report in Traditional Chinese:

```text
✓ 專案已建立：<project_name>
✓ 遊戲名稱：<GAME_TITLE_EN>（<GAME_TITLE_ZH>）
✓ 專案路徑：<TARGET_DIR>
✓ Repo 類型：<REPO_VISIBILITY>
✓ GitHub repo：https://github.com/<username>/<project_name>
✓ PDF 已複製到：data/pdfs/<filename>

下一步：
1. cd <TARGET_DIR>
2. 執行 /init-doc
```

If `REPO_VISIBILITY` is `public`, append a deployment note to the report pointing at README.md's "GitHub Pages（Public 專案推薦）" section — public projects should default to GitHub Pages over Vercel (no extra service, deploys straight from the repo).

**Verification:** All prior verifications pass; report displayed to user.

## Flowchart

```dot
digraph new_project {
    rankdir=TB;
    preconditions [label="Step 1:\nValidate\npreconditions", shape=box];
    inputs [label="Step 2:\nCollect user\ninputs", shape=box];
    variables [label="Step 3:\nResolve\nvariables", shape=box];
    repo [label="Step 4:\nCreate\nrepository", shape=box];
    pdf_config [label="Step 5:\nCopy PDF &\napply config", shape=box];
    verify [label="Step 6:\nVerify &\nreport", shape=box];

    preconditions -> inputs;
    inputs -> variables;
    variables -> repo;
    repo -> pdf_config;
    pdf_config -> verify;
}
```

## Progress Sync Contract (Required)

1. Update tasks via TaskCreate/TaskUpdate after each major step.
2. Mark blockers immediately with reason.
3. Do not claim completion with open critical items.

## When to Stop and Ask for Help

Stop when:
- repo name is unavailable and no approved fallback exists
- auth or permission errors block creation
- source PDF path remains invalid

## When to Revisit Earlier Steps

Return to input/variable steps when:
- user changes path/name/visibility
- source PDF changes

## Red Flags

| Thought | Reality |
|---------|---------|
| "Create repo without confirming user decisions" | All required inputs must be collected and confirmed first. |
| "Expose private repo URL in public homepage links" | Private repo URLs must never appear in public-facing config. |
| "Skip verification before reporting success" | Every step has a verification gate. Never skip. |

## Next Step

Continue with `/init-doc`.

## Example Usage

```text
/new-project ~/Downloads/Blades-in-the-Dark.pdf
/new-project ~/Downloads/game.pdf my-game-docs
```
