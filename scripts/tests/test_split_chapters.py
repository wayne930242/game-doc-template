"""Tests for split_chapters module."""

import pytest

from split_chapters import (
    _load_manifest_cached,
    _manifest_cache,
    extract_pages,
    generate_frontmatter,
    get_page_range,
    infer_source_stem,
    build_page_text_stats,
    group_images_by_page,
    main,
    normalize_files,
    parse_args,
    resolve_config,
    split_chapters,
    write_meta_yml,
)
from pathlib import Path


# ---------------------------------------------------------------------------
# extract_pages
# ---------------------------------------------------------------------------

class TestExtractPages:
    def test_single_page(self):
        content = "<!-- PAGE 1 -->\n\nHello world"
        pages = extract_pages(content)
        assert pages == {1: "Hello world"}

    def test_multiple_pages(self):
        content = (
            "<!-- PAGE 1 -->\n\nFirst page content\n\n"
            "<!-- PAGE 2 -->\n\nSecond page content\n\n"
            "<!-- PAGE 3 -->\n\nThird page content"
        )
        pages = extract_pages(content)
        assert len(pages) == 3
        assert pages[1] == "First page content"
        assert pages[2] == "Second page content"
        assert pages[3] == "Third page content"

    def test_empty_content(self):
        pages = extract_pages("")
        assert pages == {}

    def test_no_page_markers(self):
        pages = extract_pages("Just some text without markers")
        assert pages == {}

    def test_non_sequential_pages(self):
        content = (
            "<!-- PAGE 5 -->\n\nPage five\n\n"
            "<!-- PAGE 10 -->\n\nPage ten"
        )
        pages = extract_pages(content)
        assert len(pages) == 2
        assert pages[5] == "Page five"
        assert pages[10] == "Page ten"

    def test_page_with_multiline_content(self):
        content = "<!-- PAGE 1 -->\n\nLine one\n\nLine two\n\nLine three"
        pages = extract_pages(content)
        assert "Line one" in pages[1]
        assert "Line two" in pages[1]
        assert "Line three" in pages[1]

    def test_page_content_is_stripped(self):
        content = "<!-- PAGE 1 -->\n\n  Hello  \n\n<!-- PAGE 2 -->\n\nWorld"
        pages = extract_pages(content)
        assert pages[1] == "Hello"


# ---------------------------------------------------------------------------
# get_page_range
# ---------------------------------------------------------------------------

class TestGetPageRange:
    def test_single_page_range(self):
        pages = {1: "A", 2: "B", 3: "C"}
        result = get_page_range(pages, 2, 2)
        assert result == "B"

    def test_multi_page_range(self):
        pages = {1: "A", 2: "B", 3: "C"}
        result = get_page_range(pages, 1, 3)
        assert result == "A\n\nB\n\nC"

    def test_missing_pages_in_range(self):
        pages = {1: "A", 3: "C"}
        result = get_page_range(pages, 1, 3)
        assert result == "A\n\nC"

    def test_all_missing(self):
        pages = {1: "A"}
        result = get_page_range(pages, 5, 7)
        assert result == ""

    def test_empty_pages(self):
        result = get_page_range({}, 1, 5)
        assert result == ""


# ---------------------------------------------------------------------------
# generate_frontmatter
# ---------------------------------------------------------------------------

class TestGenerateFrontmatter:
    def test_title_only(self):
        result = generate_frontmatter("My Title")
        assert "title: My Title" in result
        assert result.startswith("---\n")
        assert result.endswith("---\n")
        assert "description" not in result
        assert "sidebar" not in result

    def test_with_description(self):
        result = generate_frontmatter("Title", description="Some desc")
        assert "title: Title" in result
        assert "description: Some desc" in result

    def test_with_order(self):
        result = generate_frontmatter("Title", order=5)
        assert "sidebar:" in result
        assert "order: 5" in result

    def test_with_all_params(self):
        result = generate_frontmatter("Title", description="Desc", order=0)
        assert "title: Title" in result
        assert "description: Desc" in result
        assert "sidebar:" in result
        assert "order: 0" in result

    def test_order_none_omits_sidebar(self):
        result = generate_frontmatter("Title", order=None)
        assert "sidebar" not in result

    def test_empty_description_omitted(self):
        result = generate_frontmatter("Title", description="")
        assert "description" not in result


