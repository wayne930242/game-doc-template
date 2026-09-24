#!/usr/bin/env python3
"""Generate homepage index.mdx and update astro.config.mjs sidebar from chapters.json."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from _markdown_utils import yaml_safe
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


# Deploy targets served under a sub-path. "blog" nests the book at /books/<slug>/ inside
# the blog site; "github-pages" serves a project site at /<repo-name>/.
SUBPATH_TARGETS = ("blog", "github-pages")


def deployment_base_path(style: dict) -> str:
    """Return the configured deployment base path (e.g. '/books/slug'), or '' for root deploys.

    Source of truth: style-decisions.json.deployment.base_path. Absolute hrefs written into
    page content (hero.actions.link, LinkCard href) are literal strings Astro does NOT
    base-resolve on its own — unlike Starlight-native sidebar `slug` entries, which Starlight
    resolves against `base` internally. Any href built here for content-embedded links must be
    prefixed with this value explicitly, or it silently 404s on non-root deploys (e.g. GitHub
    Pages project sites).
    """
    deployment = style.get("deployment", {})
    if deployment.get("target") not in SUBPATH_TARGETS:
        # Only sub-path deploys need a non-root base path. Ignore any stale
        # base_path left over from a previous target (e.g. switched back to root/Vercel)
        # so content links never carry a prefix the current deploy doesn't serve under.
        return ""
    base_path = deployment.get("base_path", "") or ""
    base_path = base_path.rstrip("/")
    if base_path and not base_path.startswith("/"):
        base_path = f"/{base_path}"
    return base_path


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

def generate_index(chapters: dict, style: dict, mode: str = "zh_only") -> str:
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
    if HERO_IMAGE.exists():
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
    has_credits = credits_cfg.get("show_on_homepage") and credits_cfg.get("entries")

    if has_copyright:
        lines += [
            "## 版權宣告",
            "",
            copyright_cfg["text"],
            "",
        ]
    if has_credits:
        lines += [
            "## 製作名單",
            "",
            "| 職責 | 人員 |",
            "| --- | --- |",
        ]
        for entry in credits_cfg["entries"]:
            role = entry.get("role", "")
            name = entry.get("name", "")
            lines.append(f"| {role} | {name} |")
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


SITE_BASE_PATTERN = re.compile(
    r"(export default defineConfig\(\{\n)(\tsite: '[^']*',\n)?(\tbase: '[^']*',\n)?",
)


def _github_pages_site_url(repo_url: str) -> str:
    """Derive https://<user>.github.io from a github.com repo URL."""
    match = re.search(r"github\.com[:/]([^/]+)/", repo_url)
    username = match.group(1) if match else "<github-username>"
    return f"https://{username}.github.io"


def update_astro_site_base(config_text: str, style: dict) -> str:
    """Insert/update or remove the top-level `site`/`base` defineConfig keys.

    Single source of truth is style-decisions.json.deployment:
    - target == "github-pages": write `site`/`base` derived from repository.url + base_path.
    - target == "blog": write `base` only; the blog owns the domain.
    - anything else (unset, "root"): strip any previously-written site/base block, since a
      root deploy (Vercel, custom domain) must not carry a stale sub-path base.
    """
    deployment = style.get("deployment", {})
    target = deployment.get("target")

    if target in SUBPATH_TARGETS:
        base_path = deployment_base_path(style)
        if not base_path:
            print(f"⚠ deployment.target={target} 但 base_path 未設定，略過 site/base 寫入", file=sys.stderr)
            return config_text
        replacement = f"\\1\tbase: '{base_path}',\n"
        if target == "github-pages":
            repo_url = style.get("repository", {}).get("url", "")
            site_url = _github_pages_site_url(repo_url)
            replacement = f"\\1\tsite: '{site_url}',\n\tbase: '{base_path}',\n"
    else:
        replacement = r"\1"

    return SITE_BASE_PATTERN.sub(replacement, config_text, count=1)


SITE_TITLE_PATTERN = re.compile(r"^(?P<lead>\ttitle: )'(?:[^'\\\n]|\\.)*',$", re.MULTILINE)


def update_astro_site_title(config_text: str, style: dict) -> str:
    """Set SITE_CONFIG.title from style-decisions.json.site.title (the same source as book.json).

    Leaves the config unchanged when no site title is recorded.
    """
    title = style.get("site", {}).get("title")
    if not title:
        return config_text
    literal = title.replace("\\", "\\\\").replace("'", "\\'")
    return SITE_TITLE_PATTERN.sub(lambda match: f"{match['lead']}'{literal}',", config_text, count=1)


def main() -> None:
    if not CHAPTERS_FILE.exists():
        print(f"❌ 找不到 {CHAPTERS_FILE}", file=sys.stderr)
        raise SystemExit(1)

    chapters_data = load_json(CHAPTERS_FILE)
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

    style = load_json(STYLE_FILE) if STYLE_FILE.exists() else {}

    # Generate index.mdx
    index_content = generate_index(chapters, style, mode=mode)
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(index_content, encoding="utf-8")
    print(f"✓ 已產生首頁: {INDEX_FILE}")

    # Update astro.config.mjs sidebar + site/base
    if ASTRO_CONFIG.exists():
        original = ASTRO_CONFIG.read_text(encoding="utf-8")
        try:
            updated = update_astro_sidebar(original, chapters, mode=mode)
        except SidebarPatchError as exc:
            print(f"❌ {exc}：{ASTRO_CONFIG}", file=sys.stderr)
            raise SystemExit(1) from exc
        updated = update_astro_site_base(updated, style)
        updated = update_astro_site_title(updated, style)
        if updated != original:
            ASTRO_CONFIG.write_text(updated, encoding="utf-8")
            print(f"✓ 已更新側邊欄、site/base 與網站標題設定: {ASTRO_CONFIG}")
        else:
            print("ℹ 側邊欄、site/base 與網站標題設定未變更")
    else:
        print(f"⚠ 找不到 {ASTRO_CONFIG}", file=sys.stderr)

    # Summary
    sections = sorted_sections(chapters)
    print(f"\n章節清單 ({len(sections)} 個):")
    for slug, section in sections:
        print(f"  /{slug}/ → {section['title']}")


if __name__ == "__main__":
    main()
