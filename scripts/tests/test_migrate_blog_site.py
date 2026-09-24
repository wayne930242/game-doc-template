from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "tools/migrate_blog_site.py"
spec = importlib.util.spec_from_file_location("migrate_blog_site", SCRIPT)
migrate_blog_site = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(migrate_blog_site)


def fixture_site(tmp_path: Path, *, title: str, home: str, style: dict | None = None) -> Path:
    repo = tmp_path / "book"
    (repo / "docs/src/content/docs").mkdir(parents=True)
    (repo / "docs/astro.config.mjs").write_text(
        "export default defineConfig({\n\tmarkdown: {},\n});\nconst SITE_CONFIG = {\n\ttitle: '" + title + "',\n};\n",
        encoding="utf-8",
    )
    (repo / "docs/src/content/docs/index.mdx").write_text(home, encoding="utf-8")
    if style is not None:
        (repo / "style-decisions.json").write_text(json.dumps(style, ensure_ascii=False), encoding="utf-8")
    return repo


def test_derives_original_title_from_home_and_requires_real_translator(tmp_path):
    repo = fixture_site(tmp_path, title="電馭叛客：赤紅", home="---\ntitle: 電馭叛客：赤紅\n---\n《電馭叛客：赤紅》（Cyberpunk Red）是一款遊戲。")
    style, missing, warnings = migrate_blog_site.derive_metadata(repo)
    assert style["site"]["title"] == "電馭叛客：赤紅"
    assert style["site"]["original_title"] == "Cyberpunk Red"
    assert style["_meta"]["description"]
    assert missing == ["translator"]
    assert warnings == []


def test_uses_recorded_project_title_and_preserves_other_credit(tmp_path):
    repo = fixture_site(tmp_path, title="迷霧傳說", home="---\ntitle: 迷霧傳說\n---\n", style={"project": {"game_title_en": "Legend in the Mist"}, "credits": {"entries": [{"role": "社群翻譯", "name": "Another"}]}})
    style, missing, _ = migrate_blog_site.derive_metadata(repo, "洪偉")
    assert style["site"]["original_title"] == "Legend in the Mist"
    assert not missing
    assert style["credits"]["entries"] == [{"role": "社群翻譯", "name": "Another"}, {"role": "翻譯", "name": "洪偉"}]


def test_apply_is_repeatable_and_preserves_book_content(tmp_path):
    home = "---\ntitle: 魔海痞徒\n---\nA custom homepage.\n"
    repo = fixture_site(tmp_path, title="魔海痞徒", home=home, style={"repository": {"game_title_en": "Rapscallion"}, "credits": {"entries": [{"role": "翻譯與整理", "name": "洪偉"}]}})
    (repo / "docs/package.json").write_text(json.dumps({"name": "docs", "dependencies": {"custom-component": "1.0.0"}}), encoding="utf-8")
    css = repo / "docs/src/styles/custom.css"
    css.parent.mkdir(parents=True)
    css.write_text("body { color: red; }", encoding="utf-8")
    first = migrate_blog_site.migrate(repo, "rapscallion", None, True)
    second = migrate_blog_site.migrate(repo, "rapscallion", None, True)
    assert first["applied"] and second["applied"]
    assert (repo / "docs/src/content/docs/index.mdx").read_text(encoding="utf-8") == home
    assert css.read_text(encoding="utf-8") == "body { color: red; }"
    assert (repo / "docs/astro.config.mjs").read_text(encoding="utf-8").count("base: '/books/rapscallion'") == 1
    assert json.loads((repo / "docs/package.json").read_text(encoding="utf-8"))["dependencies"]["custom-component"] == "1.0.0"
    assert json.loads((repo / "style-decisions.json").read_text(encoding="utf-8"))["credits"]["entries"] == [{"role": "翻譯與整理", "name": "洪偉"}]


def test_source_translation_credit_is_reported(tmp_path):
    repo = fixture_site(tmp_path, title="武林知心", home="---\ntitle: 武林知心\n---\n核心規則的翻譯由 zuzu 提供。整份文稿由洪偉整理。", style={"existing_translation_baseline": {"source": "prior translation"}})
    style, missing, warnings = migrate_blog_site.derive_metadata(repo)
    assert {"role": "翻譯", "name": "zuzu"} in style["credits"]["entries"]
    assert missing == ["original_title"]
    assert warnings


def test_apply_creates_missing_style_file(tmp_path):
    repo = fixture_site(tmp_path, title="Vaesen 北歐恐怖角色扮演", home="---\ntitle: Vaesen 北歐恐怖角色扮演\n---\n")
    (repo / "docs/package.json").write_text('{"name":"docs"}', encoding="utf-8")
    report = migrate_blog_site.migrate(repo, "vaesen-rpg", "洪偉", True)
    assert report["applied"]
    style = json.loads((repo / "style-decisions.json").read_text(encoding="utf-8"))
    assert style["site"]["original_title"] == "Vaesen"
    assert style["_meta"]["updated"]


def test_flags_translation_credit_in_a_deep_page(tmp_path):
    repo = fixture_site(tmp_path, title="Vaesen 北歐恐怖角色扮演", home="---\ntitle: Vaesen 北歐恐怖角色扮演\n---\n")
    page = repo / "docs/src/content/docs/rules.md"
    page.write_text("---\ntitle: 規則\n---\n譯者：另一位譯者。", encoding="utf-8")
    _, _, warnings = migrate_blog_site.derive_metadata(repo, "洪偉")
    assert any("rules.md" in warning for warning in warnings)


def test_confirmed_credits_replace_derived_entries(tmp_path):
    repo = fixture_site(tmp_path, title="武林知心", home="---\ntitle: 武林知心\n---\n核心規則的翻譯由 zuzu 提供。整份文稿由洪偉整理。")
    credits = [migrate_blog_site.parse_credit("核心規則翻譯=zuzu"), migrate_blog_site.parse_credit("整理=洪偉")]
    style, missing, _ = migrate_blog_site.derive_metadata(repo, original_title="Hearts of Wulin", credits=credits)
    assert not missing
    assert style["credits"]["entries"] == [{"role": "核心規則翻譯", "name": "zuzu"}, {"role": "整理", "name": "洪偉"}]
