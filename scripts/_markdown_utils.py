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
ARTIFACT_HEADING_RE = re.compile(r"^#{1,6}[ \t]*(?:\d*|[A-Za-z])[ \t]*$", re.MULTILINE)
LIST_ITEM_MARKER_RE = re.compile(r"^[ \t]*(?:[-+*]|\d+[.)])[ \t]+")
BLOCK_HEADING_RE = re.compile(r"^#{1,6}(?:[ \t]|$)")
_TERMINAL_PUNCTUATION = ".!?"
_TRAILING_CLOSERS = "'\"’”)]}"
_INTERNAL_CAP_ARTIFACT_RE = re.compile(r"[a-z][A-Z]")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_TRAILING_PAGE_NUMBER_RE = re.compile(r"(?P<keep>[.!?]['\"’”)]*)\s+\d{1,4}\s*$")
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
    """移除純數字、空白，或單一字母的 Markdown 標題（頁碼裝飾產物，與語言無關）。

    OpenDataLoader 等來源可能把頁面折角頁碼、裝飾線，或版面雜訊（如單一字母的
    首字放大裝飾）渲染成獨立標題（如 ``# 33``、``##``、``###### a``），這類標題
    不含實質內容，可安全移除；兩個以上字母的標題一律視為真實標題保留。
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


def _is_frontmatter_block(text: str) -> bool:
    """判斷區塊是否為 YAML frontmatter（Astro/Starlight 內容檔開頭的 `---` 區塊）。

    frontmatter 區塊本身不以句末標點結尾，若不排除會被誤判為段落續句的前一區塊，
    把 frontmatter 結尾的 `---` 與下一個區塊的文字黏在同一行（見 kedamono-species/index.md
    的實際案例：``--- with these other weaker creatures...``），破壞 YAML 語法。
    """
    return text.startswith("---\n") and text.rstrip("\n").endswith("\n---")


def _is_eligible_continuation_pair(prev_text: str, block: _TextBlock) -> bool:
    """判斷 `block` 是否結構上像是 `prev_text` 的段落續句（不含殘留噪音的疑似判斷）。

    條件：前一個區塊是不以句末標點結尾的一般段落（非清單項目、非標題、非 frontmatter），
    目前區塊也是以小寫字母開頭的一般段落，且雙方字數足夠、皆非裝飾性標題／目錄／表格
    標籤產物。

    供 `find_paragraph_continuation_breaks` 與符號字型裝飾字元轉換（見
    `convert_symbol_glyph_ornaments`）共用同一組「這兩個區塊結構上像續句」判斷，
    避免各自重複一套字數與裝飾產物門檻。
    """
    first_line = block.text.split("\n", 1)[0]
    if LIST_ITEM_MARKER_RE.match(first_line):
        return False
    if _block_kind(block.text) != "paragraph":
        return False
    if not first_line or not first_line[0].islower():
        return False
    if _block_kind(prev_text) != "paragraph":
        return False
    if _is_frontmatter_block(prev_text):
        return False
    if _ends_with_terminal_punctuation(prev_text):
        return False
    if (
        len(prev_text.split()) < _MIN_PARAGRAPH_CONTINUATION_PREV_WORDS
        or len(first_line.split()) < _MIN_PARAGRAPH_CONTINUATION_NEXT_WORDS
        or _is_decorative_artifact(prev_text)
        or _is_decorative_artifact(first_line)
    ):
        return False
    return True


def find_paragraph_continuation_breaks(text: str) -> tuple[list[int], list[int]]:
    """找出段落被誤斷為兩個區塊的續句，回傳 (可合併的區塊起始行號, 疑似但不確定的區塊起始行號)。

    兩者皆為 1-based 行號；區塊配對是否結構上像續句見 `_is_eligible_continuation_pair`。

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
        if not _is_eligible_continuation_pair(prev_block.text, block):
            continue

        block_is_self_contained = _ends_with_terminal_punctuation(block.text)
        if (
            block_is_self_contained and _CONTROL_CHAR_RE.search(block.text)
        ) or _TRAILING_PAGE_NUMBER_RE.search(block.text):
            ambiguous.append(block.start + 1)
            continue

        merges.append(block.start + 1)
    return merges, ambiguous


