#!/usr/bin/env python3
"""
章節拆分工具
根據設定檔將 Markdown 內容拆分成多個章節檔案

使用方式：
    # 產生範例設定檔
    python scripts/split_chapters.py --init

    # 根據設定檔拆分章節
    python scripts/split_chapters.py

    # 指定設定檔
    python scripts/split_chapters.py --config my_chapters.json

設定檔格式 (chapters.json)：
{
    "source": "data/markdown/rulebook_pages.md",
    "output_dir": "docs/src/content/docs",
    "chapters": {
        "rules": {
            "title": "核心規則",
            "files": {
                "index": {
                    "title": "規則總覽",
                    "description": "遊戲規則概述",
                    "pages": [1, 10]
                },
                "combat/damage": {
                    "title": "傷害規則",
                    "description": "戰鬥章節中的傷害處理",
                    "pages": [11, 30]
                }
            }
        }
    }
}
"""

import argparse
import json
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

from _image_analysis import (
    image_dominant_color_ratio,
    image_file_size_key,
    image_visual_key,
    is_background_candidate,
)
from _markdown_utils import clean_content, count_page_text_tokens, yaml_safe
from _layout_cleanup import (
    annotate_d66_pair_headings,
    d66_pair_pages,
    d66_pages,
    is_d66_icon,
    is_edge_sliver,
    is_page_ornament,
    repair_d66_tables,
    strip_duplicate_title,
    strip_page_furniture,
    unique_placements,
)


# Top-level section slugs that collide with the built site: `index/index.md` resolves to the
# same route as the home page `index.mdx`, `404` replaces Starlight's not-found page, and
# `_astro`/`pagefind` are directories the build and the search index write into.
RESERVED_SECTION_SLUGS = frozenset({"index", "404", "_astro", "pagefind"})


def validate_section_slugs(chapters: dict) -> None:
    """Reject top-level section slugs that collide with site routes or build output.

    Raises:
        ValueError: a section key is reserved.
    """
    reserved = sorted(RESERVED_SECTION_SLUGS.intersection(chapters))
    if reserved:
        raise ValueError(
            f"章節 slug {', '.join(reserved)} 為保留字，會與網站首頁或建置輸出衝突；"
            "請改用其他 slug（例如書末索引用 book-index）。既有專案可用 "
            "scripts/rename_chapter.py --from <slug> --to <new-slug> 修復"
        )


def load_config(config_path: Path) -> dict:
    """載入設定檔"""
    return json.loads(config_path.read_text(encoding="utf-8"))


def save_config(config: dict, config_path: Path):
    """儲存設定檔"""
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def create_example_config(config_path: Path):
    """建立範例設定檔"""
    example = {
        "source": "data/markdown/your_pdf_pages.md",
        "output_dir": "docs/src/content/docs",
        "clean_patterns": [
            r"\(Order #\d+\)",          # 移除訂單號
            r"Page \d+ of \d+",         # 移除頁碼標記
        ],
        "images": {
            "enabled": True,
            "assets_dir": "docs/src/assets/extracted",
            "repeat_file_size_threshold": 5,
        },
        "chapters": {
            "rules": {
                "title": "核心規則",
                "order": 1,
                "files": {
                    "index": {
                        "title": "規則總覽",
                        "description": "遊戲規則的基本概述",
                        "pages": [1, 10],
                        "order": 0
                    },
                    "basic-moves": {
                        "title": "基本動作",
                        "description": "角色可執行的基本動作",
                        "pages": [11, 20],
                        "order": 1
                    }
                }
            },
            "characters": {
                "title": "角色",
                "order": 2,
                "files": {
                    "index": {
                        "title": "角色創建",
                        "description": "如何創建角色",
                        "pages": [21, 40],
                        "order": 0
                    }
                }
            }
        }
    }
    save_config(example, config_path)
    print(f"✓ 已建立範例設定檔: {config_path}")
    print("\n請編輯設定檔，設定：")
    print("  - source: 來源 Markdown 檔案（使用 _pages.md 版本）")
    print("  - chapters: 章節結構與頁碼範圍")


