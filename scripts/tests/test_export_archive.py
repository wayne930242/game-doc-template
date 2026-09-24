from __future__ import annotations

import json
import tarfile

import pytest

from export_site import ExportError, check_blog_archive, write_archive

SLUG = "kedamono-opera"


def make_export(root, **manifest_overrides):
    export = root / "export"
    (export / "basic-rules").mkdir(parents=True)
    (export / "index.html").write_text("<html></html>", encoding="utf-8")
    (export / "basic-rules/index.html").write_text("<html></html>", encoding="utf-8")
    manifest = {
        "slug": SLUG,
        "title": "暗獸歌劇",
        "base_path": f"/books/{SLUG}/",
        "progress": {"completed": 27, "total": 27},
        **manifest_overrides,
    }
    (export / "book.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return export


def archive_of(root, **manifest_overrides):
    archive = root / "out" / "kedamono.tar.gz"
    write_archive(make_export(root, **manifest_overrides), archive)
    return archive


def test_archive_holds_export_contents_at_root(tmp_path):
    archive = archive_of(tmp_path)

    with tarfile.open(archive, "r:gz") as tar:
        names = sorted(tar.getnames())
    assert names == ["basic-rules", "basic-rules/index.html", "book.json", "index.html"]
    assert check_blog_archive(archive, SLUG)["title"] == "暗獸歌劇"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"slug": "other"}, "slug"),
        ({"base_path": f"/books/{SLUG}"}, "base_path"),
        ({"base_path": f"/{SLUG}/"}, "base_path"),
    ],
)
def test_rejects_manifest_the_blog_would_reject(tmp_path, overrides, message):
    with pytest.raises(ExportError, match=message):
        check_blog_archive(archive_of(tmp_path, **overrides), SLUG)


def test_rejects_archive_without_root_index(tmp_path):
    export = make_export(tmp_path)
    archive = tmp_path / "nested.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(export, arcname="export")
    with pytest.raises(ExportError, match="index.html"):
        check_blog_archive(archive, SLUG)
