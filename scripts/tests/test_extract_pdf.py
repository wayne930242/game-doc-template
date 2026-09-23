"""Tests for functions remaining in extract_pdf.py."""

from pathlib import Path
from types import SimpleNamespace

import pytest

import json

from extract_pdf import (
    build_image_filename,
    build_output_stem,
    clean_artifact_headings,
    clean_list_continuations,
    clean_opendataloader_temp_image_links,
    clean_paragraph_continuations,
    clean_watermarks,
    detect_source_type,
    load_document_extraction_settings,
    normalize_layout_profile,
    normalize_page_text_engine,
    normalize_pymupdf_sort_text,
    normalize_watermarks,
    resolve_page_text_strategy,
    write_full_markdown,
)
from _epub_lib import should_print_progress


# ---------------------------------------------------------------------------
# normalize_page_text_engine
# ---------------------------------------------------------------------------


class TestNormalizePageTextEngine:
    def test_valid_values(self):
        assert normalize_page_text_engine("auto") == "auto"
        assert normalize_page_text_engine("ocr") == "ocr"
        assert normalize_page_text_engine("pymupdf") == "pymupdf"
        assert normalize_page_text_engine("markitdown") == "markitdown"

    def test_alias_fitz(self):
        assert normalize_page_text_engine("fitz") == "pymupdf"

    def test_alias_markdown(self):
        assert normalize_page_text_engine("markdown") == "markitdown"

    def test_case_insensitive(self):
        assert normalize_page_text_engine("PyMuPDF") == "pymupdf"
        assert normalize_page_text_engine("AUTO") == "auto"
        assert normalize_page_text_engine("FITZ") == "pymupdf"

    def test_strips_whitespace(self):
        assert normalize_page_text_engine("  pymupdf  ") == "pymupdf"

    def test_none_returns_none(self):
        assert normalize_page_text_engine(None) is None

    def test_invalid_returns_none(self):
        assert normalize_page_text_engine("invalid") is None
        assert normalize_page_text_engine("") is None
        assert normalize_page_text_engine(123) is None


# ---------------------------------------------------------------------------
# normalize_layout_profile
# ---------------------------------------------------------------------------


class TestNormalizeLayoutProfile:
    def test_valid_values(self):
        assert normalize_layout_profile("auto") == "auto"
        assert normalize_layout_profile("single-column") == "single-column"
        assert normalize_layout_profile("double-column") == "double-column"

    def test_aliases(self):
        assert normalize_layout_profile("single") == "single-column"
        assert normalize_layout_profile("single_column") == "single-column"
        assert normalize_layout_profile("double") == "double-column"
        assert normalize_layout_profile("double_column") == "double-column"
        assert normalize_layout_profile("two-column") == "double-column"
        assert normalize_layout_profile("two_column") == "double-column"

    def test_case_insensitive(self):
        assert normalize_layout_profile("Double-Column") == "double-column"
        assert normalize_layout_profile("SINGLE") == "single-column"

    def test_strips_whitespace(self):
        assert normalize_layout_profile("  auto  ") == "auto"

    def test_none_returns_none(self):
        assert normalize_layout_profile(None) is None

    def test_invalid_returns_none(self):
        assert normalize_layout_profile("triple-column") is None
        assert normalize_layout_profile("") is None


# ---------------------------------------------------------------------------
# detect_source_type
# ---------------------------------------------------------------------------


class TestDetectSourceType:
    def test_pdf(self):
        assert detect_source_type(Path("book.pdf")) == "pdf"

    def test_pdf_uppercase(self):
        assert detect_source_type(Path("BOOK.PDF")) == "pdf"

    def test_epub(self):
        assert detect_source_type(Path("book.epub")) == "epub"

    def test_epub_uppercase(self):
        assert detect_source_type(Path("BOOK.EPUB")) == "epub"

    def test_image_file(self):
        assert detect_source_type(Path("page.JPG")) == "image"

    def test_image_directory(self, tmp_path):
        (tmp_path / "page2.jpg").write_text("x", encoding="utf-8")
        (tmp_path / "page10.jpg").write_text("x", encoding="utf-8")
        assert detect_source_type(tmp_path) == "image-dir"

    def test_unsupported_extension(self):
        with pytest.raises(SystemExit):
            detect_source_type(Path("book.docx"))

    def test_no_extension(self):
        with pytest.raises(SystemExit):
            detect_source_type(Path("book"))


