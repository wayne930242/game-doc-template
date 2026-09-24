from __future__ import annotations

import json

from rename_chapter import main
from translation_context import build_context, context_status, current_fingerprints

DOCS = "docs/src/content/docs"


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def make_project(root):
    (root / "data/markdown").mkdir(parents=True)
    (root / "data/markdown/book_pages.md").write_text("<!-- PAGE 1 -->\n\nRules\n", encoding="utf-8")
    write_json(
        root / "chapters.json",
        {
            "source": "data/markdown/book_pages.md",
            "output_dir": DOCS,
            "chapters": {
                "rules": {"title": "規則", "order": 1, "files": {"index": {"title": "規則", "pages": [1, 1]}}},
                "index": {"title": "索引", "order": 2, "files": {"index": {"title": "索引", "pages": [1, 1]}}},
            },
        },
    )
    write_json(root / "glossary.json", {"terms": {}})
    write_json(root / "style-decisions.json", {"deployment": {"target": "blog", "base_path": "/books/demo"}})
    chapters = []
    for slug in ("rules", "index"):
        file_path = f"{DOCS}/{slug}/index.md"
        chapters.append(
            {
                "id": f"docs-src-content-docs-{slug}-index",
                "title": slug,
                "file": file_path,
                "source_pages": "1-1",
                "status": "completed",
                "source": "data/markdown/book_pages.md",
            }
        )
    write_json(root / "data/translation-progress.json", {"chapters": chapters})
    rules = root / DOCS / "rules/index.md"
    rules.parent.mkdir(parents=True)
    rules.write_text(
        "---\ntitle: 規則\n---\n\n見[索引](/books/demo/index/#a)與<a href=\"/index/\">索引</a>，"
        "但[其他](/books/demo/index-of-things/)與[規則](/books/demo/rules/index/)不變。\n",
        encoding="utf-8",
    )
    index = root / DOCS / "index/index.md"
    index.parent.mkdir(parents=True)
    index.write_text("---\ntitle: 索引\n---\n\n回到[規則](/books/demo/rules/)。\n", encoding="utf-8")
    (root / DOCS / "index/_meta.yml").write_text("label: 索引\n", encoding="utf-8")
    draft = root / f".state/translate/drafts/{DOCS}/index/index.md"
    draft.parent.mkdir(parents=True)
    draft.write_text("草稿\n", encoding="utf-8")
    write_json(
        root / ".state/translate/draft-manifest.json",
        {
            "entries": {
                f"{DOCS}/index/index.md": {
                    "source": f"{DOCS}/index/index.md",
                    "draft": f".state/translate/drafts/{DOCS}/index/index.md",
                    "updated": "2026-09-24T00:00:00+00:00",
                }
            }
        },
    )
    write_json(root / "data/translation-context.json", build_context(root))


def test_renames_index_chapter_everywhere(tmp_path):
    make_project(tmp_path)

    assert main(["--from", "index", "--to", "book-index"], project_root=tmp_path) == 0

    new_file = f"{DOCS}/book-index/index.md"
    assert not (tmp_path / DOCS / "index").exists()
    assert (tmp_path / new_file).read_text(encoding="utf-8").endswith("回到[規則](/books/demo/rules/)。\n")
    assert (tmp_path / DOCS / "book-index/_meta.yml").exists()

    config = json.loads((tmp_path / "chapters.json").read_text(encoding="utf-8"))
    assert list(config["chapters"]) == ["rules", "book-index"]

    progress = json.loads((tmp_path / "data/translation-progress.json").read_text(encoding="utf-8"))
    assert progress["chapters"][1]["file"] == new_file
    assert progress["chapters"][1]["id"] == "docs-src-content-docs-book-index-index"
    assert progress["chapters"][0]["file"] == f"{DOCS}/rules/index.md"

    manifest = json.loads((tmp_path / ".state/translate/draft-manifest.json").read_text(encoding="utf-8"))
    entry = manifest["entries"][new_file]
    assert entry["source"] == new_file
    assert entry["draft"] == f".state/translate/drafts/{new_file}"
    assert (tmp_path / entry["draft"]).read_text(encoding="utf-8") == "草稿\n"

    context = json.loads((tmp_path / "data/translation-context.json").read_text(encoding="utf-8"))
    assert list(context["chapters"]) == [f"{DOCS}/rules/index.md", new_file]
    assert context["chapters"][new_file]["id"] == "docs-src-content-docs-book-index-index"
    assert context["_meta"]["chapters_fingerprint"] == current_fingerprints(tmp_path)["chapters_fingerprint"]

    rules = (tmp_path / DOCS / "rules/index.md").read_text(encoding="utf-8")
    assert "[索引](/books/demo/book-index/#a)" in rules
    assert '<a href="/book-index/">' in rules
    assert "(/books/demo/index-of-things/)" in rules
    assert "(/books/demo/rules/index/)" in rules


def test_stale_context_stays_stale(tmp_path):
    make_project(tmp_path)
    context_path = tmp_path / "data/translation-context.json"
    context = json.loads(context_path.read_text(encoding="utf-8"))
    context["_meta"]["chapters_fingerprint"] = "stale"
    write_json(context_path, context)

    assert main(["--from", "index", "--to", "book-index"], project_root=tmp_path) == 0

    assert context_status(tmp_path)["reasons"] == ["chapters_fingerprint"]


def test_rejects_reserved_or_existing_target(tmp_path, capsys):
    make_project(tmp_path)

    assert main(["--from", "index", "--to", "pagefind"], project_root=tmp_path) == 1
    assert main(["--from", "index", "--to", "rules"], project_root=tmp_path) == 1
    assert main(["--from", "missing", "--to", "book-index"], project_root=tmp_path) == 1
    assert (tmp_path / DOCS / "index/index.md").exists()
    assert "保留字" in capsys.readouterr().err
