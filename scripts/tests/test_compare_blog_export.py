from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "tools/compare_blog_export.py"
spec = importlib.util.spec_from_file_location("compare_blog_export", SCRIPT)
compare_blog_export = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(compare_blog_export)

BASE = "/books/demo"


def page(body: str, links: str = "") -> str:
    return (
        '<!doctype html><html><head><link rel="stylesheet" href="/books/demo/_astro/site.css"></head><body>'
        f'<nav>{links}</nav><main><div class="sl-markdown-content">{body}</div></main>'
        "<script>ignored()</script></body></html>"
    )


def write_site(root: Path, pages: dict[str, str], assets: tuple[str, ...] = ("_astro/site.css",)) -> Path:
    for rel, text in pages.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    for rel in assets:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("x", encoding="utf-8")
    return root


def test_identical_export_passes_and_crawls_local_links(tmp_path):
    baseline = write_site(tmp_path / "base", {"index.html": page("<p>首頁</p>"), "rules/index.html": page("<p>規則</p>")})
    export = write_site(
        tmp_path / "export",
        {
            "index.html": page("<p>首頁</p>", '<a href="/books/demo/rules/">規則</a><img srcset="/books/demo/a.png 1x, /books/demo/a.png 2x">'),
            "rules/index.html": page("<p>規則</p>", '<a href="../">首頁</a><a href="https://example.com/">外部</a><a href="#top">頂端</a>'),
        },
        assets=("_astro/site.css", "a.png"),
    )
    report = compare_blog_export.compare(baseline, export, BASE)
    assert report["ok"]
    assert report["baseline_pages"] == report["export_pages"] == 2
    assert report["links_checked"] == 6


def test_whitespace_only_text_differences_pass_and_are_reported(tmp_path):
    baseline = write_site(tmp_path / "base", {"index.html": page("<p>卡片</p><p>說明</p>")})
    export = write_site(tmp_path / "export", {"index.html": page("<p>卡片</p>\n  <p>說明</p><!-- page 3 -->")})
    report = compare_blog_export.compare(baseline, export, BASE)
    assert report["ok"]
    assert report["text_diffs"] == 0
    assert report["whitespace_only_pages"] == ["index.html"]


def test_text_page_and_link_losses_fail(tmp_path):
    baseline = write_site(tmp_path / "base", {"index.html": page("<p>完整規則</p>"), "gone/index.html": page("<p>消失</p>")})
    export = write_site(tmp_path / "export", {"index.html": page("<p>規則</p>", '<a href="/books/demo/missing/">缺</a><a href="/rules/">舊根</a>')})
    report = compare_blog_export.compare(baseline, export, BASE)
    assert not report["ok"]
    assert report["missing_pages"] == ["gone/index.html"]
    assert report["text_diff_pages"] == ["index.html"]
    assert report["missing_link_samples"] == [["index.html", "/books/demo/missing/"]]
    assert report["outside_link_samples"] == [["index.html", "/rules/"]]


def test_exit_codes(tmp_path):
    baseline = write_site(tmp_path / "base", {"index.html": page("<p>一</p>")})
    same = write_site(tmp_path / "same", {"index.html": page("<p>一</p>")})
    changed = write_site(tmp_path / "changed", {"index.html": page("<p>二</p>")})

    def run(export: Path) -> int:
        return subprocess.run([sys.executable, str(SCRIPT), str(baseline), str(export), "--base", BASE], capture_output=True).returncode

    assert run(same) == 0
    assert run(changed) == 1
    assert run(tmp_path / "absent") == 2