# ---------------------------------------------------------------------------
# should_print_progress
# ---------------------------------------------------------------------------


class TestShouldPrintProgress:
    def test_first_page_always(self):
        assert should_print_progress(1, 100, 25) is True

    def test_last_page_always(self):
        assert should_print_progress(100, 100, 25) is True

    def test_interval_match(self):
        assert should_print_progress(25, 100, 25) is True
        assert should_print_progress(50, 100, 25) is True
        assert should_print_progress(75, 100, 25) is True

    def test_non_interval(self):
        assert should_print_progress(2, 100, 25) is False
        assert should_print_progress(13, 100, 25) is False
        assert should_print_progress(99, 100, 25) is False


# ---------------------------------------------------------------------------
# build_image_filename
# ---------------------------------------------------------------------------


class TestBuildImageFilename:
    def test_with_rect(self):
        rect = SimpleNamespace(x0=10.4, y0=20.6, width=100.3, height=200.7)
        result = build_image_filename(1, 0, 0, rect, "png")
        assert result == "page001_img00_occ00_x10_y21_w100_h201.png"

    def test_without_rect(self):
        result = build_image_filename(1, 0, 0, None, "png")
        assert result == "page001_img00_occ00.png"

    def test_multi_digit_indices(self):
        result = build_image_filename(12, 3, 1, None, "jpg")
        assert result == "page012_img03_occ01.jpg"

    def test_with_rect_zero_coords(self):
        rect = SimpleNamespace(x0=0.0, y0=0.0, width=50.0, height=50.0)
        result = build_image_filename(1, 0, 0, rect, "png")
        assert result == "page001_img00_occ00_x0_y0_w50_h50.png"


class TestBuildOutputStem:
    def test_file_uses_stem(self):
        assert build_output_stem(Path("book.pdf"), "pdf") == "book"

    def test_directory_uses_name(self, tmp_path):
        scan_dir = tmp_path / "scan-pages"
        scan_dir.mkdir()
        assert build_output_stem(scan_dir, "image-dir") == "scan-pages"


class TestWriteFullMarkdown:
    def test_skips_empty_pages_and_joins_sections(self, tmp_path):
        output = tmp_path / "book.md"
        result = write_full_markdown(output, ["First page", "", "Second page"], "ocr")
        assert result == output
        assert output.read_text(encoding="utf-8") == "First page\n\nSecond page\n"


# ---------------------------------------------------------------------------
# load_document_extraction_settings
# ---------------------------------------------------------------------------

def _write_style_decisions(root: Path, document_format: dict) -> None:
    (root / "style-decisions.json").write_text(
        json.dumps({"_meta": {"description": "x", "updated": ""}, "document_format": document_format}),
        encoding="utf-8",
    )


class TestLoadDocumentExtractionSettings:
    def test_per_document_overrides_global(self, tmp_path):
        _write_style_decisions(
            tmp_path,
            {
                "page_text_engine": "pymupdf",
                "layout_profile": "single-column",
                "documents": {
                    "Household_1.2": {
                        "page_text_engine": "markitdown",
                        "layout_profile": "double-column",
                    }
                },
            },
        )

        settings = load_document_extraction_settings(tmp_path, "Household_1.2")

        assert settings == {"page_text_engine": "markitdown", "layout_profile": "double-column"}

    def test_falls_back_to_global_for_other_documents(self, tmp_path):
        _write_style_decisions(
            tmp_path,
            {
                "page_text_engine": "pymupdf",
                "documents": {"Household_1.2": {"page_text_engine": "markitdown"}},
            },
        )

        settings = load_document_extraction_settings(tmp_path, "Other_Book")

        assert settings == {"page_text_engine": "pymupdf"}

    def test_missing_style_decisions_returns_empty(self, tmp_path):
        assert load_document_extraction_settings(tmp_path, "Anything") == {}


