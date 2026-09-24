#!/usr/bin/env python3
"""Repair PDF layout artifacts in an already translated Starlight project.

Run after syncing template scripts into the project. The command preserves prose,
updates the translated chapter map, and is safe to repeat: once the paired repair
is recorded, reruns only apply line-local cleanups unless --reapply is given.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from _image_analysis import enrich_image_manifest
from _layout_cleanup import annotate_d66_pair_headings, chapter_fragment_classes, d66_pages, d66_pair_pages, is_edge_furniture, layout_art_classes, repair_d66_tables, strip_duplicate_title, strip_page_furniture
from _markdown_utils import find_empty_tables
from _paired_layout import _format_translated_spread, _pdf_roles, _tree_digest, add_reviewed_decisions, derive_layout_plan, match_chapter_paths, recorded_repair, repair_paired_layout
from generate_nav import deployment_base_path, regenerate
from split_chapters import build_page_text_stats, extract_pages, group_images_by_page, normalize_files, write_meta_yml
from validate_translation_structure import compare_structure

IMAGE_RE = re.compile(r"(?m)^!\[[^\]]*\]\(([^)]+)\)\s*$")
PRINTED_REF_RE = re.compile(r"第\s*(\d{1,3})\s*頁")
DOT_LEADER_RE = re.compile(r"([^\.　\n]+?)\.{8,}\s*(\d{1,3})")
TOC_HEADING_RE = re.compile(r"^#\s*(.+?)[\s　]+第\s*(\d{1,3})\s*頁$")
FRONT_TITLE_RE = re.compile(r"(?m)^title:\s*(.+?)\s*$")
FRONT_DESCRIPTION_RE = re.compile(r"(?m)^description:\s*(.+?)\s*$")


def front_title(text: str) -> str:
    match = FRONT_TITLE_RE.search(text.split("---", 2)[1] if text.startswith("---") else "")
    return match.group(1).strip().strip("\"'") if match else ""


def front_description(text: str) -> str:
    match = FRONT_DESCRIPTION_RE.search(text.split("---", 2)[1] if text.startswith("---") else "")
    return match.group(1).strip().strip("\"'") if match else ""


def split_frontmatter(text: str) -> tuple[str, str]:
    if text.startswith("---\n"):
        match = re.match(r"\A---\n.*?\n---\n", text, re.S)
        if match:
            return match.group(0), text[match.end():].strip()
    return "", text.strip()


def chapter_leaves(chapters: dict) -> list[tuple[str, dict]]:
    result: list[tuple[str, dict]] = []
    def visit(prefix: str, files: dict) -> None:
        for key, entry in files.items():
            path = f"{prefix}/{key}"
            if "files" in entry:
                visit(path, entry["files"])
            elif "pages" in entry:
                result.append((path, entry))
    for slug, section in chapters.items():
        visit(slug, section.get("files", {}))
    return result


def route_for_page(page: int, leaves: list[tuple[str, dict]], base: str) -> tuple[str, str] | None:
    for slug, entry in leaves:
        start, end = entry["pages"]
        if start <= page <= end:
            route = slug[:-6] if slug.endswith("/index") else slug
            return entry["title"], f"{base}/{route}/"
    return None


def section_route(slug: str, section: dict, leaves: list[tuple[str, dict]], base: str) -> str:
    candidates = [(entry["pages"][0], path) for path, entry in leaves if path.startswith(slug + "/")]
    if not candidates:
        return f"{base}/{slug}/"
    path = min(candidates)[1]
    return f"{base}/{path[:-6] if path.endswith('/index') else path}/"


def printed_offset(paragraphs: list[str], chapters: dict) -> int:
    sections = sorted(chapters.items(), key=lambda item: item[1].get("order", 9999))
    observed: list[int] = []
    # The first section may include covers and the printed TOC; later starts
    # give the stable physical-PDF versus printed-page offset.
    headings = [TOC_HEADING_RE.match(p) for p in paragraphs if TOC_HEADING_RE.match(p)]
    for (slug, section), match in zip(sections[1:], headings):
        starts = [entry["pages"][0] for path, entry in chapter_leaves({slug: section})]
        if starts:
            observed.append(min(starts) - int(match.group(2)))
    return Counter(observed).most_common(1)[0][0] if observed else 0


def repair_toc(body: str, chapters: dict, leaves: list[tuple[str, dict]], base: str) -> tuple[str, dict[str, str], int]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    toc_start = next((i for i, p in enumerate(paragraphs) if p in {"目錄", "Table of Contents"}), None)
    if toc_start is None:
        return body, {}, 0
    sections = sorted(chapters.items(), key=lambda item: item[1].get("order", 9999))
    heading_indices = [i for i in range(toc_start + 1, len(paragraphs)) if TOC_HEADING_RE.match(paragraphs[i])]
    if len(heading_indices) < max(1, len(sections) - 1):
        return body, {}, 0
    last_heading = heading_indices[len(sections) - 2]
    first_label = paragraphs[toc_start + 1]
    toc_end = next(
        (i for i in range(last_heading + 1, len(paragraphs)) if paragraphs[i] == first_label),
        last_heading + 1,
    )
    offset = printed_offset(paragraphs[toc_start:toc_end], chapters)
    labels: dict[str, str] = {}
    revised = paragraphs[:toc_start] + ["## 章節導覽"]
    section_index = 0
    count = 0
    i = toc_start + 1
    while i < toc_end:
        p = paragraphs[i]
        heading = TOC_HEADING_RE.match(p)
        if section_index == 0 and i + 1 < toc_end and PRINTED_REF_RE.fullmatch(paragraphs[i + 1]):
            slug, section = sections[0]
            labels[slug] = p
            revised.append(f"### [{p}]({section_route(slug, section, leaves, base)})")
            section_index += 1; count += 1; i += 2; continue
        if heading and section_index < len(sections):
            slug, section = sections[section_index]
            title = heading.group(1).strip()
            labels[slug] = title
            revised.append(f"### [{title}]({section_route(slug, section, leaves, base)})")
            section_index += 1; count += 1; i += 1; continue
        entries = DOT_LEADER_RE.findall(p)
        if entries:
            links: list[str] = []
            for label, number in entries:
                target = route_for_page(int(number) + offset, leaves, base)
                if target:
                    links.append(f"- [{label.strip()}]({target[1]})")
                    count += 1
            revised.append("\n".join(links) if links else p)
        else:
            revised.append(p)
        i += 1
    tail = paragraphs[toc_end:]
    if tail and tail[0] == labels.get(sections[0][0]):
        tail.pop(0)
    revised.extend(tail)
    return "\n\n".join(revised), labels, count


def repair_printed_refs(body: str, leaves: list[tuple[str, dict]], base: str, offset: int) -> tuple[str, int]:
    paragraphs = re.split(r"\n\s*\n", body)
    changed = 0
    for index, paragraph in enumerate(paragraphs):
        clean = paragraph.strip()
        refs = PRINTED_REF_RE.findall(clean)
        if not refs or PRINTED_REF_RE.sub("", clean).strip("　 \t"):
            continue
        links: list[str] = []
        seen: set[str] = set()
        for number in refs:
            target = route_for_page(int(number) + offset, leaves, base)
            if target and target[1] not in seen:
                links.append(f"[{target[0]}]({target[1]})")
                seen.add(target[1])
        paragraphs[index] = "相關章節：" + "、".join(links) if links else ""
        changed += 1
    return "\n\n".join(p for p in paragraphs if p.strip()), changed


def repair_english_toc(body: str, chapters: dict, leaves: list[tuple[str, dict]], base: str) -> tuple[str, int]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    start = next((i for i, p in enumerate(paragraphs) if p.lower() == "table of contents"), None)
    if start is None:
        return body, 0
    first_title = paragraphs[start + 1].strip()
    end = next((i for i in range(start + 1, len(paragraphs))
                if re.fullmatch(r"#{2,6}\s+" + re.escape(first_title), paragraphs[i], re.I)), None)
    if end is None:
        return body, 0
    sections = sorted(chapters.items(), key=lambda item: item[1].get("order", 9999))
    printed_heads = [re.fullmatch(r"#{2,6}\s+(.+?)\s+Pg\.\s*(\d+)", p, re.I)
                     for p in paragraphs[start + 1:end]]
    offsets = []
    for (slug, section), heading in zip(sections[1:], (match for match in printed_heads if match)):
        starts = [entry["pages"][0] for path, entry in leaves if path.startswith(slug + "/")]
        if starts:
            offsets.append(min(starts) - int(heading.group(2)))
    offset = Counter(offsets).most_common(1)[0][0] if offsets else 0
    revised = paragraphs[:start] + ["## Chapter navigation"]
    section_index = 0
    count = 0
    for p in paragraphs[start + 1:end]:
        if section_index == 0 and p.casefold() == first_title.casefold():
            slug, section = sections[0]
            revised.append(f"### [{p}]({section_route(slug, section, leaves, base)})")
            section_index += 1; count += 1
            continue
        if re.fullmatch(r"Pg\.\s*\d+", p, re.I):
            continue
        heading = re.fullmatch(r"#{2,6}\s+(.+?)\s+Pg\.\s*(\d+)", p, re.I)
        if heading and section_index < len(sections):
            slug, section = sections[section_index]
            revised.append(f"### [{heading.group(1)}]({section_route(slug, section, leaves, base)})")
            section_index += 1; count += 1
            continue
        entries = DOT_LEADER_RE.findall(p)
        if entries:
            links = []
            for label, number in entries:
                target = route_for_page(int(number) + offset, leaves, base)
                if target:
                    links.append(f"- [{label.strip()}]({target[1]})")
                    count += 1
            revised.append("\n".join(links) if links else p)
        else:
            revised.append(p)
    revised.extend(paragraphs[end + 1:])
    return "\n\n".join(revised), count


@lru_cache(maxsize=2)
def _pdf_heading_index(pdf: Path) -> dict[int, list[str]]:
    try:
        import pymupdf
    except ImportError:
        return {}
    with pymupdf.open(pdf) as doc:
        roles = _pdf_roles(doc, (1, len(doc)))
    headings: dict[int, list[str]] = {}
    for role in roles:
        if role.kind in {"heading", "display"}:
            headings.setdefault(role.page, []).append(role.text)
    return headings


def pdf_heading_catalog(pdf: Path, pages: tuple[int, int]) -> list[str]:
    index = _pdf_heading_index(pdf)
    return [heading for number in range(pages[0], pages[1] + 1) for heading in index.get(number, [])]


def corroborated_headings(pdf: Path, pages: dict[int, str], page_range: tuple[int, int]) -> list[str]:
    """Require both PDF typography and an extracted Markdown heading.

    The display font is also used in charts and captions; typography alone
    would turn labels such as Difficulty into document headings.
    """
    printed = pdf_heading_catalog(pdf, page_range)
    extracted = [match.group(1).strip() for page in range(page_range[0], page_range[1] + 1)
                 for match in re.finditer(r"(?m)^#{2,6}\s+(.+?)\s*$", pages.get(page, ""))]
    return [heading for heading in printed if any(
        re.sub(r"\W", "", heading).lower() == re.sub(r"\W", "", source).lower()
        for source in extracted)]


def recover_pdf_headings(body: str, catalog: list[str]) -> tuple[str, int]:
    if not catalog:
        return body, 0
    count = 0
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if (not line or len(line) > 40 or line.startswith(("#", "-", "|", "!", "<"))
                or re.search(r"[（(][^）)]*\d", line)):
            continue
        visible = re.sub(r"（[^）]*）", "", line)
        if re.search(r"[，。：「」；！？＝　]", visible) or line.endswith((".", ":", "：")):
            continue
        terms = [word.strip().lower() for term in re.findall(r"（([^）]+)）", line)
                 for word in re.findall(r"[A-Za-z][A-Za-z ]{3,}", term)]
        if not terms:
            continue
        matches = [head for head in catalog if all(term in head.lower() for term in terms)]
        if len(matches) == 1:
            lines[index] = "## " + line
            count += 1
    return "\n".join(lines), count


def recover_english_headings(body: str, catalog: list[str]) -> tuple[str, int]:
    lines = body.splitlines()
    changed = 0
    names = {re.sub(r"\W", "", title).lower() for title in catalog}
    for index, line in enumerate(lines):
        match = re.fullmatch(r"\s+(.+)", line.strip())
        if match and re.sub(r"\W", "", match.group(1)).lower() in names:
            lines[index] = "## " + match.group(1)
            changed += 1
        elif (not line.startswith("#") and len(re.findall(r"[A-Za-z]+", line)) >= 3
              and re.sub(r"\W", "", line).lower() in names):
            lines[index] = "## " + line
            changed += 1
    return "\n".join(lines), changed


def paired_english_headings(catalog: list[str], translated_body: str) -> list[str]:
    """Select source headings whose translated counterpart is a level-two heading."""
    terms = [term.lower() for line in translated_body.splitlines() if line.startswith("## ")
             for term in re.findall(r"[（(]([^）)]+)[）)]", line)]
    return [heading for heading in catalog if any(term in heading.lower() for term in terms)]


def staged_missing_headings(source_baseline: Path | None, slug: str, catalog: list[str]) -> list[str]:
    if source_baseline is None:
        return []
    path = source_baseline / f"{slug}.md"
    if not path.is_file():
        return []
    body = split_frontmatter(path.read_text(encoding="utf-8"))[1]
    marked = {re.sub(r"\W", "", match.group(1)).lower()
              for match in re.finditer(r"(?m)^\s+(.+?)\s*$", body)}
    return [heading for heading in catalog if re.sub(r"\W", "", heading).lower() in marked]


def _image_manifest(project_root: Path, config: dict) -> list[dict]:
    source = Path(config.get("source", ""))
    path = project_root / "data/markdown/images" / source.stem.removesuffix("_pages") / "manifest.json"
    if not path.exists():
        return []
    return enrich_image_manifest(json.loads(path.read_text(encoding="utf-8")).get("images", []), path.parent)


def _image_dir(project_root: Path, config: dict) -> Path:
    source = Path(config.get("source", ""))
    return project_root / "data/markdown/images" / source.stem.removesuffix("_pages")


def _chapter_image_classes(manifest: list[dict], leaves: list[tuple[str, dict]], image_dir: Path) -> dict[str, dict[str, str]]:
    return {f"{slug}.md": chapter_fragment_classes(manifest, *entry["pages"], image_dir)
            for slug, entry in leaves}


def annotate_pair_pages(body: str, pairs: dict[int, int]) -> tuple[str, int]:
    lines = body.splitlines()
    changed = 0
    for page, first_die in sorted(pairs.items()):
        markers = [i for i, line in enumerate(lines) if re.search(rf"page{page:03d}_img", line)]
        if not markers:
            continue
        first = markers[0]
        previous = max((i for i in range(first) if re.search(r"page\d{3}_img", lines[i])), default=-1)
        segment, count = annotate_d66_pair_headings("\n".join(lines[previous + 1:first]), first_die)
        if count:
            lines[previous + 1:first] = segment.splitlines()
            changed += count
    return "\n".join(lines), changed


def _update_group_titles(project_root: Path, chapters: dict, leaves: list[tuple[str, dict]], labels: dict[str, str]) -> None:
    docs = project_root / "docs/src/content/docs"
    for slug, section in chapters.items():
        if slug in labels:
            section["title"] = labels[slug]
        elif section.get("translated_title"):
            section["title"] = section["translated_title"]
        for path, entry in leaves:
            if not path.startswith(slug + "/"):
                continue
            file = docs / f"{path}.md"
            if file.exists() and (title := front_title(file.read_text(encoding="utf-8"))):
                entry["title"] = title
                if description := front_description(file.read_text(encoding="utf-8")):
                    entry["description"] = description
                if path.endswith("/index") and path != f"{slug}/index":
                    group_path = path[:-6]
                    (docs / group_path).mkdir(parents=True, exist_ok=True)
                    write_meta_yml(docs / group_path, {"title": title})
        write_meta_yml(docs / slug, section)


def remove_edge_slivers(docs: Path, manifest: list[dict]) -> list[str]:
    """Drop page-edge sliver and tab image references; return `path: filename` per removal."""
    slivers = {image["filename"] for image in manifest if is_edge_furniture(image)}
    removed: list[str] = []
    for path in sorted(docs.rglob("*.md")):
        original = path.read_text(encoding="utf-8")
        def drop(match: re.Match[str]) -> str:
            filename = Path(match.group(1)).name
            if filename not in slivers:
                return match.group(0)
            removed.append(f"{path.relative_to(docs)}: {filename}")
            return "\0"
        marked = IMAGE_RE.sub(drop, original)
        if marked != original:
            path.write_text(re.sub(r"\n*\0\n*", "\n\n", marked).rstrip("\n") + "\n", encoding="utf-8")
    return removed


def remove_classified_art(docs: Path, manifest: list[dict], chapter_classes: dict[str, dict[str, str]] | None = None) -> dict[str, list[str]]:
    """Remove individual image lines while preserving edited chapter prose."""
    classes = layout_art_classes(manifest)
    removed: dict[str, list[str]] = {}
    for path in sorted(docs.rglob("*.md")):
        original = path.read_text(encoding="utf-8")
        local_classes = chapter_classes.get(str(path.relative_to(docs)), {}) if chapter_classes else {}
        def drop(match: re.Match[str]) -> str:
            filename = Path(match.group(1)).name
            kind = classes.get(filename) or local_classes.get(filename)
            if kind is None:
                return match.group(0)
            removed.setdefault(kind, []).append(f"{path.relative_to(docs)}: {filename}")
            return "\0"
        marked = IMAGE_RE.sub(drop, original)
        if marked != original:
            path.write_text(re.sub(r"\n*\0\n*", "\n\n", marked).rstrip("\n") + "\n", encoding="utf-8")
    return removed


def skipped(step: str, reason: str) -> dict[str, object]:
    return {"already_applied": 1, "skipped": step, "reason": reason}


def repair(project_root: Path, source_baseline: Path | None = None, reapply: bool = False) -> dict[str, object]:
    docs = project_root / "docs/src/content/docs"
    plan_path = project_root / "data/layout-repair.json"
    config_path = project_root / "chapters.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    manifest = _image_manifest(project_root, config)
    chapters = config["chapters"]
    for section in chapters.values():
        section["files"] = normalize_files(section.get("files", {}))
    leaves = chapter_leaves(chapters)
    chapter_classes = _chapter_image_classes(manifest, leaves, _image_dir(project_root, config))
    reason = None if reapply else recorded_repair(plan_path, docs)
    slivers = remove_edge_slivers(docs, manifest)
    art = remove_classified_art(docs, manifest, chapter_classes)
    sliver_stats = {"edge_slivers_removed": len(slivers), "edge_sliver_files": slivers} if slivers else {}
    art_stats = {"layout_art_removed": sum(map(len, art.values())), "layout_art_files": art} if art else {}
    if reason:
        if slivers or art:
            # Record line-local image removal so the next run reports later edits.
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["applied"]["target_sha256"] = _tree_digest(docs)
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {**skipped("translated layout repair (images, TOC, page references, headings, "
                          "furniture, titles, navigation)", reason), **sliver_stats, **art_stats}
    style_path = project_root / "style-decisions.json"
    style = json.loads(style_path.read_text(encoding="utf-8")) if style_path.exists() else {}
    base = deployment_base_path(style)
    source_path = project_root / config.get("source", "")
    pages = extract_pages(source_path.read_text(encoding="utf-8")) if source_path.is_file() else {}
    page_stats = build_page_text_stats(pages, config.get("clean_patterns", []))
    allowed, _ = group_images_by_page(manifest, page_stats, {"repeat_file_size_threshold": 5, "repeat_visual_threshold": 3})
    keep = {image["filename"] for images in allowed.values() for image in images}
    known_images = {image["filename"] for image in manifest}
    dice = d66_pages(manifest)
    pairs = d66_pair_pages(manifest)
    stats = Counter()
    toc_labels: dict[str, str] = {}
    offset = 0
    first_path = docs / f"{leaves[0][0]}.md" if leaves else None
    if first_path and first_path.exists():
        first_body = split_frontmatter(first_path.read_text(encoding="utf-8"))[1]
        offset = printed_offset([p.strip() for p in re.split(r"\n\s*\n", first_body) if p.strip()], chapters)
    pdf = project_root / "data/pdfs" / (Path(config.get("source", "")).stem.removesuffix("_pages") + ".pdf")
    if source_baseline is None:
        candidate = project_root / ".state/template-sync/staging/docs/src/content/docs"
        source_baseline = candidate if candidate.is_dir() else None
    target_pages = {f"{slug}.md": tuple(entry["pages"]) for slug, entry in leaves}
    source_for_target = ({target: source for source, (target, _) in
                          match_chapter_paths(source_baseline, docs, target_pages).items()}
                         if source_baseline else {})
    for slug, entry in leaves:
        path = docs / f"{slug}.md"
        if not path.exists():
            continue
        original = path.read_text(encoding="utf-8")
        front, body = split_frontmatter(original)
        title = front_title(original)
        if set(pairs).intersection({int(match) for match in re.findall(r"page(\d{3})_img", body)}):
            body, count = annotate_pair_pages(body, pairs)
            stats["dice_callouts_repaired"] += count
        def clean_image(match: re.Match[str]) -> str:
            filename = Path(match.group(1)).name
            if (filename in keep and filename not in chapter_classes.get(f"{slug}.md", {})) or filename not in known_images:
                return match.group(0)
            stats["images_removed"] += 1
            return ""
        body = IMAGE_RE.sub(clean_image, body)
        if dice.intersection(range(entry["pages"][0], entry["pages"][1] + 1)):
            body, count = repair_d66_tables(body)
            stats["dice_tables_repaired"] += count
        body, labels, count = repair_toc(body, chapters, leaves, base)
        toc_labels.update(labels)
        stats["toc_entries_linked"] += count
        body, count = repair_printed_refs(body, leaves, base, offset)
        stats["page_ref_paragraphs_linked"] += count
        if pdf.exists():
            source_rel = source_for_target.get(f"{slug}.md", f"{slug}.md")
            catalog = staged_missing_headings(source_baseline, source_rel.removesuffix(".md"),
                                              corroborated_headings(pdf, pages, tuple(entry["pages"])))
            body, count = recover_pdf_headings(body, catalog)
            stats["headings_recovered"] += count
        old_body = body
        body = strip_page_furniture(body)
        stats["furniture_removed"] += max(0, len(old_body.splitlines()) - len(body.splitlines()))
        old_body = body
        body = strip_duplicate_title(body, title)
        stats["duplicate_titles_removed"] += max(0, len(old_body.splitlines()) - len(body.splitlines()))
        revised = front + "\n" + body.strip() + "\n"
        if revised != original:
            path.write_text(revised, encoding="utf-8")
            stats["files_changed"] += 1
    _update_group_titles(project_root, chapters, leaves, toc_labels)
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    regenerate(project_root)
    return {**stats, **sliver_stats, **art_stats}


def _prepare_staged_source(project_root: Path, source_docs: Path) -> dict[str, int]:
    """Clean a writable English copy before matching its blocks to translation.

    The staging tree is an existing translation baseline, so this edits a caller
    supplied copy in place and leaves the synced staging directory untouched.
    """
    target_docs = project_root / "docs/src/content/docs"
    config = json.loads((project_root / "chapters.json").read_text(encoding="utf-8"))
    for section in config["chapters"].values():
        section["files"] = normalize_files(section.get("files", {}))
    manifest = _image_manifest(project_root, config)
    chapter_classes = _chapter_image_classes(manifest, chapter_leaves(config["chapters"]), _image_dir(project_root, config))
    source_path = project_root / config.get("source", "")
    pages = extract_pages(source_path.read_text(encoding="utf-8")) if source_path.is_file() else {}
    page_stats = build_page_text_stats(pages, config.get("clean_patterns", []))
    allowed, _ = group_images_by_page(manifest, page_stats, {"repeat_file_size_threshold": 5, "repeat_visual_threshold": 3})
    keep = {image["filename"] for group in allowed.values() for image in group}
    known_images = {image["filename"] for image in manifest}
    dice = d66_pages(manifest)
    pairs = d66_pair_pages(manifest)
    leaves = chapter_leaves(config["chapters"])
    target_pages = {f"{slug}.md": tuple(entry["pages"]) for slug, entry in leaves}
    paired_paths = match_chapter_paths(source_docs, target_docs, target_pages)
    source_for_target = {target: source for source, (target, _) in paired_paths.items()}
    style_path = project_root / "style-decisions.json"
    style = json.loads(style_path.read_text(encoding="utf-8")) if style_path.exists() else {}
    base = deployment_base_path(style)
    pdf = project_root / "data/pdfs" / (Path(config.get("source", "")).stem.removesuffix("_pages") + ".pdf")
    stats = Counter()
    for slug, entry in leaves:
        source_rel = source_for_target.get(f"{slug}.md")
        if source_rel is None:
            continue
        path = source_docs / source_rel
        if not path.exists():
            continue
        original = path.read_text(encoding="utf-8")
        front, body = split_frontmatter(original)
        if set(pairs).intersection({int(match) for match in re.findall(r"page(\d{3})_img", body)}):
            body, count = annotate_pair_pages(body, pairs)
            stats["dice_callouts_repaired"] += count
        def clean_image(match: re.Match[str]) -> str:
            filename = Path(match.group(1)).name
            if (filename in keep and filename not in chapter_classes.get(f"{slug}.md", {})) or filename not in known_images:
                return match.group(0)
            stats["images_removed"] += 1
            return ""
        body = IMAGE_RE.sub(clean_image, body)
        if dice.intersection(range(entry["pages"][0], entry["pages"][1] + 1)):
            body, count = repair_d66_tables(body)
            stats["dice_tables_repaired"] += count
        body, count = repair_english_toc(body, config["chapters"], leaves, base)
        stats["toc_entries_linked"] += count
        if pdf.exists():
            target = target_docs / f"{slug}.md"
            target_body = split_frontmatter(target.read_text(encoding="utf-8"))[1] if target.exists() else ""
            candidates = paired_english_headings(pdf_heading_catalog(pdf, tuple(entry["pages"])), target_body)
            body, count = recover_english_headings(body, candidates)
            stats["headings_recovered"] += count
        body = strip_page_furniture(body)
        revised = front + "\n" + body.strip() + "\n"
        if revised != original:
            path.write_text(revised, encoding="utf-8")
            stats["files_changed"] += 1
    return dict(stats)


def repair_staged_source(project_root: Path, source_docs: Path, reapply: bool = False) -> dict[str, object]:
    target_docs = project_root / "docs/src/content/docs"
    reason = None if reapply else recorded_repair(project_root / "data/layout-repair.json", target_docs, source_docs)
    if reason:
        return skipped("paired layout repair", reason)
    stats = Counter(_prepare_staged_source(project_root, source_docs))
    config = json.loads((project_root / "chapters.json").read_text(encoding="utf-8"))
    for section in config["chapters"].values():
        section["files"] = normalize_files(section.get("files", {}))
    pages = {f"{slug}.md": tuple(entry["pages"])
             for slug, entry in chapter_leaves(config["chapters"])}
    pdf = project_root / "data/pdfs" / (Path(config.get("source", "")).stem.removesuffix("_pages") + ".pdf")
    stats.update(repair_paired_layout(
        source_docs, target_docs, pdf, pages,
        project_root / "glossary.json", project_root / "data/layout-repair.json"))
    return dict(stats)


def layout_issues(project_root: Path, source_baseline: Path | None = None) -> list[str]:
    """Return publication-blocking PDF layout artifacts with file locations."""
    config_file = project_root / "chapters.json"
    docs = project_root / "docs/src/content/docs"
    if not config_file.is_file() or not docs.is_dir():
        return []
    config = json.loads(config_file.read_text(encoding="utf-8"))
    issues: list[str] = []
    for section in config.get("chapters", {}).values():
        section["files"] = normalize_files(section.get("files", {}))
    leaves_by_path = {f"{slug}.md": entry for slug, entry in chapter_leaves(config.get("chapters", {}))}
    plan_path = project_root / "data/layout-repair.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.is_file() else {}
    source_for_target_plan = {target: source for source, target in plan.get("targets", {}).items()}
    pdf = project_root / "data/pdfs" / (Path(config.get("source", "")).stem.removesuffix("_pages") + ".pdf")
    if source_baseline is None:
        candidate = project_root / ".state/template-sync/staging/docs/src/content/docs"
        source_baseline = candidate if candidate.is_dir() else None
    source_for_target = ({target: source for source, (target, _) in
                          match_chapter_paths(source_baseline, docs,
                                              {rel: tuple(entry["pages"]) for rel, entry in leaves_by_path.items()}).items()}
                         if source_baseline else {})
    source_path = project_root / config.get("source", "")
    pages = extract_pages(source_path.read_text(encoding="utf-8")) if source_path.is_file() else {}
    for slug, section in config.get("chapters", {}).items():
        title = section.get("title", "")
        if title and not re.search(r"[\u3400-\u9fff]", title):
            issues.append(f"chapters.json: untranslated section label {slug}: {title}")
    manifest = _image_manifest(project_root, config)
    chapter_classes = _chapter_image_classes(manifest, chapter_leaves(config.get("chapters", {})), _image_dir(project_root, config))
    known_images = {image["filename"] for image in manifest}
    if manifest:
        page_stats = build_page_text_stats(pages, config.get("clean_patterns", []))
        allowed, _ = group_images_by_page(manifest, page_stats, {"repeat_file_size_threshold": 5, "repeat_visual_threshold": 3})
        keep = {image["filename"] for group in allowed.values() for image in group}
    else:
        keep = set()

    def part_labels(path: Path) -> set[str]:
        """Sidebar group labels and chapters.json group titles above one page."""
        labels: set[str] = set()
        rel = path.relative_to(docs)
        if len(rel.parts) < 2:
            return labels
        section = config.get("chapters", {}).get(rel.parts[0], {})
        labels.update(section.get(key, "") for key in ("title", "translated_title"))
        meta = path.parent / "_meta.yml"
        if meta.is_file() and (match := re.search(r"(?m)^label:\s*(.+)$", meta.read_text(encoding="utf-8"))):
            labels.add(match.group(1).strip().strip("'\""))
        return {re.sub(r"\s+", "", label).casefold() for label in labels if label}

    for path in sorted(docs.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = front_title(text)
        body = split_frontmatter(text)[1]
        name = str(path.relative_to(project_root))
        if "" in body:
            issues.append(f"{name}: PDF bullet marker remains in rendered prose")
        for line_number, line in enumerate(body.splitlines(), 1):
            if re.match(r"^#\s+", line):
                issues.append(f"{name}:{line_number}: body H1 remains")
        entry = leaves_by_path.get(str(path.relative_to(docs)))
        if entry and pdf.is_file():
            source_rel = source_for_target.get(str(path.relative_to(docs)), str(path.relative_to(docs)))
            catalog = staged_missing_headings(source_baseline, source_rel.removesuffix(".md"),
                                              corroborated_headings(pdf, pages, tuple(entry["pages"])))
            _, pending_headings = recover_pdf_headings(body, catalog)
            if pending_headings:
                issues.append(f"{name}: {pending_headings} source-typography headings remain plain paragraphs")
        if title:
            normalized = re.sub(r"\s+", "", title).casefold()
            headings = [(level, re.sub(r"\s+", "", label).casefold())
                        for level, label in re.findall(r"(?m)^(#{1,6})\s+(.+?)\s*$", body)]
            first_line = next((line for line in body.splitlines() if line.strip()), "")
            first_h2 = first_line.startswith("## ") and re.sub(r"\s+", "", first_line[3:]).casefold() == normalized
            if first_h2 or any(level == "#" and label == normalized for level, label in headings):
                issues.append(f"{name}: body H1/H2 duplicates frontmatter title")
            if sum(label == normalized for _, label in headings) >= 2:
                issues.append(f"{name}: repeated body title headings")
        first_heading = re.search(r"(?m)^#{2,6}\s+(.+?)\s*$", body)
        if first_heading and re.sub(r"\s+", "", first_heading.group(1)).casefold() in part_labels(path):
            issues.append(f"{name}: first heading repeats chapter part label: {first_heading.group(1)}")
        for paragraph in re.split(r"\n\s*\n", body):
            p = paragraph.strip()
            if (re.fullmatch(r"\d{1,3}|[A-Za-z]|第\s*\d+\s*章|(?:第\s*\d+\s*頁[\s　]*)+|章節封面|CHAPTER COVER", p)
                    or DOT_LEADER_RE.search(p) or TOC_HEADING_RE.fullmatch(p)):
                issues.append(f"{name}: printed furniture or TOC: {p[:60]}")
        for match in IMAGE_RE.finditer(body):
            filename = Path(match.group(1)).name
            if filename in known_images and (filename not in keep or filename in chapter_classes.get(str(path.relative_to(docs)), {})):
                issues.append(f"{name}: layout image {filename}")
        for start, _ in find_empty_tables(text):
            issues.append(f"{name}:{start + 1}: empty table")
        source_rel = source_for_target_plan.get(str(path.relative_to(docs)))
        if source_rel and source_rel in plan.get("spreads", {}):
            probe = body.splitlines()
            if _format_translated_spread(probe, plan["chapters"][source_rel], plan["spreads"][source_rel]):
                issues.append(f"{name}: flattened illustrated callouts")
    for path in sorted(docs.rglob("_meta.yml")):
        match = re.search(r"(?m)^label:\s*(.+)$", path.read_text(encoding="utf-8"))
        if match and not re.search(r"[\u3400-\u9fff]", match.group(1)):
            issues.append(f"{path.relative_to(project_root)}: untranslated sidebar label")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true", help="Report publication-blocking layout artifacts")
    parser.add_argument("--staged-source", type=Path, help="Repair a writable copy of staged English chapters")
    parser.add_argument("--derive-layout-plan", action="store_true", help="Write PDF-backed layout evidence into project data")
    parser.add_argument("--structure-report", action="store_true", help="Report paired chapter structure findings")
    parser.add_argument("--reviewed-decisions", type=Path, help="Apply individually PDF-checked residual decisions")
    parser.add_argument("--source-baseline", type=Path, help="Read-only staging tree used to corroborate lost headings")
    parser.add_argument("--reapply", action="store_true",
                        help="Rerun the full repair after a recorded paired repair; overwrites later Markdown edits")
    args = parser.parse_args()
    project_root = args.project_root.resolve()
    if args.check:
        issues = layout_issues(project_root, args.source_baseline)
        for issue in issues:
            print(issue)
        print(f"layout issues: {len(issues)}")
        return 1 if issues else 0
    if args.structure_report:
        if not args.staged_source:
            parser.error("--structure-report requires --staged-source")
        plan = json.loads((project_root / "data/layout-repair.json").read_text(encoding="utf-8"))
        source_root, target_root = args.staged_source.resolve(), project_root / "docs/src/content/docs"
        counts = {target: len(compare_structure((source_root / source).read_text(encoding="utf-8"),
                                                 (target_root / target).read_text(encoding="utf-8"),
                                                 source_root / source, target_root / target))
                  for source, target in sorted(plan["targets"].items())}
        print(json.dumps({"chapters": counts, "total": sum(counts.values()),
                          "unresolved": len(plan.get("unresolved", [])),
                          "pdf_tiebreaks": len(plan.get("pdf_tiebreaks", [])),
                          "reviewed_overrides": sum(len(records) for side in plan.get("reviewed", {}).values()
                                                    for records in side.values())}, ensure_ascii=False, indent=2))
        return 0
    if args.reviewed_decisions and not args.derive_layout_plan and not args.staged_source:
        parser.error("--reviewed-decisions requires --staged-source")
    if args.reviewed_decisions and not args.derive_layout_plan:
        result = add_reviewed_decisions(project_root / "data/layout-repair.json",
                                        args.reviewed_decisions.resolve(), args.staged_source.resolve(),
                                        project_root / "docs/src/content/docs")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.derive_layout_plan:
        if not args.staged_source or args.reviewed_decisions:
            parser.error("--derive-layout-plan requires --staged-source without reviewed decisions")
        config = json.loads((project_root / "chapters.json").read_text(encoding="utf-8"))
        for section in config["chapters"].values():
            section["files"] = normalize_files(section.get("files", {}))
        pages = {f"{slug}.md": tuple(entry["pages"])
                 for slug, entry in chapter_leaves(config["chapters"])}
        pdf = project_root / "data/pdfs" / (Path(config["source"]).stem.removesuffix("_pages") + ".pdf")
        plan = project_root / "data/layout-repair.json"
        reason = None if args.reapply else recorded_repair(plan, project_root / "docs/src/content/docs",
                                                           args.staged_source.resolve())
        if reason:
            print(json.dumps(skipped("layout plan derivation", reason), ensure_ascii=False, indent=2))
            return 0
        prepared = _prepare_staged_source(project_root, args.staged_source.resolve())
        derived = derive_layout_plan(args.staged_source.resolve(), project_root / "docs/src/content/docs",
                                     pdf, pages, project_root / "glossary.json", plan)
        stats = {"chapters": len(derived["chapters"]), "unresolved": len(derived["unresolved"]),
                 "pdf_tiebreaks": len(derived.get("pdf_tiebreaks", [])), "staged_source_files_prepared": prepared.get("files_changed", 0)}
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return 0
    if args.staged_source:
        print(json.dumps(repair_staged_source(project_root, args.staged_source.resolve(), args.reapply), ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(repair(project_root, args.source_baseline, args.reapply), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
