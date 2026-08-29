#!/usr/bin/env python3
"""Compare protected Markdown/MDX block structure between source and translation."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
from typing import Any, Sequence

from _markdown_utils import MARKDOWN_IMAGE_RE, extract_markdown_image_targets


HEADING_RE = re.compile(r"^(#{1,6})[ \t]+\S")
LIST_ITEM_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<marker>[-+*]|\d+[.)])[ \t]+")
FENCE_RE = re.compile(r"^[ \t]*(?P<fence>`{3,}|~{3,})[ \t]*(?P<info>.*)$")
ADMONITION_OPEN_RE = re.compile(
    r"^[ \t]*:::[ \t]*(?P<name>[A-Za-z][\w-]*)(?:\[[^\]]*\])?(?:\{.*\})?[ \t]*$"
)
ADMONITION_CLOSE_RE = re.compile(r"^[ \t]*:::[ \t]*$")
FRONTMATTER_KEY_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<list>-[ \t]+)?(?P<key>[A-Za-z0-9_.-]+)[ \t]*:(?P<value>.*)$"
)
FRONTMATTER_SEQUENCE_RE = re.compile(r"^(?P<indent>[ \t]*)-[ \t]+")
IMPORT_RE = re.compile(r"^[ \t]*import\b")
JSX_TAG_RE = re.compile(
    r"<(?P<closing>/)?(?P<name>[A-Za-z][A-Za-z0-9_.:-]*)(?P<attrs>[^<>]*?)(?P<self>/)?>"
)
JSX_PROP_RE = re.compile(r"(?:^|\s)([A-Za-z_:][A-Za-z0-9_.:-]*)(?=\s*=|\s|$)")
TABLE_SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")


@dataclass(frozen=True)
class StructureToken:
    """One protected structural block in source order."""

    kind: str
    detail: tuple[tuple[str, Any], ...]
    line: int

    @classmethod
    def create(cls, kind: str, line: int, **detail: Any) -> StructureToken:
        return cls(kind=kind, detail=tuple(sorted(detail.items())), line=line)

    def signature(self) -> str:
        return json.dumps(
            {"kind": self.kind, "detail": dict(self.detail)},
            ensure_ascii=False,
            sort_keys=True,
        )

    def to_json(self, path: Path) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "detail": dict(self.detail),
            "line": self.line,
            "location": f"{path.name}:{self.line}",
        }

    def describe(self) -> str:
        detail = dict(self.detail)
        if self.kind == "heading":
            return f"heading(level={detail['level']})"
        if self.kind == "list_item":
            return f"list_item(type={detail['type']}, depth={detail['depth']})"
        if self.kind == "table":
            return f"table(rows={detail['rows']}, columns={detail['columns']})"
        if self.kind == "fence":
            language = detail.get("info") or "plain"
            return f"fence(language={language}, closed={detail['closed']})"
        if self.kind == "frontmatter":
            return "frontmatter(keys/shape)"
        if detail:
            rendered = ", ".join(f"{key}={value}" for key, value in self.detail)
            return f"{self.kind}({rendered})"
        return self.kind


def _indent_columns(indent: str) -> int:
    return len(indent.expandtabs(4))


def _value_shape(value: str) -> str:
    value = value.strip()
    if not value:
        return "container"
    if value.startswith("["):
        return "inline_sequence"
    if value.startswith("{"):
        return "inline_mapping"
    if value[0] in "|>":
        return "block_scalar"
    return "scalar"


def _frontmatter_shape(lines: Sequence[str]) -> tuple[list[list[Any]], int]:
    """Return normalized YAML-like shape and the first body-line index."""
    if not lines or lines[0].lstrip("\ufeff") != "---":
        return [], 0

    closing_index = next(
        (index for index in range(1, len(lines)) if lines[index].strip() == "---"),
        None,
    )
    if closing_index is None:
        return [["unclosed"]], len(lines)

    raw_items: list[tuple[str, int, str, str]] = []
    for line in lines[1:closing_index]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key_match = FRONTMATTER_KEY_RE.match(line)
        if key_match:
            raw_items.append(
                (
                    "list_key" if key_match.group("list") else "key",
                    _indent_columns(key_match.group("indent")),
                    key_match.group("key"),
                    _value_shape(key_match.group("value")),
                )
            )
            continue
        sequence_match = FRONTMATTER_SEQUENCE_RE.match(line)
        if sequence_match:
            raw_items.append(
                (
                    "sequence_item",
                    _indent_columns(sequence_match.group("indent")),
                    "",
                    "scalar",
                )
            )

    indent_levels = {
        indent: depth for depth, indent in enumerate(sorted({item[1] for item in raw_items}))
    }
    shape = [
        [kind, indent_levels[indent], key, value_shape]
        for kind, indent, key, value_shape in raw_items
    ]
    if not shape:
        shape = [["empty"]]
    return shape, closing_index + 1


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith(r"\|"):
        stripped = stripped[:-1]

    cells: list[str] = []
    current: list[str] = []
    escaped = False
    code_delimiter: str | None = None
    for char in stripped:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            current.append(char)
            escaped = True
            continue
        if char == "`":
            code_delimiter = None if code_delimiter else "`"
            current.append(char)
            continue
        if char == "|" and code_delimiter is None:
            cells.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    cells.append("".join(current).strip())
    return cells


def _is_table_start(lines: Sequence[str], index: int) -> bool:
    if index + 1 >= len(lines) or "|" not in lines[index]:
        return False
    separator_cells = _split_table_row(lines[index + 1])
    return bool(separator_cells) and all(
        TABLE_SEPARATOR_CELL_RE.fullmatch(cell) for cell in separator_cells
    )


def _image_tokens(line: str, line_number: int) -> list[StructureToken]:
    tokens: list[StructureToken] = []
    for match in MARKDOWN_IMAGE_RE.finditer(line):
        targets = extract_markdown_image_targets(match.group(0))
        if targets:
            tokens.append(
                StructureToken.create("image", line_number, target=targets[0])
            )
    return tokens


def _normalized_import(lines: Sequence[str], index: int) -> tuple[str, int]:
    parts = [lines[index].strip()]
    end_index = index
    while end_index + 1 < len(lines):
        combined = " ".join(parts)
        side_effect_import = re.fullmatch(
            r"import\s+['\"][^'\"]+['\"]\s*;?", combined
        )
        if (
            ";" in combined
            or side_effect_import
            or re.search(r"\bfrom\s+['\"][^'\"]+['\"]\s*$", combined)
        ):
            break
        end_index += 1
        parts.append(lines[end_index].strip())
    normalized = " ".join(" ".join(parts).split())
    normalized = re.sub(r"\s*([{},])\s*", r"\1", normalized)
    normalized = normalized.replace(",}", "}")
    return normalized, end_index


def _contains_unquoted_tag_end(text: str) -> bool:
    quote: str | None = None
    escaped = False
    for char in text:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in "'\"":
            quote = char
        elif char == ">":
            return True
    return False


def _collect_mdx_tag(lines: Sequence[str], index: int) -> tuple[str, int]:
    """Collect a block-level MDX opening tag that may span several lines."""
    first = lines[index].lstrip()
    if not first.startswith("<") or first.startswith("<!--"):
        return lines[index], index

    parts = [lines[index].strip()]
    end_index = index
    while not _contains_unquoted_tag_end(" ".join(parts)) and end_index + 1 < len(lines):
        end_index += 1
        parts.append(lines[end_index].strip())
    return " ".join(parts), end_index


def _mdx_tokens(line: str, line_number: int) -> list[StructureToken]:
    tokens: list[StructureToken] = []
    for match in JSX_TAG_RE.finditer(line):
        name = match.group("name")
        if name.lower() in {"http", "https", "mailto"}:
            continue
        if match.group("closing"):
            tokens.append(StructureToken.create("mdx_close", line_number, name=name))
            continue
        prop_names = sorted(set(JSX_PROP_RE.findall(match.group("attrs"))))
        kind = "mdx_self" if match.group("self") else "mdx_open"
        tokens.append(
            StructureToken.create(kind, line_number, name=name, props=prop_names)
        )
    return tokens


def extract_structure(text: str) -> list[StructureToken]:
    """Extract protected Markdown/MDX block shape while ignoring prose."""
    lines = text.splitlines()
    tokens: list[StructureToken] = []
    frontmatter_shape, index = _frontmatter_shape(lines)
    if frontmatter_shape:
        tokens.append(
            StructureToken.create(
                "frontmatter",
                1,
                shape=frontmatter_shape,
            )
        )

    list_indents: list[int] = []
    while index < len(lines):
        line = lines[index]
        line_number = index + 1

        fence_match = FENCE_RE.match(line)
        if fence_match:
            fence = fence_match.group("fence")
            closing_index = index + 1
            while closing_index < len(lines):
                candidate = lines[closing_index].strip()
                closing_pattern = rf"{re.escape(fence[0])}{{{len(fence)},}}"
                if re.fullmatch(closing_pattern, candidate):
                    break
                closing_index += 1
            closed = closing_index < len(lines)
            tokens.append(
                StructureToken.create(
                    "fence",
                    line_number,
                    marker=fence[0],
                    info=" ".join(fence_match.group("info").split()),
                    closed=closed,
                )
            )
            index = closing_index + 1 if closed else len(lines)
            list_indents = []
            continue

        if ADMONITION_CLOSE_RE.match(line):
            tokens.append(StructureToken.create("admonition_close", line_number))
            index += 1
            list_indents = []
            continue

        admonition_match = ADMONITION_OPEN_RE.match(line)
        if admonition_match:
            tokens.append(
                StructureToken.create(
                    "admonition_open",
                    line_number,
                    type=admonition_match.group("name"),
                )
            )
            index += 1
            list_indents = []
            continue

        if IMPORT_RE.match(line):
            statement, end_index = _normalized_import(lines, index)
            tokens.append(
                StructureToken.create("import", line_number, statement=statement)
            )
            index = end_index + 1
            list_indents = []
            continue

        mdx_text, mdx_end_index = _collect_mdx_tag(lines, index)
        mdx_tokens = _mdx_tokens(mdx_text, line_number)
        if mdx_tokens:
            tokens.extend(_image_tokens(mdx_text, line_number))
            tokens.extend(mdx_tokens)
            index = mdx_end_index + 1
            list_indents = []
            continue

        heading_match = HEADING_RE.match(line)
        if heading_match:
            tokens.append(
                StructureToken.create(
                    "heading", line_number, level=len(heading_match.group(1))
                )
            )
            index += 1
            list_indents = []
            continue

        if _is_table_start(lines, index):
            table_lines = [line]
            end_index = index + 1
            while end_index < len(lines) and "|" in lines[end_index]:
                table_lines.append(lines[end_index])
                end_index += 1
            column_counts = [_split_table_row(row) for row in table_lines]
            tokens.append(
                StructureToken.create(
                    "table",
                    line_number,
                    rows=len(table_lines),
                    columns=[len(cells) for cells in column_counts],
                )
            )
            for offset, table_line in enumerate(table_lines):
                tokens.extend(_image_tokens(table_line, line_number + offset))
            index = end_index
            list_indents = []
            continue

        list_match = LIST_ITEM_RE.match(line)
        if list_match:
            indent = _indent_columns(list_match.group("indent"))
            while list_indents and indent < list_indents[-1]:
                list_indents.pop()
            if not list_indents or indent > list_indents[-1]:
                list_indents.append(indent)
            marker = list_match.group("marker")
            tokens.append(
                StructureToken.create(
                    "list_item",
                    line_number,
                    type="unordered" if marker in "-+*" else "ordered",
                    depth=len(list_indents) - 1,
                )
            )
            tokens.extend(_image_tokens(line, line_number))
            tokens.extend(_mdx_tokens(line, line_number))
            index += 1
            continue

        tokens.extend(_image_tokens(line, line_number))
        tokens.extend(_mdx_tokens(line, line_number))
        if line.strip() and not line[:1].isspace():
            list_indents = []
        index += 1

    return tokens


def _finding(
    expected: StructureToken | None,
    actual: StructureToken | None,
    source_path: Path,
    draft_path: Path,
) -> dict[str, Any]:
    if expected and actual:
        message = (
            f"expected {expected.describe()} at {source_path.name}:{expected.line}; "
            f"found {actual.describe()} at {draft_path.name}:{actual.line}"
        )
    elif expected:
        message = (
            f"missing {expected.describe()} from {source_path.name}:{expected.line} "
            "in draft"
        )
    else:
        assert actual is not None
        message = (
            f"unexpected {actual.describe()} at {draft_path.name}:{actual.line} "
            "in draft"
        )
    return {
        "message": message,
        "expected": expected.to_json(source_path) if expected else None,
        "actual": actual.to_json(draft_path) if actual else None,
    }


def compare_structure(
    source_text: str,
    draft_text: str,
    source_path: Path = Path("source.md"),
    draft_path: Path = Path("draft.md"),
) -> list[dict[str, Any]]:
    """Return structured findings for every protected-shape difference."""
    source_tokens = extract_structure(source_text)
    draft_tokens = extract_structure(draft_text)
    matcher = SequenceMatcher(
        a=[token.signature() for token in source_tokens],
        b=[token.signature() for token in draft_tokens],
        autojunk=False,
    )
    findings: list[dict[str, Any]] = []
    for opcode, source_start, source_end, draft_start, draft_end in matcher.get_opcodes():
        if opcode == "equal":
            continue
        expected = source_tokens[source_start:source_end]
        actual = draft_tokens[draft_start:draft_end]
        paired_count = min(len(expected), len(actual))
        for offset in range(paired_count):
            findings.append(
                _finding(expected[offset], actual[offset], source_path, draft_path)
            )
        for token in expected[paired_count:]:
            findings.append(_finding(token, None, source_path, draft_path))
        for token in actual[paired_count:]:
            findings.append(_finding(None, token, source_path, draft_path))
    return findings


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare protected Markdown block shape between source and draft."
    )
    parser.add_argument("source", type=Path, help="Source Markdown/MDX path")
    parser.add_argument("draft", type=Path, help="Translated draft Markdown/MDX path")
    parser.add_argument("--json", action="store_true", help="Print structured JSON")
    return parser.parse_args(argv)


def _print_error(args: argparse.Namespace, code: str, message: str) -> None:
    if args.json:
        print(
            json.dumps(
                {
                    "valid": False,
                    "source": str(args.source),
                    "draft": str(args.draft),
                    "error": {"code": code, "message": message},
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"❌ {message}")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    for path in (args.source, args.draft):
        if not path.is_file():
            _print_error(args, "file_not_found", f"Markdown file not found: {path}")
            return 2

    try:
        source_text = args.source.read_text(encoding="utf-8")
        draft_text = args.draft.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        _print_error(args, "invalid_utf8", f"Markdown must be UTF-8: {error}")
        return 2

    findings = compare_structure(
        source_text,
        draft_text,
        source_path=args.source,
        draft_path=args.draft,
    )
    payload = {
        "valid": not findings,
        "source": str(args.source),
        "draft": str(args.draft),
        "finding_count": len(findings),
        "findings": findings,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif findings:
        print(f"❌ Markdown structure mismatch ({len(findings)} finding(s)):")
        for finding in findings:
            print(f"- {finding['message']}")
    else:
        print(f"✓ Markdown structure matches: {args.source} → {args.draft}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