# ---------------------------------------------------------------------------
# resolve_page_text_strategy
# ---------------------------------------------------------------------------

class TestResolvePageTextStrategy:
    def test_epub_uses_markitdown_single_column(self, tmp_path):
        strategy = resolve_page_text_strategy(
            tmp_path / "book.epub", tmp_path, requested_engine="auto", requested_layout="auto"
        )
        assert strategy["page_text_engine"] == "markitdown"
        assert strategy["page_text_engine_source"] == "epub-default"
        assert strategy["layout_profile"] == "single-column"
        assert strategy["source_type"] == "epub"

    def test_document_settings_override_auto(self, tmp_path):
        _write_style_decisions(
            tmp_path,
            {
                "documents": {
                    "book": {"page_text_engine": "markitdown", "layout_profile": "double-column"}
                }
            },
        )

        strategy = resolve_page_text_strategy(
            tmp_path / "book.pdf", tmp_path, requested_engine="auto", requested_layout="auto"
        )

        assert strategy["page_text_engine"] == "markitdown"
        assert strategy["page_text_engine_source"] == "style-decisions"
        assert strategy["layout_profile"] == "double-column"
        assert strategy["layout_profile_source"] == "style-decisions"
        # Explicit settings short-circuit layout detection and the quality probe.
        assert strategy["detection"] is None
        assert strategy["quality_probe"] is None

    def test_cli_request_beats_style_decisions(self, tmp_path):
        _write_style_decisions(
            tmp_path,
            {"documents": {"book": {"page_text_engine": "markitdown", "layout_profile": "double-column"}}},
        )

        strategy = resolve_page_text_strategy(
            tmp_path / "book.pdf",
            tmp_path,
            requested_engine="pymupdf",
            requested_layout="single-column",
        )

        assert strategy["page_text_engine"] == "pymupdf"
        assert strategy["page_text_engine_source"] == "cli"
        assert strategy["layout_profile"] == "single-column"
        assert strategy["layout_profile_source"] == "cli"

    def test_pymupdf_sort_text_and_watermarks_default(self, tmp_path):
        strategy = resolve_page_text_strategy(
            tmp_path / "book.pdf", tmp_path, requested_engine="pymupdf", requested_layout="single-column"
        )
        assert strategy["pymupdf_sort_text"] is True
        assert strategy["pymupdf_sort_text_source"] == "default"
        assert strategy["watermarks"] == []
        assert strategy["watermarks_source"] == "default"

    def test_pymupdf_sort_text_from_style_decisions(self, tmp_path):
        _write_style_decisions(tmp_path, {"pymupdf_sort_text": False, "watermarks": ["Order #123"]})

        strategy = resolve_page_text_strategy(
            tmp_path / "book.pdf", tmp_path, requested_engine="pymupdf", requested_layout="single-column"
        )

        assert strategy["pymupdf_sort_text"] is False
        assert strategy["pymupdf_sort_text_source"] == "style-decisions"
        assert strategy["watermarks"] == ["Order #123"]
        assert strategy["watermarks_source"] == "style-decisions"

    def test_cli_pymupdf_sort_text_and_watermarks_beat_style_decisions(self, tmp_path):
        _write_style_decisions(tmp_path, {"pymupdf_sort_text": False, "watermarks": ["Order #123"]})

        strategy = resolve_page_text_strategy(
            tmp_path / "book.pdf",
            tmp_path,
            requested_engine="pymupdf",
            requested_layout="single-column",
            requested_pymupdf_sort_text=True,
            requested_watermarks=["Custom Watermark"],
        )

        assert strategy["pymupdf_sort_text"] is True
        assert strategy["pymupdf_sort_text_source"] == "cli"
        assert strategy["watermarks"] == ["Custom Watermark"]
        assert strategy["watermarks_source"] == "cli"

    def test_document_level_watermarks_override_global(self, tmp_path):
        _write_style_decisions(
            tmp_path,
            {
                "watermarks": ["Global Mark"],
                "documents": {"book": {"watermarks": ["Doc Mark"]}},
            },
        )

        strategy = resolve_page_text_strategy(
            tmp_path / "book.pdf", tmp_path, requested_engine="pymupdf", requested_layout="single-column"
        )

        assert strategy["watermarks"] == ["Doc Mark"]

    def test_image_source_still_resolves_watermarks(self, tmp_path):
        _write_style_decisions(tmp_path, {"watermarks": ["Mark"]})

        strategy = resolve_page_text_strategy(
            tmp_path / "scan.jpg", tmp_path, requested_engine="auto", requested_layout="auto"
        )

        assert strategy["source_type"] == "image"
        assert strategy["watermarks"] == ["Mark"]


