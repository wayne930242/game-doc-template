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
- `translate` 先讀全文並保存全書／各章摘要，再以每波最多 3 個較低成本的草稿 subagent 並行翻譯。每章以程式檢查 Markdown 結構，並進行一次語義審查；只有失敗時才定向修訂與必要複審。全書完成後會重建最終導覽、建置網站並驗證搜尋索引。
- `translate`、`bilingual-translate` 都會在每個 batch 完成後自動建立一個簡短進度 commit（格式：`progress: X/Y`）。舊的 `super-translate` 指令暫時保留，但會轉交新的 `translate` 流程。
- 翻譯前先確認術語（`glossary.json`），交付前執行一致性與完整性檢查

### 翻譯草稿模型分層（Codex，選用）

`translate`、`bilingual-translate` 可將草稿生成這一步（最耗 token 的步驟）交給本機 Codex CLI 執行（`gpt-5.6-luna`、low effort），每波最多並行 3 章；未使用 Codex 時改由 Claude Agent `sonnet` subagent 執行草稿。較強的執行環境保留給語義審查、歧義與收斂工作。

- 每個專案第一次執行任一翻譯 skill 時會詢問一次是否啟用，答案存在 `style-decisions.json`，之後不再詢問；不想用 Codex 的人選「否」即可，不影響其他功能。
- 啟用後才會偵測 Codex 是否可用；沒裝且本機有 npm 時才會問要不要安裝，拒絕的話也只問一次。
- Codex 產生的草稿與本機產生的草稿使用相同守門條件：程式化 Markdown 結構檢查與一次語義審查。Codex 失敗會靜默退回目前的執行環境自行產生草稿，不會中斷整批次。
- 完整運作方式見 `.claude/skills/translate/codex-tier.md`。

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
    完整執行 `translate all` 時會自動重建導覽、執行 `bun run build` 並驗證搜尋索引。確認 `docs/dist/` 後部署——Public 專案優先用 GitHub Pages，需要密碼保護或私有部署則用 Vercel。詳見〈部署〉章節。

---

## PDF 內容提取（手動流程）

不使用 AI 輔助時，可直接執行 `scripts/extract_pdf.py`、`split_chapters.py` 等腳本手動完成提取與切章。完整指令、參數與 OCR 語言設定見 [`scripts/README.md`](scripts/README.md)。

清除範本殘留資料（`new-project` 會自動執行一次，一般不需手動跑）也記錄在同一份文件的「清除範例資料」小節。

---

## 部署

先判斷專案可見度：**Public 專案優先用 GitHub Pages**（免費、不需額外服務、與現有 repo 直接整合）；需要密碼保護或私有部署，才用 Vercel。

### GitHub Pages（Public 專案推薦）

1. 在 `docs/astro.config.mjs` 設定 `site` 與 `base`（`base` 要對應 repo 名稱）：

   ```js
   export default defineConfig({
   	site: 'https://<github-username>.github.io',
   	base: '/<repo-name>',
   	// ...
   });
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

### Vercel（需要密碼保護或私有部署時使用）

1. 推送到 GitHub
2. 在 Vercel 匯入專案
3. 自動部署

### 密碼保護（可選，僅 Vercel 支援）

在 Vercel 環境變數設定 `SITE_PASSWORD` 即可啟用密碼保護：

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
