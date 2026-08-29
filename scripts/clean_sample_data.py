#!/usr/bin/env python3
"""Clean template/sample data before starting a new translation run."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from generate_nav import SIDEBAR_PATTERN

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_DIR = PROJECT_ROOT / "data" / "markdown"
DOCS_CONTENT_DIR = PROJECT_ROOT / "docs" / "src" / "content" / "docs"
GLOSSARY_PATH = PROJECT_ROOT / "glossary.json"
SAMPLE_IMAGES = [
    PROJECT_ROOT / "docs" / "public" / "bg.jpg",
    PROJECT_ROOT / "docs" / "public" / "og-image.jpg",
    PROJECT_ROOT / "docs" / "src" / "assets" / "hero.jpg",
]
CHAPTERS_PATH = PROJECT_ROOT / "chapters.json"
STYLE_PATH = PROJECT_ROOT / "style-decisions.json"
PROGRESS_GLOB_DIR = PROJECT_ROOT / "data"
ASTRO_CONFIG = PROJECT_ROOT / "docs" / "astro.config.mjs"
INDEX_MDX = PROJECT_ROOT / "docs" / "src" / "content" / "docs" / "index.mdx"
PLANS_DIR = PROJECT_ROOT / "plans"
# Generated docs content that a reset must remove. `_meta.yml` is written by
# split_chapters.write_meta_yml and consumed by starlight-auto-sidebar: leaving
# it behind keeps stale ordering/labels and keeps section dirs non-empty.
DOCS_CONTENT_SUFFIXES = {".md", ".mdx"}
DOCS_CONTENT_FILENAMES = {"_meta.yml", "_meta.yaml"}

CHAPTERS_PLACEHOLDER = {
    "source": "data/markdown/YOUR-RULEBOOK_pages.md",
    "output_dir": "docs/src/content/docs",
    "mode": "zh_only",
    "chapters": {
        "example-section": {
            "title": "Example Section",
            "order": 1,
            "files": {
                "index": {
                    "title": "Example Chapter",
                    "description": "格式參考用佔位章節；執行 /init-doc 或 /chapter-split 後會被真實內容取代。",
                    "pages": [1, 2],
                    "order": 0,
                }
            },
        }
    },
}

INDEX_PLACEHOLDER = """---
title: 遊戲規則文件
description: 使用 game-doc-template 建立的規則書文件站。執行 /init-doc 開始設定。
template: splash
hero:
  title: 遊戲規則文件
  tagline: 尚未初始化——請在專案中執行 /init-doc 匯入規則書。
---

## 開始使用

1. 將規則書 PDF 放入 `data/pdfs/`
2. 執行 `/init-doc` 完成抽取、章節切分與術語初始化
3. 執行 `/translate` 或 `/super-translate` 開始翻譯
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean sample/template content.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Apply cleanup directly (otherwise dry-run).",
    )
    return parser.parse_args()


def remove_path(path: Path, apply: bool) -> None:
    rel = path.relative_to(PROJECT_ROOT)
    if path.is_dir():
        print(f"remove dir: {rel}")
        if apply:
            shutil.rmtree(path, ignore_errors=True)
        return
    print(f"remove file: {rel}")
    if apply:
        path.unlink(missing_ok=True)


def clean_markdown_data(apply: bool) -> None:
    if not MARKDOWN_DIR.exists():
        return
    for child in sorted(MARKDOWN_DIR.iterdir()):
        if child.name == ".gitkeep":
            continue
        remove_path(child, apply)


