#!/usr/bin/env python3
"""
PDF 提取工具
將 PDF / EPUB / 圖片來源轉換為 Markdown，支援文字提取、OCR 與圖片提取

使用方式：
    python scripts/extract_pdf.py <source_file>
    python scripts/extract_pdf.py <source_file> --include-images
    python scripts/extract_pdf.py <source_file> --no-include-images
    python scripts/extract_pdf.py <source_file> --skip-full-markitdown
    python scripts/extract_pdf.py <source_file> --layout-profile double-column
    python scripts/extract_pdf.py <source_file> --page-text-engine ocr

輸出：
    data/markdown/<檔名>.md                 - 整本文字版本
    data/markdown/<檔名>_pages.md           - 含頁碼標記版本（用於章節拆分）
    data/markdown/images/<檔名>/            - 提取的圖片
    data/markdown/images/<檔名>/manifest.json - 圖片位置與尺寸資訊
"""

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

from _epub_lib import (
    extract_epub_images,
    extract_epub_with_pages,
    should_print_progress,
)
from _image_analysis import WEB_IMAGE_EXTENSIONS, analyze_image_bytes, pixmap_to_png
from _layout_lib import (
    detect_layout_profile,
    extract_page_text_pymupdf,
    probe_pymupdf_text_quality,
)
from _markdown_utils import (
    clean_symbol_glyph_ornaments,
    merge_list_continuations,
    merge_paragraph_continuations,
    strip_artifact_headings,
)
from _ocr_lib import (
    DEFAULT_OCR_DPI,
    DEFAULT_OCR_LANG,
    DEFAULT_OCR_PSM,
    IMAGE_SOURCE_SUFFIXES,
    ensure_tesseract_ready,
    find_ocr_image_files,
    render_pdf_page_for_ocr,
    run_tesseract_ocr,
)
from _opendataloader_lib import (
    check_availability as check_opendataloader_availability,
    is_available as is_opendataloader_available,
    convert_pdf_pages as opendataloader_convert_pages,
    convert_pdf_to_markdown as opendataloader_convert_markdown,
    write_pages_file as opendataloader_write_pages,
)

try:
    from markitdown import MarkItDown
except ImportError:
    MarkItDown = None

try:
    import pymupdf
except ImportError:
    pymupdf = None


VALID_PAGE_TEXT_ENGINES = {"auto", "ocr", "pymupdf", "markitdown", "opendataloader"}
VALID_LAYOUT_PROFILES = {"auto", "single-column", "double-column"}
SUPPORTED_FILE_SOURCE_TYPES = {
    ".pdf": "pdf",
    ".epub": "epub",
    **{suffix: "image" for suffix in IMAGE_SOURCE_SUFFIXES},
}
PAGE_TEXT_ENGINE_ALIASES = {
    "fitz": "pymupdf",
    "markdown": "markitdown",
    "tesseract": "ocr",
    "odl": "opendataloader",
    "open-data-loader": "opendataloader",
}
LAYOUT_PROFILE_ALIASES = {
    "single": "single-column",
    "single_column": "single-column",
    "double": "double-column",
    "double_column": "double-column",
    "two-column": "double-column",
    "two_column": "double-column",
}


def normalize_page_text_engine(value: object) -> str | None:
    """正規化頁面文字引擎設定。"""
    if value is None:
        return None
    normalized = str(value).strip().lower()
    normalized = PAGE_TEXT_ENGINE_ALIASES.get(normalized, normalized)
    if normalized in VALID_PAGE_TEXT_ENGINES:
        return normalized
    return None


def normalize_layout_profile(value: object) -> str | None:
    """正規化版面設定。"""
    if value is None:
        return None
    normalized = str(value).strip().lower()
    normalized = LAYOUT_PROFILE_ALIASES.get(normalized, normalized)
    if normalized in VALID_LAYOUT_PROFILES:
        return normalized
    return None


def normalize_pymupdf_sort_text(value: object) -> bool | None:
    """正規化 pymupdf 幾何排序設定。"""
    if isinstance(value, bool):
        return value
    return None


def normalize_watermarks(value: object) -> list[str] | None:
    """正規化要移除的浮水印字串清單。"""
    if not isinstance(value, list):
        return None
    if not all(isinstance(item, str) for item in value):
        return None
    return list(value)


def normalize_symbol_glyphs(value: object) -> list[str] | None:
    """正規化視為裝飾性符號字型殘留字元的清單。"""
    if not isinstance(value, list):
        return None
    if not all(isinstance(item, str) for item in value):
        return None
    return list(value)


