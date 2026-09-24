#!/usr/bin/env python3
"""Compare a book's pre-migration build with its blog export.

Checks the HTML page set, the visible `.sl-markdown-content` text of every page,
and every local href/src/srcset/poster in the export, which must resolve to a file
inside the export under the blog base path.

Exit codes: 0 when nothing was lost (whitespace-only text differences are reported
but pass), 1 when pages, text, or links differ, 2 for invalid input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

URL_ATTRS = ("href", "src", "srcset", "poster")
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
HIDDEN_TAGS = {"script", "style", "template", "noscript"}
SAMPLE_LIMIT = 20


class PageScanner(HTMLParser):
    """Collect the visible content text and the URL attribute values of one page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.content: list[str] = []
        self.main: list[str] = []
        self.urls: list[tuple[str, str]] = []
        self._content_depth = 0
        self._main_depth = 0
        self._hidden_depth = 0
        self.found_content = False

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in URL_ATTRS and value:
                self.urls.append((name, value))
        if tag in VOID_TAGS:
            return
        classes = (dict(attrs).get("class") or "").split()
        if self._content_depth:
            self._content_depth += 1
        elif "sl-markdown-content" in classes:
            self._content_depth = 1
            self.found_content = True
        if self._main_depth:
            self._main_depth += 1
        elif tag == "main":
            self._main_depth = 1
        if self._hidden_depth or tag in HIDDEN_TAGS:
            self._hidden_depth += 1

    def handle_startendtag(self, tag, attrs):
        for name, value in attrs:
            if name in URL_ATTRS and value:
                self.urls.append((name, value))

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        self._content_depth = max(self._content_depth - 1, 0)
        self._main_depth = max(self._main_depth - 1, 0)
        self._hidden_depth = max(self._hidden_depth - 1, 0)

    def handle_data(self, data):
        if self._hidden_depth:
            return
        if self._content_depth:
            self.content.append(data)
        if self._main_depth:
            self.main.append(data)

    def text(self) -> str:
        return "".join(self.content if self.found_content else self.main)


def scan(path: Path) -> PageScanner:
    scanner = PageScanner()
    scanner.feed(path.read_text(encoding="utf-8"))
    scanner.close()
    return scanner


def html_pages(root: Path) -> dict[str, Path]:
    return {path.relative_to(root).as_posix(): path for path in root.rglob("*.html")}


def link_urls(attr: str, value: str) -> list[str]:
    if attr == "srcset":
        return [candidate.strip().split()[0] for candidate in value.split(",") if candidate.strip()]
    return [value]


def resolve_local(export: Path, base: str, page: Path, url: str) -> Path | str | None:
    """Return the file a local URL points to, "outside" when it leaves the base, or None for non-local URLs."""
    parts = urlsplit(url)
    if parts.scheme or parts.netloc or url.startswith("#"):
        return None
    path = unquote(parts.path)
    if not path:
        return None
    if path.startswith("/"):
        if path != base and not path.startswith(base + "/"):
            return "outside"
        target = (export / path[len(base) + 1:]).resolve()
    else:
        target = (page.parent / path).resolve()
    if target != export and export not in target.parents:
        return "outside"
    return target


def local_file_exists(target: Path) -> bool:
    if target.is_dir():
        return (target / "index.html").is_file()
    return target.is_file() or target.with_name(target.name + ".html").is_file()


def compare(baseline: Path, export: Path, base: str) -> dict:
    baseline, export = baseline.resolve(), export.resolve()
    base = "/" + base.strip("/")
    for label, root in (("baseline", baseline), ("export", export)):
        if not root.is_dir():
            raise ValueError(f"{label} directory not found: {root}")
    before, after = html_pages(baseline), html_pages(export)
    if not after:
        raise ValueError(f"export has no HTML pages: {export}")

    missing_pages = sorted(set(before) - set(after))
    extra_pages = sorted(set(after) - set(before))
    text_diffs, whitespace_diffs = [], []
    missing_links, outside_links = [], []
    links_checked = 0

    for rel, page in sorted(after.items()):
        scanner = scan(page)
        if rel in before:
            old, new = scan(before[rel]).text(), scanner.text()
            if old != new:
                if re.sub(r"\s+", "", old) == re.sub(r"\s+", "", new):
                    whitespace_diffs.append(rel)
                else:
                    text_diffs.append(rel)
        for attr, value in scanner.urls:
            for url in link_urls(attr, value):
                target = resolve_local(export, base, page, url)
                if target is None:
                    continue
                links_checked += 1
                if target == "outside":
                    outside_links.append([rel, url])
                elif not local_file_exists(target):
                    missing_links.append([rel, url])

    report = {
        "baseline_pages": len(before),
        "export_pages": len(after),
        "missing_pages": missing_pages,
        "extra_pages": extra_pages,
        "text_diffs": len(text_diffs),
        "text_diff_pages": text_diffs[:SAMPLE_LIMIT],
        "whitespace_only_diffs": len(whitespace_diffs),
        "whitespace_only_pages": whitespace_diffs[:SAMPLE_LIMIT],
        "links_checked": links_checked,
        "links_missing": len(missing_links),
        "missing_link_samples": missing_links[:SAMPLE_LIMIT],
        "links_outside_base": len(outside_links),
        "outside_link_samples": outside_links[:SAMPLE_LIMIT],
    }
    report["ok"] = not (missing_pages or extra_pages or text_diffs or missing_links or outside_links)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("baseline", type=Path, help="Pre-migration build output, such as docs/dist of the old deployment")
    parser.add_argument("export", type=Path, help="Directory written by scripts/export_site.py")
    parser.add_argument("--base", required=True, help="Blog base path of the export, such as /books/vaesen-rpg")
    args = parser.parse_args()
    try:
        report = compare(args.baseline, args.export, args.base)
    except (ValueError, OSError, UnicodeDecodeError) as exc:
        print(f"Comparison error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
