#!/usr/bin/env python3
"""
轉換已翻譯 Markdown 中，裝飾性符號字型字元（如 Wingdings 字元被輸出成原始控制字元，
例如 U+0094）殘留的內容，套用與 `_markdown_utils.convert_symbol_glyph_ornaments` 相同的
規則：符號當清單項目標記時轉為 `- ` 清單項目、裝飾小節標題時去除符號並視情況轉為標題。

符號本身無法從中文譯文的大小寫或詞彙判斷分類（英文側靠前一區塊是否以句末標點結尾、
是否與其他符號區塊相鄰來分類），因此改用結構比對：先在英文來源（合併段落斷行續句、清除
頁碼殘留後）算出每個符號區塊的分類決策，再用 `validate_translation_structure.py` 既有的
結構標記序列比對，取得來源與譯文之間可信的錨點對應。在相鄰兩個錨點之間，不依一般段落區塊
的順序位置對齊——翻譯常會重新斷句、合併段落，位置計數並不可靠——而是依「該區塊是否仍含裝飾
符號殘留字元」的出現順序對齊：來源側該區間內的符號分類決策，與譯文側該區間內仍含符號殘留
字元的區塊，依相同順序一一配對。若同一錨點區間內兩側符號殘留區塊數量不一致，或譯文區塊自身
的符號出現次數與分類決策的形狀不符（例如來源判定為單一符號標題，但譯文區塊有兩次以上符號），
則該處無法安全套用，回報為 unresolved，不強行轉換。

使用方式：
    python scripts/convert_translated_symbol_glyphs.py <source> <translation> [--dry-run]
    python scripts/convert_translated_symbol_glyphs.py <source_dir> <translation_dir> [--dry-run]

`source` 與 `translation` 皆可為單一檔案，或成對的目錄樹（依相同相對路徑配對檔案）。
符號字元清單預設讀取 style-decisions.json 的 `document_format.symbol_glyphs`，可用
`--glyph` 覆蓋（可重複指定）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from _markdown_utils import (
    apply_glyph_decision_at,
    clean_symbol_glyph_ornaments,
    find_glyph_block_starts,
    find_symbol_glyph_block_decisions,
    prepare_source_pre_glyph_conversion,
)
from validate_translation_structure import (
    build_alignment_windows,
    extract_structure,
    find_alignment_window,
    realign_heading_levels,
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


def load_symbol_glyphs(project_root: Path) -> list[str]:
    """讀取 style-decisions.json 的 `document_format.symbol_glyphs`。"""
    path = project_root / "style-decisions.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    glyphs = payload.get("document_format", {}).get("symbol_glyphs")
    if not isinstance(glyphs, list) or not all(isinstance(item, str) for item in glyphs):
        return []
    return list(glyphs)


def _count_glyph_occurrences(text: str, glyphs: Sequence[str]) -> int:
    return sum(text.count(glyph) for glyph in glyphs)


def convert_one_pair(
    source_path: Path, translation_path: Path, glyphs: Sequence[str], *, dry_run: bool
) -> dict[str, Any]:
    """對單一來源／譯文檔配對套用轉換，回傳該檔案的處理結果。"""
    result: dict[str, Any] = {
        "source": str(source_path),
        "translation": str(translation_path),
        "candidates": 0,
        "titles": 0,
        "list_items_from_singleton": 0,
        "list_items_from_split": 0,
        "dropped": 0,
        "unresolved": [],
        "leftover": 0,
        "heading_levels_realigned": 0,
    }
    if not glyphs:
        return result

    translation_text = translation_path.read_text(encoding="utf-8")
    result["candidates"] = _count_glyph_occurrences(translation_text, glyphs)

    source_text = prepare_source_pre_glyph_conversion(source_path.read_text(encoding="utf-8"))

    if result["candidates"]:
        decisions = [d for d in find_symbol_glyph_block_decisions(source_text, glyphs) if not d.deferred_tail]

        # Fast path: when the whole file has exactly as many glyph-bearing draft
        # blocks as source decisions, pair them directly by document order. This
        # is the common case and sidesteps window-boundary rounding (structural
        # anchors on the two sides don't always land on exactly the same line),
        # which can otherwise push a decision's target block just outside its
        # computed window even though the file-wide counts agree.
        all_draft_glyph_blocks = find_glyph_block_starts(translation_text, glyphs)
        if len(all_draft_glyph_blocks) == len(decisions):
            applies = [
                (draft_line, decision.kind, decision.line, decision.level)
                for decision, draft_line in zip(decisions, all_draft_glyph_blocks)
            ]
        else:
            # Fall back to per-window pairing: some sections of this file may
            # already have been smoothed into prose during translation (no glyph
            # residue left there — nothing to convert, not a failure) while
            # others still carry the literal glyph and need conversion, so a
            # single file-wide count can't be trusted; match locally instead,
            # scoped by the same structural alignment windows the paragraph
            # continuation merge tools use.
            source_tokens = extract_structure(source_text)
            draft_tokens = extract_structure(translation_text)
            windows = build_alignment_windows(source_tokens, draft_tokens, heading_level_sensitive=False)

            decisions_by_window: dict[tuple[int, int | None, int, int | None], list] = {}
            for decision in decisions:
                window = find_alignment_window(windows, decision.line)
                if window is None:
                    continue
                decisions_by_window.setdefault(window, []).append(decision)

            applies = []
            for window, window_decisions in decisions_by_window.items():
                _source_lo, _source_hi, draft_lo, draft_hi = window
                draft_glyph_blocks = find_glyph_block_starts(translation_text, glyphs, draft_lo, draft_hi)
                if not draft_glyph_blocks:
                    # The translation carries no glyph residue in this window (e.g.
                    # the translator already smoothed the ornament into prose);
                    # nothing to convert here, and it is not a failure.
                    continue
                if len(draft_glyph_blocks) != len(window_decisions):
                    result["unresolved"].extend(decision.line for decision in window_decisions)
                    continue
                for decision, draft_line in zip(window_decisions, draft_glyph_blocks):
                    applies.append((draft_line, decision.kind, decision.line, decision.level))

        # Apply from the bottom of the file up so earlier splits don't shift the
        # line numbers of decisions still pending above them.
        applies.sort(key=lambda item: item[0], reverse=True)
        counted_kind = {
            "title": "titles",
            "list_singleton": "list_items_from_singleton",
            "list_split": "list_items_from_split",
            "drop": "dropped",
        }
        for draft_line, kind, source_line, level in applies:
            translation_text, item_count = apply_glyph_decision_at(
                translation_text, draft_line, kind, glyphs, level=level
            )
            if item_count:
                result[counted_kind[kind]] += item_count
            else:
                result["unresolved"].append(source_line)

        result["leftover"] = _count_glyph_occurrences(translation_text, glyphs)

    # Existing, non-glyph headings can also disagree in level with the cleaned
    # source (e.g. a translator's own heading, unrelated to any ornament) —
    # realign every structurally-aligned heading pair to the source's level so
    # both sides share the one level decision (see `realign_heading_levels`).
    cleaned_source_text, _cleanup_info = clean_symbol_glyph_ornaments(source_text, glyphs)
    source_tokens = extract_structure(cleaned_source_text)
    draft_tokens = extract_structure(translation_text)
    translation_text, realigned_count = realign_heading_levels(
        source_tokens, draft_tokens, translation_text
    )
    result["heading_levels_realigned"] = realigned_count

    converted = (
        result["titles"]
        + result["list_items_from_singleton"]
        + result["list_items_from_split"]
        + result["dropped"]
        + result["heading_levels_realigned"]
    )
    if converted and not dry_run:
        translation_path.write_text(translation_text, encoding="utf-8")

    return result


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="英文來源 Markdown 檔案或目錄樹")
    parser.add_argument("translation", type=Path, help="已翻譯 Markdown 檔案或目錄樹")
    parser.add_argument(
        "--glyph",
        dest="glyphs",
        action="append",
        default=None,
        help="視為裝飾符號的字元，可重複指定（預設讀取 style-decisions.json）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只回報將執行的轉換，不寫入檔案")
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

    project_root = Path(__file__).resolve().parents[1]
    glyphs = args.glyphs if args.glyphs is not None else load_symbol_glyphs(project_root)
    if not glyphs:
        print("❌ 找不到裝飾符號字元設定，請用 --glyph 指定，或在 style-decisions.json 的 "
              "document_format.symbol_glyphs 設定")
        return 2

    try:
        pairs = pair_files(args.source, args.translation)
    except ValueError as error:
        print(f"❌ {error}")
        return 2

    file_results = [
        convert_one_pair(source_path, translation_path, glyphs, dry_run=args.dry_run)
        for source_path, translation_path in pairs
    ]
    total_converted = sum(
        result["titles"]
        + result["list_items_from_singleton"]
        + result["list_items_from_split"]
        + result["dropped"]
        for result in file_results
    )
    total_realigned = sum(result["heading_levels_realigned"] for result in file_results)
    total_unresolved = sum(len(result["unresolved"]) for result in file_results)
    total_leftover = sum(result["leftover"] for result in file_results)
    payload = {
        "dry_run": args.dry_run,
        "files_scanned": len(file_results),
        "total_converted": total_converted,
        "total_realigned": total_realigned,
        "total_unresolved": total_unresolved,
        "total_leftover": total_leftover,
        "files": [
            result
            for result in file_results
            if result["candidates"] or result["heading_levels_realigned"]
        ],
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        verb = "將轉換" if args.dry_run else "已轉換"
        for result in payload["files"]:
            converted = (
                result["titles"]
                + result["list_items_from_singleton"]
                + result["list_items_from_split"]
                + result["dropped"]
            )
            if converted:
                print(
                    f"✓ {verb} {converted} 處（標題 {result['titles']}、單一符號清單項目 "
                    f"{result['list_items_from_singleton']}、拆分清單項目 "
                    f"{result['list_items_from_split']}、刪除裝飾符號 {result['dropped']}）: "
                    f"{result['translation']}"
                )
            if result["heading_levels_realigned"]:
                print(
                    f"✓ 標題層級已改對齊來源 {result['heading_levels_realigned']} 處: "
                    f"{result['translation']}"
                )
            for source_line in result["unresolved"]:
                print(f"⚠️  無法對齊譯文位置（來源第 {source_line} 行）: {result['translation']}")
        print(f"共掃描 {payload['files_scanned']} 組檔案，{verb} {total_converted} 處，標題層級改對齊 {total_realigned} 處")
        print(f"轉換後剩餘裝飾符號殘留字元: {total_leftover}")
        if total_unresolved:
            print(f"⚠️  {total_unresolved} 處無法對齊，需人工確認")

    return 1 if total_unresolved or total_leftover else 0


if __name__ == "__main__":
    raise SystemExit(main())
