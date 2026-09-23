"""Tests for merge_translated_list_continuations.py."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from merge_translated_list_continuations import merge_one_pair, pair_files


SCRIPT = Path(__file__).parents[1] / "merge_translated_list_continuations.py"

SOURCE_TEXT = (
    "But one should avoid overly graphic or grotesque representations of such "
    "fates (unless this was agreed\n"
    "\n"
    "- to during the Prelude phase). Such would not be part of the fun of "
    "Kedamono Opera.\n"
)

# Translator kept the same (unordered, depth-0) list-item shape when working around
# the false break, so the structure validator's alignment maps it 1:1 to the source.
TRANSLATION_TEXT = (
    "但也不該過度描繪殘忍或獵奇的場景（除非事先徵得同意\n"
    "\n"
    "- 於序章階段同意）。這不屬於暗獸歌劇的樂趣所在。\n"
)

TRANSLATION_MERGED = (
    "但也不該過度描繪殘忍或獵奇的場景（除非事先徵得同意於序章階段同意）。這不屬於暗獸歌劇的樂趣所在。\n"
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

    def test_skips_translation_files_without_matching_source(self, tmp_path):
        source_dir = tmp_path / "source"
        translation_dir = tmp_path / "translation"
        source_dir.mkdir()
        translation_dir.mkdir()
        (translation_dir / "orphan.md").write_text("b", encoding="utf-8")

        assert pair_files(source_dir, translation_dir) == []

    def test_ignores_non_markdown_files_in_tree(self, tmp_path):
        source_dir = tmp_path / "source"
        translation_dir = tmp_path / "translation"
        source_dir.mkdir()
        translation_dir.mkdir()
        (source_dir / "notes.txt").write_text("a", encoding="utf-8")
        (translation_dir / "notes.txt").write_text("b", encoding="utf-8")

        assert pair_files(source_dir, translation_dir) == []

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
    def test_merges_translation_using_source_driven_alignment(self, tmp_path):
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
        source.write_text("no breaks here\n\nmore text\n", encoding="utf-8")
        translation.write_text("沒有斷句\n\n更多文字\n", encoding="utf-8")

        result = merge_one_pair(source, translation, dry_run=False)

        assert result["candidates"] == 0
        assert result["merged"] == 0
        assert translation.read_text(encoding="utf-8") == "沒有斷句\n\n更多文字\n"

    def test_reports_unresolved_when_translation_dropped_the_list_shape(self, tmp_path):
        source = tmp_path / "source.md"
        translation = tmp_path / "translation.md"
        source.write_text(SOURCE_TEXT, encoding="utf-8")
        # Translator already rewrote this as a single merged paragraph by hand,
        # so there is no aligned list-item token left to locate.
        translation.write_text(
            "但也不該過度描繪殘忍或獵奇的場景（除非事先徵得同意於序章階段同意）。\n",
            encoding="utf-8",
        )

        result = merge_one_pair(source, translation, dry_run=False)

        assert result["candidates"] == 1
        assert result["merged"] == 0
        assert result["unresolved"] == [3]


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

    def test_exits_nonzero_when_unresolved(self, tmp_path):
        source = tmp_path / "source.md"
        translation = tmp_path / "translation.md"
        source.write_text(SOURCE_TEXT, encoding="utf-8")
        translation.write_text(
            "但也不該過度描繪殘忍或獵奇的場景（除非事先徵得同意於序章階段同意）。\n",
            encoding="utf-8",
        )

        completed = run_cli(str(source), str(translation), "--json")

        assert completed.returncode == 1
        payload = json.loads(completed.stdout)
        assert payload["total_unresolved"] == 1

    def test_missing_source_errors(self, tmp_path):
        translation = tmp_path / "translation.md"
        translation.write_text("x", encoding="utf-8")

        completed = run_cli(str(tmp_path / "missing.md"), str(translation))

        assert completed.returncode == 2
