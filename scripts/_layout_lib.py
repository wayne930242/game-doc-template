"""
版面偵測與文字品質探測工具

提供 PDF 頁面的版面分類（單欄/雙欄）、抽樣策略、
以及 pymupdf 文字流品質分析功能。
"""

import re
from pathlib import Path

try:
    import pymupdf
except ImportError:
    pymupdf = None

LONG_SPACE_RUN_RE = re.compile(r" {4,}")
NOISY_LINE_SPACE_RE = re.compile(r" {8,}")
MIN_QUALITY_PROBE_CHARS = 400
PYMUPDF_LAYOUT_NOISE_RATIO = 0.08
PYMUPDF_LAYOUT_NOISE_LINES = 4


def classify_page_layout(words: list[tuple], page_width: float) -> dict[str, object]:
    """根據單頁文字分布判斷是否為雙欄頁。"""
    if page_width <= 0:
        return {"layout_profile": "unknown", "confidence": 0.0, "classified_lines": 0}

    lines: dict[tuple[int, int], list[tuple[float, float, str]]] = {}
    for word in words:
        if len(word) < 8:
            continue
        x0, _y0, x1, _y1, text, block_no, line_no, _word_no = word[:8]
        text = str(text).strip()
        if len(re.sub(r"\W+", "", text)) < 2:
            continue
        key = (int(block_no), int(line_no))
        lines.setdefault(key, []).append((float(x0), float(x1), text))

    line_boxes: list[tuple[float, float]] = []
    for line_words in lines.values():
        line_words.sort(key=lambda item: item[0])
        joined = " ".join(text for _x0, _x1, text in line_words).strip()
        if len(joined) < 24:
            continue
        line_boxes.append(
            (
                min(x0 for x0, _x1, _text in line_words),
                max(x1 for _x0, x1, _text in line_words),
            )
        )

    if len(line_boxes) < 8:
        return {"layout_profile": "unknown", "confidence": 0.0, "classified_lines": len(line_boxes)}

    left_boundary = page_width * 0.48
    right_boundary = page_width * 0.51
    left_lines = sum(1 for x0, x1 in line_boxes if x1 <= left_boundary)
    right_lines = sum(1 for x0, x1 in line_boxes if x0 >= right_boundary)
    spanning_lines = sum(1 for x0, x1 in line_boxes if x0 < left_boundary and x1 > right_boundary)
    classified_lines = left_lines + right_lines + spanning_lines
    if classified_lines < 8:
        return {
            "layout_profile": "unknown",
            "confidence": 0.0,
            "classified_lines": classified_lines,
        }

    left_ratio = left_lines / classified_lines
    right_ratio = right_lines / classified_lines
    spanning_ratio = spanning_lines / classified_lines

    if (
        left_lines >= 3
        and right_lines >= 3
        and left_ratio >= 0.2
        and right_ratio >= 0.2
        and spanning_ratio <= 0.2
    ):
        confidence = round(min(0.99, (left_ratio + right_ratio) * (1 - spanning_ratio)), 2)
        return {
            "layout_profile": "double-column",
            "confidence": confidence,
            "classified_lines": classified_lines,
        }

    if spanning_ratio >= 0.45:
        return {
            "layout_profile": "single-column",
            "confidence": round(min(0.99, spanning_ratio), 2),
            "classified_lines": classified_lines,
        }

    return {
        "layout_profile": "unknown",
        "confidence": round(max(left_ratio, right_ratio, spanning_ratio), 2),
        "classified_lines": classified_lines,
    }


def sample_page_indices(total_pages: int, max_samples: int = 12) -> list[int]:
    """均勻抽樣頁碼索引。"""
    if total_pages <= 0:
        return []
    if total_pages <= max_samples:
        return list(range(total_pages))
    return sorted({round(i * (total_pages - 1) / (max_samples - 1)) for i in range(max_samples)})


def extract_page_text_pymupdf(page, sort: bool = True) -> str:
    """使用 pymupdf 直接提取單頁文字。

    ``sort=True``（預設）依幾何位置排序文字，但可能使多欄或表單版面交錯；
    版面雜訊較多時可傳入 ``sort=False``。
    """
    try:
        text = page.get_text("text", sort=sort)
    except TypeError:
        try:
            text = page.get_text("text")
        except TypeError:
            text = page.get_text()
    return text.strip()