def clean_docs_content(apply: bool) -> None:
    if not DOCS_CONTENT_DIR.exists():
        return
    for path in sorted(DOCS_CONTENT_DIR.rglob("*")):
        if path.is_dir():
            continue
        if (
            path.suffix.lower() not in DOCS_CONTENT_SUFFIXES
            and path.name.lower() not in DOCS_CONTENT_FILENAMES
        ):
            continue
        remove_path(path, apply)

    # remove now-empty directories
    for path in sorted(DOCS_CONTENT_DIR.rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            rel = path.relative_to(PROJECT_ROOT)
            print(f"remove empty dir: {rel}")
            if apply:
                path.rmdir()


def clean_sample_images(apply: bool) -> None:
    for path in SAMPLE_IMAGES:
        if path.exists():
            remove_path(path, apply)


def clean_glossary(apply: bool) -> None:
    if not GLOSSARY_PATH.exists():
        return

    default_description = "術語表 - 英文遊戲術語對照繁體中文翻譯"
    description = default_description

    try:
        current = json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))
        meta = current.get("_meta", {})
        description = meta.get("description") or default_description
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        description = default_description

    cleaned = {
        "_meta": {
            "description": description,
            "updated": "",
        }
    }

    rel = GLOSSARY_PATH.relative_to(PROJECT_ROOT)
    print(f"reset glossary: {rel}")
    if apply:
        GLOSSARY_PATH.write_text(
            json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _write_json(path: Path, data: dict, apply: bool, label: str) -> None:
    print(f"reset {label}: {path.relative_to(PROJECT_ROOT)}")
    if apply:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def reset_chapters(apply: bool) -> None:
    _write_json(CHAPTERS_PATH, CHAPTERS_PLACEHOLDER, apply, "chapters")


def reset_style_decisions(apply: bool) -> None:
    description = "翻譯與格式風格決策記錄"
    if STYLE_PATH.exists():
        try:
            meta = json.loads(STYLE_PATH.read_text(encoding="utf-8")).get("_meta", {})
            description = meta.get("description") or description
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            pass
    _write_json(STYLE_PATH, {"_meta": {"description": description, "updated": ""}}, apply, "style-decisions")


def remove_progress_files(apply: bool) -> None:
    if not PROGRESS_GLOB_DIR.exists():
        return
    for path in sorted(PROGRESS_GLOB_DIR.glob("translation-progress*.json")):
        remove_path(path, apply)
    context_path = PROGRESS_GLOB_DIR / "translation-context.json"
    if context_path.exists():
        remove_path(context_path, apply)


def reset_astro_config(apply: bool) -> None:
    if not ASTRO_CONFIG.exists():
        return
    import re

    text = ASTRO_CONFIG.read_text(encoding="utf-8")
    text = re.sub(r"title: '[^']*',", "title: '遊戲規則文件',", text, count=1)
    # Reuse generate_nav's line-anchored pattern: it already stops at the
    # sidebar array's own `],` instead of over-consuming into a later
    # multi-line `],` (e.g. `plugins`), and matches the collapsed empty form
    # too so no separate idempotency guard is needed.
    text = SIDEBAR_PATTERN.sub(
        lambda m: f"{m.group('indent')}sidebar: [],", text, count=1
    )
    print(f"reset astro config: {ASTRO_CONFIG.relative_to(PROJECT_ROOT)}")
    if apply:
        ASTRO_CONFIG.write_text(text, encoding="utf-8")


def write_placeholder_index(apply: bool) -> None:
    print(f"write placeholder index: {INDEX_MDX.relative_to(PROJECT_ROOT)}")
    if apply:
        INDEX_MDX.parent.mkdir(parents=True, exist_ok=True)
        INDEX_MDX.write_text(INDEX_PLACEHOLDER, encoding="utf-8")


def remove_plans_dir(apply: bool) -> None:
    if PLANS_DIR.exists():
        remove_path(PLANS_DIR, apply)


def main() -> None:
    args = parse_args()
    apply = args.yes
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"[clean-sample-data] mode={mode}")
    print("Target roots:")
    print(f"- {MARKDOWN_DIR.relative_to(PROJECT_ROOT)}")
    print(f"- {DOCS_CONTENT_DIR.relative_to(PROJECT_ROOT)}")
    print(f"- {GLOSSARY_PATH.relative_to(PROJECT_ROOT)}")
    for img in SAMPLE_IMAGES:
        print(f"- {img.relative_to(PROJECT_ROOT)}")

    clean_markdown_data(apply)
    clean_docs_content(apply)
    clean_sample_images(apply)
    clean_glossary(apply)
    reset_chapters(apply)
    reset_style_decisions(apply)
    remove_progress_files(apply)
    reset_astro_config(apply)
    write_placeholder_index(apply)
    remove_plans_dir(apply)

    if apply:
        print("✓ Cleanup complete")
    else:
        print("ℹ️ Dry-run only. Re-run with --yes to apply.")


if __name__ == "__main__":
    main()
