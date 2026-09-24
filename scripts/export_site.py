#!/usr/bin/env python3
"""Build the docs site under its blog base path and export it with a book.json manifest.

The blog copies the exported directory to public/books/<slug>/ and gates the whole
path with its shared password, so the export carries only static output: no Vercel
middleware and no auth endpoint.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from _style_decisions_lib import load_and_validate_style_decisions
from generate_nav import deployment_base_path, update_astro_site_base

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STYLE_FILE = PROJECT_ROOT / "style-decisions.json"
PROGRESS_FILE = PROJECT_ROOT / "data" / "translation-progress.json"
PDF_DIR = PROJECT_ROOT / "data" / "pdfs"
DOCS_DIR = PROJECT_ROOT / "docs"
DIST_DIR = DOCS_DIR / "dist"
ASTRO_CONFIG = DOCS_DIR / "astro.config.mjs"
MANIFEST_NAME = "book.json"
COVER_STEM = "cover"

# URL-bearing attributes in HTML and url() in CSS. A value starting with a single "/"
# is root-relative and must sit under the base path once the book lives in the blog.
HTML_URL_ATTR = re.compile(r"""\s(?:href|src|srcset|content|action|poster)=["']?(/[^"'\s>,]*)""")
CSS_URL = re.compile(r"""url\(\s*["']?(/[^"')\s]*)""")


class ExportError(RuntimeError):
    """Raised when the project is not ready to export or the build output is unsafe."""


def git_output(*args: str, cwd: Path = PROJECT_ROOT) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ExportError(f"git {' '.join(args)} 失敗：{result.stderr.strip()}")
    return result.stdout.strip()


def source_repo_from_remote(remote_url: str) -> str:
    """Return 'owner/repo' from an SSH or HTTPS GitHub remote URL."""
    match = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$", remote_url)
    if not match:
        raise ExportError(f"無法從 git remote 解析 owner/repo：{remote_url}")
    return f"{match.group(1)}/{match.group(2)}"


def blog_base_path(style: dict[str, Any]) -> str:
    """Return the configured blog base path without trailing slash, e.g. '/books/slug'."""
    deployment = style.get("deployment", {})
    if deployment.get("target") != "blog":
        raise ExportError(
            "deployment.target 不是 blog。請先執行："
            "uv run python scripts/style_decisions.py set-deployment --target blog --base-path /books/<slug>"
        )
    base_path = deployment_base_path(style)
    if not base_path:
        raise ExportError("deployment.base_path 未設定")
    return base_path


def original_title(style: dict[str, Any], pdf_dir: Path) -> str | None:
    """Return site.original_title, else the title derived from the project's single source PDF."""
    recorded = style.get("site", {}).get("original_title")
    if recorded:
        return recorded
    pdfs = sorted(pdf_dir.glob("*.pdf")) if pdf_dir.is_dir() else []
    if len(pdfs) != 1:
        return None
    return re.sub(r"[_\s]+", " ", pdfs[0].stem).strip() or None


def cover_source(style: dict[str, Any], project_root: Path) -> Path | None:
    """Return the recorded hero (or OG) image when the file exists."""
    images = style.get("images", {})
    for key in ("hero", "og"):
        recorded = images.get(key)
        if recorded and (project_root / recorded).is_file():
            return project_root / recorded
    return None


def progress_counts(progress: dict[str, Any]) -> dict[str, int]:
    chapters = progress.get("chapters", [])
    completed = sum(1 for chapter in chapters if chapter.get("status") == "completed")
    return {"completed": completed, "total": len(chapters)}


def build_manifest(
    style: dict[str, Any],
    progress: dict[str, Any],
    *,
    source_repo: str,
    updated_at: str,
    cover: str | None,
    pdf_dir: Path,
) -> dict[str, Any]:
    """Assemble book.json from recorded project data."""
    base_path = blog_base_path(style)
    site = style.get("site", {})
    slug = base_path.rsplit("/", 1)[-1]
    title = site.get("title")
    if not title:
        raise ExportError("site.title 未設定，請先執行 style_decisions.py set-site --title")
    return {
        "slug": slug,
        "title": title,
        "original_title": original_title(style, pdf_dir),
        "description": site.get("description", ""),
        "base_path": f"{base_path}/",
        "cover": cover,
        "credits": style.get("credits", {}).get("entries", []),
        "progress": progress_counts(progress),
        "updated_at": updated_at,
        "source_repo": source_repo,
    }


def assert_config_synced(config_text: str, style: dict[str, Any]) -> None:
    if update_astro_site_base(config_text, style) != config_text:
        raise ExportError("astro.config.mjs 的 base 與 style-decisions.json 不一致，請先執行 uv run python scripts/generate_nav.py")


def urls_outside_base(dist: Path, base_path: str) -> list[str]:
    """Return 'file: url' entries for root-relative URLs that escape the base path."""
    prefix = f"{base_path}/"
    offenders: list[str] = []
    for path in sorted(dist.rglob("*")):
        if path.suffix == ".html":
            pattern = HTML_URL_ATTR
        elif path.suffix == ".css":
            pattern = CSS_URL
        else:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for url in pattern.findall(text):
            if url.startswith("//") or url.startswith(prefix) or url == base_path:
                continue
            offenders.append(f"{path.relative_to(dist)}: {url}")
    return offenders


def build_site() -> None:
    try:
        subprocess.run(["bun", "run", "build"], cwd=DOCS_DIR, check=True)
    except FileNotFoundError as exc:
        raise ExportError("找不到 bun，請先安裝 bun 並在 docs/ 執行 bun install") from exc
    except subprocess.CalledProcessError as exc:
        raise ExportError(f"網站建置失敗（exit {exc.returncode}）") from exc


def prepare_out_dir(out: Path, clean: bool) -> None:
    resolved = out.resolve()
    if resolved == DIST_DIR.resolve() or resolved == PROJECT_ROOT or PROJECT_ROOT.is_relative_to(resolved):
        raise ExportError(f"輸出目錄不可為專案或 dist 本身：{out}")
    if resolved.exists() and any(resolved.iterdir()):
        if not clean:
            raise ExportError(f"輸出目錄非空：{out}（加上 --clean 以覆寫）")
        shutil.rmtree(resolved)


def tree_stats(root: Path) -> tuple[int, int]:
    files = [path for path in root.rglob("*") if path.is_file()]
    return len(files), sum(path.stat().st_size for path in files)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the site under the blog base path and export it with book.json.")
    parser.add_argument("--out", type=Path, required=True, help="Directory that receives the static site and book.json.")
    parser.add_argument("--clean", action="store_true", help="Replace the output directory when it is not empty.")
    return parser.parse_args()


def run(args: argparse.Namespace) -> None:
    style = load_and_validate_style_decisions(STYLE_FILE)
    base_path = blog_base_path(style)
    assert_config_synced(ASTRO_CONFIG.read_text(encoding="utf-8"), style)
    if not PROGRESS_FILE.exists():
        raise ExportError(f"找不到翻譯進度檔：{PROGRESS_FILE}")
    progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    source_repo = source_repo_from_remote(git_output("remote", "get-url", "origin"))
    updated_at = git_output("log", "-1", "--format=%cI")

    prepare_out_dir(args.out, args.clean)
    build_site()
    offenders = urls_outside_base(DIST_DIR, base_path)
    if offenders:
        listing = "\n".join(f"  {entry}" for entry in offenders[:20])
        raise ExportError(
            f"建置結果有 {len(offenders)} 個網址跳出 {base_path}/（內容連結需含 base，見 fix-ref 規則；"
            f"首頁連結請重跑 generate_nav.py）：\n{listing}"
        )

    shutil.copytree(DIST_DIR, args.out, dirs_exist_ok=True)
    cover_path = cover_source(style, PROJECT_ROOT)
    cover = None
    if cover_path:
        cover = f"{COVER_STEM}{cover_path.suffix.lower()}"
        shutil.copyfile(cover_path, args.out / cover)

    manifest = build_manifest(
        style, progress, source_repo=source_repo, updated_at=updated_at, cover=cover, pdf_dir=PDF_DIR
    )
    (args.out / MANIFEST_NAME).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    count, size = tree_stats(args.out)
    print(f"✓ 已匯出 {manifest['base_path']} → {args.out}")
    print(f"  檔案數 {count}，總大小 {size / 1024 / 1024:.1f} MiB")


def main() -> None:
    try:
        run(parse_args())
    except ExportError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
