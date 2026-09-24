"""Kedamono counterexamples for the seven published layout defect classes."""

from __future__ import annotations

import json
from pathlib import Path

from _layout_cleanup import (
    annotate_d66_pair_headings,
    chapter_fragment_classes,
    d66_pair_pages,
    d66_pages,
    is_edge_furniture,
    is_inner_edge_sliver,
    is_edge_sliver,
    is_edge_tab,
    is_page_ornament,
    layout_art_classes,
    repair_d66_tables,
    strip_chapter_cover,
    strip_chapter_covers,
    strip_duplicate_title,
    strip_page_furniture,
    unique_placements,
)
from split_chapters import group_images_by_page
from _paired_layout import PdfRole, _align_short_label_lists, _align_unpaired_h1, _anchors, _corroborated_display_candidates, _format_translated_spread, _pair_candidates, _position, _restore_paired_glyph_lists, _set_label, _source_candidates, _tree_digest, add_reviewed_decisions, normal, recorded_repair
from repair_layout import (
    layout_issues,
    main,
    repair,
    repair_staged_source,
    recover_pdf_headings,
    repair_english_toc,
    repair_printed_refs,
    repair_toc,
)


def test_repeated_pdf_xobject_placements_are_unique_and_rank_art_stays():
    icon = {"page": 71, "xref": 714, "x": 74, "y": 244, "width": 9.17, "height": 9.17}
    placements = [icon.copy() for _ in range(6)]
    placements += [{**icon, "y": 343}, {**icon, "y": 443}]
    assert len(unique_placements(placements)) == 3
    assert d66_pages([icon] * 36) == set()  # duplicate placements are not 36 dice
    footer = {"width": 75.48, "height": 35.7, "page_width": 420, "page_height": 595, "x": -9, "y": 553}
    rank = {**footer, "width": 149.6, "height": 47.68, "x": 226, "y": 303}
    assert is_page_ornament(footer, 117)
    assert not is_page_ornament(rank, 68)


def test_d66_legend_table_gains_text_indices_without_touching_prose():
    rows = [f"| |<br><br>|名稱{i}|說明{i}|" for i in range(12)]
    source = "|傳說表| | | |\n|---|---|---|---|\n" + "\n".join(rows) + "\n\n規則正文。"
    fixed, count = repair_d66_tables(source)
    assert count == 1
    assert "| 11–13 | 名稱0 | 說明0 |" in fixed
    assert "| 64–66 | 名稱11 | 說明11 |" in fixed
    assert fixed.endswith("規則正文。")


def test_pack_spread_die_images_become_heading_ranges():
    images = [{"page": page, "xref": page * 10 + die, "x": 22, "y": 200 + die * 16,
               "width": 13.58, "height": 13.58}
              for page in range(174, 180) for die in range(6)]
    assert d66_pair_pages(images) == {page: page - 173 for page in range(174, 180)}
    text, changed = annotate_d66_pair_headings("###### 最後遺願夥群\n\n故事。\n\n###### 旁觀者夥群", 1)
    assert changed == 2
    assert "最後遺願夥群（D66：11–13）" in text
    assert "旁觀者夥群（D66：14–16）" in text


def test_body_h1_duplicate_is_removed_but_real_subheading_remains():
    assert strip_duplicate_title("# 外典\n\n## 外典特技\n\n內容", "外典") == "## 外典特技\n\n內容"
    assert strip_duplicate_title("# merkaba\n\n正文", "Merkaba") == "正文"
    assert strip_duplicate_title("## 外典\n\n正文", "外典") == "正文"


def test_printed_toc_becomes_links_and_retains_chapter_blurb():
    chapters = {
        "basic-rules": {"title": "Basic Rules", "order": 1, "files": {"index": {"title": "基本規則", "pages": [1, 28]}}},
        "on-the-world": {"title": "On the World", "order": 2, "files": {"forest": {"title": "暗之森", "pages": [29, 50]}}},
    }
    leaves = [("basic-rules/index", chapters["basic-rules"]["files"]["index"]), ("on-the-world/forest", chapters["on-the-world"]["files"]["forest"])]
    body = "目錄\n\n基本規則\n\n第 2 頁\n\n入門章節。\n\n# 關於世界　第 21 頁\n\n世界觀說明。\n\n暗之森................................ 21\n\n基本規則\n\n正文。"
    fixed, labels, count = repair_toc(body, chapters, leaves, "/books/kedamono-opera")
    assert labels == {"basic-rules": "基本規則", "on-the-world": "關於世界"}
    assert "世界觀說明。" in fixed
    assert "[暗之森](/books/kedamono-opera/on-the-world/forest/)" in fixed
    assert "第 21 頁" not in fixed and "...." not in fixed
    assert count == 3


