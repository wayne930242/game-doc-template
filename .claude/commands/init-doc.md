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

### 3. Extract and Select Images

#### 3.1 Extract Images from PDF

Images are automatically extracted during step 2 (`extract_pdf.py`).

Images saved to `data/markdown/images/<pdf_name>/`.

#### 3.2 Present Images to User

List all extracted images with thumbnails or descriptions:

```
找到以下圖片：
1. image_001.jpg (封面, 1200x800)
2. image_002.png (角色插圖, 600x400)
3. image_003.jpg (地圖, 1000x700)
...

請選擇用途：
```

#### 3.3 Ask Image Assignments

Use AskUserQuestion to ask for each image type:

**Hero Image** (首頁主圖，會裁切成圓形):
- 建議：選擇主視覺、角色、或標誌性圖像
- 存放位置：`docs/src/assets/hero.jpg`

**Background Image** (背景圖):
- 建議：選擇氛圍圖、場景圖、或紋理
- 存放位置：`docs/public/bg.jpg`

**OG Image** (社群分享預覽圖):
- 建議：1200x630 最佳，選擇能代表遊戲的圖
- 存放位置：`docs/public/og-image.jpg`

#### 3.4 Process Selected Images

Copy selected images to appropriate locations:

```bash
# Hero image (resize if needed)
cp data/markdown/images/<pdf_name>/<selected_hero>.jpg docs/src/assets/hero.jpg

# Background image
cp data/markdown/images/<pdf_name>/<selected_bg>.jpg docs/public/bg.jpg

# OG image (resize to 1200x630 if needed)
cp data/markdown/images/<pdf_name>/<selected_og>.jpg docs/public/og-image.jpg
```

### 4. Configure Visual Theme

#### 4.1 Background Mode

Use AskUserQuestion:

```
背景色調設定：

選項：
1. 深色模式 (Dark) - 適合大多數遊戲，神秘、沉浸感
2. 淺色模式 (Light) - 清新、明亮風格

目前背景圖的主色調是什麼？
```

#### 4.2 Overlay Settings

Based on background image analysis, ask:

```
背景圖對比度設定：

觀察您選擇的背景圖，請確認：

1. 需要深色遮罩 - 背景太亮，文字可能不清楚
2. 需要淺色遮罩 - 背景太深但想要淺色主題
3. 不需要遮罩 - 背景對比度適中
4. 自訂遮罩透明度 (0-1)

建議：通常 0.6-0.8 的遮罩效果最佳
```

Update `docs/src/styles/custom.css`:

```css
/* 遮罩透明度 */
--overlay-opacity: <user_choice>;
```

#### 4.3 Color Palette Design

Use AskUserQuestion to determine color style:

```
色票風格設定：

請選擇適合遊戲氛圍的色彩風格：

1. 🌊 冷色系 (Cool)
   - 主色：藍色系
   - 適合：科幻、海洋、冬季、神秘

2. 🔥 暖色系 (Warm)
   - 主色：橘紅色系
   - 適合：冒險、沙漠、戰鬥、熱情

3. 🌲 自然系 (Nature)
   - 主色：綠色系
   - 適合：奇幻、森林、生態、治癒

4. 🌙 暗黑系 (Dark)
   - 主色：紫黑色系
   - 適合：恐怖、哥德、死亡、邪惡

5. ⚔️ 史詩系 (Epic)
   - 主色：金色系
   - 適合：中世紀、王國、戰爭、榮耀

6. 🎨 自訂 (Custom)
   - 提供主色 HEX 或描述風格
```

#### 4.4 Generate Color Variables

Based on user choice, generate HSL color scheme:

**冷色系 (Cool)**:
```css
--color-primary-h: 217;   /* 藍 */
--color-secondary-h: 180; /* 青 */
--color-tertiary-h: 260;  /* 紫 */
--color-quaternary-h: 200; /* 天藍 */
```

**暖色系 (Warm)**:
```css
--color-primary-h: 25;    /* 橘 */
--color-secondary-h: 45;  /* 金 */
--color-tertiary-h: 0;    /* 紅 */
--color-quaternary-h: 350; /* 玫瑰 */
```

**自然系 (Nature)**:
```css
--color-primary-h: 142;   /* 綠 */
--color-secondary-h: 80;  /* 黃綠 */
--color-tertiary-h: 30;   /* 棕 */
--color-quaternary-h: 160; /* 青綠 */
```

**暗黑系 (Dark)**:
```css
--color-primary-h: 280;   /* 紫 */
--color-secondary-h: 320; /* 洋紅 */
--color-tertiary-h: 0;    /* 血紅 */
--color-quaternary-h: 260; /* 暗紫 */
```

**史詩系 (Epic)**:
```css
--color-primary-h: 45;    /* 金 */
--color-secondary-h: 30;  /* 銅 */
--color-tertiary-h: 0;    /* 紅 */
--color-quaternary-h: 15; /* 橘金 */
```

#### 4.5 Apply Theme Settings

Update `docs/src/styles/custom.css` with selected colors.

If user chose background image, uncomment background-image in CSS:

```css
body {
  background-color: var(--sl-color-black);
  background-image: url('/bg.jpg');
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
  background-repeat: no-repeat;
}
```

### 5. Identify Key Terms

Scan extracted content for:
- Capitalized game terms (Move, Playbook, Harm)
- Quoted terms
- Repeated specialized vocabulary

Present terms to user for translation confirmation.

### 6. Build Glossary

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

### 7. Configure Chapters

Help user set up `chapters.json`:
1. Show table of contents from PDF
2. Suggest chapter structure based on content
3. Map page ranges to output files

### 8. Split Content

```bash
uv run python split_chapters.py
```

### 9. Analyze and Split index.md

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

### 10. Verify

- Check generated files in `docs/src/content/docs/`
- Verify sidebar order matches original TOC
- Preview: `cd docs && bun dev`

### 11. Record Configuration

Save all visual settings to `style-decisions.json`:

```json
{
  "theme": {
    "mode": "dark",
    "palette": "cool",
    "overlay_opacity": 0.7
  },
  "images": {
    "hero": "image_001.jpg",
    "background": "image_003.jpg",
    "og": "image_001.jpg"
  },
  "colors": {
    "primary_h": 217,
    "secondary_h": 180,
    "tertiary_h": 260,
    "quaternary_h": 200
  }
}
```

## Example Usage

```
/init-doc
/init-doc data/pdfs/rulebook.pdf
```
