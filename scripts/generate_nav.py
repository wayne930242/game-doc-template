#!/usr/bin/env python3
"""Generate homepage index.mdx and update astro.config.mjs sidebar from chapters.json."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from _markdown_utils import yaml_safe
from site_config import deployment_base_path, update_astro_site_base, update_astro_site_title
from split_chapters import normalize_files, validate_section_slugs

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHAPTERS_FILE = PROJECT_ROOT / "chapters.json"
STYLE_FILE = PROJECT_ROOT / "style-decisions.json"
INDEX_FILE = PROJECT_ROOT / "docs" / "src" / "content" / "docs" / "index.mdx"
ASTRO_CONFIG = PROJECT_ROOT / "docs" / "astro.config.mjs"
# Starlight binds `hero.image.file` to Astro's image() helper: emitting the key
# when the asset is missing breaks `bun run build` with [ImageNotFound].
HERO_IMAGE = PROJECT_ROOT / "docs" / "src" / "assets" / "hero.jpg"
HERO_IMAGE_REF = "../../assets/hero.jpg"


class SidebarPatchError(RuntimeError):
    """Raised when the sidebar array cannot be located in astro.config.mjs."""


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sorted_sections(chapters: dict) -> list[tuple[str, dict]]:
    """Return chapter sections sorted by order."""
    return sorted(chapters.items(), key=lambda x: x[1].get("order", 9999))


def sorted_files(section: dict) -> list[tuple[str, dict]]:
    """Return files in a section sorted by order."""
    return sorted(section.get("files", {}).items(), key=lambda x: x[1].get("order", 9999))


def mode_prefix(mode: str) -> str:
    return "bilingual/" if mode == "bilingual" else ""


def _leaf_count(files: dict, limit: int = 2) -> int:
    """Count leaf nodes recursively, stopping once *limit* is reached."""
    count = 0
    for _key, entry in sorted(files.items(), key=lambda x: x[1].get("order", 9999)):
        if "files" in entry:
            count += _leaf_count(entry["files"], max(1, limit - count))
        else:
            count += 1
        if count >= limit:
            return count
    return count


def _first_leaf_slug(base_slug: str, section: dict) -> str:
    """Recursively find the slug of the first leaf node under *section*."""
    files = sorted_files(section)
    if not files:
        return base_slug
    filename, config = files[0]
    if "files" in config:
        return _first_leaf_slug(f"{base_slug}/{filename}", config)
    if filename == "index":
        return base_slug
    return f"{base_slug}/{filename}"


def section_primary_slug(section_slug: str, section: dict, mode: str = "zh_only") -> str:
    """Return the primary doc slug for a section (recursive for nested files)."""
    prefix = mode_prefix(mode)
    return f"{prefix}{_first_leaf_slug(section_slug, section)}"


def section_primary_href(section_slug: str, section: dict, mode: str = "zh_only", base_path: str = "") -> str:
    """Return the primary doc href for a section, including the deployment base path if set."""
    return f"{base_path}/{section_primary_slug(section_slug, section, mode)}/"


def first_file_description(section: dict) -> str:
    """Get description from the first leaf file in section (recursive)."""
    for _fname, cfg in sorted_files(section):
        if "files" in cfg:
            desc = first_file_description(cfg)
            if desc:
                return desc
        else:
            desc = cfg.get("description", "")
            if desc:
                return desc
    return ""


# --- Index page generation ---

def generate_index(chapters: dict, style: dict, mode: str = "zh_only", hero_image: Path | None = None) -> str:
    base_path = deployment_base_path(style)
    sections = sorted_sections(chapters)
    first_slug = sections[0][0] if sections else "reference"
    second_slug = sections[1][0] if len(sections) > 1 else first_slug

    # Hero actions point to first two sections
    first_title = sections[0][1]["title"] if sections else "開始閱讀"
    second_title = sections[1][1]["title"] if len(sections) > 1 else ""
    first_href = section_primary_href(first_slug, sections[0][1], mode, base_path) if sections else f"{base_path}/reference/"
    second_href = (
        section_primary_href(second_slug, sections[1][1], mode, base_path)
        if len(sections) > 1
        else first_href
    )

    site = style.get("site", {})
    title = site.get("title", "遊戲規則文件")
    description = site.get("description", "遊戲規則文件首頁")
    tagline = site.get("tagline", "快速查閱核心規則、角色、裝備與主持指南")
    intro = site.get("intro", "本站整理遊戲規則的主要章節，提供易讀、可搜尋的文件版本，方便跑團前準備與遊戲中快速查表。")

    lines = [
        "---",
        f"title: {yaml_safe(title)}",
        f"description: {yaml_safe(description)}",
        "template: splash",
        "hero:",
        f"  tagline: {yaml_safe(tagline)}",
    ]
    if (hero_image or HERO_IMAGE).exists():
        lines += [
            "  image:",
            f"    file: {HERO_IMAGE_REF}",
        ]
    lines += [
        "  actions:",
        f"    - text: {yaml_safe(first_title)}",
        f"      link: {first_href}",
        "      icon: right-arrow",
    ]
    if second_title:
        lines += [
            f"    - text: {yaml_safe(second_title)}",
            f"      link: {second_href}",
            "      icon: document",
            "      variant: minimal",
        ]
    lines += [
        "sidebar:",
        "  order: 0",
        "---",
        "",
        "import { CardGrid, LinkCard } from '@astrojs/starlight/components';",
        "",
        "## 內容簡介",
        "",
        intro,
        "",
        "## 快速導航",
        "",
        "<CardGrid>",
    ]

    for slug, section in sections:
        title = section["title"]
        desc = first_file_description(section)
        href = section_primary_href(slug, section, mode, base_path)
        lines.append(f'  <LinkCard title="{title}" href="{href}" description="{desc}" />')

    lines += [
        "</CardGrid>",
        "",
        "---",
        "",
    ]

    copyright_cfg = style.get("copyright", {})
    credits_cfg = style.get("credits", {})
    has_copyright = copyright_cfg.get("show_on_homepage") and copyright_cfg.get("text")
    credit_entries = credits_cfg.get("entries", [])
    acknowledgements = credits_cfg.get("acknowledgements", [])
    has_credits = credits_cfg.get("show_on_homepage") and (credit_entries or acknowledgements)

    if has_copyright:
        lines += [
            "## 版權宣告",
            "",
            copyright_cfg["text"],
            "",
        ]
    if has_credits:
        lines += ["## 製作名單", ""]
        if credit_entries:
            lines += ["| 職責 | 人員 |", "| --- | --- |"]
            for entry in credit_entries:
                role = entry.get("role", "")
                name = entry.get("name", "")
                lines.append(f"| {role} | {name} |")
            lines.append("")
        if acknowledgements:
            lines += ["### 致謝", ""]
            for ack in acknowledgements:
                lines.append(f"- {ack['name']}：{ack['note']}")
            lines.append("")
    if not has_copyright and not has_credits:
        lines += [
            "## 聲明",
            "",
            "本站內容為規則整理與翻譯文件，僅供個人遊戲參考使用。原文著作權與商標權歸原作者與出版方所有，請支持正版。",
        ]

    # Add repo link if configured
    repo = style.get("repository", {})
    if repo.get("show_on_homepage") and repo.get("url"):
        url = repo["url"]
        lines += [
            "",
            f"[GitHub 原始碼]({url})",
        ]

    return "\n".join(lines) + "\n"


# --- Sidebar generation ---

def generate_sidebar_entries(chapters: dict, mode: str = "zh_only") -> str:
    """Generate JS sidebar array entries."""
    sections = sorted_sections(chapters)
    entries = []
    for slug, section in sections:
        title = section["title"]
        if _leaf_count(section.get("files", {})) == 1:
            primary_slug = section_primary_slug(slug, section, mode)
            entries.append(
                f"\t\t\t\t{{\n"
                f"\t\t\t\t\tlabel: '{title}',\n"
                f"\t\t\t\t\tslug: '{primary_slug}',\n"
                f"\t\t\t\t}}"
            )
            continue

        directory = f"{mode_prefix(mode)}{slug}"
        entries.append(
            f"\t\t\t\t{{\n"
            f"\t\t\t\t\tlabel: '{title}',\n"
            f"\t\t\t\t\tautogenerate: {{ directory: '{directory}' }},\n"
            f"\t\t\t\t}}"
        )
    return ",\n".join(entries)


# Matches both the collapsed blank-template form (`sidebar: [],`) and the
# populated multi-line form. The optional block is non-greedy and requires the
# closing bracket to sit on its own line, so the match stops at the sidebar
# array's own `],` instead of over-consuming `plugins` / `customCss` / the
# enclosing `starlight({...})` brackets.
SIDEBAR_PATTERN = re.compile(
    r"^(?P<indent>[ \t]*)sidebar:[ \t]*\[\s*(?:\n.*?\n[ \t]*)?\],",
    re.MULTILINE | re.DOTALL,
)


def update_astro_sidebar(config_text: str, chapters: dict, mode: str = "zh_only") -> str:
    """Replace sidebar array content in astro.config.mjs.

    Raises:
        SidebarPatchError: when the sidebar array cannot be located.
    """
    entries = generate_sidebar_entries(chapters, mode=mode)

    def _replace(match: re.Match[str]) -> str:
        indent = match.group("indent")
        return f"{indent}sidebar: [\n{entries}\n{indent}],"

    result, count = SIDEBAR_PATTERN.subn(_replace, config_text, count=1)
    if count == 0:
        raise SidebarPatchError("無法定位 astro.config.mjs 中的 sidebar 陣列")
    return result


def regenerate(project_root: Path) -> None:
    """Regenerate navigation for a selected book checkout."""
    chapters_file = project_root / "chapters.json"
    style_file = project_root / "style-decisions.json"
    index_file = project_root / "docs/src/content/docs/index.mdx"
    astro_config = project_root / "docs/astro.config.mjs"
    if not chapters_file.exists():
        print(f"❌ 找不到 {chapters_file}", file=sys.stderr)
        raise SystemExit(1)

    chapters_data = load_json(chapters_file)
    if "chapters" in chapters_data:
        chapters = chapters_data["chapters"]
        mode = chapters_data.get("mode", "zh_only")
    else:
        chapters = chapters_data
        mode = "zh_only"
    if not chapters:
        print("❌ chapters.json 中沒有章節資料", file=sys.stderr)
        raise SystemExit(1)

    try:
        validate_section_slugs(chapters)
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    # chapters.json 允許扁平斜線路徑鍵（如 "combat/actions"），實際輸出的文件樹
    # 由 split_chapters.py 透過 normalize_files() 展開後才落地；此處必須套用相同
    # 正規化，導覽/首頁連結與側邊欄才會對齊 split_chapters.py 實際寫出的結構。
    for section in chapters.values():
        section["files"] = normalize_files(section.get("files", {}))

    style = load_json(style_file) if style_file.exists() else {}

    # Generate index.mdx
    index_content = generate_index(chapters, style, mode=mode, hero_image=project_root / "docs/src/assets/hero.jpg")
    index_file.parent.mkdir(parents=True, exist_ok=True)
    index_file.write_text(index_content, encoding="utf-8")
    print(f"✓ 已產生首頁: {index_file}")

    # Update astro.config.mjs sidebar + site/base
    if astro_config.exists():
        original = astro_config.read_text(encoding="utf-8")
        try:
            updated = update_astro_sidebar(original, chapters, mode=mode)
        except SidebarPatchError as exc:
            print(f"❌ {exc}：{astro_config}", file=sys.stderr)
            raise SystemExit(1) from exc
        updated = update_astro_site_base(updated, style)
        updated = update_astro_site_title(updated, style)
        if updated != original:
            astro_config.write_text(updated, encoding="utf-8")
            print(f"✓ 已更新側邊欄、site/base 與網站標題設定: {astro_config}")
        else:
            print("ℹ 側邊欄、site/base 與網站標題設定未變更")
    else:
        print(f"⚠ 找不到 {astro_config}", file=sys.stderr)

    sections = sorted_sections(chapters)
    print(f"\n章節清單 ({len(sections)} 個):")
    for slug, section in sections:
        print(f"  /{slug}/ → {section['title']}")


def main() -> None:
    regenerate(PROJECT_ROOT)


if __name__ == "__main__":
    main()