def strip_trailing_page_number_residue(text: str) -> tuple[str, int]:
    """移除段落續句區塊尾端殘留的頁碼數字，回傳 (清理後文字, 清除次數)。

    OpenDataLoader 有時會把頁面折角頁碼黏在段落續句的句尾（例如
    ``"...are interesting when they happen. 225"``），使得
    `find_paragraph_continuation_breaks` 將其回報為疑似案例而不合併。僅處理該函式
    會判定為「結構上像續句」的區塊配對（見 `_is_eligible_continuation_pair`），避免
    誤刪段落中本來就以數字結尾的合法內容。
    """
    count = 0
    while True:
        lines = text.split("\n")
        blocks = list(_iter_text_blocks(lines))
        target_index = next(
            (
                index
                for index in range(1, len(blocks))
                if _is_eligible_continuation_pair(blocks[index - 1].text, blocks[index])
                and _TRAILING_PAGE_NUMBER_RE.search(blocks[index].text)
            ),
            None,
        )
        if target_index is None:
            break
        block = blocks[target_index]
        new_block_text = _TRAILING_PAGE_NUMBER_RE.sub(r"\g<keep>", block.text)
        new_lines = lines[: block.start] + new_block_text.split("\n") + lines[block.end + 1 :]
        text = "\n".join(new_lines)
        count += 1
    return text, count


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


# ---------------------------------------------------------------------------
# Symbol-font decorative ornaments (e.g. a Wingdings glyph extracted as its raw
# code point, such as U+0094) used either as a bullet marker or to decorate a
# subsection title.
# ---------------------------------------------------------------------------


def _flatten_block_text(block_text: str) -> str:
    """將區塊內部換行（單純折行）收攏成單一空格，回傳一行文字。"""
    return " ".join(block_text.split())


def _build_symbol_glyph_pattern(glyphs: Sequence[str]) -> re.Pattern[str] | None:
    escaped = [re.escape(glyph) for glyph in glyphs if glyph]
    if not escaped:
        return None
    return re.compile("|".join(escaped))


def find_glyph_block_starts(
    text: str, glyphs: Sequence[str], lo_line: int = 1, hi_line: int | None = None
) -> list[int]:
    """回傳 `[lo_line, hi_line)` 範圍內（1-based，`hi_line` 為 `None` 代表到檔尾）
    所有含裝飾符號字元的區塊起始行號，依出現順序排列。

    供翻譯側工具在結構錨點之間，依裝飾符號殘留字元本身的出現順序，將英文來源的分類
    決策對齊到已翻譯文字中的對應區塊；比起依段落位置計數對齊，能承受譯文段落數量因
    翻譯時重新斷句、合併而與來源不同的情況。
    """
    glyph_pattern = _build_symbol_glyph_pattern(glyphs)
    if glyph_pattern is None:
        return []
    lines = text.split("\n")
    blocks = list(_iter_text_blocks(lines))
    return [
        block.start + 1
        for block in blocks
        if block.start + 1 >= lo_line
        and (hi_line is None or block.start + 1 < hi_line)
        and glyph_pattern.search(_flatten_block_text(block.text))
    ]


@dataclass(frozen=True)
class _GlyphBlockDecision:
    """單一區塊的裝飾符號分類結果，供 `convert_symbol_glyph_ornaments` 與
    `find_symbol_glyph_block_decisions` 共用同一套分類邏輯。"""

    kind: str  # "unchanged" | "drop" | "title" | "list_singleton" | "list_split"
    line: int  # 區塊起始行號（1-based）
    leading: str = ""  # list_split 專用：第一個符號前的文字
    segments: tuple[str, ...] = ()  # 依符號出現順序排列的項目文字
    deferred_tail: bool = False  # list_split 專用：最後一段疑似跨區塊續句，未收斂
    level: int = 0  # title 專用：標題層級