def extract_pages(content: str) -> dict[int, str]:
    """從含頁碼標記的內容提取各頁"""
    pages = {}
    # A text-empty last page (e.g. only an artifact heading was stripped) ends at its marker;
    # it still owns the images the manifest places on it.
    pattern = r"<!-- PAGE (\d+) -->(?:\n\n|\s*$)(.*?)(?=<!-- PAGE \d+ -->|$)"

    for match in re.finditer(pattern, content, re.DOTALL):
        page_num = int(match.group(1))
        page_content = match.group(2).strip()
        pages[page_num] = page_content

    return pages


def get_page_range(pages: dict[int, str], start: int, end: int) -> str:
    """取得指定頁碼範圍的內容"""
    parts = []
    for page_num in range(start, end + 1):
        if page_num in pages:
            parts.append(pages[page_num])
    return "\n\n".join(parts)

def generate_frontmatter(title: str, description: str = "", order: int | None = None) -> str:
    """生成 Starlight frontmatter"""
    lines = [
        "---",
        f"title: {yaml_safe(title)}",
    ]
    if description:
        lines.append(f"description: {yaml_safe(description)}")
    if order is not None:
        lines.append("sidebar:")
        lines.append(f"  order: {order}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def infer_source_stem(source_path: Path) -> str:
    """從 _pages.md 來源檔推回 PDF stem。"""
    stem = source_path.stem
    if stem.endswith("_pages"):
        return stem[:-6]
    return stem


def normalize_files(files: dict) -> dict:
    """Convert flat slash-path entries into nested recursive structure.

    Entries like ``"combat/actions": {"pages": [5, 7]}`` become nested:
    ``"combat": {"title": "combat", "files": {"actions": {"pages": [5, 7]}}}``.

    Entries without slashes are kept as-is.  Group nodes created by
    normalisation get ``title`` set to the raw slug and no ``order``.

    Raises:
        ValueError: a key is used both as a flat leaf and as a slash-nested
            group prefix (e.g. ``"combat"`` and ``"combat/actions"``), since
            a single key cannot be both a leaf and a group.
    """
    result: dict = {}
    for key, entry in files.items():
        if "/" in key and "pages" in entry:
            parts = key.split("/")
            parent = parts[0]
            child = "/".join(parts[1:])
            if parent in result and "files" not in result[parent]:
                raise ValueError(
                    f"Key collision in chapter files: '{parent}' is used as a "
                    f"flat leaf entry and as a group prefix (from '{key}')"
                )
            if parent not in result:
                result[parent] = {"title": parent, "files": {}}
            result[parent]["files"][child] = entry
        else:
            if key in result and "files" in result[key]:
                raise ValueError(
                    f"Key collision in chapter files: '{key}' is used as a "
                    f"flat leaf entry and as a group prefix (from a nested key)"
                )
            result[key] = entry
    # Recurse for multi-level slash paths
    for key, entry in result.items():
        if "files" in entry:
            entry["files"] = normalize_files(entry["files"])
    return result


def resolve_config(chapter_key: str, chapter: dict, top_level: dict) -> dict:
    """Resolve per-chapter config with fallback to top-level defaults.

    Returns a dict with keys: source, clean_patterns, images.
    Raises ValueError if no source can be determined.
    """
    source = chapter.get("source", top_level.get("source"))
    if not source:
        raise ValueError(
            f"Chapter '{chapter_key}' has no 'source' and no top-level 'source' defined"
        )
    return {
        "source": source,
        "clean_patterns": chapter.get(
            "clean_patterns", top_level.get("clean_patterns", [])
        ),
        "images": chapter.get("images", top_level.get("images", {})),
    }


def write_meta_yml(directory: Path, entry: dict) -> None:
    """Write a ``_meta.yml`` file for a group node directory.

    Generates ``label`` from *entry["title"]* and ``order`` from
    *entry.get("order")*.  The file is compatible with the
    ``starlight-auto-sidebar`` plugin.
    """
    title = entry.get("title", directory.name)
    lines: list[str] = [f"label: {yaml_safe(title)}"]
    order = entry.get("order")
    if order is not None:
        lines.append(f"order: {order}")
    (directory / "_meta.yml").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def load_image_manifest(config: dict, project_root: Path) -> tuple[list[dict], Path | None, dict]:
    """載入圖片 manifest 與設定。"""
    image_config = config.get("images", {})
    policy = {
        "repeat_file_size_threshold": image_config.get("repeat_file_size_threshold", image_config.get("repeat_size_threshold", 5)),
        "repeat_visual_threshold": image_config.get("repeat_visual_threshold", 3),
        "background_min_coverage_ratio": image_config.get("background_min_coverage_ratio", 0.6),
        "background_min_text_tokens": image_config.get("background_min_text_tokens", 80),
        "background_edge_margin_ratio": image_config.get("background_edge_margin_ratio", 0.08),
        "background_edge_min_area_ratio": image_config.get("background_edge_min_area_ratio", 0.18),
        "background_edge_min_span_ratio": image_config.get("background_edge_min_span_ratio", 0.7),
        "background_dominant_color_ratio_threshold": image_config.get("background_dominant_color_ratio_threshold", 0.85),
    }
    if image_config.get("enabled", True) is False:
        return [], None, policy

    source_path = Path(config["source"])
    default_manifest = (
        project_root
        / "data"
        / "markdown"
        / "images"
        / infer_source_stem(source_path)
        / "manifest.json"
    )
    manifest_path = project_root / image_config["manifest"] if "manifest" in image_config else default_manifest

    if not manifest_path.exists():
        return [], None, policy

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return (
        payload.get("images", []),
        manifest_path,
        policy,
    )


def build_page_text_stats(pages: dict[int, str], clean_patterns: list[str]) -> dict[int, dict[str, int]]:
    """建立每頁文字量統計。"""
    stats: dict[int, dict[str, int]] = {}
    for page_num, content in pages.items():
        cleaned = clean_content(content, clean_patterns)
        stats[page_num] = {
            "text_tokens": count_page_text_tokens(cleaned),
            "char_count": len(cleaned),
        }
    return stats


def group_images_by_page(
    images: list[dict],
    page_text_stats: dict[int, dict[str, int]],
    policy: dict,
) -> tuple[dict[int, list[dict]], int]:
    """依頁碼整理圖片，並略過符合背景條件的圖片。"""
    repeat_file_size_threshold = int(policy.get("repeat_file_size_threshold", 0) or 0)
    repeat_visual_threshold = int(policy.get("repeat_visual_threshold", 0) or 0)
    background_dominant_color_ratio_threshold = float(
        policy.get("background_dominant_color_ratio_threshold", 0.85)
    )

    images = unique_placements(images)
    dice_pages = d66_pages(images)
    pair_pages = d66_pair_pages(images)
    ornament_counts = Counter(
        (image.get("visual_hash"), round(float(image.get("width") or 0)), round(float(image.get("height") or 0)))
        for image in images if image.get("visual_hash")
    )
    size_counts = Counter(
        size_key
        for image in images
        if (size_key := image_file_size_key(image)) is not None
    )
    visual_counts = Counter(
        visual_key
        for image in images
        if (visual_key := image_visual_key(image)) is not None
    )

    page_images: dict[int, list[dict]] = defaultdict(list)
    skipped = 0
    for image in images:
        ornament_key = (image.get("visual_hash"), round(float(image.get("width") or 0)), round(float(image.get("height") or 0)))
        if is_page_ornament(image, ornament_counts[ornament_key]) or is_edge_sliver(image) or (
            int(image["page"]) in dice_pages and is_d66_icon(image)
        ) or (
            int(image["page"]) in pair_pages
            and 13 <= float(image.get("width") or 0) <= 15
            and 13 <= float(image.get("height") or 0) <= 15
        ):
            skipped += 1
            continue
        size_key = image_file_size_key(image)
        visual_key = image_visual_key(image)
        dominant_color_ratio = image_dominant_color_ratio(image)
        is_background = is_background_candidate(image, page_text_stats, policy)

        if (
            is_background
            and
            repeat_file_size_threshold > 0
            and size_key is not None
            and size_counts[size_key] >= repeat_file_size_threshold
        ):
            skipped += 1
            continue

        if (
            is_background
            and
            repeat_visual_threshold > 0
            and visual_key is not None
            and visual_counts[visual_key] >= repeat_visual_threshold
        ):
            skipped += 1
            continue

        if (
            is_background
            and
            dominant_color_ratio is not None
            and dominant_color_ratio >= background_dominant_color_ratio_threshold
        ):
            skipped += 1
            continue

        page = int(image["page"])
        page_images[page].append(image)

    for images_on_page in page_images.values():
        images_on_page.sort(
            key=lambda image: (
                float(image["y"]) if image.get("y") is not None else float("inf"),
                float(image["x"]) if image.get("x") is not None else float("inf"),
                image["filename"],
            )
        )

    return dict(page_images), skipped


def resolve_assets_dir(config: dict, project_root: Path) -> Path:
    """決定輸出圖片資產目錄。"""
    output_dir = project_root / config["output_dir"]
    image_config = config.get("images", {})
    assets_dir = image_config.get("assets_dir")
    if assets_dir:
        return project_root / assets_dir
    return output_dir.parents[1] / "assets"


def copy_image_to_assets(
    image: dict,
    project_root: Path,
    assets_dir: Path,
    source_slug: str,
) -> Path:
    """將圖片複製到 docs assets。"""
    source_image_path = project_root / "data" / "markdown" / image["path"]
    target_path = assets_dir / source_slug / image["filename"]
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_image_path, target_path)
    return target_path


