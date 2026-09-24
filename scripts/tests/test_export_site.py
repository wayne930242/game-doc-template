from __future__ import annotations

import re
from pathlib import Path

import pytest

from export_site import (
    ExportError,
    assert_config_synced,
    build_manifest,
    cover_source,
    source_repo_from_remote,
    urls_outside_base,
)
from generate_nav import deployment_base_path, update_astro_site_base, update_astro_site_title

# Synced projects record their own title, so reset it to the template default the tests expect.
TEMPLATE_CONFIG = re.sub(
    r"\ttitle: '.*',\n",
    "\ttitle: '遊戲規則文件',\n",
    (Path(__file__).resolve().parents[2] / "docs" / "astro.config.mjs").read_text(encoding="utf-8"),
    count=1,
)

CONFIG = "import x from 'y';\n\nexport default defineConfig({\n\tmarkdown: {},\n});\n"


def blog_style(**overrides):
    style = {
        "deployment": {"target": "blog", "base_path": "/books/kedamono-opera"},
        "site": {"title": "暗獸歌劇", "original_title": "Kedamono Opera", "description": "描述"},
        "credits": {"entries": [{"role": "翻譯", "name": "洪偉"}], "show_on_homepage": True},
    }
    style.update(overrides)
    return style


PROGRESS = {
    "chapters": [
        {"file": "a.md", "status": "completed"},
        {"file": "b.md", "status": "completed"},
        {"file": "c.md", "status": "in_progress"},
    ]
}


def make_manifest(style, cover=None):
    return build_manifest(
        style,
        PROGRESS,
        source_repo="wayne930242/kedamono-opera",
        updated_at="2026-09-24T12:00:00+08:00",
        cover=cover,
    )


class TestManifest:
    def test_fields_derive_from_project_data(self):
        manifest = make_manifest(blog_style(), cover="cover.jpg")
        assert manifest == {
            "slug": "kedamono-opera",
            "title": "暗獸歌劇",
            "original_title": "Kedamono Opera",
            "description": "描述",
            "base_path": "/books/kedamono-opera/",
            "cover": "cover.jpg",
            "credits": [{"role": "翻譯", "name": "洪偉"}],
            "progress": {"completed": 2, "total": 3},
            "updated_at": "2026-09-24T12:00:00+08:00",
            "source_repo": "wayne930242/kedamono-opera",
        }

    def test_missing_original_title_fails(self):
        with pytest.raises(ExportError, match="original_title"):
            make_manifest(blog_style(site={"title": "暗獸歌劇"}))

    def test_cover_is_null_when_not_recorded(self):
        assert make_manifest(blog_style())["cover"] is None

    def test_missing_progress_is_null(self):
        assert build_manifest(blog_style(), None, source_repo="wayne930242/x", updated_at="2026-09-24", cover=None)["progress"] is None

    def test_old_path_keyed_progress_is_counted(self):
        old = {"_meta": {}, "a.md": {"status": "completed"}, "b.md": {"status": "in_progress"}}
        assert build_manifest(blog_style(), old, source_repo="wayne930242/x", updated_at="2026-09-24", cover=None)["progress"] == {"completed": 1, "total": 2}

    def test_missing_translator_fails(self):
        with pytest.raises(ExportError, match="翻譯署名"):
            make_manifest(blog_style(credits={"entries": []}))

    def test_rejects_non_blog_target(self):
        style = blog_style(deployment={"target": "root", "base_path": "/books/x"})
        with pytest.raises(ExportError, match="blog"):
            make_manifest(style)

    def test_rejects_missing_title(self):
        with pytest.raises(ExportError, match="site.title"):
            make_manifest(blog_style(site={}))


class TestCoverSource:
    def test_uses_recorded_hero_when_present(self, tmp_path):
        hero = tmp_path / "docs" / "hero.jpg"
        hero.parent.mkdir()
        hero.write_bytes(b"jpg")
        style = {"images": {"hero": "docs/hero.jpg", "og": "docs/og.jpg"}}
        assert cover_source(style, tmp_path) == hero

    def test_ignores_recorded_path_without_file(self, tmp_path):
        assert cover_source({"images": {"hero": "docs/hero.jpg"}}, tmp_path) is None