DOCUMENT_FORMAT_FIELDS = (
    ("page_text_engine", normalize_page_text_engine),
    ("layout_profile", normalize_layout_profile),
    ("pymupdf_sort_text", normalize_pymupdf_sort_text),
    ("watermarks", normalize_watermarks),
    ("symbol_glyphs", normalize_symbol_glyphs),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="將 PDF / EPUB / 圖片來源提取成可切分的 Markdown")
    parser.add_argument("source_file", help="來源 PDF / EPUB / 圖片檔案或圖片資料夾")
    parser.add_argument(
        "--skip-full-markitdown",
        action="store_true",
        help="略過整本 Markdown 輸出，只保留 _pages.md 與圖片輸出",
    )
    parser.add_argument(
        "--page-text-engine",
        choices=("auto", "ocr", "pymupdf", "markitdown", "opendataloader"),
        default="auto",
        help="生成 _pages.md 時使用的頁面文字引擎（預設: auto；圖片來源固定使用 ocr；EPUB 固定使用 markitdown）",
    )
    parser.add_argument(
        "--layout-profile",
        choices=("auto", "single-column", "double-column"),
        default="auto",
        help="文件版面設定（預設: auto；EPUB 目前不使用此設定）",
    )
    parser.add_argument(
        "--ocr-lang",
        default=DEFAULT_OCR_LANG,
        help=f"OCR 語言設定，傳給 tesseract（預設: {DEFAULT_OCR_LANG}）",
    )
    parser.add_argument(
        "--ocr-psm",
        type=int,
        default=DEFAULT_OCR_PSM,
        help=f"OCR Page Segmentation Mode（預設: {DEFAULT_OCR_PSM}）",
    )
    parser.add_argument(
        "--ocr-dpi",
        type=int,
        default=DEFAULT_OCR_DPI,
        help=f"PDF 走 OCR 時的頁面 render DPI（預設: {DEFAULT_OCR_DPI}）",
    )
    parser.add_argument(
        "--watermark",
        dest="watermarks",
        action="append",
        default=None,
        help="要從輸出 Markdown 移除的浮水印字串，可重複指定（預設讀取 style-decisions.json）",
    )
    parser.add_argument(
        "--symbol-glyph",
        dest="symbol_glyphs",
        action="append",
        default=None,
        help="視為裝飾性符號字型殘留（如 Wingdings 字元被輸出成原始控制字元）的字元，"
        "可重複指定（預設讀取 style-decisions.json）",
    )

    sort_group = parser.add_mutually_exclusive_group()
    sort_group.add_argument(
        "--pymupdf-sort",
        dest="pymupdf_sort_text",
        action="store_true",
        help="pymupdf 引擎依幾何位置排序文字（預設開啟，可用 style-decisions.json 覆蓋）",
    )
    sort_group.add_argument(
        "--no-pymupdf-sort",
        dest="pymupdf_sort_text",
        action="store_false",
        help="關閉 pymupdf 幾何排序，避免多欄或表單版面被交錯",
    )
    parser.set_defaults(pymupdf_sort_text=None)

    include_group = parser.add_mutually_exclusive_group()
    include_group.add_argument(
        "--include-images",
        dest="include_images",
        action="store_true",
        help="包含圖片提取與 manifest",
    )
    include_group.add_argument(
        "--no-include-images",
        dest="include_images",
        action="store_false",
        help="略過圖片提取",
    )
    parser.set_defaults(include_images=None)
    return parser.parse_args()


def prompt_include_images() -> bool:
    """互動詢問是否要提取圖片。非互動執行時預設為否。"""
    if not sys.stdin.isatty():
        return False

    while True:
        answer = input("是否要包含圖片提取與位置記錄？[y/N]: ").strip().lower()
        if answer in {"", "n", "no"}:
            return False
        if answer in {"y", "yes"}:
            return True
        print("請輸入 y 或 n。")


def detect_source_type(source_path: Path) -> str:
    """判斷來源格式，目前支援 PDF、EPUB、單張圖片與圖片資料夾。"""
    if source_path.is_dir():
        image_files = find_ocr_image_files(source_path)
        if image_files:
            return "image-dir"
        supported = ", ".join(sorted(IMAGE_SOURCE_SUFFIXES))
        raise SystemExit(
            "❌ 不支援的資料夾輸入：目前僅支援包含 OCR 圖片檔的資料夾"
            f"（可用副檔名：{supported}）"
        )

    source_type = SUPPORTED_FILE_SOURCE_TYPES.get(source_path.suffix.lower())
    if source_type is None:
        supported = ", ".join(sorted(SUPPORTED_FILE_SOURCE_TYPES))
        raise SystemExit(
            f"❌ 不支援的檔案格式：{source_path.suffix or '<none>'}（僅支援 {supported}）"
        )
    return source_type