def _classify_glyph_blocks(
    blocks: Sequence[_TextBlock], glyphs: Sequence[str]
) -> list[_GlyphBlockDecision]:
    """依序走訪區塊，為每個區塊產生分類決策；規則見 `convert_symbol_glyph_ornaments`。"""
    glyph_pattern = _build_symbol_glyph_pattern(glyphs)
    if glyph_pattern is None:
        return [_GlyphBlockDecision(kind="unchanged", line=block.start + 1) for block in blocks]

    ornament_adjacent = [
        bool(glyph_pattern.search(_flatten_block_text(block.text)))
        or _block_kind(block.text) == "list_item"
        for block in blocks
    ]

    decisions: list[_GlyphBlockDecision] = []
    last_heading_level: int | None = None

    for index, block in enumerate(blocks):
        line = block.start + 1

        if _block_kind(block.text) == "heading":
            first_line = block.text.split("\n", 1)[0]
            last_heading_level = len(first_line) - len(first_line.lstrip("#"))
            decisions.append(_GlyphBlockDecision(kind="unchanged", line=line))
            continue

        flat = _flatten_block_text(block.text)
        matches = list(glyph_pattern.finditer(flat))
        if not matches:
            decisions.append(_GlyphBlockDecision(kind="unchanged", line=line))
            continue

        occurrences = [match.start() for match in matches]
        leading = flat[: occurrences[0]].strip()
        segments: list[str] = []
        for occ_index, match in enumerate(matches):
            seg_end = occurrences[occ_index + 1] if occ_index + 1 < len(occurrences) else len(flat)
            segments.append(flat[match.end() : seg_end].strip())

        is_singleton = len(occurrences) == 1 and occurrences[0] == 0 and not leading

        if is_singleton:
            item_text = segments[0]
            if not item_text:
                # A bare ornament with no accompanying text (e.g. a decorative
                # divider row) carries no content worth keeping; drop it.
                decisions.append(_GlyphBlockDecision(kind="drop", line=line))
                continue
            prev_is_ornament = index > 0 and ornament_adjacent[index - 1]
            next_is_ornament = index + 1 < len(blocks) and ornament_adjacent[index + 1]
            prev_block = blocks[index - 1] if index > 0 else None
            prev_is_terminal_paragraph = (
                prev_block is not None
                and _block_kind(prev_block.text) == "paragraph"
                and _ends_with_terminal_punctuation(prev_block.text)
            )
            if not prev_is_ornament and not next_is_ornament and prev_is_terminal_paragraph:
                level = min((last_heading_level or 1) + 1, 6)
                decisions.append(
                    _GlyphBlockDecision(
                        kind="title", line=line, segments=(item_text,), level=level
                    )
                )
            else:
                decisions.append(
                    _GlyphBlockDecision(kind="list_singleton", line=line, segments=(item_text,))
                )
            continue

        if not leading and not any(segments):
            # A row of repeated ornaments with no accompanying text anywhere
            # (e.g. "\x94 \x94 \x94" as a decorative section divider) carries no
            # content worth keeping; drop the whole block, same as a bare
            # single-ornament divider row.
            decisions.append(_GlyphBlockDecision(kind="drop", line=line))
            continue

        next_block = blocks[index + 1] if index + 1 < len(blocks) else None
        deferred_tail = (
            bool(segments)
            and segments[-1]
            and not _ends_with_terminal_punctuation(segments[-1])
            and next_block is not None
            and _is_eligible_continuation_pair(segments[-1], next_block)
        )
        decisions.append(
            _GlyphBlockDecision(
                kind="list_split",
                line=line,
                leading=leading,
                segments=tuple(segments),
                deferred_tail=deferred_tail,
            )
        )

    return decisions


