from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "tools/old_host_redirect.py"
spec = importlib.util.spec_from_file_location("old_host_redirect", SCRIPT)
old_host_redirect = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(old_host_redirect)

TARGET = "https://www.wayneh.tw/books/vaesen-rpg"


def test_target_base_requires_blog_slug():
    assert old_host_redirect.target_base("vaesen-rpg", "https://www.wayneh.tw/books/") == TARGET
    with pytest.raises(ValueError):
        old_host_redirect.target_base("Vaesen RPG", old_host_redirect.BLOG_BOOKS_URL)


def test_github_pages_site_preserves_each_old_path(tmp_path):
    dist = tmp_path / "dist"
    for rel in ("index.html", "rules/combat/index.html", "404.html"):
        (dist / rel).parent.mkdir(parents=True, exist_ok=True)
        (dist / rel).write_text("<html></html>", encoding="utf-8")
    repo = tmp_path / "book"
    written = old_host_redirect.write_github_pages(repo, TARGET, dist, "/cairn-barebones-docs/")
    site = repo / old_host_redirect.PAGES_SITE_DIR
    assert "old-host-redirect/rules/combat/index.html" in written
    deep = (site / "rules/combat/index.html").read_text(encoding="utf-8")
    assert f'<meta http-equiv="refresh" content="0; url={TARGET}/rules/combat/">' in deep
    assert f'<link rel="canonical" href="{TARGET}/rules/combat/">' in deep
    assert f'location.replace("{TARGET}/rules/combat/"+location.search+location.hash)' in deep
    assert f'content="0; url={TARGET}/"' in (site / "index.html").read_text(encoding="utf-8")
    fallback = (site / "404.html").read_text(encoding="utf-8")
    assert 'var b="/cairn-barebones-docs"' in fallback and f'location.replace("{TARGET}"+(p||\'/\')' in fallback
    workflow = (repo / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
    assert "path: old-host-redirect" in workflow and "${{ steps.deployment.outputs.page_url }}" in workflow


def test_github_pages_requires_page_list(tmp_path):
    with pytest.raises(ValueError):
        old_host_redirect.write_github_pages(tmp_path / "book", TARGET, tmp_path / "missing", "")
