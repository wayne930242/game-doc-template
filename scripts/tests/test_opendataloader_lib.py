from __future__ import annotations

import sys
from pathlib import Path

from _opendataloader_lib import (
    _PAGE_SEPARATOR_TEMPLATE,
    convert_pdf_pages,
    split_pages_by_marker,
)


def test_split_pages_by_marker_splits_in_order():
    content = "<!--ODL-PAGE-1-->\np1\n<!--ODL-PAGE-2-->\np2\n<!--ODL-PAGE-3-->\np3"
    assert split_pages_by_marker(content) == [(1, "p1"), (2, "p2"), (3, "p3")]


def test_split_pages_by_marker_strips_surrounding_whitespace():
    content = "<!--ODL-PAGE-1-->\n\n  p1  \n\n<!--ODL-PAGE-2-->\n\np2\n"
    assert split_pages_by_marker(content) == [(1, "p1"), (2, "p2")]


def test_split_pages_by_marker_no_markers_returns_empty():
    assert split_pages_by_marker("single blob of text, no markers") == []


def test_split_pages_by_marker_handles_empty_pages():
    content = "<!--ODL-PAGE-1-->\n<!--ODL-PAGE-2-->\np2"
    assert split_pages_by_marker(content) == [(1, ""), (2, "p2")]


# ---------------------------------------------------------------------------
# convert_pdf_pages: single opendataloader invocation for the whole PDF
# ---------------------------------------------------------------------------


class _FakeOpendataloaderPdf:
    """Fakes opendataloader_pdf.convert() to return one page-separated file."""

    def __init__(self, content: str):
        self.calls: list[dict] = []
        self._content = content

    def convert(self, input_path, output_dir, format, quiet, markdown_page_separator=None):
        self.calls.append(
            {
                "input_path": input_path,
                "markdown_page_separator": markdown_page_separator,
            }
        )
        out_dir = Path(output_dir)
        stem = Path(input_path[0]).stem
        (out_dir / f"{stem}.md").write_text(self._content, encoding="utf-8")


def test_convert_pdf_pages_calls_opendataloader_exactly_once(monkeypatch, tmp_path):
    content = "\n".join(
        _PAGE_SEPARATOR_TEMPLATE.replace("%page-number%", str(n)) + f"\npage {n} text"
        for n in range(1, 6)
    )
    fake_odl = _FakeOpendataloaderPdf(content)
    monkeypatch.setitem(sys.modules, "opendataloader_pdf", fake_odl)

    pdf_path = tmp_path / "book.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    result = convert_pdf_pages(pdf_path)

    assert len(fake_odl.calls) == 1
    assert fake_odl.calls[0]["input_path"] == [str(pdf_path)]
    assert fake_odl.calls[0]["markdown_page_separator"] == _PAGE_SEPARATOR_TEMPLATE
    assert [page_num for page_num, _ in result] == [1, 2, 3, 4, 5]
    assert [text for _, text in result] == [f"page {n} text" for n in range(1, 6)]


def test_convert_pdf_pages_missing_output_returns_empty(monkeypatch, tmp_path):
    class _NoOutputOdl:
        def convert(self, input_path, output_dir, format, quiet, markdown_page_separator=None):
            pass  # 模擬轉換失敗，未產生任何 .md 檔

    monkeypatch.setitem(sys.modules, "opendataloader_pdf", _NoOutputOdl())

    pdf_path = tmp_path / "book.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    assert convert_pdf_pages(pdf_path) == []
