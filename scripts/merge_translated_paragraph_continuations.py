#!/usr/bin/env python3
"""
合併已翻譯 Markdown 中，OpenDataLoader 誤判為兩個獨立段落的斷行續句。

與 `merge_translated_list_continuations.py` 處理的清單項目誤判不同，這裡的續句在英文
原文中仍是兩個以空白行分隔的一般段落（見 `_markdown_utils.find_paragraph_continuation_breaks`）。
譯文是中文，沒有大小寫可判斷，因此改用結構比對：先在英文來源找出續句位置，再用
`validate_translation_structure.py` 既有的結構標記（標題、清單、表格等）序列比對，取得
來源與譯文之間可信的錨點對應；在相鄰兩個錨點之間，來源與譯文的一般段落區塊若數量相同，
即依相同順序位置對齊，換算成譯文中對應的行號後執行合併（中文併合不加空格）。若段落數量
不一致（例如譯者已手動調整過段落結構），則該處無法安全對齊，回報為 unresolved，不強行合併。

使用方式：
    python scripts/merge_translated_paragraph_continuations.py <source> <translation> [--dry-run]
    python scripts/merge_translated_paragraph_continuations.py <source_dir> <translation_dir> [--dry-run]

`source` 與 `translation` 皆可為單一檔案，或成對的目錄樹（依相同相對路徑配對檔案）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from _markdown_utils import (
    find_paragraph_block_starts,
    find_paragraph_continuation_breaks,
    merge_paragraph_continuation_at,
)
from validate_translation_structure import (
    build_alignment_windows,
    extract_structure,
    find_alignment_window,
)

MARKDOWN_SUFFIXES = {".md", ".mdx"}


def pair_files(source: Path, translation: Path) -> list[tuple[Path, Path]]:
    """回傳 (來源檔, 譯文檔) 配對清單；目錄模式依相同相對路徑配對。"""
    if source.is_file() and translation.is_file():
        return [(source, translation)]
    if source.is_dir() and translation.is_dir():
        pairs: list[tuple[Path, Path]] = []
        for translation_file in sorted(translation.rglob("*")):
            if not translation_file.is_file() or translation_file.suffix not in MARKDOWN_SUFFIXES:
                continue
            rel_path = translation_file.relative_to(translation)
            source_file = source / rel_path
            if source_file.is_file():
                pairs.append((source_file, translation_file))
        return pairs
    raise ValueError("source and translation must both be files, or both be directories")


def merge_one_pair(source_path: Path, translation_path: Path, *, dry_run: bool) -> dict[str, Any]:
    """對單一來源／譯文檔配對套用合併，回傳該檔案的處理結果。"""
    source_text = source_path.read_text(encoding="utf-8")
    source_lines, _ambiguous = find_paragraph_continuation_breaks(source_text)
    result: dict[str, Any] = {
        "source": str(source_path),
        "translation": str(translation_path),
        "candidates": len(source_lines),
        "merged": 0,
        "unresolved": [],
    }
    if not source_lines:
        return result

    translation_text = translation_path.read_text(encoding="utf-8")
    source_tokens = extract_structure(source_text)
    draft_tokens = extract_structure(translation_text)
    windows = build_alignment_windows(source_tokens, draft_tokens)

    target_draft_lines: list[int] = []
    for source_line in source_lines:
        window = find_alignment_window(windows, source_line)
        if window is None:
            result["unresolved"].append(source_line)
            continue
        source_lo, source_hi, draft_lo, draft_hi = window
        source_paragraphs = find_paragraph_block_starts(source_text, source_lo, source_hi)
        draft_paragraphs = find_paragraph_block_starts(translation_text, draft_lo, draft_hi)
        if len(source_paragraphs) != len(draft_paragraphs) or source_line not in source_paragraphs:
            result["unresolved"].append(source_line)
            continue
        index = source_paragraphs.index(source_line)
        if index == 0:
            result["unresolved"].append(source_line)
            continue
        target_draft_lines.append(draft_paragraphs[index])

    # Merge from the bottom of the file up so earlier merges don't shift the
    # line numbers of merges still pending above them.
    for draft_line in sorted(set(target_draft_lines), reverse=True):
        translation_text = merge_paragraph_continuation_at(translation_text, draft_line, separator="")
        result["merged"] += 1

    if result["merged"] and not dry_run:
        translation_path.write_text(translation_text, encoding="utf-8")

    return result


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="英文來源 Markdown 檔案或目錄樹")
    parser.add_argument("translation", type=Path, help="已翻譯 Markdown 檔案或目錄樹")
    parser.add_argument("--dry-run", action="store_true", help="只回報將執行的合併，不寫入檔案")
    parser.add_argument("--json", action="store_true", help="以 JSON 輸出結果")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.source.exists():
        print(f"❌ 來源路徑不存在: {args.source}")
        return 2
    if not args.translation.exists():
        print(f"❌ 譯文路徑不存在: {args.translation}")
        return 2

    try:
        pairs = pair_files(args.source, args.translation)
    except ValueError as error:
        print(f"❌ {error}")
        return 2

    file_results = [
        merge_one_pair(source_path, translation_path, dry_run=args.dry_run)
        for source_path, translation_path in pairs
    ]
    total_merged = sum(result["merged"] for result in file_results)
    total_unresolved = sum(len(result["unresolved"]) for result in file_results)
    payload = {
        "dry_run": args.dry_run,
        "files_scanned": len(file_results),
        "total_merged": total_merged,
        "total_unresolved": total_unresolved,
        "files": [result for result in file_results if result["candidates"]],
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        verb = "將合併" if args.dry_run else "已合併"
        for result in payload["files"]:
            if result["merged"]:
                print(f"✓ {verb} {result['merged']} 處: {result['translation']}")
            for source_line in result["unresolved"]:
                print(
                    f"⚠️  無法對齊譯文位置（來源第 {source_line} 行）: {result['translation']}"
                )
        print(f"共掃描 {payload['files_scanned']} 組檔案，{verb} {total_merged} 處")
        if total_unresolved:
            print(f"⚠️  {total_unresolved} 處無法對齊，需人工確認")

    return 1 if total_unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())
