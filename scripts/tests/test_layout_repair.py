"""Kedamono counterexamples for the seven published layout defect classes."""

from __future__ import annotations

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
from repair_layout import (
    format_english_spread_steps,
    format_spread_steps,
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


def test_spread_order_and_page_links_are_readable():
    body = "# 序幕\n\n第 158 頁　第 159 頁　第 160 頁\n\n日期、時間與參加者　邀請參加者。\n\n# 舞台演出\n\n推進故事　描述情況。\n\n# 謝幕\n\n重置暗獸　恢復可用。\n\n## 分享你的遊玩成果！"
    leaves = [("session-rules/prelude", {"title": "序幕", "pages": [166, 179]})]
    linked, count = repair_printed_refs(body, leaves, "/books/kedamono-opera", 8)
    formatted, steps = format_spread_steps(linked)
    assert count == 1 and steps >= 5
    assert "相關章節：[序幕](/books/kedamono-opera/session-rules/prelude/)" in formatted
    assert "- **日期、時間與參加者：** 邀請參加者。" in formatted
    assert "- **重置暗獸：** 恢復可用。" in formatted
    english, count = format_english_spread_steps("###### Prelude\n\nDate, Time, and People Recruit everyone.\n\n###### Share Your Play!")
    assert count == 3 and "- **Date, Time, and People:** Recruit everyone." in english


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