class TestSourceRepo:
    @pytest.mark.parametrize(
        "remote",
        [
            "git@github.com:wayne930242/kedamono-opera.git",
            "https://github.com/wayne930242/kedamono-opera.git",
            "https://github.com/wayne930242/kedamono-opera",
        ],
    )
    def test_parses_ssh_and_https(self, remote):
        assert source_repo_from_remote(remote) == "wayne930242/kedamono-opera"

    def test_rejects_non_github_remote(self):
        with pytest.raises(ExportError):
            source_repo_from_remote("/local/path/repo")


class TestBasePathConfig:
    def test_blog_target_writes_base_only(self):
        result = update_astro_site_base(CONFIG, blog_style())
        assert "\tbase: '/books/kedamono-opera',\n" in result
        assert "site:" not in result

    def test_blog_base_path_prefixes_content_links(self):
        assert deployment_base_path(blog_style()) == "/books/kedamono-opera"

    def test_switching_from_github_pages_to_blog_drops_site(self):
        github = {"deployment": {"target": "github-pages", "base_path": "/repo"}, "repository": {"url": "https://github.com/u/repo"}}
        with_pages = update_astro_site_base(CONFIG, github)
        assert "site: 'https://u.github.io'" in with_pages
        with_blog = update_astro_site_base(with_pages, blog_style())
        assert "site:" not in with_blog
        assert with_blog.count("base:") == 1

    def test_switching_back_to_root_restores_original(self):
        with_blog = update_astro_site_base(CONFIG, blog_style())
        assert update_astro_site_base(with_blog, {"deployment": {"target": "root"}}) == CONFIG

    def test_unset_base_keeps_root_config(self):
        assert update_astro_site_base(CONFIG, {}) == CONFIG
        assert deployment_base_path({}) == ""

    def test_sync_check_passes_after_generate(self):
        assert_config_synced(update_astro_site_base(CONFIG, blog_style()), blog_style())

    def test_sync_check_fails_on_stale_config(self):
        with pytest.raises(ExportError, match="generate_nav"):
            assert_config_synced(CONFIG, blog_style())


class TestSiteTitleConfig:
    def test_writes_recorded_title_into_site_config(self):
        result = update_astro_site_title(TEMPLATE_CONFIG, blog_style())
        assert "\ttitle: '暗獸歌劇',\n" in result
        assert "遊戲規則文件" not in result
        assert "title: SITE_CONFIG.title," in result
        assert update_astro_site_title(result, blog_style()) == result

    def test_escapes_quotes_and_backslashes(self):
        result = update_astro_site_title(TEMPLATE_CONFIG, {"site": {"title": "It's a \\ test"}})
        assert "\ttitle: 'It\\'s a \\\\ test',\n" in result

    def test_updates_double_quoted_legacy_title(self):
        config = TEMPLATE_CONFIG.replace("title: '遊戲規則文件'", 'title: "舊標題"')
        result = update_astro_site_title(config, {"site": {"title": "新標題"}})
        assert 'title: "新標題"' in result

    def test_keeps_config_without_recorded_title(self):
        assert update_astro_site_title(TEMPLATE_CONFIG, {}) == TEMPLATE_CONFIG

    def test_sync_check_rejects_template_default_title(self):
        with_base = update_astro_site_base(TEMPLATE_CONFIG, blog_style())
        with pytest.raises(ExportError, match="網站標題"):
            assert_config_synced(with_base, blog_style())
        assert_config_synced(update_astro_site_title(with_base, blog_style()), blog_style())


class TestUrlsOutsideBase:
    def test_reports_root_relative_urls_outside_prefix(self, tmp_path):
        (tmp_path / "index.html").write_text(
            '<a href="/books/x/a/">ok</a><a href="/basic-rules/">bad</a>'
            '<img src="//cdn.example/x.png"><a href="https://e.com/">ext</a><a href="#top">anchor</a>',
            encoding="utf-8",
        )
        (tmp_path / "style.css").write_text("a{background:url('/bg.jpg')}b{background:url(/books/x/ok.png)}", encoding="utf-8")
        assert urls_outside_base(tmp_path, "/books/x") == ["index.html: /basic-rules/", "style.css: /bg.jpg"]

    def test_clean_output_has_no_offenders(self, tmp_path):
        (tmp_path / "index.html").write_text('<link href="/books/x/_astro/a.css"><a href=/books/x/>home</a>', encoding="utf-8")
        assert urls_outside_base(tmp_path, "/books/x") == []
