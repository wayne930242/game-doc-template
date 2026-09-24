"""Source-backed cleanup shared by chapter splitting and translated-site repair."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path


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


def is_edge_sliver(image: dict) -> bool:
    """Detect bleed and frame strips cut off at a page edge.

    A sliver touches a page edge along its thin side, spans at most 7% of the
    page across, and is at least ten times longer than it is thin. Symbols and
    rules inside the page fail one of these tests. The 7% bound admits a 6.7%
    crop of spread art and rejects 10% column art standing on the edge.
    """
    width, height = image.get("width"), image.get("height")
    pw, ph = image.get("page_width"), image.get("page_height")
    x, y = image.get("x"), image.get("y")
    if not all(value is not None for value in (width, height, pw, ph, x, y)):
        return False
    width, height, pw, ph, x, y = map(float, (width, height, pw, ph, x, y))
    vertical = (x <= 1 or x + width >= pw - 1) and width <= pw * 0.07 and height >= width * 10
    horizontal = (y <= 1 or y + height >= ph - 1) and height <= ph * 0.07 and width >= height * 10
    return vertical or horizontal


def is_edge_tab(image: dict) -> bool:
    """Detect printed thumb-index tabs and banner flags standing on a side edge.

    A tab touches the left or right page edge and stays within 10% of the page
    width and 7% of its height; printed tabs measure about 6-9% by 6%. Inline
    symbols and rules sit inside the page, and edge art is larger.
    """
    width, height = image.get("width"), image.get("height")
    pw, ph = image.get("page_width"), image.get("page_height")
    x = image.get("x")
    if not all(value is not None for value in (width, height, pw, ph, x)):
        return False
    width, height, pw, ph, x = map(float, (width, height, pw, ph, x))
    return (x <= 1 or x + width >= pw - 1) and width <= pw * 0.1 and height <= ph * 0.07


def is_edge_furniture(image: dict) -> bool:
    return is_edge_sliver(image) or is_edge_tab(image) or is_inner_edge_sliver(image)


def is_inner_edge_sliver(image: dict) -> bool:
    """Find low-detail, narrow frame crops close to a page's vertical edge."""
    keys = ("x", "width", "height", "page_width", "file_size", "dominant_color_ratio", "edge_density")
    if any(image.get(key) is None for key in keys):
        return False
    x, width, height, page_width = (float(image[key]) for key in keys[:4])
    return (page_width > 0 and width > 0 and height > 0
            and width <= page_width * 0.11 and height >= width * 10
            and (x <= page_width * 0.05 or x + width >= page_width * 0.95)
            and int(image["file_size"]) <= 5000
            and float(image["dominant_color_ratio"]) >= 0.8
            and float(image["edge_density"]) <= 0.05)


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