# ---------------------------------------------------------------------------
# normalize_pymupdf_sort_text / normalize_watermarks
# ---------------------------------------------------------------------------


class TestNormalizePymupdfSortText:
    def test_true(self):
        assert normalize_pymupdf_sort_text(True) is True

    def test_false(self):
        assert normalize_pymupdf_sort_text(False) is False

    def test_none_returns_none(self):
        assert normalize_pymupdf_sort_text(None) is None

    def test_non_bool_returns_none(self):
        assert normalize_pymupdf_sort_text("true") is None
        assert normalize_pymupdf_sort_text(1) is None


class TestNormalizeWatermarks:
    def test_list_of_strings(self):
        assert normalize_watermarks(["a", "b"]) == ["a", "b"]

    def test_empty_list_is_valid(self):
        assert normalize_watermarks([]) == []

    def test_none_returns_none(self):
        assert normalize_watermarks(None) is None

    def test_non_list_returns_none(self):
        assert normalize_watermarks("watermark") is None

    def test_list_with_non_string_returns_none(self):
        assert normalize_watermarks(["a", 1]) is None


# ---------------------------------------------------------------------------
# clean_watermarks
# ---------------------------------------------------------------------------


class TestCleanWatermarks:
    def test_removes_watermark_from_file(self, tmp_path):
        target = tmp_path / "book.md"
        target.write_text("intro Wei Hung (Order #53155335) body", encoding="utf-8")

        clean_watermarks([target], ["Wei Hung (Order #53155335)"])

        assert "Wei Hung" not in target.read_text(encoding="utf-8")

    def test_multiple_watermarks(self, tmp_path):
        target = tmp_path / "book.md"
        target.write_text("a MARK1 b MARK2 c", encoding="utf-8")

        clean_watermarks([target], ["MARK1", "MARK2"])

        content = target.read_text(encoding="utf-8")
        assert "MARK1" not in content
        assert "MARK2" not in content

    def test_no_watermarks_leaves_file_untouched(self, tmp_path):
        target = tmp_path / "book.md"
        target.write_text("unchanged content", encoding="utf-8")

        clean_watermarks([target], [])

        assert target.read_text(encoding="utf-8") == "unchanged content"

    def test_missing_file_is_skipped(self, tmp_path):
        missing = tmp_path / "missing.md"
        clean_watermarks([missing], ["anything"])  # should not raise

    def test_no_match_does_not_rewrite_file(self, tmp_path):
        target = tmp_path / "book.md"
        target.write_text("clean content", encoding="utf-8")
        original_mtime = target.stat().st_mtime_ns

        clean_watermarks([target], ["not present"])

        assert target.stat().st_mtime_ns == original_mtime


# ---------------------------------------------------------------------------
# clean_opendataloader_temp_image_links
# ---------------------------------------------------------------------------


class TestCleanOpendataloaderTempImageLinks:
    def test_removes_temp_image_link(self, tmp_path):
        target = tmp_path / "book.md"
        target.write_text(
            "before ![img](page_3_images/pic.png) after",
            encoding="utf-8",
        )

        clean_opendataloader_temp_image_links([target])

        content = target.read_text(encoding="utf-8")
        assert "page_3_images" not in content
        assert "before" in content
        assert "after" in content

    def test_keeps_non_temp_image_links(self, tmp_path):
        target = tmp_path / "book.md"
        target.write_text("![alt](images/book/pic.png)", encoding="utf-8")

        clean_opendataloader_temp_image_links([target])

        assert "images/book/pic.png" in target.read_text(encoding="utf-8")

    def test_missing_file_is_skipped(self, tmp_path):
        missing = tmp_path / "missing.md"
        clean_opendataloader_temp_image_links([missing])  # should not raise


