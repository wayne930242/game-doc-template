"""
圖片分析共用模組
提供圖片視覺指紋、背景判定與去重用的存取函式。
"""

import hashlib
import math
from collections import Counter
from pathlib import Path

try:
    import pymupdf
except ImportError:
    pymupdf = None


# Formats every browser displays. PDF-embedded images in any other format (JPEG 2000
# `jpx`, JBIG2 `jb2`, ...) render empty on the site and are re-encoded as PNG.
WEB_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def pixmap_to_png(pixmap: "pymupdf.Pixmap") -> bytes:
    """Encode a decoded image as PNG, converting non-gray/RGB colorspaces (e.g. CMYK) to RGB."""
    if pixmap.colorspace is not None and pixmap.colorspace.n not in (1, 3):
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pixmap)
    return pixmap.tobytes("png")


def compute_visual_hash(samples: list[int]) -> str | None:
    """根據灰階採樣建立簡單視覺指紋。"""
    if not samples:
        return None
    average = sum(samples) / len(samples)
    bits = "".join("1" if sample >= average else "0" for sample in samples)
    return f"{int(bits, 2):016x}"


def analyze_image_bytes(image_bytes: bytes) -> dict[str, object]:
    """分析圖片內容，提供背景判定可用的視覺特徵。"""
    if pymupdf is None or not hasattr(pymupdf, "Pixmap"):
        return {}

    try:
        pixmap = pymupdf.Pixmap(image_bytes)
    except Exception:
        return {}

    width = int(getattr(pixmap, "width", 0) or 0)
    height = int(getattr(pixmap, "height", 0) or 0)
    stride = int(getattr(pixmap, "stride", 0) or 0)
    channel_count = int(getattr(pixmap, "n", 0) or 0)
    samples = getattr(pixmap, "samples", b"")

    if width <= 0 or height <= 0 or stride <= 0 or channel_count <= 0 or not samples:
        return {}

    color_counts: Counter[tuple[int, int, int]] = Counter()
    grayscale_samples: list[int] = []
    max_sample_axis = 48
    grid_axis = 8
    step_x = max(1, width // max_sample_axis)
    step_y = max(1, height // max_sample_axis)

    def sample_rgb(x: int, y: int) -> tuple[int, int, int]:
        offset = y * stride + x * channel_count
        pixel = samples[offset: offset + channel_count]
        if not pixel:
            return (0, 0, 0)
        if channel_count == 1:
            value = pixel[0]
            return (value, value, value)
        if channel_count >= 3:
            return (pixel[0], pixel[1], pixel[2])
        value = pixel[0]
        return (value, value, value)

    for y in range(0, height, step_y):
        for x in range(0, width, step_x):
            r, g, b = sample_rgb(x, y)
            color_counts[(r // 16, g // 16, b // 16)] += 1

    for grid_y in range(grid_axis):
        sample_y = min(height - 1, int((grid_y + 0.5) * height / grid_axis))
        for grid_x in range(grid_axis):
            sample_x = min(width - 1, int((grid_x + 0.5) * width / grid_axis))
            r, g, b = sample_rgb(sample_x, sample_y)
            grayscale = int(0.299 * r + 0.587 * g + 0.114 * b)
            grayscale_samples.append(grayscale)

    # The same 64x64 grid captures broad paper grain and black/white masks
    # without tying thresholds to the PDF image's native resolution.
    detail_axis = 64
    detail = []
    for grid_y in range(detail_axis):
        y = min(height - 1, int((grid_y + 0.5) * height / detail_axis))
        for grid_x in range(detail_axis):
            x = min(width - 1, int((grid_x + 0.5) * width / detail_axis))
            r, g, b = sample_rgb(x, y)
            detail.append((r + g + b) / 3)
    mean = sum(detail) / len(detail)
    deviation = math.sqrt(sum((value - mean) ** 2 for value in detail) / len(detail))
    horizontal_edges = sum(
        abs(detail[index] - detail[index + 1]) > 25
        for index in range(len(detail)) if index % detail_axis < detail_axis - 1
    )

    total_samples = sum(color_counts.values())
    dominant_color_ratio = None
    if total_samples:
        dominant_color_ratio = round(max(color_counts.values()) / total_samples, 4)

    return {
        "visual_hash": compute_visual_hash(grayscale_samples),
        "dominant_color_ratio": dominant_color_ratio,
        "sampled_pixel_count": total_samples,
        "pixel_sha256": hashlib.sha256(
            f"{width}x{height}x{channel_count}:".encode() + samples
        ).hexdigest(),
        "gray_mean": round(mean, 2),
        "gray_std": round(deviation, 2),
        "edge_density": round(horizontal_edges / len(detail), 4),
        "white_ratio": round(sum(value >= 245 for value in detail) / len(detail), 4),
        "black_ratio": round(sum(value <= 20 for value in detail) / len(detail), 4),
    }


def enrich_image_manifest(images: list[dict], image_dir: Path) -> list[dict]:
    """Add pixel evidence to manifests written by earlier template versions."""
    for image in images:
        if image.get("pixel_sha256") and image.get("gray_mean") is not None:
            continue
        path = image_dir / image["filename"]
        if path.is_file():
            image.update(analyze_image_bytes(path.read_bytes()))
    return images


def image_file_size_key(image: dict) -> int | None:
    """為圖片建立檔案大小去重 key。"""
    file_size = image.get("file_size")
    if file_size is None:
        return None
    return int(file_size)


def image_visual_key(image: dict) -> str | None:
    """為圖片建立視覺去重 key。"""
    visual_hash = image.get("visual_hash")
    if not visual_hash:
        return None
    return str(visual_hash)


def image_coverage_ratio(image: dict) -> float | None:
    """讀取圖片覆蓋頁面的比例。"""
    ratio = image.get("coverage_ratio")
    if ratio is None:
        return None
    return float(ratio)


def image_dominant_color_ratio(image: dict) -> float | None:
    """讀取圖片單色占比。"""
    ratio = image.get("dominant_color_ratio")
    if ratio is None:
        return None
    return float(ratio)


def image_page_dimensions(image: dict) -> tuple[float, float] | tuple[None, None]:
    """讀取圖片所屬頁面的寬高。"""
    page_width = image.get("page_width")
    page_height = image.get("page_height")
    if page_width is None or page_height is None:
        return None, None
    return float(page_width), float(page_height)


def is_background_candidate(
    image: dict,
    page_text_stats: dict[int, dict[str, int]],
    policy: dict,
) -> bool:
    """判斷圖片是否符合大面積背景候選條件。"""
    coverage_ratio = image_coverage_ratio(image)
    if coverage_ratio is None:
        return False

    page_stat = page_text_stats.get(int(image["page"]), {})
    text_tokens = int(page_stat.get("text_tokens", 0))
    if text_tokens < int(policy.get("background_min_text_tokens", 80) or 0):
        return False

    if coverage_ratio >= float(policy.get("background_min_coverage_ratio", 0.6)):
        return True

    page_width, page_height = image_page_dimensions(image)
    image_width = image.get("width")
    image_height = image.get("height")
    image_x = image.get("x")
    image_y = image.get("y")
    if (
        page_width is None
        or page_height is None
        or image_width is None
        or image_height is None
        or image_x is None
        or image_y is None
    ):
        return False

    image_width = float(image_width)
    image_height = float(image_height)
    image_x = float(image_x)
    image_y = float(image_y)
    edge_margin_ratio = float(policy.get("background_edge_margin_ratio", 0.08))
    edge_min_area_ratio = float(policy.get("background_edge_min_area_ratio", 0.18))
    edge_min_span_ratio = float(policy.get("background_edge_min_span_ratio", 0.7))

    touches_left = image_x <= page_width * edge_margin_ratio
    touches_top = image_y <= page_height * edge_margin_ratio
    touches_right = (image_x + image_width) >= page_width * (1 - edge_margin_ratio)
    touches_bottom = (image_y + image_height) >= page_height * (1 - edge_margin_ratio)
    touches_edge = touches_left or touches_top or touches_right or touches_bottom
    width_ratio = image_width / page_width if page_width else 0.0
    height_ratio = image_height / page_height if page_height else 0.0
    span_ratio = max(width_ratio, height_ratio)

    return (
        touches_edge
        and coverage_ratio >= edge_min_area_ratio
        and span_ratio >= edge_min_span_ratio
    )
