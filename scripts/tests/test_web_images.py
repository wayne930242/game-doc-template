from __future__ import annotations

import io
import json

import pymupdf
from PIL import Image

from convert_web_images import main as convert_main
from extract_pdf import extract_images


def jpeg2000_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (16, 12), (200, 40, 40)).save(buffer, format="JPEG2000")
    return buffer.getvalue()


def test_extract_images_writes_png_for_jpeg2000(tmp_path):
    pdf_path = tmp_path / "book.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(pymupdf.Rect(10, 10, 170, 130), stream=jpeg2000_bytes())
    doc.save(pdf_path)
    doc.close()
    source = pymupdf.open(pdf_path)
    assert source.extract_image(source[0].get_images()[0][0])["ext"] == "jpx"
    source.close()

    images = extract_images(pdf_path, tmp_path / "out")

    assert [image["filename"].rsplit(".", 1)[1] for image in images] == ["png"]
    written = tmp_path / "out" / images[0]["path"]
    assert written.read_bytes().startswith(b"\x89PNG")
    assert images[0]["file_size"] == written.stat().st_size
    assert pymupdf.Pixmap(str(written)).width == 16


def test_convert_web_images_repairs_project(tmp_path):
    name = "page001_img00_occ00_x10_y10_w160_h120.jpx"
    png_name = name.replace(".jpx", ".png")
    images_dir = tmp_path / "data/markdown/images/book"
    assets_dir = tmp_path / "docs/src/assets/extracted/book"
    images_dir.mkdir(parents=True)
    assets_dir.mkdir(parents=True)
    (images_dir / name).write_bytes(jpeg2000_bytes())
    (assets_dir / name).write_bytes(jpeg2000_bytes())
    (images_dir / "keep.png").write_bytes(b"png")
    (images_dir / "manifest.json").write_text(
        json.dumps({"images": [{"filename": name, "path": f"images/book/{name}", "file_size": 1}]}),
        encoding="utf-8",
    )
    reference = f"![第 1 頁插圖](../../../assets/extracted/book/{name})"
    chapter = tmp_path / "docs/src/content/docs/rules/index.md"
    draft = tmp_path / ".state/translate/drafts/docs/src/content/docs/rules/index.md"
    for path in (chapter, draft):
        path.parent.mkdir(parents=True)
        path.write_text(f"---\ntitle: 規則\n---\n\n{reference}\n", encoding="utf-8")

    assert convert_main([], project_root=tmp_path) == 0

    assert sorted(p.name for p in images_dir.iterdir()) == ["keep.png", "manifest.json", png_name]
    assert [p.name for p in assets_dir.iterdir()] == [png_name]
    entry = json.loads((images_dir / "manifest.json").read_text(encoding="utf-8"))["images"][0]
    assert entry["filename"] == png_name
    assert entry["path"] == f"images/book/{png_name}"
    assert entry["file_size"] == (images_dir / png_name).stat().st_size
    for path in (chapter, draft):
        text = path.read_text(encoding="utf-8")
        assert ".jpx" not in text
        assert f"assets/extracted/book/{png_name})" in text


def test_convert_web_images_dry_run_leaves_files(tmp_path, capsys):
    assets_dir = tmp_path / "docs/src/assets/extracted/book"
    assets_dir.mkdir(parents=True)
    (assets_dir / "a.jpx").write_bytes(jpeg2000_bytes())

    assert convert_main(["--dry-run"], project_root=tmp_path) == 0

    assert (assets_dir / "a.jpx").exists()
    assert "1 張圖片需轉成 PNG" in capsys.readouterr().out