def build_output_stem(source_path: Path, source_type: str | None = None) -> str:
    """根據來源建立輸出檔名前綴。"""
    resolved_source_type = source_type or detect_source_type(source_path)
    if resolved_source_type == "image-dir":
        return source_path.name
    return source_path.stem


def write_full_markdown(output_file: Path, page_texts: list[str], source_label: str) -> Path:
    """將逐頁文字合併成整本 Markdown。"""
    content = "\n\n".join(text.strip() for text in page_texts if text.strip()).strip()
    output_file.write_text(f"{content}\n" if content else "", encoding="utf-8")
    print(f"✓ 已提取（整本，{source_label}）: {output_file}")
    return output_file


def extract_with_markitdown(source_path: Path, output_dir: Path) -> Path | None:
    """使用 markitdown 提取整本來源內容。"""
    if MarkItDown is None:
        print("⚠️  markitdown 未安裝，跳過")
        return None

    md = MarkItDown()
    result = md.convert(str(source_path))

    output_file = output_dir / f"{source_path.stem}.md"
    output_file.write_text(result.text_content, encoding="utf-8")

    print(f"✓ 已提取: {output_file}")
    return output_file


def clean_watermarks(output_files: list[Path], watermarks: list[str]) -> None:
    """從輸出 Markdown 移除指定的浮水印字串。"""
    if not watermarks:
        return
    for output_file in output_files:
        if not output_file.exists():
            continue
        original = output_file.read_text(encoding="utf-8")
        cleaned = original
        for watermark in watermarks:
            cleaned = cleaned.replace(watermark, "")
        if cleaned != original:
            output_file.write_text(cleaned, encoding="utf-8")
            print(f"✓ 已清除浮水印: {output_file}")


def clean_opendataloader_temp_image_links(output_files: list[Path]) -> None:
    """移除 opendataloader 逐頁暫存圖片連結；圖片由 manifest 重新插入。"""
    pattern = re.compile(r"!\[[^\]]*\]\(page_\d+_images/[^)\s]+\)")
    for output_file in output_files:
        if not output_file.exists():
            continue
        original = output_file.read_text(encoding="utf-8")
        cleaned = pattern.sub("", original)
        if cleaned != original:
            output_file.write_text(cleaned, encoding="utf-8")
            print(f"✓ 已移除暫存圖片連結（由 manifest 重新插入）: {output_file}")


def clean_artifact_headings(output_files: list[Path]) -> None:
    """移除 opendataloader 產生的頁碼裝飾標題（純數字或空白標題）。"""
    for output_file in output_files:
        if not output_file.exists():
            continue
        original = output_file.read_text(encoding="utf-8")
        cleaned = strip_artifact_headings(original)
        if cleaned != original:
            output_file.write_text(cleaned, encoding="utf-8")
            print(f"✓ 已移除頁碼裝飾標題: {output_file}")


def clean_list_continuations(output_files: list[Path]) -> None:
    """合併 opendataloader 誤判為清單項目的段落斷行續句。"""
    for output_file in output_files:
        if not output_file.exists():
            continue
        original = output_file.read_text(encoding="utf-8")
        cleaned, count = merge_list_continuations(original)
        if count:
            output_file.write_text(cleaned, encoding="utf-8")
            print(f"✓ 已合併斷行續句清單項目（{count} 處）: {output_file}")


def clean_paragraph_continuations(output_files: list[Path]) -> None:
    """合併 opendataloader 誤判為兩個獨立段落的斷行續句；疑似案例僅回報，不自動合併。"""
    for output_file in output_files:
        if not output_file.exists():
            continue
        original = output_file.read_text(encoding="utf-8")
        cleaned, count, ambiguous = merge_paragraph_continuations(original)
        if count:
            output_file.write_text(cleaned, encoding="utf-8")
            print(f"✓ 已合併段落斷行續句（{count} 處）: {output_file}")
        if ambiguous:
            lines_str = "、".join(str(line) for line in ambiguous)
            print(f"⚠️  疑似段落斷行續句但未自動合併，需人工確認（第 {lines_str} 行）: {output_file}")


