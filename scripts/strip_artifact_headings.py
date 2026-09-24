#!/usr/bin/env python3
"""
移除既有 Markdown 中的版面裝飾標題（頁碼、空白、單一字母、兩個小寫字母）。

`extract_pdf.py` 在提取時已套用同一規則（`_markdown_utils.strip_artifact_headings`）；
本工具供規則擴充後修復既有專案：提取結果、已拆分章節、已翻譯章節與翻譯草稿。

使用方式：
    python scripts/strip_artifact_headings.py <path>... [--dry-run]

`path` 可為 Markdown 檔案或目錄（遞迴處理其中的 .md／.mdx）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from _markdown_utils import ARTIFACT_HEADING_RE, strip_artifact_headings

MARKDOWN_SUFFIXES = {".md", ".mdx"}


def iter_markdown_files(paths: Sequence[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(p for p in path.rglob("*") if p.is_file() and p.suffix in MARKDOWN_SUFFIXES))
        else:
            raise FileNotFoundError(f"找不到路徑：{path}")
    return files


def strip_file(path: Path, *, dry_run: bool) -> list[str]:
    """移除檔案中的裝飾標題，回傳被移除的標題行。"""
    text = path.read_text(encoding="utf-8")
    removed = [match.group(0) for match in ARTIFACT_HEADING_RE.finditer(text)]
    if removed and not dry_run:
        cleaned = strip_artifact_headings(text)
        path.write_text(f"{cleaned}\n" if text.endswith("\n") else cleaned, encoding="utf-8")
    return removed


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remove layout-artifact headings from existing Markdown files.")
    parser.add_argument("paths", nargs="+", type=Path, help="Markdown files or directories to clean in place")
    parser.add_argument("--dry-run", action="store_true", help="Report matches without writing files")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        files = iter_markdown_files(args.paths)
    except FileNotFoundError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    total = 0
    for path in files:
        removed = strip_file(path, dry_run=args.dry_run)
        if removed:
            total += len(removed)
            print(f"{'（預覽）' if args.dry_run else '✓'} {path}: {', '.join(repr(line) for line in removed)}")
    print(f"共 {total} 個裝飾標題{'（未寫入）' if args.dry_run else '已移除'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