def convert_symbol_glyph_ornaments(
    text: str, glyphs: Sequence[str]
) -> tuple[str, dict[str, int]]:
    """將裝飾性符號字型字元（如 Wingdings 字元被輸出成原始控制字元）轉換為結構化 Markdown。

    `glyphs` 是視為裝飾符號的字元清單（來自 style-decisions.json 的
    `document_format.symbol_glyphs`，與浮水印設定同樣的設定模式），與字型無關，僅依
    字元本身比對。

    判斷規則：
    - 區塊內符號出現一次以上，或出現位置並非區塊開頭，一律視為清單項目標記：依每次
      出現位置切分成多個清單項目（符號前若還有文字，該文字原樣保留為一般段落）。若
      區塊內每次符號出現的前後都沒有任何文字（例如連續多個符號組成的裝飾分隔列），
      則視為純裝飾分隔列，整個區塊直接刪除（計入 `counts["dropped"]`）。
    - 區塊開頭且僅出現一次的「單一符號」區塊，若前一或後一個區塊本身也含有符號
      （不論在區塊開頭或內文，代表它與同一組清單項目相鄰），仍視為清單項目。
    - 否則，若前一個區塊是以句末標點結尾的一般段落，視為裝飾小節標題：去除符號，轉換
      成 Markdown 標題，層級為前一個標題層級 + 1（上限六層；找不到前一個標題時預設
      層級為二）。此規則的依據：小節標題緊接在完整段落之後，是文件敘事的自然轉折；
      清單項目則多半緊接在說明性短句（不以句末標點結尾的圖說／提示句，或另一個清單
      項目）之後。
    - 其餘情況（例如前一區塊是不以句末標點結尾的簡短說明文字）預設視為清單項目，
      因為裝飾標題必須緊接在完整段落之後，這是較安全的預設值。

    區塊內最後一段若不以句末標點結尾，且與下一個區塊構成合法的段落續句配對（見
    `_is_eligible_continuation_pair`），則保留符號原樣、不轉換，留待段落續句合併把
    它與下一個區塊接回完整後，再次呼叫本函式收斂；避免把跨區塊斷行的清單項目攔腰
    轉換成殘缺內容。呼叫端應搭配 `clean_symbol_glyph_ornaments` 反覆執行至收斂。
    """
    counts = {
        "list_items_from_split": 0,
        "list_items_from_singleton": 0,
        "titles": 0,
        "dropped": 0,
    }
    if _build_symbol_glyph_pattern(glyphs) is None:
        return text, counts

    lines = text.split("\n")
    blocks = list(_iter_text_blocks(lines))
    if not blocks:
        return text, counts

    decisions = _classify_glyph_blocks(blocks, glyphs)

    new_block_texts: list[list[str]] = []
    changed = False

    for block, decision in zip(blocks, decisions):
        if decision.kind == "unchanged":
            new_block_texts.append([block.text])
        elif decision.kind == "drop":
            new_block_texts.append([])
            counts["dropped"] += 1
            changed = True
        elif decision.kind == "title":
            new_block_texts.append([f"{'#' * decision.level} {decision.segments[0]}"])
            counts["titles"] += 1
            changed = True
        elif decision.kind == "list_singleton":
            new_block_texts.append([f"- {decision.segments[0]}"])
            counts["list_items_from_singleton"] += 1
            changed = True
        else:  # list_split
            out_texts: list[str] = []
            if decision.leading:
                out_texts.append(decision.leading)
            for seg_index, seg_text in enumerate(decision.segments):
                if not seg_text:
                    continue
                is_last_segment = seg_index == len(decision.segments) - 1
                if is_last_segment and decision.deferred_tail:
                    # Defer: keep as a plain paragraph fragment (glyph re-attached) so
                    # the next paragraph-continuation-merge pass can complete it first.
                    out_texts.append(f"{glyphs[0]} {seg_text}")
                    continue
                out_texts.append(f"- {seg_text}")
                counts["list_items_from_split"] += 1
            changed = True
            new_block_texts.append(out_texts)

    if not changed:
        return text, counts

    rebuilt: list[str] = []
    for block_texts in new_block_texts:
        rebuilt.extend(block_texts)
    new_text = "\n\n".join(rebuilt)
    if text.endswith("\n") and not new_text.endswith("\n"):
        new_text += "\n"
    return new_text, counts