def test_staged_english_toc_uses_chapter_page_offset_and_preserves_blurbs():
    chapters = {
        "basic-rules": {"title": "Basic Rules", "order": 1, "files": {"index": {"title": "Basic Rules", "pages": [1, 28]}}},
        "on-the-world": {"title": "On the World", "order": 2, "files": {"forest": {"title": "Forest", "pages": [29, 50]}}},
    }
    leaves = [("basic-rules/index", chapters["basic-rules"]["files"]["index"]), ("on-the-world/forest", chapters["on-the-world"]["files"]["forest"])]
    body = "Table of Contents\n\nbasic rules\n\nPg. 2\n\nChapter blurb.\n\n###### on the World Pg. 21\n\nWorld blurb.\n\nForest........................ 21\n\n#### basiC rules\n\nBody."
    fixed, count = repair_english_toc(body, chapters, leaves, "/books/example")
    assert count == 3
    assert "Chapter blurb." in fixed and "World blurb." in fixed
    assert "- [Forest](/books/example/on-the-world/forest/)" in fixed
    assert "Pg. 21" not in fixed


def test_page_furniture_removal_keeps_table_values_and_numbered_steps():
    text = "a\n\n第 1 章\n\n6\n\n第 165 頁　第 158 頁\n\n- 6\n\n| 6 | 骰子 |\n\n內容。"
    fixed = strip_page_furniture(text)
    assert "第 1 章" not in fixed and "第 165 頁" not in fixed
    assert "- 6" in fixed and "| 6 | 骰子 |" in fixed


def test_pdf_proved_heading_only_not_short_body_line():
    text = "外典特技（Apocryphal Feats）\n\n外典特技與暗獸物種的特技不同。\n\n帶領序幕（Prelude）"
    fixed, count = recover_pdf_headings(text, ["Apocryphal Feats", "Running the Prelude"])
    assert count == 2
    assert "## 外典特技（Apocryphal Feats）" in fixed
    assert "\n外典特技與暗獸物種的特技不同。" in fixed


def test_pdf_proved_spread_order_and_page_links_are_readable():
    body = "第 158 頁　第 159 頁　第 160 頁"
    leaves = [("session-rules/prelude", {"title": "序幕", "pages": [166, 179]})]
    linked, count = repair_printed_refs(body, leaves, "/books/kedamono-opera", 8)
    assert count == 1 and "相關章節：[序幕](/books/kedamono-opera/session-rules/prelude/)" in linked
    lines = ["## 開始", "第一步　準備。", "## 選擇", "做出選擇。", "## 結束", "最後一步　收尾。"]
    entries = [{"target": title, "pdf": {"kind": "display", "size": 26, "page": page}}
               for title, page in (("開始", 1), ("結束", 2))]
    labels = [{"page": page} for page in (1, 1, 2)]
    assert _format_translated_spread(lines, entries, labels) == 3
    assert lines[1] == "- **第一步：** 準備。"
    assert lines[2] == "- **選擇：** 做出選擇。"
    assert lines[5] == "- **最後一步：** 收尾。"
    assert _format_translated_spread(lines, entries, labels) == 0


def test_layout_gate_flags_english_navigation_and_raw_artifacts(tmp_path: Path):
    docs = tmp_path / "docs/src/content/docs/basic-rules"
    docs.mkdir(parents=True)
    (tmp_path / "chapters.json").write_text('{"chapters":{"basic-rules":{"title":"Basic Rules"}}}', encoding="utf-8")
    (docs / "_meta.yml").write_text("label: Basic Rules\n", encoding="utf-8")
    (docs / "index.md").write_text("---\ntitle: 基本規則\n---\n\n# 基本規則\n\n6\n\n# 關於世界　第 21 頁\n", encoding="utf-8")
    issues = layout_issues(tmp_path)
    assert any("untranslated section label" in issue for issue in issues)
    assert any("body H1/H2 duplicates" in issue for issue in issues)
    assert any("printed furniture" in issue for issue in issues)
    assert any("untranslated sidebar label" in issue for issue in issues)


def test_layout_gate_flags_repeated_lower_level_page_titles(tmp_path: Path):
    docs = tmp_path / "docs/src/content/docs/species"
    docs.mkdir(parents=True)
    (tmp_path / "chapters.json").write_text('{"chapters":{"species":{"title":"物種"}}}', encoding="utf-8")
    (docs / "sphinx.md").write_text("---\ntitle: 斯芬克斯\n---\n\n## 斯芬克斯\n\n 故事。\n\n### 斯芬克斯\n", encoding="utf-8")
    issues = layout_issues(tmp_path)
    assert any("repeated body title headings" in issue for issue in issues)
    assert any("PDF bullet marker remains" in issue for issue in issues)


