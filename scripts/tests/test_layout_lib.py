"""Tests for _layout_lib module."""

import pytest

from _layout_lib import (
    analyze_pymupdf_text_noise,
    classify_page_layout,
    extract_page_text_pymupdf,
    sample_page_indices,
    MIN_QUALITY_PROBE_CHARS,
)


# ---------------------------------------------------------------------------
# sample_page_indices
# ---------------------------------------------------------------------------

class TestSamplePageIndices:
    def test_zero_pages(self):
        assert sample_page_indices(0) == []

    def test_negative_pages(self):
        assert sample_page_indices(-5) == []

    def test_fewer_than_max(self):
        assert sample_page_indices(5) == [0, 1, 2, 3, 4]

    def test_equal_to_max(self):
        assert sample_page_indices(12) == list(range(12))

    def test_more_than_max(self):
        result = sample_page_indices(100, max_samples=5)
        assert len(result) == 5
        assert result[0] == 0
        assert result[-1] == 99
        assert result == sorted(result)

    def test_large_page_count(self):
        result = sample_page_indices(1000, max_samples=12)
        assert len(result) == 12
        assert result[0] == 0
        assert result[-1] == 999

    def test_single_page(self):
        assert sample_page_indices(1) == [0]

    def test_two_pages_max_two(self):
        result = sample_page_indices(2, max_samples=2)
        assert result == [0, 1]

    def test_indices_are_sorted(self):
        result = sample_page_indices(50, max_samples=7)
        assert result == sorted(result)

    def test_no_duplicates(self):
        result = sample_page_indices(50, max_samples=10)
        assert len(result) == len(set(result))


# ---------------------------------------------------------------------------
# classify_page_layout
# ---------------------------------------------------------------------------

def _make_word(x0, y0, x1, y1, text, block_no=0, line_no=0, word_no=0):
    """Helper to build a word tuple matching pymupdf format."""
    return (x0, y0, x1, y1, text, block_no, line_no, word_no)


def _make_line_words(x0, x1, text, block_no, line_no, page_width=600):
    """Build words for a single line spanning x0..x1."""
    words = []
    n_words = max(1, len(text.split()))
    step = (x1 - x0) / n_words
    for i, w in enumerate(text.split()):
        wx0 = x0 + i * step
        wx1 = wx0 + step
        words.append(_make_word(wx0, 100, wx1, 120, w, block_no, line_no, i))
    return words


class TestClassifyPageLayout:
    def test_empty_words(self):
        result = classify_page_layout([], 600)
        assert result["layout_profile"] == "unknown"

    def test_zero_page_width(self):
        result = classify_page_layout([], 0)
        assert result["layout_profile"] == "unknown"
        assert result["confidence"] == 0.0

    def test_negative_page_width(self):
        result = classify_page_layout([], -100)
        assert result["layout_profile"] == "unknown"

    def test_too_few_lines(self):
        # Only 2 lines — not enough for classification
        words = []
        for i in range(2):
            words.extend(_make_line_words(10, 580, "This is a spanning line of text here", 0, i))
        result = classify_page_layout(words, 600)
        assert result["layout_profile"] == "unknown"

    def test_single_column_detected(self):
        """Lines spanning full width should be classified as single-column."""
        page_width = 600
        words = []
        for i in range(12):
            words.extend(
                _make_line_words(
                    20, 580,
                    "This is a long spanning line of text content here okay",
                    0, i, page_width,
                )
            )
        result = classify_page_layout(words, page_width)
        assert result["layout_profile"] == "single-column"
        assert result["confidence"] > 0

    def test_double_column_detected(self):
        """Half the lines on the left, half on the right."""
        page_width = 600
        words = []
        for i in range(6):
            # Left column: x0=20, x1=280 (< 0.48*600=288)
            words.extend(
                _make_line_words(
                    20, 280,
                    "Left column text line here for the test okay sure",
                    0, i, page_width,
                )
            )
        for i in range(6):
            # Right column: x0=320 (> 0.51*600=306), x1=580
            words.extend(
                _make_line_words(
                    320, 580,
                    "Right column text line here for the test okay sure",
                    1, i, page_width,
                )
            )
        result = classify_page_layout(words, page_width)
        assert result["layout_profile"] == "double-column"
        assert result["confidence"] > 0

    def test_short_text_filtered(self):
        """Words with < 2 non-whitespace chars should be ignored."""
        words = [_make_word(10, 10, 50, 30, "a", 0, 0, 0)]
        result = classify_page_layout(words, 600)
        assert result["layout_profile"] == "unknown"

    def test_result_keys(self):
        result = classify_page_layout([], 600)
        assert "layout_profile" in result
        assert "confidence" in result
        assert "classified_lines" in result