def clean_symbol_glyphs(output_files: list[Path], glyphs: list[str]) -> None:
    """將裝飾性符號字型殘留字元（如 Wingdings 字元被輸出成原始控制字元）轉換為
    結構化 Markdown（清單項目或小節標題）；`glyphs` 為空時略過。"""
    if not glyphs:
        return
    for output_file in output_files:
        if not output_file.exists():
            continue
        original = output_file.read_text(encoding="utf-8")
        cleaned, counts = clean_symbol_glyph_ornaments(original, glyphs)
        if cleaned != original:
            output_file.write_text(cleaned, encoding="utf-8")
            print(
                f"✓ 已轉換裝飾符號殘留字元（清單項目 "
                f"{counts['list_items_from_split'] + counts['list_items_from_singleton']}、"
                f"標題 {counts['titles']}）: {output_file}"
            )
        if counts["ambiguous"]:
            lines_str = "、".join(str(line) for line in counts["ambiguous"])
            print(f"⚠️  疑似段落斷行續句但未自動合併，需人工確認（第 {lines_str} 行）: {output_file}")


def load_style_decisions(project_root: Path) -> dict:
    """讀取 style-decisions.json。"""
    path = project_root / "style-decisions.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"⚠️  style-decisions.json 解析失敗，忽略文件抽取設定：{exc}")
        return {}


def load_document_extraction_settings(project_root: Path, pdf_stem: str) -> dict[str, object]:
    """讀取全域與每文件抽取設定。"""
    style_decisions = load_style_decisions(project_root)
    document_format = style_decisions.get("document_format", {})
    if not isinstance(document_format, dict):
        return {}

    settings: dict[str, object] = {}
    for key, normalizer in DOCUMENT_FORMAT_FIELDS:
        normalized = normalizer(document_format.get(key))
        if normalized is not None:
            settings[key] = normalized

    documents = document_format.get("documents", {})
    if isinstance(documents, dict):
        doc_settings = documents.get(pdf_stem, {})
        if isinstance(doc_settings, dict):
            for key, normalizer in DOCUMENT_FORMAT_FIELDS:
                normalized = normalizer(doc_settings.get(key))
                if normalized is not None:
                    settings[key] = normalized

    return settings