def layout_art_classes(images: list[dict]) -> dict[str, str]:
    """Classify non-content page art using decoded pixels and PDF placement.

    Pale, low-edge images are paper; near-binary black/white images are
    clipping masks or small frame fragments. Repeated pixels identify small
    marginal marks and thin rules.
    """
    images = unique_placements(images)
    classified: dict[str, str] = {}
    by_digest: dict[str, list[dict]] = {}
    for image in images:
        filename = image["filename"]
        coverage = float(image.get("coverage_ratio") or 0)
        mean = image.get("gray_mean")
        deviation = image.get("gray_std")
        edges = image.get("edge_density")
        if all(value is not None for value in (mean, deviation, edges)):
            if (coverage >= 0.35 or (coverage >= 0.15 and float(deviation) >= 10)) and (
                    float(mean) >= 180 and float(deviation) <= 55 and float(edges) <= 0.07):
                classified[filename] = "paper_texture"
            elif (coverage >= 0.45 and float(deviation) >= 90 and float(edges) <= 0.12
                  and float(image.get("white_ratio") or 0) >= 0.15
                  and float(image.get("black_ratio") or 0) >= 0.4
                  and float(image.get("white_ratio") or 0) + float(image.get("black_ratio") or 0) >= 0.8):
                classified[filename] = "ink_mask"
            if (0.02 <= coverage <= 0.1 and image.get("file_size") is not None
                    and int(image["file_size"]) <= 10000
                    and float(edges) <= 0.1
                    and float(image.get("white_ratio") or 0) + float(image.get("black_ratio") or 0) >= 0.95
                    and float(image.get("dominant_color_ratio") or 0) >= 0.6
                    and not is_inner_edge_sliver(image)):
                classified[filename] = "small_binary_fragment"
        if image.get("pixel_sha256"):
            by_digest.setdefault(str(image["pixel_sha256"]), []).append(image)

    # Reused small marks and paired shallow rules decorate the printed page.
    for group in by_digest.values():
        pages = Counter(int(image["page"]) for image in group)
        for image in group:
            pw, ph = float(image.get("page_width") or 0), float(image.get("page_height") or 0)
            width, height = float(image.get("width") or 0), float(image.get("height") or 0)
            coverage = float(image.get("coverage_ratio") or 0)
            x = image.get("x")
            marginal = x is not None and (float(x) <= pw * 0.13 or float(x) + width >= pw * 0.87)
            simple = (image.get("file_size") is not None and int(image["file_size"]) <= 500
                      and image.get("edge_density") is not None and float(image["edge_density"]) <= 0.02)
            if (len(pages) >= 3 and pw and ph and width > 0 and height > 0
                    and width <= pw * 0.13 and height <= ph * 0.1 and coverage <= 0.01
                    and (marginal or simple)):
                classified[image["filename"]] = "repeated_small_mark"
            if (pages[int(image["page"])] >= 2 and pw and ph
                    and width <= pw * 0.055 and height <= ph * 0.045
                    and coverage <= 0.002):
                classified[image["filename"]] = "repeated_tiny_fragment"
            if (pages[int(image["page"])] >= 2 and pw and ph and height > 0
                    and width <= pw * 0.55 and height <= ph * 0.025
                    and width / height >= 12 and coverage <= 0.02
                    and image.get("file_size") is not None
                    and int(image["file_size"]) <= 1000):
                classified[image["filename"]] = "repeated_thin_rule"
            if (pages[int(image["page"])] >= 2 and pw and ph and
                    width <= pw * 0.36 and height <= ph * 0.07 and
                    width / max(height, 1) >= 3.4):
                classified[image["filename"]] = "repeated_flourish"

    # Full-page illustrations can recur with a new XObject or a slightly
    # different raster crop. Preserve the first placement as the book image.
    large = sorted((image for image in images
                    if image["filename"] not in classified
                    and float(image.get("coverage_ratio") or 0) >= 0.5
                    and image.get("visual_hash") and image.get("gray_mean") is not None),
                   key=lambda image: (int(image["page"]), image["filename"]))
    firsts: list[dict] = []
    for image in large:
        match = next((first for first in firsts if _same_large_art(first, image)), None)
        if match is None:
            firsts.append(image)
        else:
            classified[image["filename"]] = "repeated_art"
    return classified


def _same_large_art(first: dict, image: dict) -> bool:
    if first.get("pixel_sha256") and first["pixel_sha256"] == image.get("pixel_sha256"):
        return True
    width_ratio = float(first.get("width") or 0) / max(float(first.get("height") or 0), 1)
    other_ratio = float(image.get("width") or 0) / max(float(image.get("height") or 0), 1)
    return (abs(width_ratio - other_ratio) <= 0.03
            and abs(float(first["gray_mean"]) - float(image["gray_mean"])) <= 5
            and abs(float(first["gray_std"]) - float(image["gray_std"])) <= 5
            and (int(str(first["visual_hash"]), 16) ^ int(str(image["visual_hash"]), 16)).bit_count() <= 10)


def chapter_fragment_classes(images: list[dict], start: int, end: int, image_dir: Path | None = None) -> dict[str, str]:
    """Classify repeated panel pieces and reused art within one output page."""
    images = unique_placements(images)
    global_art = layout_art_classes(images)
    chapter = sorted((image for image in images if start <= int(image["page"]) <= end),
                     key=lambda image: (int(image["page"]), image["filename"]))
    digest_pages: dict[str, Counter[int]] = {}
    for image in images:
        if digest := image.get("pixel_sha256"):
            digest_pages.setdefault(str(digest), Counter())[int(image["page"])] += 1
    panels = [image for image in chapter if _is_repeated_panel_piece(image, digest_pages)]
    classified = ({image["filename"]: "repeated_panel_piece" for image in panels}
                  if len(panels) >= 2 else {})

    previous: list[dict] = []
    feature_cache: dict[str, tuple] = {}
    for image in chapter:
        if image["filename"] in classified or image["filename"] in global_art or not _is_art_candidate(image):
            continue
        match = next((first for first in previous if 0 < int(image["page"]) - int(first["page"]) <= 4
                      and _same_chapter_art(first, image, image_dir, feature_cache)), None)
        if match is None:
            previous.append(image)
        else:
            classified[image["filename"]] = "reused_chapter_art"
    return classified


