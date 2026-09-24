#!/usr/bin/env python3
"""Move an existing book checkout onto the template's blog export pipeline."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TEMPLATE / "scripts"))
from site_config import update_astro_site_base, update_astro_site_title  # noqa: E402


def frontmatter_value(index_text: str, key: str) -> str | None:
    match = re.match(r"\A---\s*\n(.*?)\n---", index_text, re.S)
    if not match:
        return None
    field = re.search(rf"(?m)^{re.escape(key)}:\s*(.+?)\s*$", match.group(1))
    return field.group(1).strip().strip("\"'") if field else None


def astro_title(config_text: str) -> str | None:
    match = re.search(r"(?m)^\s*title:\s*['\"]([^'\"]+)['\"],?\s*$", config_text)
    return match.group(1) if match else None


def original_title_from_home(index_text: str, title: str | None) -> str | None:
    # Existing homepages often introduce the translated title and original together.
    pair = re.search(r"《[^》]+》[（(]([A-Za-z][A-Za-z0-9 '’:\-]+)[）)]", index_text)
    if pair:
        return pair.group(1).strip()
    if title:
        latin = re.match(r"^([A-Za-z][A-Za-z0-9 '’:\-]*?)(?=\s*[\u3400-\u9fff]|$)", title)
        if latin:
            return latin.group(1).strip()
    return None


def original_title_from_recorded_text(index_text: str, site: dict) -> str | None:
    source_line = re.search(r"(?m)^[-*]\s*原作[:：]\s*\*\*([A-Za-z][A-Za-z0-9 '’:\-]+)\*\*", index_text)
    if source_line:
        return source_line.group(1).strip()
    emphasized = re.search(r"\*\*([A-Za-z][A-Za-z0-9 '’:\-]+)[（(][^）)]+[）)]\*\*", index_text)
    if emphasized:
        return emphasized.group(1).strip()
    introduction = re.search(r"本站整理\s+([A-Za-z][A-Za-z0-9 '’:\-]+?)\s+TTRPG", index_text)
    if introduction:
        return introduction.group(1).strip()
    home_title = frontmatter_value(index_text, "title")
    if home_title and not re.search(r"[\u3400-\u9fff]", home_title) and re.search(r"[A-Za-z]", home_title):
        return home_title
    for text in (site.get("description", ""), site.get("intro", ""), frontmatter_value(index_text, "description") or ""):
        pair = re.search(r"[（(]([A-Za-z][A-Za-z0-9 '’:\-]+)[）)]", text)
        if pair:
            return pair.group(1).strip()
        leading = re.match(r"^([A-Za-z][A-Za-z0-9 '’:\-]+)\s+繁體中文", text)
        if leading:
            return leading.group(1).strip()
    return None


def recorded_translators(style: dict, index_text: str) -> list[str]:
    names = [entry.get("name", "").strip() for entry in style.get("credits", {}).get("entries", []) if "翻譯" in entry.get("role", "")]
    for pattern in (r"(?:翻譯|譯者)[:：]\s*([^\n|<]+)", r"本站由([^\n。]{1,40})翻譯", r"翻譯由\s*([^\s，。]+)\s*提供"):
        for match in re.finditer(pattern, index_text):
            names.append(match.group(1).strip())
    return list(dict.fromkeys(name for name in names if name))


def source_translation_warnings(repo: Path) -> list[str]:
    docs = repo / "docs/src/content/docs"
    indicator = re.compile(r"翻譯由\s*[^\s，。]+\s*提供|(?:譯者|翻譯)[:：]\s*[^\n]+|社群翻譯|來源譯本|既有譯本|翻譯來源|based on (?:the )?translation", re.I)
    matches = []
    for path in sorted(docs.rglob("*")):
        if path.suffix not in {".md", ".mdx"}:
            continue
        match = indicator.search(path.read_text(encoding="utf-8", errors="replace"))
        if match:
            matches.append(f"{path.relative_to(repo)}: {match.group(0)[:60]}")
    return matches[:10] + ([f"and {len(matches) - 10} more files"] if len(matches) > 10 else [])


def site_images(repo: Path, index_path: Path, index_text: str) -> dict[str, str]:
    """Locate the hero and OG images the site actually serves, as repo-relative paths."""
    found = {}
    hero = re.search(r"^\s+file:\s*['\"]?([^'\"\s]+)", index_text, re.MULTILINE)
    if hero and (index_path.parent / hero.group(1)).resolve().is_file():
        found["hero"] = str((index_path.parent / hero.group(1)).resolve().relative_to(repo))
    og = sorted((repo / "docs/public").glob("og-image.*")) if (repo / "docs/public").is_dir() else []
    if og:
        found["og"] = str(og[0].relative_to(repo))
    return found


def derive_metadata(
    repo: Path,
    translator: str | None = None,
    title: str | None = None,
    original_title: str | None = None,
    credits: list[dict] | None = None,
) -> tuple[dict, list[str], list[str]]:
    style_path = repo / "style-decisions.json"
    style = json.loads(style_path.read_text(encoding="utf-8")) if style_path.is_file() else {}
    if not isinstance(style, dict):
        raise ValueError(f"Style decisions must be a JSON object: {style_path}")
    meta = style.setdefault("_meta", {})
    if not isinstance(meta, dict):
        raise ValueError(f"Style decisions _meta must be an object: {style_path}")
    meta.setdefault("description", "風格決定記錄")
    meta.setdefault("updated", datetime.now(timezone.utc).date().isoformat())
    config = (repo / "docs/astro.config.mjs").read_text(encoding="utf-8")
    index_path = repo / "docs/src/content/docs/index.mdx"
    index = index_path.read_text(encoding="utf-8") if index_path.is_file() else ""
    site = style.setdefault("site", {})
    project = style.get("project", {})
    repository = style.get("repository", {})
    if not site.get("title"):
        site["title"] = project.get("game_title_zh") or astro_title(config) or frontmatter_value(index, "title")
    if not site.get("original_title"):
        site["original_title"] = project.get("game_title_en") or repository.get("game_title_en") or original_title_from_home(index, site.get("title")) or original_title_from_recorded_text(index, site)
    if not site.get("description"):
        site["description"] = frontmatter_value(index, "description") or ""
    if title:
        site["title"] = title
    if original_title:
        site["original_title"] = original_title
    if credits:
        if not any("翻譯" in entry["role"] for entry in credits):
            raise ValueError("Confirmed credits need at least one role containing 翻譯")
        style["credits"] = {**style.get("credits", {}), "entries": credits}
    images = style.setdefault("images", {})
    for key, path in site_images(repo, index_path, index).items():
        if not images.get(key) or not (repo / images[key]).is_file():
            images[key] = path
    recorded = recorded_translators(style, index)
    credit = translator or (recorded[0] if len(recorded) == 1 else None) or ("confirmed" if credits else None)
    missing = [field for field in ("title", "original_title") if not site.get(field)]
    if not credit:
        missing.append("translator")
    warnings = source_translation_warnings(repo)
    if translator and any(name != translator for name in recorded):
        warnings.append(f"Recorded translator differs from supplied credit: {', '.join(recorded)}")
    if "existing_translation_baseline" in style:
        warnings.append("Style decisions record an existing translation baseline; inspect attribution")
    if re.search(r"既有譯名|既有.{0,10}翻譯|社群翻譯", json.dumps(style, ensure_ascii=False)):
        warnings.append("Style decisions mention another translation; inspect attribution")
    if credit and not credits:
        entries = style.setdefault("credits", {}).setdefault("entries", [])
        if not any("翻譯" in entry.get("role", "") and entry.get("name") == credit for entry in entries):
            entries.append({"role": "翻譯", "name": credit})
    return style, missing, warnings


def astro_base(config: str) -> str:
    match = re.search(r"^\s*base:\s*['\"]([^'\"]+)['\"],?\s*$", config, re.MULTILINE)
    return match.group(1).rstrip("/") if match else ""


def strip_content_base(repo: Path, old_base: str) -> int:
    """Make content links base-agnostic by removing a previous deployment base."""
    pattern = re.compile(r"(?<=[(\"'\s=])" + re.escape(old_base) + r"(?=[/\"')\s#?]|$)", re.MULTILINE)
    changed = 0
    for path in sorted((repo / "docs/src/content/docs").rglob("*")):
        if path.suffix not in {".md", ".mdx"}:
            continue
        text = path.read_text(encoding="utf-8")
        revised = pattern.sub(lambda match: "" if text[match.end():match.end() + 1] == "/" else "/", text)
        if revised != text:
            path.write_text(revised, encoding="utf-8")
            changed += 1
    return changed


def merge_package(old: dict, current: dict) -> dict:
    merged = dict(old)
    for key, value in current.items():
        if key in {"scripts", "dependencies", "devDependencies"}:
            merged[key] = {**old.get(key, {}), **value}
        else:
            merged[key] = value
    merged.get("dependencies", {}).pop("@astrojs/vercel", None)
    merged.get("devDependencies", {}).pop("@astrojs/vercel", None)
    return merged


def migrate(
    repo: Path,
    slug: str,
    translator: str | None,
    apply: bool,
    *,
    title: str | None = None,
    original_title: str | None = None,
    credits: list[dict] | None = None,
) -> dict:
    repo = repo.resolve()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("slug must use lowercase letters, digits, and hyphens")
    if not (repo / "docs/astro.config.mjs").is_file() or not (repo / "docs/src/content/docs").is_dir():
        raise ValueError(f"Not a book checkout: {repo}")
    style, missing, warnings = derive_metadata(repo, translator, title, original_title, credits)
    report = {"repo": str(repo), "slug": slug, "metadata": {"title": style["site"].get("title"), "original_title": style["site"].get("original_title"), "credits": style.get("credits", {}).get("entries", [])}, "missing": missing, "warnings": warnings, "applied": False}
    if missing or not apply:
        return report
    style["deployment"] = {"target": "blog", "base_path": f"/books/{slug}"}
    config_path = repo / "docs/astro.config.mjs"
    config = config_path.read_text(encoding="utf-8")
    old_base = astro_base(config)
    if old_base and old_base != f"/books/{slug}":
        report["content_files_rebased"] = strip_content_base(repo, old_base)
    updated = update_astro_site_title(update_astro_site_base(config, style), style)
    if updated == config and f"base: '/books/{slug}'" not in config:
        raise ValueError("Could not update Astro base")
    package_path = repo / "docs/package.json"
    merged_package = merge_package(json.loads(package_path.read_text(encoding="utf-8")), json.loads((TEMPLATE / "docs/package.json").read_text(encoding="utf-8")))
    (repo / "scripts").mkdir(exist_ok=True)
    for name in ("export_site.py", "site_config.py"):
        shutil.copy2(TEMPLATE / "scripts" / name, repo / "scripts" / name)
    search = repo / "docs/search"
    if search.is_symlink():
        search.unlink()
    elif search.exists():
        shutil.rmtree(search)
    shutil.copytree(TEMPLATE / "docs/search", search)
    shutil.copytree(TEMPLATE / "docs/build", repo / "docs/build", dirs_exist_ok=True)
    workflow = repo / ".github/workflows/book-export.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TEMPLATE / ".github/workflows/book-export.yml", workflow)
    package_path.write_text(json.dumps(merged_package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    config_path.write_text(updated, encoding="utf-8")
    (repo / "style-decisions.json").write_text(json.dumps(style, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["applied"] = True
    return report


def parse_credit(value: str) -> dict:
    role, sep, name = value.partition("=")
    if not sep or not role.strip() or not name.strip():
        raise argparse.ArgumentTypeError("credit must be ROLE=NAME")
    return {"role": role.strip(), "name": name.strip()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True, help="Existing book checkout")
    parser.add_argument("--slug", required=True, help="Blog slug")
    parser.add_argument("--translator", help="Confirmed translator when not recorded by the book")
    parser.add_argument("--title", help="Confirmed translated title when not recorded by the book")
    parser.add_argument("--original-title", help="Confirmed original title when not recorded by the book")
    parser.add_argument("--credit", action="append", type=parse_credit, metavar="ROLE=NAME", help="Confirmed credit entry, repeatable; replaces the book's recorded credits")
    parser.add_argument("--apply", action="store_true", help="Write the migration into the checkout")
    args = parser.parse_args()
    try:
        report = migrate(args.repo, args.slug, args.translator, args.apply, title=args.title, original_title=args.original_title, credits=args.credit)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"Migration error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if report["missing"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
