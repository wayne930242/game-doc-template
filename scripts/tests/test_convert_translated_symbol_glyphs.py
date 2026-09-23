"""Tests for convert_translated_symbol_glyphs.py."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from convert_translated_symbol_glyphs import convert_one_pair, load_symbol_glyphs, pair_files


SCRIPT = Path(__file__).parents[1] / "convert_translated_symbol_glyphs.py"
GLYPH = "\x94"

SOURCE_TITLE_TEXT = (
    "## Chapter\n"
    "\n"
    "This is a complete introductory sentence that ends properly.\n"
    "\n"
    f"{GLYPH} Goal of the Game\n"
    "\n"
    "More prose follows this heading and continues normally with the story.\n"
    "\n"
    "## Next Chapter\n"
)

TRANSLATION_TITLE_TEXT = (
    "## 章節\n"
    "\n"
    "這是一段完整的介紹句子，並以句號正確結尾。\n"
    "\n"
    f"{GLYPH} 遊戲目標\n"
    "\n"
    "標題之後接著更多文字，故事繼續正常發展下去。\n"
    "\n"
    "## 下一章\n"
)

TRANSLATION_TITLE_CONVERTED = (
    "## 章節\n"
    "\n"
    "這是一段完整的介紹句子，並以句號正確結尾。\n"
    "\n"
    "### 遊戲目標\n"
    "\n"
    "標題之後接著更多文字，故事繼續正常發展下去。\n"
    "\n"
    "## 下一章\n"
)


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False
    )


# ---------------------------------------------------------------------------
# pair_files
# ---------------------------------------------------------------------------


class TestPairFiles:
    def test_pairs_single_files(self, tmp_path):
        source = tmp_path / "source.md"
        translation = tmp_path / "translation.md"
        source.write_text("a", encoding="utf-8")
        translation.write_text("b", encoding="utf-8")

        assert pair_files(source, translation) == [(source, translation)]

    def test_pairs_matching_relative_paths_in_trees(self, tmp_path):
        source_dir = tmp_path / "source"
        translation_dir = tmp_path / "translation"
        (source_dir / "chapters").mkdir(parents=True)
        (translation_dir / "chapters").mkdir(parents=True)
        (source_dir / "chapters" / "intro.md").write_text("a", encoding="utf-8")
        (translation_dir / "chapters" / "intro.md").write_text("b", encoding="utf-8")

        pairs = pair_files(source_dir, translation_dir)

        assert pairs == [
            (source_dir / "chapters" / "intro.md", translation_dir / "chapters" / "intro.md")
        ]

    def test_rejects_file_directory_mismatch(self, tmp_path):
        source = tmp_path / "source.md"
        translation_dir = tmp_path / "translation"
        source.write_text("a", encoding="utf-8")
        translation_dir.mkdir()

        with pytest.raises(ValueError):
            pair_files(source, translation_dir)


# ---------------------------------------------------------------------------
# load_symbol_glyphs
# ---------------------------------------------------------------------------


class TestLoadSymbolGlyphs:
    def test_reads_from_style_decisions(self, tmp_path):
        (tmp_path / "style-decisions.json").write_text(
            json.dumps({"document_format": {"symbol_glyphs": [GLYPH]}}), encoding="utf-8"
        )
        assert load_symbol_glyphs(tmp_path) == [GLYPH]

    def test_missing_file_returns_empty(self, tmp_path):
        assert load_symbol_glyphs(tmp_path) == []

    def test_missing_key_returns_empty(self, tmp_path):
        (tmp_path / "style-decisions.json").write_text(
            json.dumps({"document_format": {}}), encoding="utf-8"
        )
        assert load_symbol_glyphs(tmp_path) == []

    def test_malformed_json_returns_empty(self, tmp_path):
        (tmp_path / "style-decisions.json").write_text("{not json", encoding="utf-8")
        assert load_symbol_glyphs(tmp_path) == []


# ---------------------------------------------------------------------------
# convert_one_pair
# ---------------------------------------------------------------------------


class TestConvertOnePair:
    def test_converts_title_using_structure_anchored_alignment(self, tmp_path):
        source = tmp_path / "source.md"
        translation = tmp_path / "translation.md"
        source.write_text(SOURCE_TITLE_TEXT, encoding="utf-8")
        translation.write_text(TRANSLATION_TITLE_TEXT, encoding="utf-8")

        result = convert_one_pair(source, translation, [GLYPH], dry_run=False)

        assert result["candidates"] == 1
        assert result["titles"] == 1
        assert result["list_items_from_singleton"] == 0
        assert result["list_items_from_split"] == 0
        assert result["dropped"] == 0
        assert result["unresolved"] == []
        assert result["leftover"] == 0
        assert translation.read_text(encoding="utf-8") == TRANSLATION_TITLE_CONVERTED

    def test_dry_run_does_not_write(self, tmp_path):
        source = tmp_path / "source.md"
        translation = tmp_path / "translation.md"
        source.write_text(SOURCE_TITLE_TEXT, encoding="utf-8")
        translation.write_text(TRANSLATION_TITLE_TEXT, encoding="utf-8")

        result = convert_one_pair(source, translation, [GLYPH], dry_run=True)

        assert result["titles"] == 1
        assert translation.read_text(encoding="utf-8") == TRANSLATION_TITLE_TEXT

    def test_no_residue_in_translation_is_not_a_failure(self, tmp_path):
        # The translator already smoothed the ornament into prose by hand
        # (no literal glyph survives); nothing to convert, and it must not
        # be reported as unresolved.
        source = tmp_path / "source.md"
        translation = tmp_path / "translation.md"
        source.write_text(f"## Chapter\n\nComplete sentence here.\n\n{GLYPH} A Title\n", encoding="utf-8")
        translation.write_text("## 章節\n\n完整的句子在此。\n\n### 一個標題\n", encoding="utf-8")

        result = convert_one_pair(source, translation, [GLYPH], dry_run=False)

        assert result["candidates"] == 0
        assert result["titles"] == 0
        assert result["unresolved"] == []

    def test_reports_unresolved_when_window_counts_mismatch(self, tmp_path):
        # Source has two singleton glyph blocks in the same structural
        # window; the translator already hand-merged them into one bullet,
        # so the draft only carries one glyph residue there.
        source = tmp_path / "source.md"
        translation = tmp_path / "translation.md"
        source.write_text(
            "## Chapter\n"
            "\n"
            "- An existing list item to anchor the window.\n"
            "\n"
            f"{GLYPH} First point mentioned here\n"
            "\n"
            f"{GLYPH} Second point mentioned here\n"
            "\n"
            "## Next Chapter\n",
            encoding="utf-8",
        )
        translation.write_text(
            "## 章節\n"
            "\n"
            "- 一個既有的清單項目，用來當作錨點。\n"
            "\n"
            f"{GLYPH} 這裡提到的重點合併在一起了\n"
            "\n"
            "## 下一章\n",
            encoding="utf-8",
        )

        result = convert_one_pair(source, translation, [GLYPH], dry_run=False)

        assert result["candidates"] == 1
        assert result["titles"] == 0
        assert result["list_items_from_singleton"] == 0
        assert result["unresolved"] == [5, 7]
        assert result["leftover"] == 1
        # Nothing applied safely, so the translation is left untouched.
        assert GLYPH in translation.read_text(encoding="utf-8")

    def test_no_glyphs_configured_is_a_no_op(self, tmp_path):
        source = tmp_path / "source.md"
        translation = tmp_path / "translation.md"
        source.write_text(SOURCE_TITLE_TEXT, encoding="utf-8")
        translation.write_text(TRANSLATION_TITLE_TEXT, encoding="utf-8")

        result = convert_one_pair(source, translation, [], dry_run=False)

        assert result["candidates"] == 0
        assert translation.read_text(encoding="utf-8") == TRANSLATION_TITLE_TEXT


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli:
    def test_dry_run_reports_json_without_writing(self, tmp_path):
        source = tmp_path / "source.md"
        translation = tmp_path / "translation.md"
        source.write_text(SOURCE_TITLE_TEXT, encoding="utf-8")
        translation.write_text(TRANSLATION_TITLE_TEXT, encoding="utf-8")

        completed = run_cli(str(source), str(translation), "--glyph", GLYPH, "--dry-run", "--json")

        assert completed.returncode == 0
        payload = json.loads(completed.stdout)
        assert payload["dry_run"] is True
        assert payload["total_converted"] == 1
        assert payload["total_unresolved"] == 0
        assert payload["total_leftover"] == 0
        assert translation.read_text(encoding="utf-8") == TRANSLATION_TITLE_TEXT

    def test_applies_conversion_and_exits_zero(self, tmp_path):
        source = tmp_path / "source.md"
        translation = tmp_path / "translation.md"
        source.write_text(SOURCE_TITLE_TEXT, encoding="utf-8")
        translation.write_text(TRANSLATION_TITLE_TEXT, encoding="utf-8")

        completed = run_cli(str(source), str(translation), "--glyph", GLYPH, "--json")

        assert completed.returncode == 0
        payload = json.loads(completed.stdout)
        assert payload["dry_run"] is False
        assert payload["total_converted"] == 1
        assert translation.read_text(encoding="utf-8") == TRANSLATION_TITLE_CONVERTED

    def test_exits_nonzero_when_unresolved_remain(self, tmp_path):
        source = tmp_path / "source.md"
        translation = tmp_path / "translation.md"
        source.write_text(
            "## Chapter\n"
            "\n"
            "- An existing list item to anchor the window.\n"
            "\n"
            f"{GLYPH} First point mentioned here\n"
            "\n"
            f"{GLYPH} Second point mentioned here\n"
            "\n"
            "## Next Chapter\n",
            encoding="utf-8",
        )
        translation.write_text(
            "## 章節\n"
            "\n"
            "- 一個既有的清單項目，用來當作錨點。\n"
            "\n"
            f"{GLYPH} 這裡提到的重點合併在一起了\n"
            "\n"
            "## 下一章\n",
            encoding="utf-8",
        )

        completed = run_cli(str(source), str(translation), "--glyph", GLYPH, "--dry-run", "--json")

        assert completed.returncode == 1
        payload = json.loads(completed.stdout)
        assert payload["total_unresolved"] == 2

    def test_missing_source_errors(self, tmp_path):
        translation = tmp_path / "translation.md"
        translation.write_text("x", encoding="utf-8")

        completed = run_cli(str(tmp_path / "missing.md"), str(translation), "--glyph", GLYPH)

        assert completed.returncode == 2

    def test_no_glyphs_available_errors(self, tmp_path):
        source = tmp_path / "source.md"
        translation = tmp_path / "translation.md"
        source.write_text("a", encoding="utf-8")
        translation.write_text("b", encoding="utf-8")

        completed = run_cli(str(source), str(translation))

        assert completed.returncode == 2
