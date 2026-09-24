"""Kedamono counterexamples for the seven published layout defect classes."""

from __future__ import annotations

import json
from pathlib import Path

from _layout_cleanup import (
    annotate_d66_pair_headings,
    d66_pair_pages,
    d66_pages,
    is_page_ornament,
    repair_d66_tables,
    strip_duplicate_title,
    strip_page_furniture,
    unique_placements,
)
from _paired_layout import PdfRole, _anchors, _corroborated_display_candidates, _format_translated_spread, _pair_candidates, _position, _restore_paired_glyph_lists, _set_label, _source_candidates, _tree_digest, layout_plan_applied, normal
from repair_layout import (
    layout_issues,
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


def test_applied_layout_plan_refuses_changed_content(tmp_path: Path):
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir(); target.mkdir()
    (source / "chapter.md").write_text("## Rule\n", encoding="utf-8")
    (target / "chapter.md").write_text("## 規則\n", encoding="utf-8")
    plan = tmp_path / "layout-repair.json"
    plan.write_text(json.dumps({"applied": {"source_sha256": _tree_digest(source),
                                             "target_sha256": _tree_digest(target)}}), encoding="utf-8")
    assert layout_plan_applied(plan, source, target)
    (target / "chapter.md").write_text("## 新規則\n", encoding="utf-8")
    try:
        layout_plan_applied(plan, source, target)
    except ValueError as error:
        assert "derive a new PDF layout plan" in str(error)
    else:
        raise AssertionError("changed content must require a fresh plan")
