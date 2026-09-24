#!/usr/bin/env python3
"""
將既有專案中瀏覽器無法顯示的提取圖片（如 JPEG 2000 `.jpx`）轉成 PNG，並改寫引用。

`extract_pdf.py` 提取時已直接輸出 PNG；本工具修復在此之前提取的專案：
- 轉換 `data/markdown/images/` 與 `docs/src/assets/` 下的非網頁格式圖片（刪除原檔）
- 更新圖片 manifest 的 `filename`、`path`、`file_size`
- 改寫 `docs/src/content/docs/` 與 `.state/*/drafts/` 中 Markdown 的圖片引用

使用方式：
    python scripts/convert_web_images.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

import pymupdf

from _image_analysis import pixmap_to_png

PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMAGE_ROOTS = (Path("data/markdown/images"), Path("docs/src/assets"))
MARKDOWN_ROOTS = (Path("docs/src/content/docs"), Path(".state"))
MARKDOWN_SUFFIXES = {".md", ".mdx"}
# Formats PyMuPDF extraction can emit that browsers do not display.
NON_WEB_IMAGE_SUFFIXES = {".jpx", ".jp2", ".tif", ".tiff", ".bmp", ".pnm"}


def find_non_web_images(project_root: Path) -> list[Path]:
    images: list[Path] = []
    for root in IMAGE_ROOTS:
        base = project_root / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix.lower() in NON_WEB_IMAGE_SUFFIXES:
                images.append(path)
    return images


def convert_image(path: Path) -> Path:
    target = path.with_suffix(".png")
    target.write_bytes(pixmap_to_png(pymupdf.Pixmap(str(path))))
    path.unlink()
    return target


def update_manifests(project_root: Path, renames: dict[str, str]) -> int:
    """Point manifest entries at the converted files; return the number of entries updated."""
    updated = 0
    images_root = project_root / IMAGE_ROOTS[0]
    if not images_root.is_dir():
        return 0
    for manifest_path in sorted(images_root.rglob("manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        changed = False
        for entry in manifest.get("images", []):
            new_name = renames.get(entry.get("filename", ""))
            if not new_name:
                continue
            entry["filename"] = new_name
            entry["path"] = str(Path(entry["path"]).with_name(new_name).as_posix())
            entry["file_size"] = (manifest_path.parent / new_name).stat().st_size
            changed = True
            updated += 1
        if changed:
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return updated


def rewrite_markdown_references(project_root: Path, renames: dict[str, str]) -> tuple[int, int]:
    """Rewrite references to converted files; return (files changed, references rewritten)."""
    files_changed = 0
    references = 0
    for root in MARKDOWN_ROOTS:
        base = project_root / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix not in MARKDOWN_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8")
            new_text = text
            for old_name, new_name in renames.items():
                count = new_text.count(old_name)
                if count:
                    new_text = new_text.replace(old_name, new_name)
                    references += count
            if new_text != text:
                path.write_text(new_text, encoding="utf-8")
                files_changed += 1
    return files_changed, references


def convert_project(project_root: Path, *, dry_run: bool) -> dict[str, int]:
    images = find_non_web_images(project_root)
    renames = {path.name: path.with_suffix(".png").name for path in images}
    if dry_run:
        return {"images": len(images), "manifest_entries": 0, "markdown_files": 0, "references": 0}
    for path in images:
        convert_image(path)
    manifest_entries = update_manifests(project_root, renames)
    markdown_files, references = rewrite_markdown_references(project_root, renames)
    return {
        "images": len(images),
        "manifest_entries": manifest_entries,
        "markdown_files": markdown_files,
        "references": references,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert extracted non-web images (e.g. JPEG 2000) to PNG and rewrite references.")
    parser.add_argument("--dry-run", action="store_true", help="Count images to convert without writing files")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None, project_root: Path = PROJECT_ROOT) -> int:
    args = parse_args(argv)
    try:
        counts = convert_project(project_root, dry_run=args.dry_run)
    except (pymupdf.FileDataError, RuntimeError) as exc:
        print(f"❌ 圖片轉換失敗：{exc}", file=sys.stderr)
        return 2
    if args.dry_run:
        print(f"（預覽）{counts['images']} 張圖片需轉成 PNG")
        return 0
    print(
        f"✓ 已轉換 {counts['images']} 張圖片為 PNG；更新 manifest {counts['manifest_entries']} 筆；"
        f"改寫 {counts['markdown_files']} 個 Markdown 檔中 {counts['references']} 處引用"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