# ---------------------------------------------------------------------------
# clean_artifact_headings
# ---------------------------------------------------------------------------


class TestCleanArtifactHeadings:
    def test_removes_numeric_and_empty_headings(self, tmp_path):
        target = tmp_path / "book.md"
        target.write_text("# 33\n\n## Real Heading\ncontent\n\n##\n", encoding="utf-8")

        clean_artifact_headings([target])

        content = target.read_text(encoding="utf-8")
        assert "# 33" not in content
        assert "## Real Heading" in content

    def test_missing_file_is_skipped(self, tmp_path):
        missing = tmp_path / "missing.md"
        clean_artifact_headings([missing])  # should not raise


# ---------------------------------------------------------------------------
# clean_list_continuations
# ---------------------------------------------------------------------------


class TestCleanListContinuations:
    def test_merges_wrapped_list_continuation(self, tmp_path):
        target = tmp_path / "book.md"
        target.write_text(
            "But one should avoid overly graphic representations (unless this "
            "was agreed\n"
            "\n"
            "- to during the Prelude phase). Such would not be part of the fun.\n",
            encoding="utf-8",
        )

        clean_list_continuations([target])

        content = target.read_text(encoding="utf-8")
        assert "- to during" not in content
        assert "agreed to during the Prelude phase" in content

    def test_leaves_genuine_list_untouched(self, tmp_path):
        target = tmp_path / "book.md"
        original = "###### Heading\n\n- At last, your game has come to an end.\n"
        target.write_text(original, encoding="utf-8")

        clean_list_continuations([target])

        assert target.read_text(encoding="utf-8") == original

    def test_missing_file_is_skipped(self, tmp_path):
        missing = tmp_path / "missing.md"
        clean_list_continuations([missing])  # should not raise


# ---------------------------------------------------------------------------
# clean_paragraph_continuations
# ---------------------------------------------------------------------------


class TestCleanParagraphContinuations:
    def test_merges_wrapped_paragraph_continuation(self, tmp_path, capsys):
        target = tmp_path / "book.md"
        target.write_text(
            "Kedamono Opera is a game that depicts nightmarish creatures with "
            "dualistic natures. While monsters perhaps, at the same time, "
            "there’s room for negotiation\n"
            "\n"
            "with these other weaker creatures. How that comes about is "
            "something entirely up to you.\n",
            encoding="utf-8",
        )

        clean_paragraph_continuations([target])

        content = target.read_text(encoding="utf-8")
        assert "room for negotiation\n\nwith" not in content
        assert "room for negotiation with these other weaker creatures" in content
        assert "已合併段落斷行續句" in capsys.readouterr().out

    def test_reports_ambiguous_case_without_merging(self, tmp_path, capsys):
        target = tmp_path / "book.md"
        original = (
            "\x94 Portents featuring things not included in the scenario’s "
            "outline, but\n"
            "\n"
            "are interesting when they happen. 225\n"
        )
        target.write_text(original, encoding="utf-8")

        clean_paragraph_continuations([target])

        assert target.read_text(encoding="utf-8") == original
        assert "疑似段落斷行續句" in capsys.readouterr().out

    def test_leaves_table_of_contents_untouched(self, tmp_path):
        target = tmp_path / "book.md"
        original = "Table of ConTenTs\n\nbasiC rules\n\nPg. 2\n"
        target.write_text(original, encoding="utf-8")

        clean_paragraph_continuations([target])

        assert target.read_text(encoding="utf-8") == original

    def test_missing_file_is_skipped(self, tmp_path):
        missing = tmp_path / "missing.md"
        clean_paragraph_continuations([missing])  # should not raise