def test_pdf_heading_roles_match_source_without_a_book_table():
    source = ["---", "title: Forest", "---", "", " Forest Entrance", "", "A passage leads inside."]
    roles = [PdfRole("Forest Entrance", 7, 11.0, 40.5, 115.0, "heading")]
    candidates = _source_candidates(source, roles)
    assert [(item["text"], item["page"], item["kind"]) for item in candidates] == [
        ("Forest Entrance", 7, "heading")
    ]


def test_shared_media_anchors_translation_position():
    source = ["Intro", "![map](page007_img01.png)", "Forest Entrance", "Rule text"]
    target = ["前言", "![map](page007_img01.png)", "", "森林入口", "規則文字"]
    points = _anchors(source, target)
    assert (1, 1) in points
    assert 2 < _position(2, points) < 4


def test_structural_alignment_uses_glossary_and_order():
    source = [
        {"text": "Forest Entrance", "expected": 2.1, "page_title": "森林", "block": 2},
        {"text": "Dark Forest", "expected": 5.2, "page_title": "森林", "block": 5},
    ]
    target = [
        {"text": "森林入口", "heading": False, "block": 2},
        {"text": "附近的道路", "heading": False, "block": 3},
        {"text": "暗之森", "heading": True, "block": 5},
    ]
    pairs, missing = _pair_candidates(source, target, [(normal("Dark Forest"), "暗之森")])
    assert pairs == [(0, 0), (1, 2)] and missing == []


def test_heading_update_uses_block_position_for_repeated_labels():
    lines = ["第一段。", "", "難度", "", "第二段。", "", "難度"]
    assert _set_label(lines, "難度", 3, 3)
    assert lines[2] == "難度" and lines[6] == "### 難度"


def test_plain_pdf_display_needs_aligned_glossary_heading():
    roles = [PdfRole("Opera", 17, 20, 40, 100, "display")]
    source = ["Intro", "Opera", "Rules"]
    target = ["前言", "### 歌劇", "規則"]
    assert _corroborated_display_candidates(source, target, roles, [(0, 0), (3, 3)],
                                            [(normal("Opera"), "歌劇")], []) == [
        {"block": 1, "text": "Opera", "page": 17, "size": 20, "kind": "display", "x": 40, "y": 100}
    ]
    assert not _corroborated_display_candidates(source, target, roles, [(0, 0), (3, 3)], [], [])


def test_paired_bullet_recovery_preserves_paragraph_boundaries():
    source = ["介紹。", "", " First item.  Second item.", "", "結語。"]
    target = ["介紹。", "", "- 第一項。", "", "- 第二項。", "", "結語。"]
    assert _restore_paired_glyph_lists(source, target) == 2
    assert source == ["介紹。", "", "- First item.", "- Second item.", "", "結語。"]
    assert target == ["介紹。", "", "- 第一項。", "", "- 第二項。", "", "結語。"]


def test_recorded_repair_marks_the_book_repaired_even_after_edits(tmp_path: Path):
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir(); target.mkdir()
    (source / "chapter.md").write_text("## Rule\n", encoding="utf-8")
    (target / "chapter.md").write_text("## 規則\n", encoding="utf-8")
    plan = tmp_path / "layout-repair.json"
    assert recorded_repair(plan, target, source) is None
    plan.write_text(json.dumps({"chapters": {}}), encoding="utf-8")
    assert recorded_repair(plan, target, source) is None
    plan.write_text(json.dumps({"applied": {"source_sha256": _tree_digest(source),
                                             "target_sha256": _tree_digest(target)}}), encoding="utf-8")
    assert "unchanged" in recorded_repair(plan, target, source)
    (target / "chapter.md").write_text("## 新規則\n", encoding="utf-8")
    reason = recorded_repair(plan, target, source)
    assert "translated Markdown changed" in reason and "--reapply" in reason
    assert "staged English source" not in reason


def test_text_pair_fixes_orphan_label_and_prose_h1_without_changing_words():
    source = ["### Scenario", "", "Description.", "", "- Player", "", "A person plays."]
    target = ["### 劇本", "", "說明。", "", "玩家", "", "玩家參與。"]
    assert _align_short_label_lists(source, target, Path("source.md"), Path("target.md")) == 1
    assert source[4] == "### Player" and target[4] == "### 玩家"
    source = ["- A storm changes the land."]
    target = ["# 風暴改變地貌。"]
    assert _align_unpaired_h1(source, target, Path("source.md"), Path("target.md")) == 1
    assert target == ["- 風暴改變地貌。"]


