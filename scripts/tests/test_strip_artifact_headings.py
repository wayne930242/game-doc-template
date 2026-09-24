from __future__ import annotations

from strip_artifact_headings import main

CHAPTER = "---\ntitle: 索引\n---\n\n## 索引\n\n內文。\n\n###### iz\n"


def test_removes_artifact_headings_in_directory(tmp_path, capsys):
    chapter = tmp_path / "docs" / "index.md"
    chapter.parent.mkdir()
    chapter.write_text(CHAPTER, encoding="utf-8")
    untouched = tmp_path / "docs" / "cards.md"
    untouched.write_text("###### soar\n\n你可以自由飛翔。\n", encoding="utf-8")

    assert main([str(tmp_path / "docs")]) == 0

    assert chapter.read_text(encoding="utf-8") == "---\ntitle: 索引\n---\n\n## 索引\n\n內文。\n"
    assert untouched.read_text(encoding="utf-8") == "###### soar\n\n你可以自由飛翔。\n"
    assert "共 1 個裝飾標題已移除" in capsys.readouterr().out


def test_dry_run_leaves_file(tmp_path):
    chapter = tmp_path / "index.md"
    chapter.write_text(CHAPTER, encoding="utf-8")

    assert main([str(chapter), "--dry-run"]) == 0

    assert chapter.read_text(encoding="utf-8") == CHAPTER


def test_missing_path_fails(tmp_path):
    assert main([str(tmp_path / "missing.md")]) == 1