def analyze_pymupdf_text_noise(text: str) -> dict[str, object]:
    """估算 pymupdf 文字是否混入大量版面空白或側欄干擾。"""
    normalized = text.replace("\x00", "")
    char_count = len(normalized)
    long_space_runs = [len(match.group(0)) for match in LONG_SPACE_RUN_RE.finditer(normalized)]
    long_space_chars = sum(long_space_runs)
    noisy_lines = sum(1 for line in normalized.splitlines() if NOISY_LINE_SPACE_RE.search(line))
    whitespace_ratio = round(long_space_chars / char_count, 4) if char_count else 0.0
    is_noisy = (
        char_count >= MIN_QUALITY_PROBE_CHARS
        and (
            whitespace_ratio >= PYMUPDF_LAYOUT_NOISE_RATIO
            or noisy_lines >= PYMUPDF_LAYOUT_NOISE_LINES
        )
    )
    return {
        "char_count": char_count,
        "long_space_runs": len(long_space_runs),
        "max_long_space_run": max(long_space_runs) if long_space_runs else 0,
        "noisy_lines": noisy_lines,
        "whitespace_ratio": whitespace_ratio,
        "is_noisy": is_noisy,
    }


def probe_pymupdf_text_quality(pdf_path: Path, max_samples: int = 12) -> dict[str, object]:
    """抽樣檢查 pymupdf 的文字流是否受版面噪訊污染。"""
    if pymupdf is None:
        return {
            "prefer_markitdown": False,
            "source": "pymupdf-quality-probe",
            "sampled_pages": [],
            "informative_pages": 0,
            "noisy_pages": 0,
            "required_noisy_pages": 0,
        }

    doc = pymupdf.open(str(pdf_path))
    try:
        results: list[dict[str, object]] = []
        for page_index in sample_page_indices(len(doc), max_samples=max_samples):
            page = doc[page_index]
            text = extract_page_text_pymupdf(page)
            result = analyze_pymupdf_text_noise(text)
            result["page"] = page_index + 1
            results.append(result)

        informative = [result for result in results if result["char_count"] >= MIN_QUALITY_PROBE_CHARS]
        noisy = [result for result in informative if result["is_noisy"]]
        required_noisy_pages = max(2, (len(informative) + 2) // 3) if informative else 0
        prefer_markitdown = bool(informative) and len(noisy) >= required_noisy_pages

        return {
            "prefer_markitdown": prefer_markitdown,
            "source": "pymupdf-quality-probe",
            "sampled_pages": results,
            "informative_pages": len(informative),
            "noisy_pages": len(noisy),
            "required_noisy_pages": required_noisy_pages,
        }
    finally:
        doc.close()


def detect_layout_profile(pdf_path: Path, max_samples: int = 12) -> dict[str, object]:
    """抽樣頁面，自動判斷單欄或雙欄。"""
    if pymupdf is None:
        return {
            "layout_profile": "single-column",
            "confidence": 0.0,
            "source": "fallback",
            "sampled_pages": [],
        }

    doc = pymupdf.open(str(pdf_path))
    try:
        results: list[dict[str, object]] = []
        for page_index in sample_page_indices(len(doc), max_samples=max_samples):
            page = doc[page_index]
            try:
                words = page.get_text("words", sort=False)
            except TypeError:
                words = page.get_text("words")
            result = classify_page_layout(words or [], float(page.rect.width))
            result["page"] = page_index + 1
            results.append(result)

        known = [result for result in results if result["layout_profile"] != "unknown"]
        if not known:
            return {
                "layout_profile": "single-column",
                "confidence": 0.0,
                "source": "auto-detect",
                "sampled_pages": results,
            }

        double_votes = sum(1 for result in known if result["layout_profile"] == "double-column")
        single_votes = sum(1 for result in known if result["layout_profile"] == "single-column")
        if double_votes > single_votes:
            layout_profile = "double-column"
            confidence = round(double_votes / len(known), 2)
        else:
            layout_profile = "single-column"
            confidence = round(single_votes / len(known), 2)

        return {
            "layout_profile": layout_profile,
            "confidence": confidence,
            "source": "auto-detect",
            "sampled_pages": results,
        }
    finally:
        doc.close()