def resolve_page_text_strategy(
    pdf_path: Path,
    project_root: Path,
    requested_engine: str,
    requested_layout: str,
    requested_pymupdf_sort_text: bool | None = None,
    requested_watermarks: list[str] | None = None,
    requested_symbol_glyphs: list[str] | None = None,
) -> dict[str, object]:
    """綜合 CLI、style-decisions 與自動偵測，決定分頁提取策略。"""
    source_type = detect_source_type(pdf_path)
    settings = load_document_extraction_settings(project_root, pdf_path.stem)

    pymupdf_sort_text = requested_pymupdf_sort_text
    pymupdf_sort_text_source = "cli" if pymupdf_sort_text is not None else None
    if pymupdf_sort_text is None:
        style_sort = settings.get("pymupdf_sort_text")
        if isinstance(style_sort, bool):
            pymupdf_sort_text = style_sort
            pymupdf_sort_text_source = "style-decisions"
    if pymupdf_sort_text is None:
        pymupdf_sort_text = True
        pymupdf_sort_text_source = "default"

    watermarks = requested_watermarks
    watermarks_source = "cli" if watermarks is not None else None
    if watermarks is None:
        style_watermarks = settings.get("watermarks")
        if isinstance(style_watermarks, list):
            watermarks = style_watermarks
            watermarks_source = "style-decisions"
    if watermarks is None:
        watermarks = []
        watermarks_source = "default"

    symbol_glyphs = requested_symbol_glyphs
    symbol_glyphs_source = "cli" if symbol_glyphs is not None else None
    if symbol_glyphs is None:
        style_symbol_glyphs = settings.get("symbol_glyphs")
        if isinstance(style_symbol_glyphs, list):
            symbol_glyphs = style_symbol_glyphs
            symbol_glyphs_source = "style-decisions"
    if symbol_glyphs is None:
        symbol_glyphs = []
        symbol_glyphs_source = "default"

    if source_type in {"image", "image-dir"}:
        return {
            "page_text_engine": "ocr",
            "page_text_engine_source": "image-source",
            "layout_profile": "single-column",
            "layout_profile_source": "image-source",
            "pymupdf_sort_text": pymupdf_sort_text,
            "pymupdf_sort_text_source": pymupdf_sort_text_source,
            "watermarks": watermarks,
            "watermarks_source": watermarks_source,
            "symbol_glyphs": symbol_glyphs,
            "symbol_glyphs_source": symbol_glyphs_source,
            "document_settings": {},
            "detection": None,
            "quality_probe": None,
            "source_type": source_type,
        }
    if source_type == "epub":
        return {
            "page_text_engine": "markitdown",
            "page_text_engine_source": "epub-default",
            "layout_profile": "single-column",
            "layout_profile_source": "epub-default",
            "pymupdf_sort_text": pymupdf_sort_text,
            "pymupdf_sort_text_source": pymupdf_sort_text_source,
            "watermarks": watermarks,
            "watermarks_source": watermarks_source,
            "symbol_glyphs": symbol_glyphs,
            "symbol_glyphs_source": symbol_glyphs_source,
            "document_settings": {},
            "detection": None,
            "quality_probe": None,
            "source_type": source_type,
        }

    page_text_engine = normalize_page_text_engine(requested_engine) or "auto"
    layout_profile = normalize_layout_profile(requested_layout) or "auto"
    engine_source = "cli" if page_text_engine != "auto" else None
    layout_source = "cli" if layout_profile != "auto" else None

    if page_text_engine == "auto":
        style_engine = settings.get("page_text_engine")
        if style_engine and style_engine != "auto":
            page_text_engine = style_engine
            engine_source = "style-decisions"

    if layout_profile == "auto":
        style_layout = settings.get("layout_profile")
        if style_layout and style_layout != "auto":
            layout_profile = style_layout
            layout_source = "style-decisions"

    # opendataloader 優先：auto 模式下若可用則直接使用
    if page_text_engine == "auto" and is_opendataloader_available():
        page_text_engine = "opendataloader"
        engine_source = "auto-opendataloader"
        print("ℹ️  偵測到 opendataloader-pdf + Java 11+，優先使用 opendataloader 引擎")

    # 明確指定 opendataloader 但不可用時報錯
    if page_text_engine == "opendataloader" and not is_opendataloader_available():
        availability = check_opendataloader_availability()
        reason = availability.get("reason", "未知原因")
        raise SystemExit(f"❌ 無法使用 opendataloader 引擎：{reason}")

    detection: dict[str, object] | None = None
    quality_probe: dict[str, object] | None = None
    if layout_profile == "auto":
        detection = detect_layout_profile(pdf_path)
        layout_profile = str(detection.get("layout_profile", "single-column"))
        layout_source = str(detection.get("source", "auto-detect"))

    if (
        page_text_engine == "auto"
        and layout_profile == "single-column"
        and MarkItDown is not None
    ):
        quality_probe = probe_pymupdf_text_quality(pdf_path)
        if quality_probe.get("prefer_markitdown"):
            page_text_engine = "markitdown"
            engine_source = str(quality_probe.get("source", "quality-probe"))

    if page_text_engine == "auto":
        # opendataloader 不可用時的降級路徑
        if not is_opendataloader_available():
            availability = check_opendataloader_availability()
            reason = availability.get("reason", "未知原因")
            print(f"ℹ️  opendataloader 不可用（{reason}），使用傳統引擎")
        page_text_engine = "markitdown" if layout_profile == "double-column" else "pymupdf"
        engine_source = "layout-profile"

    if page_text_engine == "markitdown" and MarkItDown is None:
        print("⚠️  需要 markitdown 才能使用雙欄保守路徑，已回退到 pymupdf")
        page_text_engine = "pymupdf"
        engine_source = "fallback"

    return {
        "page_text_engine": page_text_engine,
        "page_text_engine_source": engine_source or "default",
        "layout_profile": layout_profile,
        "layout_profile_source": layout_source or "default",
        "pymupdf_sort_text": pymupdf_sort_text,
        "pymupdf_sort_text_source": pymupdf_sort_text_source,
        "watermarks": watermarks,
        "watermarks_source": watermarks_source,
        "symbol_glyphs": symbol_glyphs,
        "symbol_glyphs_source": symbol_glyphs_source,
        "document_settings": settings,
        "detection": detection,
        "quality_probe": quality_probe,
        "source_type": source_type,
    }