def find_symbol_glyph_block_decisions(
    text: str, glyphs: Sequence[str]
) -> list[_GlyphBlockDecision]:
    """回傳文字中每個含裝飾符號區塊的分類決策，不修改文字，單輪不重試收斂。

    分類規則與 `convert_symbol_glyph_ornaments` 完全相同（共用 `_classify_glyph_blocks`）。
    與 `convert_symbol_glyph_ornaments` 不同之處：只回報，跳過 `kind == "unchanged"` 的區塊；
    `deferred_tail` 為真的 `list_split` 決策代表最後一段疑似跨區塊續句，本函式只跑單輪、不會
    重試收斂（呼叫端若需要完整收斂請改用 `clean_symbol_glyph_ornaments`），因此該筆決策視為
    無法確定，由呼叫端自行決定是否略過套用。

    供翻譯側工具（`convert_translated_symbol_glyphs.py`）依英文來源的分類決策與結構對齊，
    套用到已翻譯區塊，維持「決策只從英文來源算一次」的原則。
    """
    lines = text.split("\n")
    blocks = list(_iter_text_blocks(lines))
    if not blocks:
        return []
    decisions = _classify_glyph_blocks(blocks, glyphs)
    return [decision for decision in decisions if decision.kind != "unchanged"]


def apply_glyph_decision_at(
    text: str,
    block_start_line: int,
    kind: str,
    glyphs: Sequence[str],
    level: int | None = None,
) -> tuple[str, int]:
    """對起始於 `block_start_line`（1-based）的區塊套用 `kind`
    （`"title"` / `"list_singleton"` / `"list_split"` / `"drop"`，見
    `_GlyphBlockDecision.kind`）所指定的裝飾符號轉換，回傳 (轉換後文字, 產生的項目數)。
    項目數為 0 代表未套用；`title` 與 `list_singleton` 成功時固定為 1，`list_split`
    為實際拆出的清單項目數（可能大於 1），`drop`（區塊整段移除）成功時固定為 1。

    重新掃描該區塊自身的符號出現位置與次數，不假設與決策來源（通常是英文原文）相同
    次數；若區塊實際形狀與 `kind` 不符（例如來源判定為單一符號標題，但這個區塊本身
    有兩次以上符號，或反之），則不套用，回傳項目數 0，呼叫端應視為無法對齊。

    `kind == "title"` 時的標題層級：若呼叫端傳入 `level`（來源側 `_GlyphBlockDecision.level`
    已算好的層級），直接採用該值，不重新計算——來源與譯文的標題結構可能不同步（例如
    譯者已手動把某些裝飾符號標題轉成標題，但層級與來源不同），若各自依自身前文重新推算，
    兩側算出的層級會分歧。未傳入 `level` 時（例如舊呼叫端或未經結構比對的獨立呼叫），才
    退回依這段文字自身前面最近一個標題的層級往下推算一層（上限六層；找不到則預設層級二）。

    供翻譯側工具在依結構對齊找出來源決策對應的譯文區塊位置後，套用該決策。
    """
    glyph_pattern = _build_symbol_glyph_pattern(glyphs)
    if glyph_pattern is None or kind not in ("title", "list_singleton", "list_split", "drop"):
        return text, 0

    lines = text.split("\n")
    blocks = list(_iter_text_blocks(lines))
    block_index = next(
        (index for index, block in enumerate(blocks) if block.start == block_start_line - 1),
        None,
    )
    if block_index is None:
        return text, 0
    block = blocks[block_index]

    flat = _flatten_block_text(block.text)
    matches = list(glyph_pattern.finditer(flat))
    if not matches:
        return text, 0

    occurrences = [match.start() for match in matches]
    leading = flat[: occurrences[0]].strip()
    segments: list[str] = []
    for occ_index, match in enumerate(matches):
        seg_end = occurrences[occ_index + 1] if occ_index + 1 < len(occurrences) else len(flat)
        segments.append(flat[match.end() : seg_end].strip())
    is_singleton = len(occurrences) == 1 and occurrences[0] == 0 and not leading

    if kind == "drop":
        if leading or any(segments):
            return text, 0
        new_lines = lines[: block.start] + lines[block.end + 1 :]
        return "\n".join(new_lines), 1

    if kind in ("title", "list_singleton"):
        if not is_singleton or not segments[0]:
            return text, 0
        if kind == "title":
            if level is None:
                last_heading_level: int | None = None
                for prior in blocks[:block_index]:
                    if _block_kind(prior.text) == "heading":
                        first_line = prior.text.split("\n", 1)[0]
                        last_heading_level = len(first_line) - len(first_line.lstrip("#"))
                level = min((last_heading_level or 1) + 1, 6)
            replacement = [f"{'#' * level} {segments[0]}"]
        else:
            replacement = [f"- {segments[0]}"]
        item_count = 1
    else:  # list_split
        if is_singleton:
            return text, 0
        list_items = [seg for seg in segments if seg]
        replacement = ([leading] if leading else []) + [f"- {seg}" for seg in list_items]
        if not replacement:
            return text, 0
        item_count = len(list_items)

    new_lines = lines[: block.start] + "\n\n".join(replacement).split("\n") + lines[block.end + 1 :]
    return "\n".join(new_lines), item_count


