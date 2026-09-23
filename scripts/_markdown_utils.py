"""Markdown 文字處理共用工具函式。"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from urllib.parse import unquote

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LINKED_MARKDOWN_IMAGE_RE = re.compile(r"\[!\[[^\]]*]\([^)]+\)]\([^)]+\)")
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*]\([^)]+\)")
MARKDOWN_HEADING_RE = re.compile(r"^#{1,3}\s+\S")
ARTIFACT_HEADING_RE = re.compile(r"^#{1,6}[ \t]*\d*[ \t]*$", re.MULTILINE)
LIST_ITEM_MARKER_RE = re.compile(r"^[ \t]*(?:[-+*]|\d+[.)])[ \t]+")
BLOCK_HEADING_RE = re.compile(r"^#{1,6}(?:[ \t]|$)")
_TERMINAL_PUNCTUATION = ".!?"
_TRAILING_CLOSERS = "'\"’”)]}"
_INTERNAL_CAP_ARTIFACT_RE = re.compile(r"[a-z][A-Z]")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_TRAILING_PAGE_NUMBER_RE = re.compile(r"[.!?]['\"’”)]*\s+\d{1,4}\s*$")
_MIN_PARAGRAPH_CONTINUATION_PREV_WORDS = 4
_MIN_PARAGRAPH_CONTINUATION_NEXT_WORDS = 3


# ---------------------------------------------------------------------------
# Functions from extract_pdf.py
# ---------------------------------------------------------------------------


def strip_markdown_images(text: str) -> str:
    """移除 Markdown 圖片語法，避免後續依 manifest 再插圖時重複。"""
    stripped = LINKED_MARKDOWN_IMAGE_RE.sub("", text)
    stripped = MARKDOWN_IMAGE_RE.sub("", stripped)
    stripped = re.sub(r"\n{3,}", "\n\n", stripped)
    return stripped.strip()


def extract_markdown_image_targets(text: str) -> list[str]:
    """擷取 Markdown 中的圖片路徑。"""
    targets: list[str] = []
    for match in MARKDOWN_IMAGE_RE.finditer(text):
        target = match.group(0).split("](", 1)[1].rsplit(")", 1)[0].strip()
        target = target.split(maxsplit=1)[0].strip("<>")
        if target:
            targets.append(unquote(target))
    return targets


def strip_artifact_headings(text: str) -> str:
    """移除純數字或空白的 Markdown 標題（頁碼裝飾產物，與語言無關）。

    OpenDataLoader 等來源可能把頁面折角頁碼或裝飾線渲染成獨立標題
    （如 ``# 33``、``##``），這類標題不含實質內容，可安全移除。
    此規則不涉及語言，翻譯後的 Markdown 也適用。
    """
    cleaned = ARTIFACT_HEADING_RE.sub("", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


@dataclass(frozen=True)
class _TextBlock:
    """一段以空白行分隔的區塊，`start`／`end` 為 0-based、含首尾的行號。"""

    start: int
    end: int
    text: str


def _iter_text_blocks(lines: Sequence[str]) -> Iterator[_TextBlock]:
    """依空白行切分區塊；`lines` 須為 `text.split("\\n")` 的結果，以保留結尾換行資訊。"""
    start: int | None = None
    buf: list[str] = []
    for index, line in enumerate(lines):
        if line.strip() == "":
            if buf:
                yield _TextBlock(start, index - 1, "\n".join(buf))
                buf = []
                start = None
            continue
        if start is None:
            start = index
        buf.append(line)
    if buf:
        yield _TextBlock(start, len(lines) - 1, "\n".join(buf))


def _block_kind(block_text: str) -> str:
    first_line = block_text.split("\n", 1)[0]
    if BLOCK_HEADING_RE.match(first_line):
        return "heading"
    if LIST_ITEM_MARKER_RE.match(first_line):
        return "list_item"
    return "paragraph"


def _ends_with_terminal_punctuation(block_text: str) -> bool:
    stripped = block_text.rstrip()
    while stripped and stripped[-1] in _TRAILING_CLOSERS:
        stripped = stripped[:-1]
    return bool(stripped) and stripped[-1] in _TERMINAL_PUNCTUATION


def find_list_continuation_items(text: str) -> list[int]:
    """找出被誤判為清單項目的斷行續句，回傳每個項目起始行號（1-based）。

    OpenDataLoader 有時會把換行後的段落續句渲染成獨立的 Markdown 清單項目
    （例如 ``...agreed\\n\\n- to during the Prelude phase)...``）。判斷條件：
    前一個非空白區塊是不以句末標點結尾的一般段落（非清單項目、非標題），
    且目前區塊是以小寫字母開頭的清單項目。真正的清單不受影響。
    """
    lines = text.split("\n")
    blocks = list(_iter_text_blocks(lines))
    matches: list[int] = []
    for prev_block, block in zip(blocks, blocks[1:]):
        first_line = block.text.split("\n", 1)[0]
        marker_match = LIST_ITEM_MARKER_RE.match(first_line)
        if not marker_match:
            continue
        item_text = first_line[marker_match.end() :]
        if not item_text or not item_text[0].islower():
            continue
        if _block_kind(prev_block.text) != "paragraph":
            continue
        if _ends_with_terminal_punctuation(prev_block.text):
            continue
        matches.append(block.start + 1)
    return matches


def _splice_block_into_previous(
    lines: list[str],
    blocks: list[_TextBlock],
    block_index: int,
    first_text: str,
    separator: str,
) -> str:
    """將 `blocks[block_index]` 併回 `blocks[block_index - 1]`，回傳合併後的完整文字。

    `first_text` 是欲併入前一區塊尾端的文字（清單項目已去除 marker，一般段落則是整個
    第一行）；該區塊其餘行原樣保留。呼叫端負責驗證 `block_index` 有效且非首個區塊。
    """
    item_block = blocks[block_index]
    prev_block = blocks[block_index - 1]
    item_rest_lines = item_block.text.split("\n")[1:]

    merged_last_line = lines[prev_block.end].rstrip() + separator + first_text
    new_lines = (
        lines[: prev_block.end]
        + [merged_last_line]
        + item_rest_lines
        + lines[item_block.end + 1 :]
    )
    return "\n".join(new_lines)


def merge_list_continuation_at(text: str, item_start_line: int, separator: str = " ") -> str:
    """將起始於 `item_start_line`（1-based）的清單項目併回前一個區塊。

    `separator` 是併回時項目文字與前一區塊之間插入的字元；中文譯文併合時應傳入
    空字串（不加空格），英文原文併合則使用單一空格。
    """
    lines = text.split("\n")
    blocks = list(_iter_text_blocks(lines))
    block_index = next(
        (index for index, block in enumerate(blocks) if block.start == item_start_line - 1),
        None,
    )
    if block_index is None:
        raise ValueError(f"No block starts at line {item_start_line}")

    item_block = blocks[block_index]
    first_line = item_block.text.split("\n", 1)[0]
    marker_match = LIST_ITEM_MARKER_RE.match(first_line)
    if not marker_match:
        raise ValueError(f"Block at line {item_start_line} is not a list item")
    if block_index == 0:
        raise ValueError(f"No preceding block to merge line {item_start_line} into")

    item_first_text = first_line[marker_match.end() :]
    return _splice_block_into_previous(lines, blocks, block_index, item_first_text, separator)


def merge_list_continuations(text: str) -> tuple[str, int]:
    """合併所有斷行續句誤判清單項目，回傳 (合併後文字, 合併次數)。與語言相關（依英文小寫判斷）。"""
    count = 0
    while True:
        items = find_list_continuation_items(text)
        if not items:
            break
        text = merge_list_continuation_at(text, items[0], separator=" ")
        count += 1
    return text, count


# ---------------------------------------------------------------------------
# Paragraph-to-paragraph continuation breaks (sibling of the list-item case
# above): OpenDataLoader sometimes splits one sentence across two plain
# paragraph blocks instead of mangling it into a list item.
# ---------------------------------------------------------------------------


def _is_decorative_artifact(text: str) -> bool:
    """判斷文字是否像裝飾性標題／目錄／表格標籤產物，而非一般段落文字。

    OpenDataLoader 對美術字型（如全大寫小型大寫字）常會輸出全大寫，或大小寫字母交錯
    的產物（例如 ``basiC``、``ConTenTs``），這類文字不是續句，與語言無關。
    """
    return bool(text) and (text.isupper() or bool(_INTERNAL_CAP_ARTIFACT_RE.search(text)))


def find_paragraph_continuation_breaks(text: str) -> tuple[list[int], list[int]]:
    """找出段落被誤斷為兩個區塊的續句，回傳 (可合併的區塊起始行號, 疑似但不確定的區塊起始行號)。

    兩者皆為 1-based 行號，依前一個區塊判斷：前一個非空白區塊是不以句末標點結尾的一般
    段落（非清單項目、非標題），且目前區塊也是以小寫字母開頭的一般段落。

    以下情形視為明確不是續句而略過，不回報：前一或目前區塊字數過少，或呈現裝飾性標題／
    目錄／表格標籤產物（全大寫或大小寫交錯，見 `_is_decorative_artifact`）。

    以下情形視為結構上像續句，但含有殘留噪音而不安全直接合併，回報為疑似案例而非直接
    合併：目前區塊已自成一個以句末標點結尾的完整單位、卻仍內含控制字元殘留（代表它
    除了續句本身之外，還吸收了後面另一個被壓縮在同一行的清單項目，非單純的段落續
    句），或目前區塊尾端疑似殘留頁碼數字。若目前區塊本身仍未以句末標點結尾（本身還
    要再往下續接），則其中殘留的控制字元不影響這一次的合併判斷。
    """
    lines = text.split("\n")
    blocks = list(_iter_text_blocks(lines))
    merges: list[int] = []
    ambiguous: list[int] = []
    for prev_block, block in zip(blocks, blocks[1:]):
        first_line = block.text.split("\n", 1)[0]
        if LIST_ITEM_MARKER_RE.match(first_line):
            continue
        if _block_kind(block.text) != "paragraph":
            continue
        if not first_line or not first_line[0].islower():
            continue
        if _block_kind(prev_block.text) != "paragraph":
            continue
        if _ends_with_terminal_punctuation(prev_block.text):
            continue

        if (
            len(prev_block.text.split()) < _MIN_PARAGRAPH_CONTINUATION_PREV_WORDS
            or len(first_line.split()) < _MIN_PARAGRAPH_CONTINUATION_NEXT_WORDS
            or _is_decorative_artifact(prev_block.text)
            or _is_decorative_artifact(first_line)
        ):
            continue

        block_is_self_contained = _ends_with_terminal_punctuation(block.text)
        if (
            block_is_self_contained and _CONTROL_CHAR_RE.search(block.text)
        ) or _TRAILING_PAGE_NUMBER_RE.search(block.text):
            ambiguous.append(block.start + 1)
            continue

        merges.append(block.start + 1)
    return merges, ambiguous


def merge_paragraph_continuation_at(text: str, block_start_line: int, separator: str = " ") -> str:
    """將起始於 `block_start_line`（1-based）的一般段落區塊併回前一個區塊。

    `separator` 是併回時該區塊文字與前一區塊之間插入的字元；中文譯文併合時應傳入空
    字串（不加空格），英文原文併合則使用單一空格。
    """
    lines = text.split("\n")
    blocks = list(_iter_text_blocks(lines))
    block_index = next(
        (index for index, block in enumerate(blocks) if block.start == block_start_line - 1),
        None,
    )
    if block_index is None:
        raise ValueError(f"No block starts at line {block_start_line}")
    if block_index == 0:
        raise ValueError(f"No preceding block to merge line {block_start_line} into")

    first_line = blocks[block_index].text.split("\n", 1)[0]
    return _splice_block_into_previous(lines, blocks, block_index, first_line, separator)


def merge_paragraph_continuations(text: str) -> tuple[str, int, list[int]]:
    """合併所有段落斷行續句，回傳 (合併後文字, 合併次數, 疑似案例起始行號列表)。

    與語言相關（依英文小寫判斷）；疑似案例（含控制字元殘留或疑似頁碼殘留）不會被合併。
    """
    count = 0
    ambiguous: list[int] = []
    while True:
        merges, ambiguous = find_paragraph_continuation_breaks(text)
        if not merges:
            break
        text = merge_paragraph_continuation_at(text, merges[0], separator=" ")
        count += 1
    return text, count, ambiguous


def find_paragraph_block_starts(
    text: str, lo_line: int = 1, hi_line: int | None = None
) -> list[int]:
    """回傳 `[lo_line, hi_line)` 範圍內（1-based，`hi_line` 為 `None` 代表到檔尾）
    所有一般段落區塊的起始行號，依出現順序排列。

    供翻譯側續句合併工具在結構錨點之間，依序對齊來源與譯文段落區塊的位置。
    """
    lines = text.split("\n")
    blocks = list(_iter_text_blocks(lines))
    return [
        block.start + 1
        for block in blocks
        if block.start + 1 >= lo_line
        and (hi_line is None or block.start + 1 < hi_line)
        and _block_kind(block.text) == "paragraph"
    ]


def split_markdown_sections(text: str) -> list[str]:
    """依 heading 將 Markdown 切成較細的虛擬頁碼區塊。"""
    lines = text.splitlines()
    sections: list[str] = []
    current: list[str] = []

    for line in lines:
        if MARKDOWN_HEADING_RE.match(line) and any(part.strip() for part in current):
            section = "\n".join(current).strip()
            if section:
                sections.append(section)
            current = [line]
            continue
        current.append(line)

    if any(part.strip() for part in current):
        section = "\n".join(current).strip()
        if section:
            sections.append(section)

    return sections or [text.strip()]


# ---------------------------------------------------------------------------
# Functions from split_chapters.py
# ---------------------------------------------------------------------------


def clean_content(text: str, patterns: list[str]) -> str:
    """清理內容"""
    for pattern in patterns:
        text = re.sub(pattern, "", text)
    # 移除多餘空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def count_page_text_tokens(text: str) -> int:
    """估算頁面文字量。"""
    return len(re.findall(r"\S+", text))


# ---------------------------------------------------------------------------
# Shared chapters.json 'files' tree walker
# ---------------------------------------------------------------------------


def iter_leaves(files: dict, path_prefix: str = "") -> Iterator[tuple[str, dict]]:
    """Recursively walk a normalized chapters.json ``files`` dict.

    Yields ``(key_path, entry)`` for each leaf node (an entry with ``pages``),
    in ``order``-sorted sequence, matching the sibling order used when
    writing files to disk. ``key_path`` joins nested group keys with ``/``.

    Raises:
        ValueError: an entry has neither ``pages`` nor ``files``.
    """
    for key, entry in sorted(files.items(), key=lambda kv: kv[1].get("order", 9999)):
        key_path = f"{path_prefix}/{key}" if path_prefix else key
        if "pages" in entry:
            yield key_path, entry
        elif "files" in entry:
            yield from iter_leaves(entry["files"], key_path)
        else:
            raise ValueError(f"Invalid entry '{key}': must have 'pages' or 'files'")


# ---------------------------------------------------------------------------
# Functions from generate_nav.py
# ---------------------------------------------------------------------------


def yaml_safe(value: str) -> str:
    """Wrap YAML-sensitive scalars in double quotes."""
    if any(
        ch in value
        for ch in (
            ":",
            "：",
            "#",
            "{",
            "}",
            "[",
            "]",
            ",",
            "&",
            "*",
            "?",
            "|",
            "-",
            "<",
            ">",
            "=",
            "!",
            "%",
            "@",
            "`",
        )
    ):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value