# ---------------------------------------------------------------------------
# infer_source_stem
# ---------------------------------------------------------------------------

class TestInferSourceStem:
    def test_with_pages_suffix(self):
        assert infer_source_stem(Path("data/markdown/rulebook_pages.md")) == "rulebook"

    def test_without_pages_suffix(self):
        assert infer_source_stem(Path("data/markdown/rulebook.md")) == "rulebook"

    def test_complex_name_with_pages(self):
        assert infer_source_stem(Path("my_game_rules_pages.md")) == "my_game_rules"

    def test_pages_in_middle_not_stripped(self):
        # Only strip _pages at the end of the stem
        assert infer_source_stem(Path("pages_data.md")) == "pages_data"


# ---------------------------------------------------------------------------
# build_page_text_stats
# ---------------------------------------------------------------------------

class TestBuildPageTextStats:
    def test_basic_stats(self):
        pages = {1: "Hello world", 2: "Another page with more text"}
        stats = build_page_text_stats(pages, [])
        assert 1 in stats
        assert 2 in stats
        assert "text_tokens" in stats[1]
        assert "char_count" in stats[1]
        assert stats[1]["char_count"] == len("Hello world")

    def test_empty_pages(self):
        stats = build_page_text_stats({}, [])
        assert stats == {}

    def test_clean_patterns_applied(self):
        pages = {1: "Hello (Order #123) world"}
        stats_without = build_page_text_stats(pages, [])
        stats_with = build_page_text_stats(pages, [r"\(Order #\d+\)"])
        # After cleaning, char count should be smaller
        assert stats_with[1]["char_count"] < stats_without[1]["char_count"]

    def test_text_tokens_positive(self):
        pages = {1: "Some actual text content here"}
        stats = build_page_text_stats(pages, [])
        assert stats[1]["text_tokens"] > 0


# ---------------------------------------------------------------------------
# normalize_files
# ---------------------------------------------------------------------------

class TestNormalizeFiles:
    def test_flat_entry_unchanged(self):
        files = {"actions": {"title": "Actions", "pages": [5, 7], "order": 0}}
        result = normalize_files(files)
        assert result == files

    def test_single_slash_path_becomes_nested(self):
        files = {"combat/actions": {"title": "Actions", "pages": [5, 7], "order": 0}}
        result = normalize_files(files)
        assert "combat" in result
        assert "files" in result["combat"]
        assert "actions" in result["combat"]["files"]
        assert result["combat"]["files"]["actions"]["pages"] == [5, 7]
        assert result["combat"]["title"] == "combat"

    def test_multi_level_slash_path(self):
        files = {"a/b/c": {"title": "C", "pages": [1, 2], "order": 0}}
        result = normalize_files(files)
        assert "a" in result
        assert "b" in result["a"]["files"]
        assert "c" in result["a"]["files"]["b"]["files"]

    def test_multiple_children_same_parent(self):
        files = {
            "combat/actions": {"title": "Actions", "pages": [5, 7], "order": 0},
            "combat/damage": {"title": "Damage", "pages": [8, 10], "order": 1},
        }
        result = normalize_files(files)
        assert "combat" in result
        assert "actions" in result["combat"]["files"]
        assert "damage" in result["combat"]["files"]

    def test_mixed_flat_and_slash(self):
        files = {
            "index": {"title": "Index", "pages": [1, 4], "order": 0},
            "combat/actions": {"title": "Actions", "pages": [5, 7], "order": 1},
        }
        result = normalize_files(files)
        assert "index" in result
        assert "pages" in result["index"]
        assert "combat" in result
        assert "files" in result["combat"]

    def test_group_node_has_no_pages(self):
        files = {"combat/actions": {"title": "Actions", "pages": [5, 7], "order": 0}}
        result = normalize_files(files)
        assert "pages" not in result["combat"]

    def test_empty_files(self):
        assert normalize_files({}) == {}

    def test_flat_leaf_then_nested_same_prefix_raises(self):
        files = {
            "combat": {"title": "Combat", "pages": [1, 2], "order": 0},
            "combat/actions": {"title": "Actions", "pages": [5, 7], "order": 1},
        }
        with pytest.raises(ValueError, match="combat"):
            normalize_files(files)

    def test_nested_then_flat_leaf_same_prefix_raises(self):
        files = {
            "combat/actions": {"title": "Actions", "pages": [5, 7], "order": 0},
            "combat": {"title": "Combat", "pages": [1, 2], "order": 1},
        }
        with pytest.raises(ValueError, match="combat"):
            normalize_files(files)


