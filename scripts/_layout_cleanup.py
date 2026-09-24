"""Source-backed cleanup shared by chapter splitting and translated-site repair."""

from __future__ import annotations

import re
from collections import Counter


def placement_key(image: dict) -> tuple | None:
    """Identify one PDF XObject at one physical placement."""
    if image.get("xref") is None or image.get("x") is None or image.get("y") is None:
        return None
    return (
        int(image["page"]),
        int(image["xref"]),
        round(float(image["x"]), 1),
        round(float(image["y"]), 1),
        round(float(image.get("width") or 0), 1),
        round(float(image.get("height") or 0), 1),
    )


def unique_placements(images: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    result: list[dict] = []
    for image in images:
        key = placement_key(image)
        if key is not None and key in seen:
            continue
        if key is not None:
            seen.add(key)
        result.append(image)
    return result


def is_d66_icon(image: dict) -> bool:
    width, height = image.get("width"), image.get("height")
    return bool(width and height and 8 <= float(width) <= 11 and 8 <= float(height) <= 11)


def d66_pages(images: list[dict]) -> set[int]:
    counts = Counter(int(image["page"]) for image in unique_placements(images) if is_d66_icon(image))
    return {page for page, count in counts.items() if count >= 30}


def d66_pair_pages(images: list[dict]) -> dict[int, int]:
    """Find six consecutive spread pages with two three-face D66 callouts."""
    counts = Counter(
        int(image["page"]) for image in unique_placements(images)
        if 13 <= float(image.get("width") or 0) <= 15
        and 13 <= float(image.get("height") or 0) <= 15
    )
    candidates = sorted(page for page, count in counts.items() if count == 6)
    groups: dict[int, int] = {}
    for start in candidates:
        run = list(range(start, start + 6))
        if all(page in candidates for page in run):
            groups.update({page: index + 1 for index, page in enumerate(run)})
    return groups


def annotate_d66_pair_headings(text: str, first_die: int) -> tuple[str, int]:
    lines = text.splitlines()
    indices = [i for i, line in enumerate(lines) if re.match(r"^#{2,6} ", line)]
    if len(indices) < 2:
        return text, 0
    changed = 0
    for index, suffix in zip(indices[-2:], ("1–3", "4–6")):
        if "D66" not in lines[index]:
            start, end = suffix.split("–")
            lines[index] += f"（D66：{first_die}{start}–{first_die}{end}）"
            changed += 1
    return "\n".join(lines), changed


def is_page_ornament(image: dict, repeat_count: int) -> bool:
    """Drop repeated marginal art and blank pixels; keep labeled rank and scene art."""
    width, height = image.get("width"), image.get("height")
    pw, ph = image.get("page_width"), image.get("page_height")
    x, y = image.get("x"), image.get("y")
    if not all(value is not None for value in (width, height, pw, ph, x, y)):
        return False
    width, height, pw, ph, x, y = map(float, (width, height, pw, ph, x, y))
    if width <= 2 and height <= 2:
        return True
    if repeat_count < 5:
        return False
    footer = y >= ph * 0.87 and height <= ph * 0.08 and width <= pw * 0.22
    side_ribbon = x <= pw * 0.04 and width <= pw * 0.12 and height <= ph * 0.08
    heading_backdrop = y <= ph * 0.09 and width >= pw * 0.8 and height <= ph * 0.25
    bottom_flourish = y >= ph * 0.72 and width <= pw * 0.4 and height <= ph * 0.08
    divider_flourish = width <= pw * 0.34 and height <= ph * 0.065 and width / max(height, 1) >= 3.4
    callout_ring = (x <= pw * 0.2 and y >= ph * 0.55 and
                    pw * 0.2 <= width <= pw * 0.3 and ph * 0.15 <= height <= ph * 0.22)
    return footer or side_ribbon or heading_backdrop or bottom_flourish or divider_flourish or callout_ring


_FURNITURE = re.compile(
    r"(?m)(?<=\n\n)(?:\d{1,3}|[A-Za-z]|第\s*\d+\s*章|(?:第\s*\d+\s*頁[\s　]*)+|章節封面|CHAPTER COVER)(?=\n\n|\n?$)"
)


def strip_page_furniture(text: str) -> str:
    """Remove isolated printed furniture, leaving table cells and list items intact."""
    padded = "\n\n" + text.strip() + "\n\n"
    return re.sub(r"\n{3,}", "\n\n", _FURNITURE.sub("", padded)).strip()


def strip_duplicate_title(text: str, title: str) -> str:
    normalized = re.sub(r"\s+", "", title).casefold()
    lines = text.splitlines()
    cleaned_lines: list[str] = []
    first_content = True
    for line in lines:
        h1 = line.startswith("# ") and re.sub(r"\s+", "", line[2:]).casefold() == normalized
        h2 = first_content and line.startswith("## ") and re.sub(r"\s+", "", line[3:]).casefold() == normalized
        if not (h1 or h2):
            cleaned_lines.append(line)
        if line.strip():
            first_content = False
    cleaned = "\n".join(cleaned_lines).strip()
    return re.sub(r"\n{3,}", "\n\n", cleaned)


def repair_d66_tables(text: str) -> tuple[str, int]:
    """Restore D66 indices on the two table layouts observed in the source PDF.

    Call only for pages where the image manifest contains a full 36-face table.
    The 12-row layout groups three second-die values per result; the 18-row
    layout prints two sets of 18 results side by side.
    """
    lines = text.splitlines()
    output: list[str] = []
    repaired = 0
    i = 0
    while i < len(lines):
        if not lines[i].startswith("|") or i + 1 >= len(lines) or not re.fullmatch(r"\|[-:| ]+\|", lines[i + 1]):
            output.append(lines[i]); i += 1; continue
        j = i + 2
        while j < len(lines) and lines[j].startswith("|"):
            j += 1
        cells = [[cell.strip() for cell in line.strip("|").split("|")] for line in lines[i:j]]
        header, rows = cells[0], cells[2:]
        if len(rows) == 12 and len(header) == 4 and all(len(row) == 4 and not row[0] and row[2] and row[3] for row in rows):
            caption = header[0]
            output += [f"**{caption}**", "", "| D66 | 項目 | 說明 |", "| --- | --- | --- |"]
            for index, row in enumerate(rows):
                first = index // 2 + 1
                start, end = (1, 3) if index % 2 == 0 else (4, 6)
                output.append(f"| {first}{start}–{first}{end} | {row[2]} | {row[3]} |")
            repaired += 1
        elif len(rows) == 18 and len(header) == 6 and all(len(row) == 6 and not row[0] and not row[1] and not row[3] and not row[4] and row[2] and row[5] for row in rows):
            caption = header[0]
            output += [f"**{caption}**", "", "| D66 | 項目 | D66 | 項目 |", "| --- | --- | --- | --- |"]
            for index, row in enumerate(rows):
                second = index % 6 + 1
                left = index // 6 + 1
                right = left + 3
                output.append(f"| {left}{second} | {row[2]} | {right}{second} | {row[5]} |")
            repaired += 1
        else:
            output.extend(lines[i:j])
        i = j
    return "\n".join(output), repaired