def build_image_markdown(image: dict, target_path: Path, markdown_path: Path) -> str:
    """生成 Markdown 圖片引入。"""
    relative_path = Path(os.path.relpath(target_path, markdown_path.parent)).as_posix()
    alt_text = f"第 {image['page']} 頁插圖"
    return f"![{alt_text}]({relative_path})"


def build_section_content(
    pages: dict[int, str],
    start: int,
    end: int,
    clean_patterns: list[str],
    page_images: dict[int, list[dict]],
    output_path: Path,
    project_root: Path,
    assets_dir: Path,
    source_slug: str,
) -> tuple[str, int]:
    """組合章節內容與對應圖片。"""
    parts = []
    copied_count = 0

    for page_num in range(start, end + 1):
        if page_num not in pages:
            continue

        page_content = strip_page_furniture(clean_content(pages[page_num], clean_patterns))
        images = page_images.get(page_num, [])
        image_lines = []
        for image in images:
            target_path = copy_image_to_assets(image, project_root, assets_dir, source_slug)
            image_lines.append(build_image_markdown(image, target_path, output_path))
            copied_count += 1

        block_parts = [part for part in [page_content, "\n\n".join(image_lines)] if part]
        if block_parts:
            parts.append("\n\n".join(block_parts))

    return "\n\n".join(parts).strip(), copied_count