# ---------------------------------------------------------------------------
# resolve_config
# ---------------------------------------------------------------------------

class TestResolveConfig:
    def test_chapter_source_overrides_top_level(self):
        chapter = {"source": "chapter_source.md"}
        top = {"source": "top_source.md"}
        cfg = resolve_config("test", chapter, top)
        assert cfg["source"] == "chapter_source.md"

    def test_fallback_to_top_level_source(self):
        chapter = {}
        top = {"source": "top_source.md"}
        cfg = resolve_config("test", chapter, top)
        assert cfg["source"] == "top_source.md"

    def test_missing_source_raises(self):
        with pytest.raises(ValueError, match="test"):
            resolve_config("test", {}, {})

    def test_chapter_clean_patterns_override(self):
        chapter = {"source": "s.md", "clean_patterns": ["\\[footer\\]"]}
        top = {"clean_patterns": ["\\[header\\]"]}
        cfg = resolve_config("test", chapter, top)
        assert cfg["clean_patterns"] == ["\\[footer\\]"]

    def test_fallback_clean_patterns(self):
        chapter = {}
        top = {"source": "s.md", "clean_patterns": ["\\[header\\]"]}
        cfg = resolve_config("test", chapter, top)
        assert cfg["clean_patterns"] == ["\\[header\\]"]

    def test_default_clean_patterns_empty(self):
        chapter = {"source": "s.md"}
        cfg = resolve_config("test", chapter, {})
        assert cfg["clean_patterns"] == []

    def test_chapter_images_override(self):
        chapter = {"source": "s.md", "images": {"enabled": True}}
        top = {"images": {"enabled": False}}
        cfg = resolve_config("test", chapter, top)
        assert cfg["images"]["enabled"] is True

    def test_default_images_empty(self):
        chapter = {"source": "s.md"}
        cfg = resolve_config("test", chapter, {})
        assert cfg["images"] == {}


# ---------------------------------------------------------------------------
# write_meta_yml
# ---------------------------------------------------------------------------

class TestWriteMetaYml:
    def test_writes_label_and_order(self, tmp_path):
        entry = {"title": "Combat", "order": 1, "files": {}}
        write_meta_yml(tmp_path, entry)
        content = (tmp_path / "_meta.yml").read_text(encoding="utf-8")
        assert "label: Combat" in content
        assert "order: 1" in content

    def test_no_order_omits_order(self, tmp_path):
        entry = {"title": "Combat", "files": {}}
        write_meta_yml(tmp_path, entry)
        content = (tmp_path / "_meta.yml").read_text(encoding="utf-8")
        assert "label: Combat" in content
        assert "order" not in content

    def test_yaml_special_chars_quoted(self, tmp_path):
        entry = {"title": "Damage: Conditions & Recovery", "order": 2, "files": {}}
        write_meta_yml(tmp_path, entry)
        content = (tmp_path / "_meta.yml").read_text(encoding="utf-8")
        assert 'label: "Damage: Conditions & Recovery"' in content

    def test_overwrites_existing(self, tmp_path):
        (tmp_path / "_meta.yml").write_text("old content", encoding="utf-8")
        entry = {"title": "New", "order": 0, "files": {}}
        write_meta_yml(tmp_path, entry)
        content = (tmp_path / "_meta.yml").read_text(encoding="utf-8")
        assert "label: New" in content