def _is_repeated_panel_piece(image: dict, digest_pages: dict[str, Counter[int]]) -> bool:
    pw, ph = float(image.get("page_width") or 0), float(image.get("page_height") or 0)
    width, height = float(image.get("width") or 0), float(image.get("height") or 0)
    coverage = float(image.get("coverage_ratio") or 0)
    digest = str(image.get("pixel_sha256") or "")
    occurrences = digest_pages.get(digest, Counter())
    repeated = len(occurrences) >= 3 or max(occurrences.values(), default=0) >= 3
    return bool(pw and ph and height and digest and repeated
                and coverage <= 0.04 and width <= pw * 0.4 and height <= ph * 0.12
                and width / height >= 2.3)


def _is_art_candidate(image: dict) -> bool:
    return (float(image.get("coverage_ratio") or 0) >= 0.07
            and int(image.get("file_size") or 0) >= 50000)


def _same_chapter_art(first: dict, image: dict, image_dir, feature_cache: dict) -> bool:
    if first.get("pixel_sha256") and first["pixel_sha256"] == image.get("pixel_sha256"):
        return True
    if (image_dir is None or first.get("gray_mean") is None or image.get("gray_mean") is None
            or abs(float(first["gray_mean"]) - float(image["gray_mean"])) > 25):
        return False
    import cv2
    import numpy as np

    def features(item: dict):
        name = item["filename"]
        if name not in feature_cache:
            path = image_dir / name
            pixels = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE) if path.is_file() else None
            feature_cache[name] = ([], None) if pixels is None else cv2.SIFT_create(nfeatures=700).detectAndCompute(pixels, None)
        return feature_cache[name]

    first_points, first_desc = features(first)
    image_points, image_desc = features(image)
    if first_desc is None or image_desc is None:
        return False
    pairs = cv2.BFMatcher().knnMatch(first_desc, image_desc, k=2)
    matches = [best for pair in pairs if len(pair) == 2 for best, second in [pair]
               if best.distance < second.distance * 0.72]
    if len(matches) < 60:
        return False
    source = np.float32([first_points[pair.queryIdx].pt for pair in matches]).reshape(-1, 1, 2)
    target = np.float32([image_points[pair.trainIdx].pt for pair in matches]).reshape(-1, 1, 2)
    _, mask = cv2.findHomography(source, target, cv2.RANSAC, 4.0)
    return mask is not None and int(mask.sum()) >= 60 and float(mask.mean()) >= 0.7


_FURNITURE = re.compile(
    r"(?m)(?<=\n\n)(?:\d{1,3}|[A-Za-z]|第\s*\d+\s*章|(?:第\s*\d+\s*頁[\s　]*)+|章節封面|CHAPTER COVER)(?=\n\n|\n?$)"
)


_COVER_MARKER = re.compile(r"(?im)^(?:chapter\s+cover|章節封面)$")
_PAGE_MARKER = re.compile(r"(<!-- PAGE \d+ -->)")


def strip_chapter_cover(page: str) -> str:
    """Empty one page's text when it is a chapter cover.

    A cover page carries the printed `CHAPTER COVER` label (on one line or two)
    beside at most four short lines such as the chapter number and part name.
    Its text is page furniture; the cover art comes from the image manifest.
    """
    lines = "\n".join(line.strip().lstrip("#").strip() for line in page.splitlines() if line.strip())
    if not _COVER_MARKER.search(lines):
        return page
    rest = [line for line in _COVER_MARKER.sub("", lines).splitlines() if line.strip()]
    if len(rest) > 4 or any(len(line) > 60 for line in rest):
        return page
    return ""


def strip_chapter_covers(text: str) -> tuple[str, list[str]]:
    """Empty every cover page in `<!-- PAGE N -->` text; return removed page texts."""
    parts = _PAGE_MARKER.split(text)
    removed: list[str] = []
    for index in range(2, len(parts), 2):
        if parts[index].strip() and not strip_chapter_cover(parts[index]):
            removed.append(parts[index].strip())
            parts[index] = "\n\n" if index + 1 < len(parts) else "\n"
    return "".join(parts), removed


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
