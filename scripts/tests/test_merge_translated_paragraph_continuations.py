"""Tests for merge_translated_paragraph_continuations.py."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from merge_translated_paragraph_continuations import merge_one_pair, pair_files


SCRIPT = Path(__file__).parents[1] / "merge_translated_paragraph_continuations.py"

# Real break drawn from kedamono-opera/data/markdown/Kedamono_Opera.md
# (lines 1244-1246), bounded by headings so the structural-anchor windowing
# has real anchors to align on either side.
SOURCE_TEXT = (
    "## Chapter\n"
    "\n"
    "Kedamono Opera is a game that depicts nightmarish creatures with dualistic "
    "natures. While monsters perhaps, at the same time, there’s room for negotiation\n"
    "\n"
    "with these other weaker creatures. How that comes about is something "
    "entirely up to you.\n"
    "\n"
    "## Next Chapter\n"
)

# Translator kept the same two-paragraph shape when working around the false
# break, so the structure validator's heading-anchored alignment locates it.
TRANSLATION_TEXT = (
    "## 章節\n"
    "\n"
    "暗獸歌劇是一款描繪具有雙重本性的惡夢生物的遊戲。雖然看似怪物，但同時仍有協商的餘地\n"
    "\n"
    "與這些較弱小的生物之間。事情如何發展，完全取決於你。\n"
    "\n"
    "## 下一章\n"
)

TRANSLATION_MERGED = (
    "## 章節\n"
    "\n"
    "暗獸歌劇是一款描繪具有雙重本性的惡夢生物的遊戲。雖然看似怪物，但同時仍有協商的餘地與"
    "這些較弱小的生物之間。事情如何發展，完全取決於你。\n"
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
# merge_one_pair
# ---------------------------------------------------------------------------


class TestMergeOnePair:
    def test_merges_translation_using_structure_anchored_alignment(self, tmp_path):
        source = tmp_path / "source.md"
        translation = tmp_path / "translation.md"
        source.write_text(SOURCE_TEXT, encoding="utf-8")
        translation.write_text(TRANSLATION_TEXT, encoding="utf-8")

        result = merge_one_pair(source, translation, dry_run=False)

        assert result["candidates"] == 1
        assert result["merged"] == 1
        assert result["unresolved"] == []
        assert translation.read_text(encoding="utf-8") == TRANSLATION_MERGED

    def test_dry_run_does_not_write(self, tmp_path):
        source = tmp_path / "source.md"
        translation = tmp_path / "translation.md"
        source.write_text(SOURCE_TEXT, encoding="utf-8")
        translation.write_text(TRANSLATION_TEXT, encoding="utf-8")

        result = merge_one_pair(source, translation, dry_run=True)

        assert result["merged"] == 1
        assert translation.read_text(encoding="utf-8") == TRANSLATION_TEXT

    def test_no_candidates_leaves_translation_untouched(self, tmp_path):
        source = tmp_path / "source.md"
        translation = tmp_path / "translation.md"
        source.write_text("## Chapter\n\nno breaks here.\n\nmore text.\n", encoding="utf-8")
        translation.write_text("## 章節\n\n沒有斷句。\n\n更多文字。\n", encoding="utf-8")

        result = merge_one_pair(source, translation, dry_run=False)

        assert result["candidates"] == 0
        assert result["merged"] == 0
        assert translation.read_text(encoding="utf-8") == "## 章節\n\n沒有斷句。\n\n更多文字。\n"

    def test_reports_unresolved_when_paragraph_counts_mismatch(self, tmp_path):
        source = tmp_path / "source.md"
        translation = tmp_path / "translation.md"
        source.write_text(SOURCE_TEXT, encoding="utf-8")
        # Translator already rewrote this as a single merged paragraph by hand,
        # so the window has one paragraph in the draft against two in the source.
        translation.write_text(
            "## 章節\n\n"
            "暗獸歌劇是一款描繪具有雙重本性的惡夢生物的遊戲。雖然看似怪物，但同時仍有協商的餘地"
            "與這些較弱小的生物之間。事情如何發展，完全取決於你。\n\n"
            "## 下一章\n",
            encoding="utf-8",
        )

        result = merge_one_pair(source, translation, dry_run=False)

        assert result["candidates"] == 1
        assert result["merged"] == 0
        assert result["unresolved"] == [5]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli:
    def test_dry_run_reports_json_without_writing(self, tmp_path):
        source = tmp_path / "source.md"
        translation = tmp_path / "translation.md"
        source.write_text(SOURCE_TEXT, encoding="utf-8")
        translation.write_text(TRANSLATION_TEXT, encoding="utf-8")

        completed = run_cli(str(source), str(translation), "--dry-run", "--json")

        assert completed.returncode == 0
        payload = json.loads(completed.stdout)
        assert payload["dry_run"] is True
        assert payload["total_merged"] == 1
        assert translation.read_text(encoding="utf-8") == TRANSLATION_TEXT

    def test_applies_merge_and_exits_zero(self, tmp_path):
        source = tmp_path / "source.md"
        translation = tmp_path / "translation.md"
        source.write_text(SOURCE_TEXT, encoding="utf-8")
        translation.write_text(TRANSLATION_TEXT, encoding="utf-8")

        completed = run_cli(str(source), str(translation), "--json")

        assert completed.returncode == 0
        payload = json.loads(completed.stdout)
        assert payload["dry_run"] is False
        assert payload["total_merged"] == 1
        assert translation.read_text(encoding="utf-8") == TRANSLATION_MERGED

    def test_missing_source_errors(self, tmp_path):
        translation = tmp_path / "translation.md"
        translation.write_text("x", encoding="utf-8")

        completed = run_cli(str(tmp_path / "missing.md"), str(translation))

        assert completed.returncode == 2
