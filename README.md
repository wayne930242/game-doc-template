# 遊戲文件模板 (Game Documentation Template)

基於 Astro + Starlight 的遊戲規則文件模板，專為 TRPG 設計，也適用於任何遊戲規則文件。

本模板內建作者本人的翻譯風格（見 `.claude/skills/translate/translator-style.md`），`translate`／`bilingual-translate` 預設都會套用這份風格；由此模板複製出的新專案會自動繼承，不需每個專案重新設定。

## 快速開始

### 1. 建立專案

```bash
./gh-clone.sh my-game-docs           # 建立 private repo
./gh-clone.sh my-game-docs --public  # 建立 public repo
cd my-game-docs
```

或使用 GitHub 網頁的「Use this template」按鈕。

### 2. 安裝依賴

```bash
# 前端（文件網站）
cd docs
bun install  # 或 npm install

# 回到專案根目錄
cd ..

# Python/uv 工具鏈（PDF 處理）
# 注意：已改為在「專案根目錄」初始化，不在 scripts/ 子目錄
uv sync  # 或 pip install markitdown pymupdf

# 術語 POS/lemma（spaCy 模型）
uv run python -m ensurepip --upgrade
uv run python -m spacy download en_core_web_sm
```

### 3. 啟動開發伺服器

```bash
cd docs
bun dev
```

開啟 http://localhost:4321 預覽網站。

---

## 自訂設定

### 網站標題與基本設定

編輯 `docs/astro.config.mjs` 頂部的 `SITE_CONFIG`：

```javascript
const SITE_CONFIG = {
  title: "您的遊戲名稱",
  defaultLocale: "zh-TW",
  localeLabel: "繁體中文",
  allowIndexing: false, // SEO 設定
};
```

### 圖片資源

| 檔案       | 位置                       | 說明                        |
| ---------- | -------------------------- | --------------------------- |
| 背景圖     | `docs/public/bg.jpg`       | 1920x1080，深色低對比度為佳 |
| 社群分享圖 | `docs/public/og-image.jpg` | 1200x630                    |
| 首頁主圖   | `docs/src/assets/hero.jpg` | 560x560，會裁切成圓形       |
| 網站圖示   | `docs/public/favicon.svg`  | 32x32                       |

### 背景圖設定

預設使用純色背景。如需背景圖片：

1. 將圖片放入 `docs/public/bg.jpg`
2. 編輯 `docs/src/styles/custom.css`，取消 `body` 區塊中背景圖片的註解

若要調整半透明遮罩透明度，修改同檔案中的 `.main-pane` 區塊。

### 主題配色

編輯 `docs/src/styles/custom.css` 的 `:root` 區塊修改顏色變數。

預設色票風格（只需修改 H 值）：

- **冷色系**：藍青紫，適合科幻、海洋、神秘
- **暖色系**：橘金紅，適合冒險、戰鬥、熱情
- **自然系**：綠黃棕，適合奇幻、森林、治癒
- **暗黑系**：紫洋紅紅，適合恐怖、哥德、邪惡
- **史詩系**：金銅紅，適合中世紀、王國、榮耀

### 側邊欄結構

編輯 `docs/astro.config.mjs` 的 `sidebar` 區塊調整目錄結構。

---

## 使用 AI 輔助翻譯（支援 Claude Code、Codex CLI、Gemini CLI）

本專案已內建：

- `AGENTS.md -> CLAUDE.md`
- `.codex/skills -> .claude/skills`
- `.gemini/settings.json`（`context.fileName = "CLAUDE.md"`）
- `.gemini/skills -> .claude/skills`
- `.gemini/commands/*.toml`（將 slash 指令映射到既有 skills）

Windows 使用者需啟用 `git config core.symlinks true` 並以系統管理員或開發者模式 clone，`.codex/`、`.gemini/skills` 的 symlink 才會實體化。

### 使用原則