def test_review_decisions_accept_only_explicit_residual_lines(tmp_path: Path):
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir(); target.mkdir()
    (source / "chapter.md").write_text("## Section\n\nBody.\n", encoding="utf-8")
    (target / "chapter.md").write_text("## 章節\n\n### Extra\n", encoding="utf-8")
    plan_path = tmp_path / "layout-repair.json"
    plan_path.write_text(json.dumps({"chapters": {"chapter.md": []},
                                     "targets": {"chapter.md": "chapter.md"}}), encoding="utf-8")
    decisions_path = tmp_path / "decisions.json"
    decisions_path.write_text(json.dumps([{"side": "target", "chapter": "chapter.md", "line": 3,
                                           "text": "Extra", "marker": "", "pdf_page": 7,
                                           "reason": "The PDF cannot distinguish this small label from body text."}]),
                              encoding="utf-8")
    assert add_reviewed_decisions(plan_path, decisions_path, source, target) == {"reviewed_overrides": 1}
    assert (target / "chapter.md").read_text(encoding="utf-8") == "## 章節\n\nExtra\n"
    record = json.loads(plan_path.read_text(encoding="utf-8"))["reviewed"]["target"]["chapter.md"][0]
    assert record["pdf_page"] == 7 and record["reason"].startswith("The PDF")


PAGE = {"page_width": 419.53, "page_height": 595.28}
# Published bleed/frame strips: (x, y, width, height) in PDF points.
EDGE_SLIVERS = [
    (-1.3, -1.5, 1.3, 532.7), (-1.2, -1.5, 1.9, 407.8), (-1.1, 40.9, 2.2, 307.9),
    (-1.1, -1.1, 2.3, 108.0), (-1.1, -1.0, 2.3, 87.0), (-1.4, -1.1, 2.5, 370.5),
    (-1.1, 24.4, 2.6, 312.2), (-1.1, 57.5, 3.7, 278.1), (-1.2, -1.1, 4.0, 108.0),
    (-1.3, -1.1, 4.4, 398.6), (-1.4, -1.6, 4.4, 373.6), (-1.4, -1.3, 4.4, 342.5),
    # Borderline: a 21 pt crop of spread art bleeding past the gutter (4.9% wide, 13.7:1).
    (-1.1, -1.1, 20.7, 283.7),
    # Widest published crop: 28 pt of spread art cut at the edge (6.7% wide, 10.8:1).
    (-1.0, 287.1, 28.0, 301.9),
]
# Published thumb-index tabs and banner flags on the left edge (5.6-9.1% wide, 6.0% tall).
EDGE_TABS = [
    (0.4, 51.9, 27.2, 35.7), (-1.0, 50.6, 37.6, 35.7), (-0.0, 86.3, 29.4, 35.7),
    (0.7, 227.7, 34.1, 35.7), (-0.3, 298.5, 27.3, 35.7), (-1.1, 45.0, 28.0, 35.7),
    (-1.0, 201.8, 23.5, 35.7), (-1.1, 336.9, 28.0, 35.7), (-1.0, 179.5, 36.3, 35.7),
    (-1.1, 416.3, 28.0, 35.7), (-1.0, 45.0, 38.0, 35.7), (-1.0, 62.9, 23.2, 35.7),
    (0.7, 86.5, 23.5, 35.7),
]
# Real art: inline symbols, in-page rules, ordinary illustrations, column art
# standing on the right edge (10.2% wide), and full-bleed chapter-cover art.
KEPT_ART = [
    (194.2, 243.2, 8.8, 8.8), (170.0, 194.6, 13.2, 9.9), (93.3, 349.8, 213.8, 10.4),
    (203.9, 517.3, 19.7, 19.2), (48.96, 56.44, 321.92, 143.3), (378.0, 135.0, 43.0, 461.4),
    (-10.0, -10.0, 430.0, 614.0),
]


def _placement(x, y, width, height, **extra):
    return {"x": x, "y": y, "width": width, "height": height, **PAGE, **extra}


def test_edge_slivers_are_thin_long_strips_touching_a_page_edge():
    assert all(is_edge_sliver(_placement(*box)) for box in EDGE_SLIVERS)
    assert not any(is_edge_sliver(_placement(*box)) for box in KEPT_ART)
    # The same rule applies to the right, top, and bottom edges.
    assert is_edge_sliver(_placement(PAGE["page_width"] - 2, 30, 3, 300))
    assert is_edge_sliver(_placement(20, -1, 350, 4))
    assert is_edge_sliver(_placement(20, PAGE["page_height"] - 3, 350, 4))
    assert not is_edge_sliver(_placement(20, 300, 350, 4))


def test_edge_tabs_are_small_marks_standing_on_a_side_edge():
    assert all(is_edge_tab(_placement(*box)) for box in EDGE_TABS)
    assert not any(is_edge_furniture(_placement(*box)) for box in KEPT_ART)
    assert is_edge_tab(_placement(PAGE["page_width"] - 30, 200, 31, 35.7))
    # The same mark inside the page is content, and a taller edge block is art.
    assert not is_edge_tab(_placement(30, 200, 28, 35.7))
    assert not is_edge_tab(_placement(-1, 200, 28, 60))


