#!/usr/bin/env python3
"""Read and display translation progress."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROGRESS = PROJECT_ROOT / "data" / "translation-progress.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read translation progress.")
    parser.add_argument(
        "--progress-file",
        type=Path,
        default=DEFAULT_PROGRESS,
        help="Path to translation-progress JSON file.",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON.")
    parser.add_argument(
        "--status",
        type=str,
        choices=["not_started", "in_progress", "completed"],
        help="Filter by status.",
    )
    parser.add_argument(
        "--next",
        type=int,
        metavar="N",
        help="Show next N files to translate (in_progress first, then not_started).",
    )
    parser.add_argument(
        "--source",
        type=str,
        help="Filter chapters whose source field contains this substring.",
    )
    return parser.parse_args()


def load_progress(path: Path) -> dict:
    if not path.exists():
        print(f"❌ 進度檔案不存在：{path}", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    args = parse_args()
    progress_file = args.progress_file
    if not progress_file.is_absolute():
        progress_file = PROJECT_ROOT / progress_file

    data = load_progress(progress_file)
    meta = data.get("_meta", {})
    chapters = data.get("chapters", [])

    total = meta.get("total_chapters", len(chapters))
    if args.source:
        chapters = [
            c for c in chapters
            if args.source in c.get("source", "")
        ]
        total = len(chapters)

    # Compute counts
    counts = {"not_started": 0, "in_progress": 0, "completed": 0}
    for ch in chapters:
        s = ch.get("status", "not_started")
        counts[s] = counts.get(s, 0) + 1

    # Filter
    if args.status:
        filtered = [ch for ch in chapters if ch.get("status") == args.status]
    elif args.next:
        not_started = [ch for ch in chapters if ch.get("status") == "not_started"]
        in_progress = [ch for ch in chapters if ch.get("status") == "in_progress"]
        filtered = (in_progress + not_started)[: args.next]
    else:
        filtered = chapters

    report = {
        "progress_file": str(progress_file.relative_to(PROJECT_ROOT) if progress_file.is_relative_to(PROJECT_ROOT) else progress_file),
        "total": total,
        "completed": counts["completed"],
        "in_progress": counts["in_progress"],
        "not_started": counts["not_started"],
        "updated": meta.get("updated", ""),
        "chapters": filtered,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    total = report["total"]
    print(f"翻譯進度：已完成 {report['completed']} / {total} 個章節")
    print(f"  進行中：{report['in_progress']}")
    print(f"  未開始：{report['not_started']}")
    if report["updated"]:
        print(f"  更新時間：{report['updated']}")
    print()

    status_icon = {"not_started": "·", "in_progress": "▶", "completed": "✓"}
    for ch in filtered:
        s = ch.get("status", "not_started")
        icon = status_icon.get(s, "?")
        title = ch.get("title", "")
        f = ch.get("file", "")
        notes = ch.get("notes", "")
        line = f"  {icon} {title}  ({f})"
        if notes:
            line += f"  [{notes}]"
        print(line)


if __name__ == "__main__":
    main()