def extract_with_pages(
    pdf_path: Path,
    output_dir: Path,
    page_text_engine: str = "pymupdf",
    progress_every: int = 25,
    pymupdf_sort_text: bool = True,
) -> Path | None:
    """提取含頁碼標記的內容，用於章節拆分。"""
    source_type = detect_source_type(pdf_path)
    if source_type == "epub":
        return extract_epub_with_pages(pdf_path, output_dir, progress_every=max(1, progress_every // 5))

    if page_text_engine == "opendataloader":
        output_file = output_dir / f"{pdf_path.stem}_pages.md"
        pages = opendataloader_convert_pages(pdf_path)
        if not pages:
            print("⚠️  opendataloader 提取失敗，跳過")
            return None
        opendataloader_write_pages(pages, output_file)
        print(f"✓ 已提取（含頁碼，opendataloader）: {output_file}")
        return output_file

    if pymupdf is None:
        print("⚠️  pymupdf 未安裝（需要用於分頁），跳過")
        return None
    if page_text_engine == "markitdown" and MarkItDown is None:
        print("⚠️  markitdown 未安裝，無法使用 markitdown 分頁模式")
        return None

    doc = pymupdf.open(str(pdf_path))
    total_pages = len(doc)
    progress_every = max(1, progress_every)
    output_file = output_dir / f"{pdf_path.stem}_pages.md"
    try:
        with output_file.open("w", encoding="utf-8") as handle:
            if page_text_engine == "pymupdf":
                for page_num, page in enumerate(doc, 1):
                    page_text = extract_page_text_pymupdf(page, sort=pymupdf_sort_text)
                    handle.write(f"\n\n<!-- PAGE {page_num} -->\n\n{page_text}")
                    if should_print_progress(page_num, total_pages, progress_every):
                        print(f"↻ 分頁提取進度（pymupdf）: {page_num}/{total_pages}")
            else:
                md = MarkItDown()
                with tempfile.TemporaryDirectory() as tmp_dir:
                    for page_num in range(total_pages):
                        single = pymupdf.open()
                        single.insert_pdf(doc, from_page=page_num, to_page=page_num)
                        tmp_pdf = Path(tmp_dir) / f"page_{page_num + 1}.pdf"
                        single.save(str(tmp_pdf))
                        single.close()

                        result = md.convert(str(tmp_pdf))
                        handle.write(
                            f"\n\n<!-- PAGE {page_num + 1} -->\n\n{result.text_content.strip()}"
                        )
                        if should_print_progress(page_num + 1, total_pages, progress_every):
                            print(f"↻ 分頁提取進度（markitdown）: {page_num + 1}/{total_pages}")
    finally:
        doc.close()

    print(f"✓ 已提取（含頁碼，{page_text_engine}）: {output_file}")
    return output_file


def extract_with_ocr_pages(
    source_path: Path,
    output_dir: Path,
    ocr_lang: str,
    ocr_psm: int,
    ocr_dpi: int,
    progress_every: int = 25,
) -> tuple[Path | None, list[str]]:
    """使用 OCR 逐頁提取來源內容。"""
    source_type = detect_source_type(source_path)
    ensure_tesseract_ready(ocr_lang)
    output_file = output_dir / f"{build_output_stem(source_path, source_type)}_pages.md"
    page_texts: list[str] = []
    progress_every = max(1, progress_every)

    if source_type in {"image", "image-dir"}:
        image_files = [source_path] if source_type == "image" else find_ocr_image_files(source_path)
        total_pages = len(image_files)
        with output_file.open("w", encoding="utf-8") as handle:
            for page_num, image_path in enumerate(image_files, 1):
                page_text = run_tesseract_ocr(image_path, ocr_lang=ocr_lang, ocr_psm=ocr_psm)
                page_texts.append(page_text)
                handle.write(f"\n\n<!-- PAGE {page_num} -->\n\n{page_text}")
                if should_print_progress(page_num, total_pages, progress_every):
                    print(f"↻ 分頁提取進度（ocr / image）: {page_num}/{total_pages}")

        print(f"✓ 已提取（含頁碼，ocr）: {output_file}")
        return output_file, page_texts

    if source_type != "pdf":
        raise RuntimeError(f"不支援的 OCR 來源型別：{source_type}")
    if pymupdf is None:
        print("⚠️  pymupdf 未安裝（需要用於 PDF OCR 分頁），跳過")
        return None, []

    doc = pymupdf.open(str(source_path))
    total_pages = len(doc)
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with output_file.open("w", encoding="utf-8") as handle:
                for page_num, page in enumerate(doc, 1):
                    page_image_path = Path(tmp_dir) / f"page_{page_num:04d}.png"
                    render_pdf_page_for_ocr(page, page_image_path, dpi=ocr_dpi)
                    page_text = run_tesseract_ocr(
                        page_image_path,
                        ocr_lang=ocr_lang,
                        ocr_psm=ocr_psm,
                    )
                    page_texts.append(page_text)
                    handle.write(f"\n\n<!-- PAGE {page_num} -->\n\n{page_text}")
                    if should_print_progress(page_num, total_pages, progress_every):
                        print(f"↻ 分頁提取進度（ocr / pdf）: {page_num}/{total_pages}")
    finally:
        doc.close()

    print(f"✓ 已提取（含頁碼，ocr）: {output_file}")
    return output_file, page_texts


def build_image_filename(page_num: int, image_index: int, placement_index: int, rect, ext: str) -> str:
    """建立包含位置與尺寸資訊的圖片檔名。"""
    if rect is None:
        return f"page{page_num:03d}_img{image_index:02d}_occ{placement_index:02d}.{ext}"

    x = round(rect.x0)
    y = round(rect.y0)
    width = round(rect.width)
    height = round(rect.height)
    return (
        f"page{page_num:03d}_img{image_index:02d}_occ{placement_index:02d}"
        f"_x{x}_y{y}_w{width}_h{height}.{ext}"
    )


def extract_images(pdf_path: Path, output_dir: Path) -> list[dict]:
    """提取 PDF 中的圖片，並記錄位置與尺寸資訊。"""
    source_type = detect_source_type(pdf_path)
    if source_type == "epub":
        return extract_epub_images(pdf_path, output_dir)

    if pymupdf is None:
        print("⚠️  pymupdf 未安裝，無法提取圖片")
        return []

    doc = pymupdf.open(str(pdf_path))
    images_dir = output_dir / "images" / pdf_path.stem
    images_dir.mkdir(parents=True, exist_ok=True)

    saved_images: list[dict] = []
    for page_num, page in enumerate(doc, 1):
        page_rect = getattr(page, "rect", None)
        page_width = round(float(page_rect.width), 2) if page_rect is not None else None
        page_height = round(float(page_rect.height), 2) if page_rect is not None else None

        try:
            page_images = page.get_images(full=True)
        except TypeError:
            page_images = page.get_images()

        # get_images() may list one XObject once for every use. get_image_rects()
        # already returns every placement, so visiting the XObject again multiplies
        # the output (a 36-die table became 216 files in Kedamono Opera).
        seen_xrefs: set[int] = set()
        for img_index, img in enumerate(page_images):
            xref = img[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            if image_ext not in WEB_IMAGE_EXTENSIONS:
                image_bytes = pixmap_to_png(pymupdf.Pixmap(doc, xref))
                image_ext = "png"
            analysis = analyze_image_bytes(image_bytes)
            try:
                rects = page.get_image_rects(xref, transform=False)
            except TypeError:
                rects = page.get_image_rects(xref)
            except AttributeError:
                rects = []

            if not rects:
                rects = [None]

            for placement_index, rect in enumerate(rects):
                image_name = build_image_filename(
                    page_num,
                    img_index,
                    placement_index,
                    rect,
                    image_ext,
                )
                image_path = images_dir / image_name
                image_path.write_bytes(image_bytes)

                if rect is None:
                    x = None
                    y = None
                    width = base_image.get("width")
                    height = base_image.get("height")
                else:
                    x = round(rect.x0, 2)
                    y = round(rect.y0, 2)
                    width = round(rect.width, 2)
                    height = round(rect.height, 2)

                coverage_ratio = None
                if (
                    width
                    and height
                    and page_width
                    and page_height
                    and page_width > 0
                    and page_height > 0
                ):
                    coverage_ratio = round((width * height) / (page_width * page_height), 4)

                saved_images.append(
                    {
                        "page": page_num,
                        "image_index": img_index,
                        "placement_index": placement_index,
                        "xref": xref,
                        "filename": image_name,
                        "path": str(image_path.relative_to(output_dir).as_posix()),
                        "x": x,
                        "y": y,
                        "width": width,
                        "height": height,
                        "page_width": page_width,
                        "page_height": page_height,
                        "coverage_ratio": coverage_ratio,
                        "file_size": len(image_bytes),
                        "visual_hash": analysis.get("visual_hash"),
                        "dominant_color_ratio": analysis.get("dominant_color_ratio"),
                        "sampled_pixel_count": analysis.get("sampled_pixel_count"),
                    }
                )

    doc.close()

    manifest_path = images_dir / "manifest.json"
    manifest = {
        "pdf": pdf_path.name,
        "images_dir": str(images_dir.relative_to(output_dir).as_posix()),
        "images": saved_images,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"✓ 已提取 {len(saved_images)} 張圖片到 {images_dir}")
    print(f"✓ 已建立圖片 manifest: {manifest_path}")
    return saved_images


def main():
    args = parse_args()
    source_path = Path(args.source_file)

    if not source_path.exists():
        print(f"❌ 找不到檔案: {source_path}")
        sys.exit(1)
    if args.ocr_psm <= 0:
        print("❌ `--ocr-psm` 必須大於 0")
        sys.exit(1)
    if args.ocr_dpi <= 0:
        print("❌ `--ocr-dpi` 必須大於 0")
        sys.exit(1)

    source_type = detect_source_type(source_path)

    # 設定輸出目錄
    project_root = Path(__file__).resolve().parents[1]
    output_dir = project_root / "data" / "markdown"
    output_dir.mkdir(parents=True, exist_ok=True)
    strategy = resolve_page_text_strategy(
        source_path,
        project_root,
        requested_engine=args.page_text_engine,
        requested_layout=args.layout_profile,
        requested_pymupdf_sort_text=args.pymupdf_sort_text,
        requested_watermarks=args.watermarks,
        requested_symbol_glyphs=args.symbol_glyphs,
    )

    print(f"\n📄 處理: {source_path.name} ({source_type.upper()})")
    print(
        f"🧭 分頁引擎: {strategy['page_text_engine']} "
        f"（來源: {strategy['page_text_engine_source']}）"
    )
    print(
        f"🧭 版面設定: {strategy['layout_profile']} "
        f"（來源: {strategy['layout_profile_source']}）"
    )
    if not strategy["pymupdf_sort_text"]:
        print(f"🧭 pymupdf 排序: 關閉（來源: {strategy['pymupdf_sort_text_source']}）")
    if strategy["watermarks"]:
        print(f"🧭 浮水印清除: {', '.join(strategy['watermarks'])}（來源: {strategy['watermarks_source']}）")
    if strategy["symbol_glyphs"]:
        print(
            f"🧭 裝飾符號殘留字元: {', '.join(repr(g) for g in strategy['symbol_glyphs'])}"
            f"（來源: {strategy['symbol_glyphs_source']}）"
        )
    if strategy["detection"] is not None:
        sampled_pages = [
            f"p.{result['page']}={result['layout_profile']}"
            for result in strategy["detection"].get("sampled_pages", [])
            if result.get("layout_profile") != "unknown"
        ]
        if sampled_pages:
            print(f"   自動偵測抽樣: {', '.join(sampled_pages[:8])}")
    quality_probe = strategy.get("quality_probe")
    if quality_probe and quality_probe.get("prefer_markitdown"):
        noisy_pages = [
            f"p.{result['page']}={result['whitespace_ratio']}"
            for result in quality_probe.get("sampled_pages", [])
            if result.get("is_noisy")
        ]
        if noisy_pages:
            print(f"   文字品質探測：PyMuPDF 版面噪訊偏高，改用 markitdown（{', '.join(noisy_pages[:8])}）")
    print("-" * 50)

    source_label = str(strategy["page_text_engine"])
    page_texts: list[str] = []
    if source_type in {"image", "image-dir"} or strategy["page_text_engine"] == "ocr":
        pages_output, page_texts = extract_with_ocr_pages(
            source_path,
            output_dir,
            ocr_lang=args.ocr_lang,
            ocr_psm=args.ocr_psm,
            ocr_dpi=args.ocr_dpi,
        )
        if pages_output is None:
            sys.exit(1)
        if args.skip_full_markitdown:
            print("↷ 已略過整本 Markdown 輸出")
        else:
            write_full_markdown(
                output_dir / f"{build_output_stem(source_path, source_type)}.md",
                page_texts,
                source_label=source_label,
            )
    elif strategy["page_text_engine"] == "opendataloader":
        if args.skip_full_markitdown:
            print("↷ 已略過整本 Markdown 輸出")
        else:
            full_md = opendataloader_convert_markdown(source_path, output_dir)
            if full_md is not None:
                full_output = output_dir / f"{build_output_stem(source_path, source_type)}.md"
                full_output.write_text(full_md, encoding="utf-8")
                print(f"✓ 已提取（整本，opendataloader）: {full_output}")

        extract_with_pages(
            source_path,
            output_dir,
            page_text_engine="opendataloader",
        )
    else:
        if args.skip_full_markitdown:
            print("↷ 已略過整本 markitdown 提取")
        else:
            extract_with_markitdown(source_path, output_dir)

        extract_with_pages(
            source_path,
            output_dir,
            page_text_engine=strategy["page_text_engine"],
            pymupdf_sort_text=strategy["pymupdf_sort_text"],
        )

    output_stem = build_output_stem(source_path, source_type)
    generated_markdown = [
        output_dir / f"{output_stem}.md",
        output_dir / f"{output_stem}_pages.md",
    ]
    clean_watermarks(generated_markdown, strategy["watermarks"])
    if strategy["page_text_engine"] == "opendataloader":
        clean_opendataloader_temp_image_links(generated_markdown)
        clean_artifact_headings(generated_markdown)
        clean_list_continuations(generated_markdown)
        clean_paragraph_continuations(generated_markdown)
        clean_symbol_glyphs(generated_markdown, strategy["symbol_glyphs"])

    include_images = args.include_images
    if include_images is None:
        include_images = prompt_include_images()

    if include_images and source_type in {"image", "image-dir"}:
        print("↷ 圖片來源本身不做額外圖片提取")
    elif include_images:
        extract_images(source_path, output_dir)
    else:
        print("↷ 已略過圖片提取")

    print("-" * 50)
    print("✅ 完成！")
    print(f"\n下一步：使用 split_chapters.py 拆分章節")


if __name__ == "__main__":
    main()