def test_chapter_split_skips_edge_tabs():
    tab = _placement(-1.0, 62.9, 23.2, 35.7, page=3, filename="tab.png")
    cover = _placement(-10.0, -10.0, 430.0, 614.0, page=3, filename="cover.png")
    allowed, skipped = group_images_by_page([tab, cover], {}, {})
    assert [image["filename"] for image in allowed[3]] == ["cover.png"]
    assert skipped == 1


def test_chapter_split_skips_edge_slivers_but_keeps_symbols():
    sliver = _placement(-1.3, -1.1, 4.4, 398.6, page=3, filename="sliver.png")
    symbol = _placement(194.2, 243.2, 8.8, 8.8, page=3, filename="symbol.png")
    allowed, skipped = group_images_by_page([sliver, symbol], {}, {})
    assert [image["filename"] for image in allowed[3]] == ["symbol.png"]
    assert skipped == 1


def _sliver_project(tmp_path: Path) -> Path:
    docs = tmp_path / "docs/src/content/docs/rules"
    docs.mkdir(parents=True)
    (tmp_path / "chapters.json").write_text(json.dumps({
        "source": "data/markdown/Book_pages.md",
        "chapters": {"rules": {"title": "規則", "files": {"index": {"title": "規則", "pages": [1, 2]}}}},
    }), encoding="utf-8")
    images = tmp_path / "data/markdown/images/Book"
    images.mkdir(parents=True)
    (images / "manifest.json").write_text(json.dumps({"images": [
        _placement(-1.3, -1.1, 4.4, 398.6, page=1, filename="page001_sliver.png"),
        _placement(194.2, 243.2, 8.8, 8.8, page=1, filename="page001_symbol.png"),
    ]}), encoding="utf-8")
    (docs / "index.md").write_text(
        "---\ntitle: 規則\n---\n\n正文。\n\n![](../../../assets/page001_sliver.png)\n\n"
        "![](../../../assets/page001_symbol.png)\n\n| |\n|---|\n\n|階級|骰子| |\n|---|---|---|\n",
        encoding="utf-8")
    return tmp_path


def test_layout_gate_flags_edge_slivers_and_empty_tables(tmp_path: Path):
    issues = layout_issues(_sliver_project(tmp_path))
    assert "docs/src/content/docs/rules/index.md: layout image page001_sliver.png" in issues
    assert "docs/src/content/docs/rules/index.md:11: empty table" in issues
    assert not any("page001_symbol.png" in issue for issue in issues)
    assert sum("empty table" in issue for issue in issues) == 1


def test_repair_drops_edge_slivers_after_paired_repair_was_applied(tmp_path: Path):
    project = _sliver_project(tmp_path)
    docs = project / "docs/src/content/docs"
    plan_path = project / "data/layout-repair.json"
    plan_path.write_text(json.dumps({"applied": {"source_sha256": "s", "target_sha256": _tree_digest(docs)}}),
                         encoding="utf-8")
    result = repair(project)
    assert result["already_applied"] == 1 and "unchanged" in result["reason"]
    assert result["edge_slivers_removed"] == 1
    assert result["edge_sliver_files"] == ["rules/index.md: page001_sliver.png"]
    text = (docs / "rules/index.md").read_text(encoding="utf-8")
    assert "page001_sliver.png" not in text and "page001_symbol.png" in text
    assert "正文。\n\n![](../../../assets/page001_symbol.png)" in text
    assert json.loads(plan_path.read_text(encoding="utf-8"))["applied"]["target_sha256"] == _tree_digest(docs)
    assert "edge_slivers_removed" not in repair(project)


def _edited_after_repair(tmp_path: Path) -> Path:
    """A repaired project whose chapter later gained a hand-written body title."""
    project = _sliver_project(tmp_path)
    docs = project / "docs/src/content/docs"
    (project / "data/layout-repair.json").write_text(json.dumps(
        {"applied": {"source_sha256": "s", "target_sha256": _tree_digest(docs)}}), encoding="utf-8")
    chapter = docs / "rules/index.md"
    chapter.write_text(chapter.read_text(encoding="utf-8").replace("正文。", "# 規則\n\n正文。"), encoding="utf-8")
    return project


def test_first_time_repair_runs_the_full_transform(tmp_path: Path):
    project = _sliver_project(tmp_path)
    chapter = project / "docs/src/content/docs/rules/index.md"
    chapter.write_text(chapter.read_text(encoding="utf-8").replace("正文。", "# 規則\n\n正文。"), encoding="utf-8")
    result = repair(project)
    assert "skipped" not in result
    assert result["duplicate_titles_removed"] and result["edge_slivers_removed"] == 1
    assert "# 規則" not in chapter.read_text(encoding="utf-8")