_page_cache: dict[str, dict[int, str]] = {}
_manifest_cache: dict[tuple[str, str], tuple[list[dict], Path | None, dict]] = {}


def _load_pages_cached(source_path: Path) -> dict[int, str]:
    """Load and cache pages from a _pages.md file."""
    key = str(source_path)
    if key not in _page_cache:
        content = source_path.read_text(encoding="utf-8")
        _page_cache[key] = extract_pages(content)
    return _page_cache[key]


def _load_manifest_cached(
    source: str, images_config: dict, project_root: Path
) -> tuple[list[dict], Path | None, dict]:
    """Load and cache image manifest for a source."""
    config_key = json.dumps(images_config, sort_keys=True, ensure_ascii=False)
    cache_key = (source, config_key)
    if cache_key not in _manifest_cache:
        dummy_config = {"source": source, "images": images_config}
        _manifest_cache[cache_key] = load_image_manifest(dummy_config, project_root)
    return _manifest_cache[cache_key]


def process_files(
    files: dict,
    output_dir: Path,
    pages: dict[int, str],
    clean_patterns: list[str],
    page_images: dict[int, list[dict]],
    project_root: Path,
    assets_dir: Path,
    source_slug: str,
) -> tuple[int, int]:
    """Recursively process files dict. Returns (total_files, total_images)."""
    total_files = 0
    total_images = 0
    for key, entry in files.items():
        if "pages" in entry:
            # Leaf node — write .md file
            title = entry["title"]
            description = entry.get("description", "")
            order = entry.get("order")
            start_page, end_page = entry["pages"]
            output_path = output_dir / f"{key}.md"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            section_content, image_count = build_section_content(
                pages, start_page, end_page, clean_patterns,
                page_images, output_path, project_root, assets_dir, source_slug,
            )
            frontmatter = generate_frontmatter(title, description, order)
            section_content = strip_duplicate_title(section_content, title)
            full_content = frontmatter + "\n" + section_content
            output_path.write_text(full_content, encoding="utf-8")
            char_count = len(section_content)
            image_note = f", {image_count} 張圖" if image_count else ""
            print(
                f"   ✓ {key}.md - {title} "
                f"(p.{start_page}-{end_page}, {char_count:,} 字{image_note})"
            )
            total_files += 1
            total_images += image_count
        elif "files" in entry:
            # Group node — create subdirectory + _meta.yml, recurse
            sub_dir = output_dir / key
            sub_dir.mkdir(parents=True, exist_ok=True)
            write_meta_yml(sub_dir, entry)
            sub_files, sub_images = process_files(
                entry["files"], sub_dir, pages, clean_patterns,
                page_images, project_root, assets_dir, source_slug,
            )
            total_files += sub_files
            total_images += sub_images
        else:
            raise ValueError(f"Invalid entry '{key}': must have 'pages' or 'files'")
    return total_files, total_images


