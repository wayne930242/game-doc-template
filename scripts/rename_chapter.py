#!/usr/bin/env python3
"""
重新命名既有專案的頂層章節 slug，並同步所有引用該章節路徑的專案資料。

用於修復使用保留 slug（如 `index`）的章節，見 `split_chapters.RESERVED_SECTION_SLUGS`。
會一併更新：
- 章節目錄（`docs/src/content/docs/<slug>/`，雙語模式為 `bilingual/<slug>/`）
- `chapters.json` 的章節鍵（保留原順序）
- `data/translation-progress.json` 的 `file` 與 `id`
- `.state/*/draft-manifest.json` 與對應草稿檔
- `data/translation-context.json` 的章節鍵與 `id`（原本指紋一致時同步更新章節指紋）
- 內容中指向該章節的絕對路由連結（含或不含 deployment base path）

完成後請執行 `uv run python scripts/generate_nav.py` 重建首頁與側邊欄。

使用方式：
    python scripts/rename_chapter.py --from index --to book-index
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Sequence

from generate_nav import deployment_base_path
from init_create_progress import chapter_id_from_path
from split_chapters import RESERVED_SECTION_SLUGS
from translation_context import ContextError, current_fingerprints

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHAPTERS_FILE = Path("chapters.json")
PROGRESS_FILE = Path("data/translation-progress.json")
CONTEXT_FILE = Path("data/translation-context.json")
STYLE_FILE = Path("style-decisions.json")
STATE_DIR = Path(".state")
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MARKDOWN_SUFFIXES = {".md", ".mdx"}


class RenameError(RuntimeError):
    """Raised when the rename cannot be applied safely."""


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def docs_prefix(config: dict[str, Any]) -> str:
    """Return the project-relative docs directory the chapters live in."""
    output_dir = config.get("output_dir", "docs/src/content/docs").rstrip("/")
    return f"{output_dir}/bilingual" if config.get("mode") == "bilingual" else output_dir


def replace_path_prefix(path: str, old_prefix: str, new_prefix: str) -> str:
    if path == old_prefix or path.startswith(f"{old_prefix}/"):
        return new_prefix + path[len(old_prefix):]
    return path


def rename_chapters_key(config: dict[str, Any], old: str, new: str) -> None:
    config["chapters"] = {(new if key == old else key): value for key, value in config["chapters"].items()}


def rename_progress(progress: dict[str, Any], old_prefix: str, new_prefix: str) -> int:
    count = 0
    for chapter in progress.get("chapters", []):
        file_path = chapter.get("file", "")
        renamed = replace_path_prefix(file_path, old_prefix, new_prefix)
        if renamed != file_path:
            chapter["file"] = renamed
            chapter["id"] = chapter_id_from_path(renamed)
            count += 1
    return count


def rename_draft_manifest(root: Path, manifest_path: Path, old_prefix: str, new_prefix: str) -> int:
    manifest = read_json(manifest_path)
    entries: dict[str, Any] = {}
    count = 0
    for key, entry in manifest.get("entries", {}).items():
        new_key = replace_path_prefix(key, old_prefix, new_prefix)
        if new_key != key:
            count += 1
            entry["source"] = replace_path_prefix(entry["source"], old_prefix, new_prefix)
            old_draft = entry["draft"]
            entry["draft"] = old_draft.replace(old_prefix, new_prefix, 1)
            if (root / old_draft).exists():
                (root / entry["draft"]).parent.mkdir(parents=True, exist_ok=True)
                (root / old_draft).rename(root / entry["draft"])
        entries[new_key] = entry
    manifest["entries"] = entries
    write_json(manifest_path, manifest)
    return count


def rename_context(context: dict[str, Any], old_prefix: str, new_prefix: str) -> int:
    chapters: dict[str, Any] = {}
    count = 0
    for key, entry in context.get("chapters", {}).items():
        new_key = replace_path_prefix(key, old_prefix, new_prefix)
        if new_key != key:
            entry["id"] = chapter_id_from_path(new_key)
            count += 1
        chapters[new_key] = entry
    context["chapters"] = chapters
    return count


def route_pattern(old: str, base_path: str) -> re.Pattern[str]:
    base = f"(?:{re.escape(base_path)})?" if base_path else ""
    return re.compile(rf"""(?P<lead>\]\(|href=["'])(?P<base>{base})/{re.escape(old)}(?=[/#?)"'])""")


def rewrite_links(docs_dir: Path, old: str, new: str, base_path: str) -> tuple[int, int]:
    pattern = route_pattern(old, base_path)
    files_changed = 0
    links = 0
    for path in sorted(docs_dir.rglob("*")):
        if not path.is_file() or path.suffix not in MARKDOWN_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8")
        new_text, count = pattern.subn(lambda match: f"{match['lead']}{match['base']}/{new}", text)
        if count:
            path.write_text(new_text, encoding="utf-8")
            files_changed += 1
            links += count
    return files_changed, links


def rename_chapter(root: Path, old: str, new: str) -> dict[str, int]:
    if not SLUG_PATTERN.match(new) or new in RESERVED_SECTION_SLUGS:
        raise RenameError(f"新 slug 必須是 kebab-case 且非保留字：{new}")
    config = read_json(root / CHAPTERS_FILE)
    if old not in config.get("chapters", {}):
        raise RenameError(f"chapters.json 沒有章節 {old}")
    if new in config["chapters"]:
        raise RenameError(f"chapters.json 已有章節 {new}")
    prefix = docs_prefix(config)
    old_prefix, new_prefix = f"{prefix}/{old}", f"{prefix}/{new}"
    if (root / new_prefix).exists():
        raise RenameError(f"目標目錄已存在：{new_prefix}")

    context_path = root / CONTEXT_FILE
    context = read_json(context_path) if context_path.is_file() else None
    context_was_current = False
    if context is not None:
        try:
            context_was_current = (
                context.get("_meta", {}).get("chapters_fingerprint") == current_fingerprints(root)["chapters_fingerprint"]
            )
        except ContextError:
            context_was_current = False

    counts: dict[str, int] = {}
    if (root / old_prefix).is_dir():
        (root / old_prefix).rename(root / new_prefix)
        counts["directories"] = 1
    rename_chapters_key(config, old, new)
    write_json(root / CHAPTERS_FILE, config)

    progress_path = root / PROGRESS_FILE
    if progress_path.is_file():
        progress = read_json(progress_path)
        counts["progress_entries"] = rename_progress(progress, old_prefix, new_prefix)
        write_json(progress_path, progress)

    counts["draft_entries"] = sum(
        rename_draft_manifest(root, manifest, old_prefix, new_prefix)
        for manifest in sorted((root / STATE_DIR).glob("*/draft-manifest.json"))
    )

    if context is not None:
        counts["context_entries"] = rename_context(context, old_prefix, new_prefix)
        if context_was_current:
            context["_meta"]["chapters_fingerprint"] = current_fingerprints(root)["chapters_fingerprint"]
        write_json(context_path, context)

    style_path = root / STYLE_FILE
    base_path = deployment_base_path(read_json(style_path)) if style_path.is_file() else ""
    counts["link_files"], counts["links"] = rewrite_links(root / prefix, old, new, base_path)
    return counts


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rename a top-level chapter slug and update every project reference to it.")
    parser.add_argument("--from", dest="old", required=True, help="Current top-level chapter slug (e.g. index)")
    parser.add_argument("--to", dest="new", required=True, help="New kebab-case slug (e.g. book-index)")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None, project_root: Path = PROJECT_ROOT) -> int:
    args = parse_args(argv)
    try:
        counts = rename_chapter(project_root, args.old, args.new)
    except RenameError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    summary = "、".join(f"{key}={value}" for key, value in counts.items())
    print(f"✓ 已將章節 {args.old} 重新命名為 {args.new}：{summary}")
    print("  下一步：uv run python scripts/generate_nav.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