def test_repair_keeps_edits_made_after_the_paired_repair(tmp_path: Path):
    project = _edited_after_repair(tmp_path)
    docs = project / "docs/src/content/docs"
    result = repair(project)
    assert result["skipped"].startswith("translated layout repair")
    assert "translated Markdown changed" in result["reason"] and "--reapply" in result["reason"]
    assert result["edge_sliver_files"] == ["rules/index.md: page001_sliver.png"]
    text = (docs / "rules/index.md").read_text(encoding="utf-8")
    assert "# 規則\n\n正文。" in text and "page001_sliver.png" not in text
    assert not (docs / "rules/_meta.yml").exists()
    before = text
    second = repair(project)
    assert "unchanged" in second["reason"] and "edge_slivers_removed" not in second
    assert (docs / "rules/index.md").read_text(encoding="utf-8") == before


def test_paired_steps_skip_edited_books_and_leave_files_alone(tmp_path: Path, monkeypatch, capsys):
    project = _edited_after_repair(tmp_path)
    source = tmp_path / "source"
    (source / "rules").mkdir(parents=True)
    (source / "rules/index.md").write_text("## Rules\n", encoding="utf-8")
    plan_before = (project / "data/layout-repair.json").read_text(encoding="utf-8")
    result = repair_staged_source(project, source)
    assert result["skipped"] == "paired layout repair"
    assert "translated Markdown and staged English source changed" in result["reason"]
    monkeypatch.setattr("sys.argv", ["repair_layout.py", "--project-root", str(project),
                                     "--staged-source", str(source), "--derive-layout-plan"])
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["skipped"] == "layout plan derivation"
    assert (project / "data/layout-repair.json").read_text(encoding="utf-8") == plan_before
    assert (source / "rules/index.md").read_text(encoding="utf-8") == "## Rules\n"


def test_reapply_reruns_the_full_repair_over_later_edits(tmp_path: Path):
    project = _edited_after_repair(tmp_path)
    result = repair(project, reapply=True)
    assert "skipped" not in result and result["duplicate_titles_removed"]
    assert "# 規則" not in (project / "docs/src/content/docs/rules/index.md").read_text(encoding="utf-8")


def test_repair_drops_edge_tabs_on_an_edited_project(tmp_path: Path):
    project = _edited_after_repair(tmp_path)
    docs = project / "docs/src/content/docs"
    manifest = project / "data/markdown/images/Book/manifest.json"
    images = json.loads(manifest.read_text(encoding="utf-8"))["images"]
    images.append(_placement(-1.0, 62.9, 23.2, 35.7, page=1, filename="page001_tab.png"))
    manifest.write_text(json.dumps({"images": images}), encoding="utf-8")
    chapter = docs / "rules/index.md"
    chapter.write_text(chapter.read_text(encoding="utf-8").replace(
        "正文。", "![](../../../assets/page001_tab.png)\n\n正文。"), encoding="utf-8")
    assert "docs/src/content/docs/rules/index.md: layout image page001_tab.png" in layout_issues(project)
    result = repair(project)
    assert result["edge_sliver_files"] == ["rules/index.md: page001_tab.png", "rules/index.md: page001_sliver.png"]
    text = chapter.read_text(encoding="utf-8")
    assert "# 規則\n\n正文。" in text and "page001_tab.png" not in text and "page001_symbol.png" in text
    assert not any("page001_tab.png" in issue for issue in layout_issues(project))


def _page_art_samples() -> list[dict]:
    return json.loads((Path(__file__).parent / "fixtures/kedamono_page_art.json").read_text())


def _fragment_samples() -> list[dict]:
    return json.loads((Path(__file__).parent / "fixtures/kedamono_image_fragments.json").read_text())


def test_fragment_samples_keep_single_symbols_and_pale_art():
    samples = _fragment_samples()
    classes = layout_art_classes(samples)
    name = lambda prefix: next(image["filename"] for image in samples if image["filename"].startswith(prefix))
    for prefix in ("page018_img02", "page019_img01", "page019_img02"):
        assert classes[name(prefix)] == "paper_texture"
    for prefix in ("page239_img00", "page242_img00", "page244_img00"):
        assert classes[name(prefix)] == "small_binary_fragment"
    assert classes[name("page201_img01")] == "repeated_tiny_fragment"
    for prefix in ("page239_img01", "page244_img03"):
        assert classes[name(prefix)] == "repeated_small_mark"
    assert all(classes[image["filename"]] == "repeated_thin_rule" for image in samples
               if image["filename"].startswith("page251_img04"))
    for prefix in ("page021_img00", "page021_img01", "page173_img00", "page024_img01"):
        assert name(prefix) not in classes
    centered = {**next(image for image in samples if image["filename"].startswith("page239_img01")),
                "filename": "centered-icon.png", "x": 180, "file_size": 15000}
    assert centered["filename"] not in layout_art_classes(samples + [centered])