_MAX_SYMBOL_GLYPH_ROUNDS = 10


def prepare_source_pre_paragraph_merge(text: str) -> str:
    """重現來源清理管線中，段落斷行續句合併之前的狀態（去除頁碼裝飾標題、合併清單
    續句），依 `extract_pdf.py` 實際管線順序：`strip_artifact_headings` →
    `merge_list_continuations`。

    供翻譯側同步工具（合併段落續句、轉換裝飾符號）共用，取得與來源側清理管線在同一
    階段一致的結構（標題、清單），避免翻譯側工具因為缺少這兩步而看到不同的結構錨點，
    導致結構定位與來源側清理結果分歧。
    """
    text = strip_artifact_headings(text)
    text, _ = merge_list_continuations(text)
    return text


def prepare_source_pre_glyph_conversion(text: str) -> str:
    """重現來源清理管線中，符號裝飾轉換之前那一刻的狀態，在
    `prepare_source_pre_paragraph_merge` 之上，再收斂執行頁碼殘留清除與段落續句合併
    （對應 `clean_symbol_glyph_ornaments` 迴圈中，符號轉換前的部分）。

    供 `convert_translated_symbol_glyphs.py` 依此文字做符號裝飾分類，確保分類依據與
    來源側清理管線在同一階段看到的文字一致。
    """
    text = prepare_source_pre_paragraph_merge(text)
    for _ in range(_MAX_SYMBOL_GLYPH_ROUNDS):
        text, stripped = strip_trailing_page_number_residue(text)
        text, merged, _ambiguous = merge_paragraph_continuations(text)
        if stripped == 0 and merged == 0:
            break
    return text


def clean_symbol_glyph_ornaments(text: str, glyphs: Sequence[str]) -> tuple[str, dict[str, object]]:
    """反覆清除頁碼殘留、合併段落續句、轉換裝飾符號字元，直到收斂或達輪數上限。

    三者交互影響：段落續句合併會先把被符號字元切斷的續句接回完整，讓符號轉換能看到
    完整的區塊；符號轉換又可能產生新的、可再次合併的段落殘段（見
    `convert_symbol_glyph_ornaments` 的延後轉換規則），因此需要反覆執行直到不再有
    變化。回傳的 dict 含 `ambiguous`：最後一輪 `merge_paragraph_continuations` 回報、
    仍無法安全合併的段落續句起始行號。
    """
    totals: dict[str, object] = {
        "page_number_residue_stripped": 0,
        "paragraph_merges": 0,
        "list_items_from_split": 0,
        "list_items_from_singleton": 0,
        "titles": 0,
        "dropped": 0,
        "ambiguous": [],
    }
    for _ in range(_MAX_SYMBOL_GLYPH_ROUNDS):
        text, stripped = strip_trailing_page_number_residue(text)
        totals["page_number_residue_stripped"] += stripped
        text, merged, ambiguous = merge_paragraph_continuations(text)
        totals["paragraph_merges"] += merged
        totals["ambiguous"] = ambiguous
        text, glyph_counts = convert_symbol_glyph_ornaments(text, glyphs)
        for key in ("list_items_from_split", "list_items_from_singleton", "titles", "dropped"):
            totals[key] += glyph_counts[key]
        if stripped == 0 and merged == 0 and not any(glyph_counts.values()):
            break
    return text, totals


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
