"""
opendataloader-pdf 引擎封裝

提供可用性偵測、PDF 轉 Markdown 呼叫、頁碼標記後處理。
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

_PAGE_SEPARATOR_TEMPLATE = "<!--ODL-PAGE-%page-number%-->"
_PAGE_SEPARATOR_RE = re.compile(r"<!--ODL-PAGE-(\d+)-->")

_availability_cache: dict[str, object] | None = None


def check_availability() -> dict[str, object]:
    """檢查 opendataloader-pdf 套件和 Java 執行環境是否可用。"""
    global _availability_cache
    if _availability_cache is not None:
        return _availability_cache

    result: dict[str, object] = {
        "available": False,
        "package_installed": False,
        "java_available": False,
        "java_version": None,
        "reason": None,
    }

    try:
        import opendataloader_pdf  # noqa: F401

        result["package_installed"] = True
    except ImportError:
        result["reason"] = "opendataloader-pdf 套件未安裝"
        _availability_cache = result
        return result

    java_bin = shutil.which("java")
    if java_bin is None:
        result["reason"] = "Java 未安裝"
        _availability_cache = result
        return result

    try:
        proc = subprocess.run(
            ["java", "-version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
        version_output = proc.stderr or proc.stdout
        match = re.search(r'"(\d+)[\._]', version_output)
        if match:
            major = int(match.group(1))
            result["java_version"] = major
            if major >= 11:
                result["java_available"] = True
            else:
                result["reason"] = f"Java 版本 {major} 低於最低要求 11"
                _availability_cache = result
                return result
        else:
            result["reason"] = f"無法解析 Java 版本：{version_output[:100]}"
            _availability_cache = result
            return result
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        result["reason"] = f"Java 版本檢查失敗：{exc}"
        _availability_cache = result
        return result

    result["available"] = True
    result["reason"] = None
    _availability_cache = result
    return result


def is_available() -> bool:
    """快速檢查 opendataloader 是否可用。"""
    return bool(check_availability()["available"])


def convert_pdf_to_markdown(pdf_path: Path, output_dir: Path) -> str | None:
    """使用 opendataloader-pdf fast 模式將 PDF 轉為 Markdown。

    回傳完整 Markdown 文字內容，失敗時回傳 None。
    """
    import opendataloader_pdf

    with tempfile.TemporaryDirectory() as tmp_dir:
        opendataloader_pdf.convert(
            input_path=[str(pdf_path)],
            output_dir=tmp_dir,
            format="markdown",
            quiet=True,
        )

        md_files = list(Path(tmp_dir).glob("**/*.md"))
        if not md_files:
            print("⚠️  opendataloader 未產出 Markdown 檔案")
            return None

        return md_files[0].read_text(encoding="utf-8")


def split_pages_by_marker(content: str) -> list[tuple[int, str]]:
    """依 `_PAGE_SEPARATOR_RE` 標記切分整份 Markdown 內容為逐頁清單。"""
    matches = list(_PAGE_SEPARATOR_RE.finditer(content))
    pages: list[tuple[int, str]] = []
    for i, match in enumerate(matches):
        page_num = int(match.group(1))
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        pages.append((page_num, content[start:end].strip()))
    return pages


def convert_pdf_pages(pdf_path: Path) -> list[tuple[int, str]]:
    """逐頁提取 PDF 並回傳 (page_num, text) 列表。

    整份 PDF 只呼叫一次 opendataloader（單一 Java 行程），
    透過 markdown_page_separator 標記頁碼後再切分，
    以產生與其他引擎一致的 <!-- PAGE N --> 標記，且不隨頁數增加而多次啟動 Java。
    """
    import opendataloader_pdf

    with tempfile.TemporaryDirectory() as tmp_dir:
        opendataloader_pdf.convert(
            input_path=[str(pdf_path)],
            output_dir=tmp_dir,
            format="markdown",
            quiet=True,
            markdown_page_separator=_PAGE_SEPARATOR_TEMPLATE,
        )

        md_files = list(Path(tmp_dir).glob("**/*.md"))
        if not md_files:
            print("⚠️  opendataloader 未產出 Markdown 檔案")
            return []

        content = md_files[0].read_text(encoding="utf-8")

    return split_pages_by_marker(content)


def write_pages_file(
    pages: list[tuple[int, str]],
    output_file: Path,
) -> Path:
    """將頁面列表寫入含 <!-- PAGE N --> 標記的檔案。"""
    with output_file.open("w", encoding="utf-8") as handle:
        for page_num, text in pages:
            handle.write(f"\n\n<!-- PAGE {page_num} -->\n\n{text}")

    return output_file