def test_inner_edge_crop_uses_pixel_evidence():
    sliver = next(image for image in _fragment_samples() if image["filename"].startswith("page132_img00"))
    assert is_inner_edge_sliver(sliver)
    assert is_inner_edge_sliver({**sliver, "x": sliver["x"] - 15})
    assert not is_inner_edge_sliver({**sliver, "file_size": 20000})
    assert not is_inner_edge_sliver({**sliver, "x": 180})


def test_repeated_panel_fragments_need_multiple_pieces_in_output_page():
    samples = _fragment_samples()
    classes = chapter_fragment_classes(samples, 63, 65)
    assert {name.split("_img")[0] for name in classes} == {"page063", "page065"}
    assert set(classes.values()) == {"repeated_panel_piece"}
    assert chapter_fragment_classes(samples, 1, 28) == {}
    single_page = [image for image in samples if image["filename"].startswith("page156_img01")]
    assert len(chapter_fragment_classes(single_page, 156, 156)) == 4


def test_reused_chapter_art_matches_resized_crop_but_keeps_distinct_art(tmp_path: Path):
    import cv2
    import numpy as np

    rng = np.random.default_rng(31)
    first = np.full((500, 500), 255, dtype=np.uint8)
    for _ in range(500):
        x, y = rng.integers(20, 480, size=2)
        cv2.circle(first, (int(x), int(y)), int(rng.integers(3, 16)),
                   int(rng.integers(0, 180)), int(rng.integers(1, 3)))
    crop = cv2.resize(first, (750, 750))[20:730, 20:730]
    other = rng.integers(0, 256, (500, 500), dtype=np.uint8)
    images = []
    for page, pixels in ((1, first), (2, crop), (3, other)):
        name = f"art-{page}.png"
        cv2.imwrite(str(tmp_path / name), pixels)
        images.append({"page": page, "filename": name, "coverage_ratio": 0.2,
                       "file_size": (tmp_path / name).stat().st_size,
                       "gray_mean": 127, "pixel_sha256": str(page)})
    classes = chapter_fragment_classes(images, 1, 3, tmp_path)
    assert classes == {"art-2.png": "reused_chapter_art"}
    assert chapter_fragment_classes(images, 2, 3, tmp_path) == {}
    late_copy = {**images[0], "page": 8, "filename": "art-8.png"}
    assert "art-8.png" not in chapter_fragment_classes(images + [late_copy], 1, 8, tmp_path)


def test_real_page_art_samples_separate_print_art_from_illustrations():
    images = _page_art_samples()
    classes = layout_art_classes(images)
    by_prefix = {image["filename"].split("_occ")[0]: image["filename"] for image in images
                 if not image["filename"].startswith("page172_img03")}
    for prefix in ("page019_img03", "page073_img10", "page073_img11", "page077_img00",
                   "page094_img03", "page094_img04", "page170_img00", "page172_img00"):
        assert classes[by_prefix[prefix]] == "paper_texture", prefix
    for prefix in ("page018_img00", "page094_img00", "page206_img00"):
        assert classes[by_prefix[prefix]] == "ink_mask", prefix
    for prefix in ("page002_img01", "page003_img03", "page056_img00", "page162_img00",
                   "page218_img00", "page236_img02", "page256_img00", "page262_img01"):
        assert classes[by_prefix[prefix]] == "repeated_art", prefix
    assert sum(kind == "repeated_flourish" for kind in classes.values()) == 2
    for prefix in ("page001_img03", "page018_img01", "page029_img00", "page094_img01",
                   "page094_img02", "page260_img01", "page261_img00"):
        assert by_prefix[prefix] not in classes, prefix


def test_pixel_art_line_cleanup_preserves_edited_prose_and_check_reports_residue(tmp_path: Path):
    project = _sliver_project(tmp_path)
    images = _page_art_samples()
    manifest = project / "data/markdown/images/Book/manifest.json"
    manifest.write_text(json.dumps({"images": images}), encoding="utf-8")
    docs = project / "docs/src/content/docs"
    chapter = docs / "rules/index.md"
    by_prefix = {image["filename"].split("_occ")[0]: image["filename"] for image in images
                 if not image["filename"].startswith("page172_img03")}
    lines = ["---", "title: 規則", "---", "", "編輯後的正文。", ""]
    for prefix in ("page001_img03", "page002_img01", "page094_img00", "page094_img01",
                   "page094_img03", "page172_img00", "page260_img01"):
        lines.extend((f"![](../../../assets/{by_prefix[prefix]})", ""))
    for image in images:
        if image["filename"].startswith("page172_img03"):
            lines.extend((f"![](../../../assets/{image['filename']})", ""))
    chapter.write_text("\n".join(lines), encoding="utf-8")
    plan = project / "data/layout-repair.json"
    plan.write_text(json.dumps({"applied": {"source_sha256": "s", "target_sha256": "prior"}}), encoding="utf-8")
    pending = layout_issues(project)
    for prefix in ("page002_img01", "page094_img00", "page094_img03",
                   "page172_img00", "page172_img03"):
        assert any(prefix in issue for issue in pending), prefix
    result = repair(project)
    assert result["already_applied"] == 1
    assert result["layout_art_removed"] == 6
    assert set(result["layout_art_files"]) == {"paper_texture", "ink_mask", "repeated_art", "repeated_flourish"}
    text = chapter.read_text(encoding="utf-8")
    assert "編輯後的正文。" in text
    for prefix in ("page001_img03", "page094_img01", "page260_img01"):
        assert by_prefix[prefix] in text
    assert not any("layout image" in issue for issue in layout_issues(project))
    assert "layout_art_removed" not in repair(project)