# ---------------------------------------------------------------------------
# extract_page_text_pymupdf
# ---------------------------------------------------------------------------

class _FakePage:
    """Records the ``sort`` kwarg passed to ``get_text``."""

    def __init__(self, text: str = "hello world"):
        self.text = text
        self.calls: list[dict] = []

    def get_text(self, mode, sort=None):
        self.calls.append({"mode": mode, "sort": sort})
        return self.text


class TestExtractPageTextPymupdf:
    def test_default_sorts_true(self):
        page = _FakePage()
        extract_page_text_pymupdf(page)
        assert page.calls[-1]["sort"] is True

    def test_explicit_sort_false(self):
        page = _FakePage()
        extract_page_text_pymupdf(page, sort=False)
        assert page.calls[-1]["sort"] is False

    def test_strips_result(self):
        page = _FakePage("  padded text  ")
        assert extract_page_text_pymupdf(page) == "padded text"

    def test_falls_back_when_sort_unsupported(self):
        class NoSortPage:
            def get_text(self, mode, sort=None):
                if sort is not None:
                    raise TypeError("unexpected keyword argument 'sort'")
                return "fallback text"

        assert extract_page_text_pymupdf(NoSortPage()) == "fallback text"


# ---------------------------------------------------------------------------
# analyze_pymupdf_text_noise
# ---------------------------------------------------------------------------

class TestAnalyzePymupdfTextNoise:
    def test_empty_text(self):
        result = analyze_pymupdf_text_noise("")
        assert result["char_count"] == 0
        assert result["is_noisy"] is False

    def test_clean_text(self):
        text = "This is clean text. " * 30
        result = analyze_pymupdf_text_noise(text)
        assert result["is_noisy"] is False
        assert result["long_space_runs"] == 0

    def test_noisy_whitespace_ratio(self):
        # Create text with many long space runs
        clean = "word " * 50
        noisy = "word" + " " * 20 + "word" + " " * 20 + "word\n" * 20
        text = clean + noisy
        # Ensure enough chars
        text = text * 3
        result = analyze_pymupdf_text_noise(text)
        assert result["long_space_runs"] > 0
        assert result["whitespace_ratio"] > 0

    def test_noisy_lines_threshold(self):
        # Build text with >= 4 lines containing 8+ spaces
        lines = []
        for _ in range(5):
            lines.append("word" + " " * 10 + "another word here okay")
        lines.extend(["normal line of text"] * 20)
        text = "\n".join(lines)
        # Pad to reach MIN_QUALITY_PROBE_CHARS
        while len(text) < MIN_QUALITY_PROBE_CHARS:
            text += "\nnormal line of text with enough chars"
        result = analyze_pymupdf_text_noise(text)
        assert result["noisy_lines"] >= 4

    def test_short_text_not_noisy(self):
        # Short text should never be noisy even with spaces
        text = "a" + " " * 20 + "b"
        result = analyze_pymupdf_text_noise(text)
        assert result["is_noisy"] is False

    def test_null_bytes_removed(self):
        text = "hello\x00world"
        result = analyze_pymupdf_text_noise(text)
        assert result["char_count"] == len("helloworld")

    def test_result_keys(self):
        result = analyze_pymupdf_text_noise("test")
        expected_keys = {
            "char_count", "long_space_runs", "max_long_space_run",
            "noisy_lines", "whitespace_ratio", "is_noisy",
        }
        assert set(result.keys()) == expected_keys