class TestLoadManifestCached:
    def test_cache_respects_images_config_for_same_source(self):
        _manifest_cache.clear()

        _load_manifest_cached(
            "same_pages.md",
            {"enabled": False, "repeat_file_size_threshold": 1},
            Path("."),
        )
        _, _, second_policy = _load_manifest_cached(
            "same_pages.md",
            {"enabled": True, "repeat_file_size_threshold": 99},
            Path("."),
        )

        assert second_policy["repeat_file_size_threshold"] == 99


# ---------------------------------------------------------------------------
# group_images_by_page
# ---------------------------------------------------------------------------

_BG_POLICY = {
    "background_min_coverage_ratio": 0.6,
    "background_min_text_tokens": 80,
    "background_dominant_color_ratio_threshold": 0.85,
}
_BG_STATS = {1: {"text_tokens": 100, "char_count": 500}, 2: {"text_tokens": 100, "char_count": 500}}


def _bg_image(page: int, filename: str, **overrides) -> dict:
    """A background-candidate image (high coverage, page has plenty of text)."""
    base = {
        "page": page,
        "filename": filename,
        "coverage_ratio": 0.8,
        "page_width": 612,
        "page_height": 792,
        "width": 600,
        "height": 780,
        "x": 0,
        "y": 0,
    }
    base.update(overrides)
    return base


class TestGroupImagesByPage:
    def test_skips_repeated_file_sizes(self):
        images = [
            _bg_image(1, "a.png", file_size=1000),
            _bg_image(2, "b.png", file_size=1000),
        ]
        policy = {**_BG_POLICY, "repeat_file_size_threshold": 2}

        page_images, skipped = group_images_by_page(images, _BG_STATS, policy)

        assert page_images == {}
        assert skipped == 2

    def test_keeps_repeated_file_sizes_when_not_background(self):
        # Low text pages disqualify the background heuristic, so nothing is skipped.
        images = [
            _bg_image(1, "a.png", file_size=1000),
            _bg_image(2, "b.png", file_size=1000),
        ]
        policy = {**_BG_POLICY, "repeat_file_size_threshold": 2}
        stats = {1: {"text_tokens": 5, "char_count": 20}, 2: {"text_tokens": 5, "char_count": 20}}

        page_images, skipped = group_images_by_page(images, stats, policy)

        assert skipped == 0
        assert sorted(page_images) == [1, 2]

    def test_skips_repeated_visual_hashes(self):
        images = [
            _bg_image(1, "a.png", visual_hash="deadbeef"),
            _bg_image(2, "b.png", visual_hash="deadbeef"),
        ]
        policy = {**_BG_POLICY, "repeat_visual_threshold": 2}

        _, skipped = group_images_by_page(images, _BG_STATS, policy)

        assert skipped == 2

    def test_skips_flat_dominant_color_backgrounds(self):
        images = [_bg_image(1, "a.png", dominant_color_ratio=0.95)]

        page_images, skipped = group_images_by_page(images, _BG_STATS, _BG_POLICY)

        assert page_images == {}
        assert skipped == 1

    def test_orders_page_images_by_position_then_filename(self):
        images = [
            _bg_image(1, "c.png", y=100, x=10, coverage_ratio=0.1),
            _bg_image(1, "a.png", y=10, x=50, coverage_ratio=0.1),
            _bg_image(1, "b.png", y=10, x=5, coverage_ratio=0.1),
        ]

        page_images, skipped = group_images_by_page(images, _BG_STATS, _BG_POLICY)

        assert skipped == 0
        assert [img["filename"] for img in page_images[1]] == ["b.png", "a.png", "c.png"]