COVER_PAGE = "Chapter 2\n\n###### on The World\n\nCHAPTER COVER"


def test_chapter_cover_page_text_is_dropped_whole():
    assert strip_chapter_cover(COVER_PAGE) == ""
    assert strip_chapter_cover("index\n\nCHAPTER COVER") == ""
    # A body page that happens to hold the label keeps its prose.
    body = "CHAPTER COVER\n\n" + "A long rules paragraph that explains how scenes open and close. " * 2
    assert strip_chapter_cover(body) == body
    assert strip_chapter_cover("###### on The World") == "###### on The World"


def test_chapter_covers_are_emptied_across_marked_pages():
    text = f"<!-- PAGE 28 -->\n\nEnd.\n\n<!-- PAGE 29 -->\n\n{COVER_PAGE}\n\n<!-- PAGE 30 -->\n\n###### Next\n"
    cleaned, removed = strip_chapter_covers(text)
    assert removed == [COVER_PAGE]
    assert cleaned == "<!-- PAGE 28 -->\n\nEnd.\n\n<!-- PAGE 29 -->\n\n<!-- PAGE 30 -->\n\n###### Next\n"
    assert strip_chapter_covers(cleaned) == (cleaned, [])


def test_chapter_split_drops_cover_block_but_keeps_cover_art(tmp_path: Path):
    from split_chapters import build_section_content, extract_pages

    pages = extract_pages(f"<!-- PAGE 29 -->\n\n{COVER_PAGE}\n\n<!-- PAGE 30 -->\n\nA kedamono is a beast.\n")
    art = tmp_path / "data/markdown/images/Book/page029_art.png"
    art.parent.mkdir(parents=True)
    art.write_bytes(b"png")
    cover = _placement(-10.0, -10.0, 430.0, 614.0, page=29, filename="page029_art.png",
                       path="images/Book/page029_art.png")
    output = tmp_path / "docs/src/content/docs/on-the-world/definition.md"
    content, copied = build_section_content(pages, 29, 30, [], {29: [cover]}, output, tmp_path,
                                            tmp_path / "docs/src/assets/extracted", "Book")
    assert copied == 1
    assert content.startswith("![") and "page029_art.png" in content
    assert "on The World" not in content and "Chapter 2" not in content and "COVER" not in content
    assert content.endswith("A kedamono is a beast.")


def test_layout_gate_flags_first_heading_repeating_the_part_label(tmp_path: Path):
    docs = tmp_path / "docs/src/content/docs/on-the-world"
    docs.mkdir(parents=True)
    (tmp_path / "chapters.json").write_text(json.dumps({"chapters": {"on-the-world": {
        "title": "On the World", "translated_title": "關於世界",
        "files": {"definition": {"title": "定義", "pages": [29, 38]},
                  "forest": {"title": "森林", "pages": [39, 50]}}}}}), encoding="utf-8")
    (docs / "_meta.yml").write_text("label: 世界觀\norder: 2\n", encoding="utf-8")
    (docs / "definition.md").write_text("---\ntitle: 定義\n---\n\n## 關於世界\n\n正文。\n\n## 分類\n", encoding="utf-8")
    (docs / "forest.md").write_text("---\ntitle: 森林\n---\n\n## 世界觀\n\n正文。\n", encoding="utf-8")
    (docs / "clean.md").write_text("---\ntitle: 乾淨\n---\n\n## 分類\n\n關於世界。\n\n## 關於世界\n", encoding="utf-8")
    issues = [issue for issue in layout_issues(tmp_path) if "part label" in issue]
    assert issues == [
        "docs/src/content/docs/on-the-world/definition.md: first heading repeats chapter part label: 關於世界",
        "docs/src/content/docs/on-the-world/forest.md: first heading repeats chapter part label: 世界觀",
    ]
