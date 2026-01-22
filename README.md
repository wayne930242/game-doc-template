# 遊戲文件模板 (Game Documentation Template)

基於 Astro + Starlight 的遊戲規則文件模板，專為 TRPG 設計，也適用於任何遊戲規則文件。

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

# 後端（PDF 處理，可選）
cd ../scripts
uv sync  # 或 pip install markitdown pymupdf
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
  title: '您的遊戲名稱',
  defaultLocale: 'zh-TW',
  localeLabel: '繁體中文',
  allowIndexing: false,  // SEO 設定
};
```

### 圖片資源

| 檔案 | 位置 | 說明 |
|------|------|------|
| 背景圖 | `docs/public/bg.jpg` | 1920x1080，深色低對比度為佳 |
| 社群分享圖 | `docs/public/og-image.jpg` | 1200x630 |
| 首頁主圖 | `docs/src/assets/hero.jpg` | 560x560，會裁切成圓形 |
| 網站圖示 | `docs/public/favicon.svg` | 32x32 |

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

## 使用 AI 輔助翻譯（需安裝 Claude Code）

本專案內建 AI 輔助翻譯工具，透過 Claude Code 執行以下命令：

### 建立新專案

```
/new-project ~/Downloads/your-game.pdf
```

從模板建立新專案，自動建立 GitHub 私人 repo 並複製 PDF。

### 初始化翻譯專案

```
/init-doc
```

完整初始化流程：
- 提取 PDF 內容與圖片
- 選擇 Hero、背景、OG 圖片
- 設定背景色調與遮罩
- 選擇色票風格（冷色、暖色、自然、暗黑、史詩）
- 建立術語表與章節結構

### 術語一致性校對

```
/check-consistency
```

檢查所有文件的術語使用是否一致。

### 用語決定與批量替換

```
/term-decision
```

選擇術語翻譯方式並全文替換。

### 完整性檢查

```
/check-completeness
```

確認規則內容是否有缺漏。

---

## PDF 內容提取（手動流程）

若不使用 AI 輔助，可手動執行：

```bash
cd scripts

# 1. 提取 PDF
uv run python extract_pdf.py ../data/pdfs/your-rulebook.pdf

# 2. 產生章節設定範例
uv run python split_chapters.py --init

# 3. 編輯 chapters.json 設定章節結構

# 4. 拆分章節
uv run python split_chapters.py
```

---

## 部署

### Vercel（推薦）

1. 推送到 GitHub
2. 在 Vercel 匯入專案
3. 自動部署

### 密碼保護（可選）

在 Vercel 環境變數設定 `SITE_PASSWORD` 即可啟用密碼保護：

1. 進入 Vercel 專案設定 → Environment Variables
2. 新增 `SITE_PASSWORD`，值為您想要的密碼
3. 重新部署

未設定此變數則不啟用保護。

### 手動建置

```bash
cd docs
bun run build
# 輸出在 docs/dist/
```

---

## 授權

MIT License