def split_chapters(config: dict, project_root: Path):
    """根據設定拆分章節（支援多 source 與遞迴 files）"""
    output_dir = project_root / config.get("output_dir", "docs/src/content/docs")
    if config.get("mode") == "bilingual":
        output_dir = output_dir / "bilingual"

    # Clear caches for fresh run
    _page_cache.clear()
    _manifest_cache.clear()

    validate_section_slugs(config["chapters"])

    total_files = 0
    total_images = 0

    for section_name, section_config in config["chapters"].items():
        # Resolve per-chapter config with fallback
        ch_config = resolve_config(section_name, section_config, config)
        source_path = project_root / ch_config["source"]
        clean_patterns = ch_config["clean_patterns"]
        images_config = ch_config["images"]

        if not source_path.exists():
            print(f"❌ 找不到來源檔案: {source_path}")
            sys.exit(1)

        # Load pages (cached)
        pages = _load_pages_cached(source_path)

        # Load images (cached)
        page_text_stats = build_page_text_stats(pages, clean_patterns)
        manifest_images, manifest_path, image_policy = _load_manifest_cached(
            ch_config["source"], images_config, project_root
        )
        for page_num in d66_pages(manifest_images):
            if page_num in pages:
                pages[page_num], _ = repair_d66_tables(pages[page_num])
        for page_num, first_die in d66_pair_pages(manifest_images).items():
            if page_num in pages:
                pages[page_num], _ = annotate_d66_pair_headings(pages[page_num], first_die)
        page_images, skipped = group_images_by_page(
            manifest_images, page_text_stats, image_policy
        )
        assets_dir = resolve_assets_dir(
            {"output_dir": config.get("output_dir", "docs/src/content/docs"), "images": images_config},
            project_root,
        )
        source_slug = infer_source_stem(Path(ch_config["source"]))

        section_title = section_config.get("title", section_name)
        print(f"\n📁 {section_title} ({section_name}/) [source: {ch_config['source']}]")

        # Create section directory + _meta.yml
        section_dir = output_dir / section_name
        section_dir.mkdir(parents=True, exist_ok=True)
        write_meta_yml(section_dir, section_config)

        # Normalize flat slash-paths to recursive structure
        files = normalize_files(section_config.get("files", {}))

        # Process recursively
        sec_files, sec_images = process_files(
            files, section_dir, pages, clean_patterns,
            page_images, project_root, assets_dir, source_slug,
        )
        total_files += sec_files
        total_images += sec_images

    print("-" * 50)
    print(f"✅ 完成！共產生 {total_files} 個檔案，插入 {total_images} 張圖片")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="根據設定檔將 Markdown 內容拆分成多個章節檔案")
    parser.add_argument("--init", action="store_true", help="建立範例設定檔（chapters.json）並結束")
    parser.add_argument("--config", type=Path, default=None, help="指定設定檔路徑（預設: chapters.json）")
    return parser.parse_args()


def main():
    project_root = Path(__file__).resolve().parents[1]
    default_config = project_root / "chapters.json"
    args = parse_args()

    if args.init:
        create_example_config(default_config)
        return

    config_path = args.config if args.config is not None else default_config

    if not config_path.exists():
        print(f"❌ 找不到設定檔: {config_path}")
        print("   請先執行: python scripts/split_chapters.py --init")
        sys.exit(1)

    config = load_config(config_path)
    try:
        split_chapters(config, project_root)
    except ValueError as exc:
        print(f"❌ {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
