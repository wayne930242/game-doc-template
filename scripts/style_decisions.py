#!/usr/bin/env python3
"""Create and update style-decisions.json via validated script commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _style_decisions_lib import (
    DEFAULT_STYLE_DECISIONS,
    DEFAULT_STYLE_DECISIONS_SCHEMA,
    TRANSLATION_MODE_OPTIONS,
    deep_merge,
    default_style_decisions_payload,
    load_and_validate_style_decisions,
    load_style_decisions,
    save_style_decisions,
)


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"無法解析布林值: {value}")


def parse_bounded_number(value: str, low: float, high: float, label: str) -> str:
    normalized = value.strip()
    try:
        number = float(normalized)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{label} 必須是數字: {value}") from None
    if not low <= number <= high:
        raise argparse.ArgumentTypeError(f"{label} 必須介於 {low:g} 到 {high:g} 之間: {value}")
    return normalized


def parse_overlay(value: str) -> str:
    """遮罩不透明度，0 表示純色背景不加遮罩。"""
    return parse_bounded_number(value, 0.0, 1.0, "overlay")


def parse_hue(value: str) -> str:
    """背景色相 --bg-h，單位為角度。"""
    return parse_bounded_number(value, 0.0, 360.0, "bg-h")


def parse_lightness(value: str) -> str:
    """背景亮度 --bg-l，統一正規化為百分比字串。"""
    normalized = parse_bounded_number(value.replace("%", ""), 0.0, 100.0, "bg-l")
    number = float(normalized)
    rendered = f"{number:g}"
    return f"{rendered}%"


def parse_credit_entry(value: str) -> dict[str, str]:
    if ":" not in value:
        raise argparse.ArgumentTypeError("credits entry 必須使用 '職責:姓名' 格式")
    role, name = value.split(":", 1)
    role = role.strip()
    name = name.strip()
    if not role or not name:
        raise argparse.ArgumentTypeError("credits entry 必須同時包含職責與姓名")
    return {"role": role, "name": name}


def load_existing_or_default(style_path: Path, schema_path: Path) -> dict[str, Any]:
    existing = load_style_decisions(style_path)
    if existing is None:
        return default_style_decisions_payload()
    return load_and_validate_style_decisions(style_path, schema_path=schema_path)


def merge_and_save(
    style_path: Path,
    schema_path: Path,
    patch: dict[str, Any],
) -> dict[str, Any]:
    payload = load_existing_or_default(style_path, schema_path)
    merged = deep_merge(payload, patch)
    return save_style_decisions(style_path, merged, schema_path=schema_path)


def cmd_init(args: argparse.Namespace) -> None:
    if args.style.exists() and not args.force:
        load_and_validate_style_decisions(args.style, schema_path=args.schema)
        print(f"✓ style decisions 已存在且通過驗證: {args.style}")
        return

    payload = default_style_decisions_payload()
    payload["_meta"]["description"] = args.description
    save_style_decisions(args.style, payload, schema_path=args.schema)
    print(f"✓ 已初始化 style decisions: {args.style}")


def cmd_merge_json(args: argparse.Namespace) -> None:
    if bool(args.patch) == bool(args.patch_file):
        raise SystemExit("❌ 請擇一提供 --patch 或 --patch-file")

    patch_text = args.patch
    if args.patch_file:
        patch_text = args.patch_file.read_text(encoding="utf-8")

    patch = json.loads(patch_text)
    if not isinstance(patch, dict):
        raise SystemExit("❌ patch 必須是 JSON object")

    merge_and_save(args.style, args.schema, patch)
    print(f"✓ 已更新 style decisions: {args.style}")


def cmd_set_repository(args: argparse.Namespace) -> None:
    patch: dict[str, Any] = {"repository": {}}
    for key in ("name", "slug", "visibility", "url", "show_on_homepage"):
        value = getattr(args, key)
        if value is not None:
            patch["repository"][key] = value
    if not patch["repository"]:
        raise SystemExit("❌ set-repository 至少需要一個欄位")
    merge_and_save(args.style, args.schema, patch)
    print(f"✓ 已更新 repository 設定: {args.style}")


def cmd_set_deployment(args: argparse.Namespace) -> None:
    patch: dict[str, Any] = {"deployment": {}}
    for key in ("target", "base_path"):
        value = getattr(args, key)
        if value is not None:
            patch["deployment"][key] = value
    if not patch["deployment"]:
        raise SystemExit("❌ set-deployment 至少需要一個欄位")
    merge_and_save(args.style, args.schema, patch)
    print(f"✓ 已更新 deployment 設定: {args.style}")


def cmd_set_site(args: argparse.Namespace) -> None:
    patch: dict[str, Any] = {"site": {}}
    for key in ("title", "description", "tagline", "intro"):
        value = getattr(args, key)
        if value is not None:
            patch["site"][key] = value
    if not patch["site"]:
        raise SystemExit("❌ set-site 至少需要一個欄位")
    merge_and_save(args.style, args.schema, patch)
    print(f"✓ 已更新網站設定: {args.style}")


def cmd_set_images(args: argparse.Namespace) -> None:
    patch: dict[str, Any] = {"images": {}}
    for key in ("preserve_images", "hero", "background", "og"):
        value = getattr(args, key)
        if value is not None:
            patch["images"][key] = value
    if not patch["images"]:
        raise SystemExit("❌ set-images 至少需要一個欄位")
    merge_and_save(args.style, args.schema, patch)
    print(f"✓ 已更新圖片設定: {args.style}")


def cmd_set_theme(args: argparse.Namespace) -> None:
    patch: dict[str, Any] = {"theme": {}}
    for key in ("mode", "overlay", "palette", "bg_h", "bg_l"):
        value = getattr(args, key)
        if value is not None:
            patch["theme"][key] = value
    if not patch["theme"]:
        raise SystemExit("❌ set-theme 至少需要一個欄位")
    merge_and_save(args.style, args.schema, patch)
    print(f"✓ 已更新主題設定: {args.style}")


def build_document_format_patch(args: argparse.Namespace) -> dict[str, Any]:
    entry: dict[str, Any] = {}

    if args.layout_profile is not None:
        entry["layout_profile"] = args.layout_profile
    if args.page_text_engine is not None:
        entry["page_text_engine"] = args.page_text_engine
    if args.pymupdf_sort_text is not None:
        entry["pymupdf_sort_text"] = args.pymupdf_sort_text
    if args.watermarks:
        entry["watermarks"] = args.watermarks

    aside_mapping = {
        name: value
        for name, value in (
            ("note", args.aside_note),
            ("tip", args.aside_tip),
            ("caution", args.aside_caution),
            ("danger", args.aside_danger),
        )
        if value is not None
    }
    if aside_mapping:
        entry["aside_mapping"] = aside_mapping

    component_usage = {
        name: value
        for name, value in (
            ("cards", args.cards_usage),
            ("tabs", args.tabs_usage),
        )
        if value is not None
    }
    if component_usage:
        entry["component_usage"] = component_usage

    table_conventions = {
        name: value
        for name, value in (
            ("tables", args.tables_convention),
            ("dice_tables", args.dice_tables_convention),
        )
        if value is not None
    }
    if table_conventions:
        entry["table_conventions"] = table_conventions

    if not entry:
        raise SystemExit("❌ set-document-format 至少需要一個欄位")

    if args.document_key:
        return {"document_format": {"documents": {args.document_key: entry}}}
    return {"document_format": entry}


def cmd_set_document_format(args: argparse.Namespace) -> None:
    patch = build_document_format_patch(args)
    merge_and_save(args.style, args.schema, patch)
    print(f"✓ 已更新文件格式設定: {args.style}")


def cmd_set_translation_mode(args: argparse.Namespace) -> None:
    patch = {
        "translation_mode": {
            "mode": args.mode,
            "options": TRANSLATION_MODE_OPTIONS,
        }
    }
    if args.reason is not None:
        patch["translation_mode"]["reason"] = args.reason
    merge_and_save(args.style, args.schema, patch)
    print(f"✓ 已更新翻譯模式: {args.style}")


def cmd_add_translation_note(args: argparse.Namespace) -> None:
    payload = load_existing_or_default(args.style, args.schema)
    translation_notes = payload.setdefault("translation_notes", {})
    bucket: list[dict[str, str]]
    if args.document_key:
        documents = translation_notes.setdefault("documents", {})
        bucket = documents.setdefault(args.document_key, [])
    else:
        bucket = translation_notes.setdefault("global", [])

    if not isinstance(bucket, list):
        raise SystemExit("❌ translation_notes 結構不正確，請先修正 style-decisions.json")

    entry = {"note": args.note}
    if args.key is not None:
        entry["key"] = args.key
    if args.topic is not None:
        entry["topic"] = args.topic

    replaced = False
    if args.key is not None:
        for idx, existing in enumerate(bucket):
            if isinstance(existing, dict) and existing.get("key") == args.key:
                bucket[idx] = entry
                replaced = True
                break
    if not replaced:
        bucket.append(entry)

    save_style_decisions(args.style, payload, schema_path=args.schema)
    print(f"✓ 已更新翻譯備註: {args.style}")


def cmd_set_copyright(args: argparse.Namespace) -> None:
    patch: dict[str, Any] = {"copyright": {}}
    if args.text is not None:
        patch["copyright"]["text"] = args.text
    if args.show_on_homepage is not None:
        patch["copyright"]["show_on_homepage"] = args.show_on_homepage
    if not patch["copyright"]:
        raise SystemExit("❌ set-copyright 至少需要一個欄位")
    merge_and_save(args.style, args.schema, patch)
    print(f"✓ 已更新版權設定: {args.style}")


def cmd_set_credits(args: argparse.Namespace) -> None:
    patch: dict[str, Any] = {"credits": {}}
    if args.entry:
        patch["credits"]["entries"] = args.entry
    if args.show_on_homepage is not None:
        patch["credits"]["show_on_homepage"] = args.show_on_homepage
    if not patch["credits"]:
        raise SystemExit("❌ set-credits 至少需要一個欄位")
    merge_and_save(args.style, args.schema, patch)
    print(f"✓ 已更新製作名單: {args.style}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage style-decisions.json with schema validation.")
    parser.add_argument("--style", type=Path, default=DEFAULT_STYLE_DECISIONS)
    parser.add_argument("--schema", type=Path, default=DEFAULT_STYLE_DECISIONS_SCHEMA)

    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialize style-decisions.json if missing.")
    p_init.add_argument("--force", action="store_true")
    p_init.add_argument(
        "--description",
        default="風格決定記錄 - 翻譯用語選擇與原因",
    )
    p_init.set_defaults(func=cmd_init)

    p_merge = sub.add_parser("merge-json", help="Deep-merge a JSON patch into style-decisions.json.")
    p_merge.add_argument("--patch")
    p_merge.add_argument("--patch-file", type=Path)
    p_merge.set_defaults(func=cmd_merge_json)

    p_repo = sub.add_parser("set-repository", help="Update repository metadata.")
    p_repo.add_argument("--name")
    p_repo.add_argument("--slug")
    p_repo.add_argument("--visibility", choices=("public", "private"))
    p_repo.add_argument("--url")
    p_repo.add_argument("--show-on-homepage", type=parse_bool)
    p_repo.set_defaults(func=cmd_set_repository)

    p_deploy = sub.add_parser("set-deployment", help="Update deployment target and base path.")
    p_deploy.add_argument("--target", choices=("github-pages", "root"))
    p_deploy.add_argument("--base-path", dest="base_path", help="e.g. /repo-name for GitHub Pages, or empty string for root deploys")
    p_deploy.set_defaults(func=cmd_set_deployment)

    p_site = sub.add_parser("set-site", help="Update homepage site metadata.")
    p_site.add_argument("--title")
    p_site.add_argument("--description")
    p_site.add_argument("--tagline")
    p_site.add_argument("--intro")
    p_site.set_defaults(func=cmd_set_site)

    p_images = sub.add_parser("set-images", help="Update image-related settings.")
    p_images.add_argument("--preserve-images", type=parse_bool)
    p_images.add_argument("--hero")
    p_images.add_argument("--background")
    p_images.add_argument("--og")
    p_images.set_defaults(func=cmd_set_images)

    p_theme = sub.add_parser("set-theme", help="Update theme settings recorded for docs/src/styles/custom.css.")
    p_theme.add_argument("--mode", help="主題模式，例：dark-forced")
    p_theme.add_argument(
        "--overlay",
        type=parse_overlay,
        help="背景遮罩不透明度 0-1，對應 --overlay-opacity；純色背景請填 0",
    )
    p_theme.add_argument("--palette", help="色票說明，例：primary=330 粉、secondary=180 青")
    p_theme.add_argument("--bg-h", type=parse_hue, help="背景色相 --bg-h，0-360")
    p_theme.add_argument(
        "--bg-l",
        type=parse_lightness,
        help="背景亮度 --bg-l，深色模式建議 5%%-16%%；可填 6 或 6%%",
    )
    p_theme.set_defaults(func=cmd_set_theme)

    p_format = sub.add_parser("set-document-format", help="Update document format decisions.")
    p_format.add_argument("--document-key")
    p_format.add_argument("--layout-profile", choices=("auto", "single-column", "double-column"))
    p_format.add_argument(
        "--page-text-engine",
        choices=("auto", "ocr", "pymupdf", "markitdown", "opendataloader"),
    )
    p_format.add_argument(
        "--pymupdf-sort-text",
        type=parse_bool,
        help="pymupdf 引擎是否依幾何位置排序文字（true/false）",
    )
    p_format.add_argument(
        "--watermark",
        dest="watermarks",
        action="append",
        help="要從輸出 Markdown 移除的浮水印字串，可重複指定",
    )
    p_format.add_argument("--aside-note")
    p_format.add_argument("--aside-tip")
    p_format.add_argument("--aside-caution")
    p_format.add_argument("--aside-danger")
    p_format.add_argument("--cards-usage")
    p_format.add_argument("--tabs-usage")
    p_format.add_argument("--tables-convention")
    p_format.add_argument("--dice-tables-convention")
    p_format.set_defaults(func=cmd_set_document_format)

    p_mode = sub.add_parser("set-translation-mode", help="Update translation mode.")
    p_mode.add_argument("--mode", required=True, choices=("full", "summary", "bilingual"))
    p_mode.add_argument("--reason")
    p_mode.set_defaults(func=cmd_set_translation_mode)

    p_note = sub.add_parser("add-translation-note", help="Add or replace a translation note.")
    p_note.add_argument("--document-key")
    p_note.add_argument("--key")
    p_note.add_argument("--topic")
    p_note.add_argument("--note", required=True)
    p_note.set_defaults(func=cmd_add_translation_note)

    p_copy = sub.add_parser("set-copyright", help="Update copyright settings.")
    p_copy.add_argument("--text")
    p_copy.add_argument("--show-on-homepage", type=parse_bool)
    p_copy.set_defaults(func=cmd_set_copyright)

    p_credits = sub.add_parser("set-credits", help="Update credits entries.")
    p_credits.add_argument("--entry", type=parse_credit_entry, action="append")
    p_credits.add_argument("--show-on-homepage", type=parse_bool)
    p_credits.set_defaults(func=cmd_set_credits)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
