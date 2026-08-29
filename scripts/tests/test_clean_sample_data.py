from __future__ import annotations

import json

import clean_sample_data as csd


def _patch_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(csd, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(csd, "CHAPTERS_PATH", tmp_path / "chapters.json")
    monkeypatch.setattr(csd, "STYLE_PATH", tmp_path / "style-decisions.json")
    monkeypatch.setattr(csd, "PROGRESS_GLOB_DIR", tmp_path / "data")
    monkeypatch.setattr(csd, "ASTRO_CONFIG", tmp_path / "docs" / "astro.config.mjs")
    monkeypatch.setattr(csd, "INDEX_MDX", tmp_path / "docs" / "src" / "content" / "docs" / "index.mdx")
    monkeypatch.setattr(csd, "PLANS_DIR", tmp_path / "plans")
    monkeypatch.setattr(csd, "MARKDOWN_DIR", tmp_path / "data" / "markdown")
    monkeypatch.setattr(csd, "DOCS_CONTENT_DIR", tmp_path / "docs" / "src" / "content" / "docs")
    monkeypatch.setattr(csd, "GLOSSARY_PATH", tmp_path / "glossary.json")


def test_reset_chapters_writes_placeholder(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    (tmp_path / "chapters.json").write_text('{"source": "old"}', encoding="utf-8")
    csd.reset_chapters(apply=True)
    data = json.loads((tmp_path / "chapters.json").read_text(encoding="utf-8"))
    assert data["source"] == "data/markdown/YOUR-RULEBOOK_pages.md"
    assert "example-section" in data["chapters"]


def test_reset_style_decisions_keeps_only_meta(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    (tmp_path / "style-decisions.json").write_text(
        '{"_meta": {"description": "d", "updated": "x"}, "site": {"title": "YZE"}}',
        encoding="utf-8",
    )
    csd.reset_style_decisions(apply=True)
    data = json.loads((tmp_path / "style-decisions.json").read_text(encoding="utf-8"))
    assert list(data.keys()) == ["_meta"]


def test_remove_progress_files(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    (tmp_path / "data").mkdir()
    for name in ("translation-progress.json", "translation-progress-bilingual.json"):
        (tmp_path / "data" / name).write_text("{}", encoding="utf-8")
    (tmp_path / "data" / "translation-context.json").write_text("{}", encoding="utf-8")
    csd.remove_progress_files(apply=True)
    assert not list((tmp_path / "data").glob("translation-progress*.json"))
    assert not (tmp_path / "data" / "translation-context.json").exists()


def test_reset_astro_config_title_and_sidebar(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    cfg = tmp_path / "docs" / "astro.config.mjs"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        "const SITE_CONFIG = {\n\ttitle: 'Old Sample Title',\n};\n"
        "export default defineConfig({\n\tsidebar: [\n\t\t{ label: 'X', slug: 'bilingual/x' },\n\t],\n});\n",
        encoding="utf-8",
    )
    csd.reset_astro_config(apply=True)
    text = cfg.read_text(encoding="utf-8")
    assert "title: '遊戲規則文件'" in text
    assert "bilingual/x" not in text
    assert "sidebar: []," in text


def test_reset_astro_config_idempotent_on_second_run(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    cfg = tmp_path / "docs" / "astro.config.mjs"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        "const SITE_CONFIG = {\n\ttitle: 'Old Sample Title',\n};\n"
        "export default defineConfig({\n"
        "\tintegrations: [\n"
        "\t\tstarlight({\n"
        "\t\t\tsidebar: [\n\t\t\t\t{ label: 'X', slug: 'bilingual/x' },\n\t\t\t],\n"
        "\t\t\tplugins: [starlightAutoSidebar()],\n"
        "\t\t\tcustomCss: ['./src/styles/custom.css'],\n"
        "\t\t}),\n"
        "\t],\n"
        "});\n",
        encoding="utf-8",
    )
    csd.reset_astro_config(apply=True)
    first_pass = cfg.read_text(encoding="utf-8")
    assert "sidebar: []," in first_pass
    assert "plugins: [starlightAutoSidebar()]," in first_pass
    assert "customCss: ['./src/styles/custom.css']," in first_pass

    # Re-running on an already-blank sidebar must not corrupt subsequent lines.
    csd.reset_astro_config(apply=True)
    second_pass = cfg.read_text(encoding="utf-8")
    assert second_pass == first_pass


def test_reset_astro_config_nested_populated_sidebar_preserves_siblings(monkeypatch, tmp_path):
    """Regression for the old unanchored regex over-consuming into a later
    `],` (e.g. `plugins`'s own closing bracket) when the sidebar sits nested
    inside `starlight({...})`."""
    _patch_paths(monkeypatch, tmp_path)
    cfg = tmp_path / "docs" / "astro.config.mjs"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        "export default defineConfig({\n"
        "\tintegrations: [\n"
        "\t\tstarlight({\n"
        "\t\t\tsidebar: [\n\t\t\t\t{ label: 'X', slug: 'x' },\n\t\t\t],\n"
        "\t\t\tplugins: [starlightAutoSidebar()],\n"
        "\t\t\tcustomCss: ['./src/styles/custom.css'],\n"
        "\t\t}),\n"
        "\t],\n"
        "});\n",
        encoding="utf-8",
    )
    csd.reset_astro_config(apply=True)
    text = cfg.read_text(encoding="utf-8")
    assert "sidebar: []," in text
    assert "plugins: [starlightAutoSidebar()]," in text
    assert "customCss: ['./src/styles/custom.css']," in text
    assert text.rstrip().endswith("});")


def test_clean_glossary_handles_invalid_utf8(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    glossary = tmp_path / "glossary.json"
    glossary.write_bytes(b"\xff\xfe not valid utf-8")

    csd.clean_glossary(apply=True)

    payload = json.loads(glossary.read_text(encoding="utf-8"))
    assert payload["_meta"]["description"] == "術語表 - 英文遊戲術語對照繁體中文翻譯"


def test_write_placeholder_index_and_remove_plans(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    (tmp_path / "plans").mkdir()
    (tmp_path / "plans" / "x.md").write_text("x", encoding="utf-8")
    csd.write_placeholder_index(apply=True)
    csd.remove_plans_dir(apply=True)
    index = tmp_path / "docs" / "src" / "content" / "docs" / "index.mdx"
    assert index.exists()
    assert "title:" in index.read_text(encoding="utf-8")
    assert not (tmp_path / "plans").exists()


def test_clean_markdown_data_keeps_only_gitkeep(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    markdown_dir = tmp_path / "data" / "markdown"
    markdown_dir.mkdir(parents=True)
    (markdown_dir / ".gitkeep").write_text("", encoding="utf-8")
    (markdown_dir / "a.md").write_text("x", encoding="utf-8")
    images = markdown_dir / "images"
    images.mkdir()
    (images / "i.png").write_text("x", encoding="utf-8")

    csd.clean_markdown_data(apply=True)

    assert (markdown_dir / ".gitkeep").exists()
    assert not (markdown_dir / "a.md").exists()
    assert not images.exists()


def test_clean_docs_content_removes_generated_content_only(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    docs_dir = tmp_path / "docs" / "src" / "content" / "docs"
    docs_dir.mkdir(parents=True)
    (docs_dir / "a.md").write_text("x", encoding="utf-8")
    (docs_dir / "b.mdx").write_text("x", encoding="utf-8")
    (docs_dir / "c.txt").write_text("x", encoding="utf-8")

    csd.clean_docs_content(apply=True)

    assert not (docs_dir / "a.md").exists()
    assert not (docs_dir / "b.mdx").exists()
    assert (docs_dir / "c.txt").exists()


def test_clean_docs_content_removes_meta_yml_and_empty_dirs(monkeypatch, tmp_path):
    """`_meta.yml` drives starlight-auto-sidebar; leftovers keep stale nav data
    and keep section dirs non-empty so the empty-dir sweep skips them."""
    _patch_paths(monkeypatch, tmp_path)
    docs_dir = tmp_path / "docs" / "src" / "content" / "docs"
    section = docs_dir / "combat"
    group = section / "actions"
    group.mkdir(parents=True)
    (section / "_meta.yml").write_text("label: 戰鬥\n", encoding="utf-8")
    (group / "_meta.yaml").write_text("label: 行動\n", encoding="utf-8")
    (group / "index.md").write_text("x", encoding="utf-8")

    csd.clean_docs_content(apply=True)

    assert not (section / "_meta.yml").exists()
    assert not (group / "_meta.yaml").exists()
    assert not group.exists()
    assert not section.exists()


def test_clean_glossary_resets_to_meta_only(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    glossary = tmp_path / "glossary.json"
    glossary.write_text(
        json.dumps(
            {"_meta": {"description": "custom", "updated": "now"}, "Move": {"zh": "動作"}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    csd.clean_glossary(apply=True)

    payload = json.loads(glossary.read_text(encoding="utf-8"))
    assert payload["_meta"]["description"] == "custom"
    assert payload["_meta"]["updated"] == ""
    assert set(payload.keys()) == {"_meta"}


def test_idempotent_second_run(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    csd.reset_chapters(apply=True)
    first = (tmp_path / "chapters.json").read_text(encoding="utf-8")
    csd.reset_chapters(apply=True)
    assert (tmp_path / "chapters.json").read_text(encoding="utf-8") == first
