# docs — 文件網站

本目錄是由 [game-doc-template](../README.md) 管理的 Astro 5 + Starlight 文件站，內容（`src/content/docs/`）與側欄（`astro.config.mjs` 的 `sidebar`）由專案根目錄的轉換管線產生：`/init-doc` 抽取規則書 → `/chapter-split` 切分章節（`scripts/split_chapters.py` 依 `chapters.json`）→ `scripts/generate_nav.py` 重寫首頁與側欄。

## 指令

| 指令 | 說明 |
| --- | --- |
| `bun install` | 安裝相依 |
| `bun run dev` | 本地開發（localhost:4321） |
| `bun run build` | 建置到 `./dist/` |
| `bun run preview` | 預覽建置結果 |

手動編輯 `src/content/docs/` 的內容會在下次執行管線時被覆寫；請透過 `/translate` 工作流程修改。