# ---------------------------------------------------------------------------
# split_chapters (output directory routing)
# ---------------------------------------------------------------------------

def _minimal_config(mode: str | None) -> dict:
    config = {
        "source": "source.md",
        "output_dir": "docs/src/content/docs",
        "chapters": {
            "rules": {
                "title": "規則",
                "order": 1,
                "files": {
                    "index": {"title": "規則總覽", "description": "test", "pages": [1, 1]},
                },
            }
        },
    }
    if mode is not None:
        config["mode"] = mode
    return config


class TestSplitChaptersOutputDir:
    def test_bilingual_mode_writes_to_bilingual_subdir(self, tmp_path):
        (tmp_path / "source.md").write_text(
            "<!-- page 1 -->\n# Test\n\nHello world.\n", encoding="utf-8"
        )

        split_chapters(_minimal_config("bilingual"), tmp_path)

        page = tmp_path / "docs" / "src" / "content" / "docs" / "bilingual" / "rules" / "index.md"
        assert page.exists()

    def test_default_mode_writes_to_output_dir(self, tmp_path):
        (tmp_path / "source.md").write_text(
            "<!-- page 1 -->\n# Test\n\nHello world.\n", encoding="utf-8"
        )

        split_chapters(_minimal_config(None), tmp_path)

        page = tmp_path / "docs" / "src" / "content" / "docs" / "rules" / "index.md"
        assert page.exists()
        assert not (tmp_path / "docs" / "src" / "content" / "docs" / "bilingual").exists()


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------


class TestParseArgs:
    def test_help_exits_cleanly(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", ["split_chapters.py", "--help"])
        with pytest.raises(SystemExit) as exc_info:
            parse_args()
        assert exc_info.value.code == 0
        assert "usage" in capsys.readouterr().out.lower()

    def test_no_args_defaults(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["split_chapters.py"])
        args = parse_args()
        assert args.init is False
        assert args.config is None

    def test_init_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["split_chapters.py", "--init"])
        args = parse_args()
        assert args.init is True

    def test_config_flag(self, monkeypatch, tmp_path):
        config_path = tmp_path / "custom.json"
        monkeypatch.setattr("sys.argv", ["split_chapters.py", "--config", str(config_path)])
        args = parse_args()
        assert args.config == config_path


class TestMainSideEffects:
    def test_help_does_not_touch_filesystem(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("sys.argv", ["split_chapters.py", "--help"])
        with pytest.raises(SystemExit):
            main()
        assert list(tmp_path.iterdir()) == []

    def test_missing_config_exits_with_error(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "sys.argv", ["split_chapters.py", "--config", str(tmp_path / "missing.json")]
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_init_calls_create_example_config(self, monkeypatch, tmp_path):
        import split_chapters as sc

        monkeypatch.setattr("sys.argv", ["split_chapters.py", "--init"])
        calls: list[Path] = []
        monkeypatch.setattr(sc, "create_example_config", lambda path: calls.append(path))

        main()

        assert len(calls) == 1
        assert calls[0].name == "chapters.json"

    def test_config_flag_used_when_provided(self, monkeypatch, tmp_path):
        import split_chapters as sc

        config_path = tmp_path / "custom.json"
        config_path.write_text('{"chapters": {}}', encoding="utf-8")
        monkeypatch.setattr("sys.argv", ["split_chapters.py", "--config", str(config_path)])

        loaded: list[Path] = []
        monkeypatch.setattr(sc, "load_config", lambda path: loaded.append(path) or {"chapters": {}})
        monkeypatch.setattr(sc, "split_chapters", lambda config, project_root: None)

        main()

        assert loaded == [config_path]