- 建議流程：`new-project` → `init-doc`。`init-doc` 通過初始化守門檢查後，會依翻譯模式自動進入 `translate all` 或 `bilingual-translate all`；若來源更新或要重切章，插入 `chapter-split`。完整步驟見下方[本專案工作流程](#本專案工作流程簡版)。
- `translate` 先讀全文並保存全書／各章摘要，再以每波最多 3 章的獨立草稿工作單元並行翻譯。每章以程式檢查 Markdown 結構，並進行一次語義審查；只有失敗時才定向修訂與必要複審。全書完成後會重建最終導覽、建置網站並驗證搜尋索引。
- `translate`、`bilingual-translate` 都會在每個 batch 完成後自動建立一個簡短進度 commit（格式：`progress: X/Y`）。舊的 `super-translate` 指令暫時保留，但會轉交新的 `translate` 流程。
- 翻譯前先確認術語（`glossary.json`），交付前執行一致性與完整性檢查

### 派工（Straw Boss）

草稿、審查與章節規劃等可委派的工作單元，由主協調者透過 [Straw Boss](https://github.com/wayne930242/straw-boss) 的 `boss-say` 派工，並由主協調者決定每個 worker 的 provider、模型與 effort。skills 只定義 brief、凍結輸入、獨佔寫入路徑與整合步驟，不指定模型。

### 常用指令對照

| 功能                             | 指令                         |
| -------------------------------- | ---------------------------- |
| 建立新專案                       | `new-project <pdf-path>`     |
| 初始化翻譯專案                   | `init-doc`                   |
| 重新切章與重建導覽               | `chapter-split [source]`     |
| 翻譯章節或整本規則書             | `translate [target]`         |
| 舊版翻譯相容入口（逐步淘汰）     | `super-translate [target]`   |
| Markdown 結構與風格檢查          | `md-review [target]`         |
| 單輪雙語翻譯（中文正文＋英文引用） | `bilingual-translate [target]` |
| 術語一致性檢查                   | `check-consistency`          |
| 術語決策與批次替換               | `term-decision`              |
| 術語表建立／驗證／強制執行       | `terminology-management`     |
| 內容完整性檢查                   | `check-completeness`         |
| 修正頁碼參照為內部連結           | `fix-ref`                    |
| 出版前最終校對                   | `final-proofread`            |

---

## 本專案工作流程（簡版）

1. 準備來源檔  
   把規則 PDF 放到 `data/pdfs/`。

2. 初始化專案（建議）  
   執行 `init-doc` 建立初始內容。初始化守門檢查通過後會依 `translation_mode.mode` 自動開始完整翻譯，不必再手動執行下一條指令。若之後來源更新或章節結構要重切，改用 `chapter-split` 重建 `chapters.json` 與導覽。

3. 提取 PDF 與章節裁切（Python）  
   預設引擎為 `opendataloader-pdf`（自動偵測；需 Java 11 以上，無 Java 時自動退回 `pymupdf`／`markitdown`）。
   1. `uv run python scripts/extract_pdf.py data/pdfs/your-rulebook.pdf`
   2. 若是掃描 PDF，可改用 `uv run python scripts/extract_pdf.py data/pdfs/your-rulebook.pdf --page-text-engine ocr`
   3. 日文掃描來源建議加 `--ocr-lang jpn+eng`；英文掃描來源建議加 `--ocr-lang eng`
   4. 若來源是一整個 `jpg/png` 頁面資料夾，也可直接執行 `uv run python scripts/extract_pdf.py data/scans/your-rulebook-pages`
   5. `uv run python scripts/split_chapters.py --init`
   6. 編輯 `chapters.json`（設定章節與頁碼範圍；長章節優先用來源子標題或巢狀路徑切分，避免 `1`、`2`、`3` 這類無語意命名）
   7. `uv run python scripts/split_chapters.py`  
      產出檔案到 `docs/src/content/docs/`。

4. 術語預處理
   原則：`glossary.json` 是唯一術語來源，先定義再翻譯，避免同詞多譯。  
   建議指令：
   1. `uv run python scripts/term_generate.py --min-frequency 2`（找高頻候選詞）
   2. `uv run python scripts/term_edit.py --term "<TERM>" --set-zh "<ZH>" --status approved --mark-term`（核准術語，未管理詞彙會自動執行 `--cal`）

5. 執行翻譯（套用術語表）
   翻譯時以 `glossary.json` 優先，並保留 Markdown 結構。原理：翻譯不是逐句自由發揮，而是「內容翻譯 + 術語套版」。
   - `translate`：首次執行會建立可重用的全文與各章摘要，之後以每波最多 3 個隔離草稿並行翻譯。各章先做程式化結構檢查，再進行一次語義審查；最後依章序寫回、更新進度並自動繼續。所有章節完成且通過一致性與完整性檢查後，自動重建導覽並產生已驗證搜尋功能的 `docs/dist/` 網站。
   - `super-translate`：舊版相容入口，會把相同範圍轉交 `translate`，不再執行獨立的多 agent 審查循環。

6. 修正頁碼參照  
   翻譯完成後執行 `fix-ref`，把「見 12 頁」之類的列印頁碼參照轉換成內部 Markdown 連結。

7. 術語校驗與完整性檢查  
   原則：翻譯後再做一次全站術語稽核，收斂不一致。  
   建議指令：
   1. `uv run python scripts/validate_glossary.py`（檢查術語表格式）
   2. `uv run python scripts/term_read.py`（檢查缺漏詞、禁用詞、未知高頻詞）
   3. `check-completeness`（檢查內容缺頁與規則缺漏）

8. 最終校對  
   出版前執行 `final-proofread`，依序檢查 frontmatter 完整性、內容完整性、頁碼參照連結三道品質關卡。

9. 預覽與調整樣式  
   在 `docs/` 下執行 `bun dev`，檢查頁面、目錄、連結、圖片與主題樣式。

10. 建置與部署  
    完整執行 `translate all` 時會自動重建導覽、執行 `bun run build` 並驗證搜尋索引。確認後以 `uv run python scripts/export_site.py --out <dir>` 匯出到 blog；仍需獨立部署的專案才用 GitHub Pages 或 Vercel。詳見〈部署〉章節。

---

## PDF 內容提取（手動流程）

不使用 AI 輔助時，可直接執行 `scripts/extract_pdf.py`、`split_chapters.py` 等腳本手動完成提取與切章。完整指令、參數與 OCR 語言設定見 [`scripts/README.md`](scripts/README.md)。

清除範本殘留資料（`new-project` 會自動執行一次，一般不需手動跑）也記錄在同一份文件的「清除範例資料」小節。

---

## 部署

**預設流程是匯出到 blog**：每本書仍是獨立的 Starlight 建置，但以子路徑 `/books/<slug>/` 併入 blog（wayneh.tw），由 blog 統一以共用密碼保護整個 `/books/` 路徑。只有仍需獨立部署的專案才使用下方的 GitHub Pages 或 Vercel 流程。

部署目標與子路徑統一記錄在 `style-decisions.json` 的 `deployment`（`target` 為 `blog`、`github-pages` 或 `root`），`generate_nav.py` 依此寫入 `docs/astro.config.mjs` 的 `base`，並把首頁連結加上同樣的前綴。

### 匯出到 blog（預設）

1. 記錄子路徑（`new-project` 已預設寫入 `/books/<slug>`），並重建導覽讓 `base` 與首頁連結同步：

   ```bash
   uv run python scripts/style_decisions.py set-deployment --target blog --base-path /books/<slug>
   uv run python scripts/generate_nav.py
   ```

2. 建置並匯出：

   ```bash
   uv run python scripts/export_site.py --out <dir>          # <dir> 須不存在或為空
   uv run python scripts/export_site.py --out <dir> --clean  # 覆寫既有輸出
   ```

   指令會先確認 `astro.config.mjs` 的 `base` 與 `style-decisions.json` 一致，接著執行 `bun run build`（含 zh-TW 搜尋後處理），再掃描所有 HTML／CSS，只要有網址跳出 `/books/<slug>/` 就中止並列出位置。通過後把靜態輸出複製到 `<dir>/`，並寫入 `<dir>/book.json`。結束時會印出檔案數與總大小（blog 的 Vercel 部署有檔案數限制）。

3. `book.json` 的欄位全部取自專案既有資料，不需逐專案手填：

   | 欄位 | 來源 |
   | --- | --- |
   | `slug`、`base_path` | `deployment.base_path` |
   | `title`、`description` | `site.title`、`site.description` |
   | `original_title` | `site.original_title`；未記錄時取 `data/pdfs/` 唯一 PDF 的檔名，否則為 `null` |
   | `cover` | `images.hero`（其次 `images.og`）存在時複製為 `cover.<副檔名>`，否則為 `null` |
   | `credits` | `credits.entries` |
   | `progress` | `data/translation-progress.json` 的完成章數／總章數 |
   | `updated_at` | 最後一次 commit 時間 |
   | `source_repo` | `git remote origin` 的 `owner/repo` |

4. blog 端把 `<dir>/` 放到 `public/books/<slug>/`。匯出內容不含 `middleware.ts` 與 `api/`，密碼保護由 blog 負責。

內文中手寫的絕對連結（例如 `fix-ref` 產生的跨頁連結）不會被 Astro 自動加上 `base`，必須含 `/books/<slug>` 前綴；匯出時的網址掃描會抓出遺漏。

### GitHub Pages（獨立部署的 Public 專案）

1. 記錄部署目標並重建導覽，`generate_nav.py` 會在 `docs/astro.config.mjs` 寫入 `site` 與 `base`：

   ```bash
   uv run python scripts/style_decisions.py set-deployment --target github-pages --base-path /<repo-name>
   uv run python scripts/generate_nav.py
   ```

2. 新增 `.github/workflows/deploy.yml`：

   ```yaml
   name: Deploy to GitHub Pages

   on:
     push:
       branches: [main]
     workflow_dispatch:

   permissions:
     contents: read
     pages: write
     id-token: write

   concurrency:
     group: pages
     cancel-in-progress: false

   jobs:
     build:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: oven-sh/setup-bun@v2
         - working-directory: docs
           run: bun install
         - working-directory: docs
           run: bun run build
         - uses: actions/configure-pages@v5
         - uses: actions/upload-pages-artifact@v3
           with:
             path: docs/dist

     deploy:
       needs: build
       runs-on: ubuntu-latest
       environment:
         name: github-pages
         url: ${{ steps.deployment.outputs.page_url }}
       steps:
         - id: deployment
           uses: actions/deploy-pages@v4
   ```

3. 推送到 `main`，並啟用 Pages（Actions 來源）：

   ```bash
   gh api repos/<owner>/<repo>/pages -X POST -f "build_type=workflow"
   ```

4. 之後每次推送到 `main` 都會自動重新部署，網址為 `https://<github-username>.github.io/<repo-name>/`。

GitHub Pages 是純靜態託管，沒有 middleware，無法做密碼保護——需要密碼保護時請改用下方的 Vercel 流程。

### Vercel（獨立部署且需要密碼保護時使用）

1. 推送到 GitHub
2. 在 Vercel 匯入專案
3. 自動部署

### 密碼保護（可選，僅 Vercel 支援）

獨立部署到 Vercel 時，在環境變數設定 `SITE_PASSWORD` 即可啟用密碼保護（匯出到 blog 時不需要，由 blog 統一把關）：

1. 進入 Vercel 專案設定 → Environment Variables
2. 新增 `SITE_PASSWORD`，值為您想要的密碼
3. 重新部署

未設定此變數則不啟用保護。

> **已知風險（刻意保留）**：`middleware.ts` 會放行社群平台爬蟲的 User-Agent（`facebookexternalhit`、`Twitterbot`、`Slackbot` 等），以便分享連結時能產生 OG 預覽。這代表任何人只要偽造 User-Agent（例如 `curl -A Twitterbot`）即可完整繞過密碼閘道。因此此功能**不是安全邊界**，僅能阻擋隨手點入的訪客，請勿用來保護機密或未授權散布的內容。若需要真正的存取控制，請改用平台層級的驗證（例如 Vercel Authentication）或不要公開部署。

### 手動建置

```bash
cd docs
bun run build
# 輸出在 docs/dist/
```

---

## 授權

MIT License
