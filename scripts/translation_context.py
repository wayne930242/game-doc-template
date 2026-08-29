#!/usr/bin/env python3
"""建立並驗證可重用的全書翻譯脈絡。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTEXT_PATH = Path("data/translation-context.json")
CHAPTERS_PATH = Path("chapters.json")
PROGRESS_PATH = Path("data/translation-progress.json")
GLOSSARY_PATH = Path("glossary.json")
STYLE_PATH = Path("style-decisions.json")
BOOK_SUMMARY_FIELDS = (
    "subject",
    "structure",
    "tone",
    "core_concepts",
    "translation_priorities",
)


class ContextError(RuntimeError):
    """翻譯脈絡無法建立或驗證。"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="管理全書翻譯脈絡。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="建立翻譯脈絡骨架。")
    init_parser.add_argument("--force", action="store_true", help="覆寫既有脈絡。")
    _add_project_root(init_parser)

    status_parser = subparsers.add_parser("status", help="檢查脈絡是否可重用。")
    status_parser.add_argument("--json", action="store_true", help="輸出 JSON。")
    status_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="脈絡不是 ready 時以非零狀態結束。",
    )
    _add_project_root(status_parser)

    finalize_parser = subparsers.add_parser("finalize", help="驗證並完成翻譯脈絡。")
    _add_project_root(finalize_parser)
    return parser.parse_args()


def _add_project_root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help=argparse.SUPPRESS,
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ContextError(f"找不到必要檔案：{path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContextError(f"無法讀取 JSON：{path}（{exc}）") from exc
    if not isinstance(payload, dict):
        raise ContextError(f"JSON 根節點必須是物件：{path}")
    return payload


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _json_fingerprint(path: Path) -> str:
    return _sha256(_canonical_json(_read_json(path)))


def _ordered_chapters(progress: dict[str, Any]) -> list[dict[str, Any]]:
    chapters = progress.get("chapters")
    if not isinstance(chapters, list):
        raise ContextError("translation-progress.json 的 chapters 必須是陣列。")

    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, chapter in enumerate(chapters):
        if not isinstance(chapter, dict):
            raise ContextError(f"translation-progress.json chapters[{index}] 必須是物件。")
        path = chapter.get("file")
        if not isinstance(path, str) or not path.strip():
            raise ContextError(f"translation-progress.json chapters[{index}].file 不可為空。")
        if path in seen:
            raise ContextError(f"translation-progress.json 有重複的章節路徑：{path}")
        seen.add(path)
        ordered.append(chapter)
    return ordered


def _chapter_mapping_payload(
    chapters_config: dict[str, Any], ordered: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "chapters_json": chapters_config,
        "progress_order": [
            {
                "id": chapter.get("id", ""),
                "file": chapter.get("file", ""),
                "source": chapter.get("source", ""),
                "source_pages": chapter.get("source_pages", ""),
            }
            for chapter in ordered
        ],
    }


def _source_fingerprint(root: Path, ordered: list[dict[str, Any]]) -> str:
    corpus: list[dict[str, str]] = []
    for chapter in ordered:
        source = chapter.get("source", "")
        if not isinstance(source, str) or not source.strip():
            raise ContextError(f"章節 {chapter.get('file', '')} 缺少 source。")
        source_path = Path(source)
        if not source_path.is_absolute():
            source_path = root / source_path
        if not source_path.is_file():
            raise ContextError(f"找不到章節來源：{source_path}")
        corpus.append(
            {
                "source": source,
                "source_pages": str(chapter.get("source_pages", "")),
                "content_fingerprint": _sha256(source_path.read_bytes()),
            }
        )
    return _sha256(_canonical_json(corpus))


def current_fingerprints(root: Path) -> dict[str, str]:
    chapters_config = _read_json(root / CHAPTERS_PATH)
    progress = _read_json(root / PROGRESS_PATH)
    ordered = _ordered_chapters(progress)
    return {
        "source_fingerprint": _source_fingerprint(root, ordered),
        "chapters_fingerprint": _sha256(
            _canonical_json(_chapter_mapping_payload(chapters_config, ordered))
        ),
        "glossary_fingerprint": _json_fingerprint(root / GLOSSARY_PATH),
        "style_fingerprint": _json_fingerprint(root / STYLE_PATH),
    }


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_context(root: Path) -> dict[str, Any]:
    chapters_config = _read_json(root / CHAPTERS_PATH)
    progress = _read_json(root / PROGRESS_PATH)
    ordered = _ordered_chapters(progress)
    fingerprints = {
        "source_fingerprint": _source_fingerprint(root, ordered),
        "chapters_fingerprint": _sha256(
            _canonical_json(_chapter_mapping_payload(chapters_config, ordered))
        ),
        "glossary_fingerprint": _json_fingerprint(root / GLOSSARY_PATH),
        "style_fingerprint": _json_fingerprint(root / STYLE_PATH),
    }

    chapters: dict[str, dict[str, Any]] = {}
    for chapter in ordered:
        target = str(chapter["file"])
        chapters[target] = {
            "id": str(chapter.get("id", "")),
            "source": str(chapter.get("source", "")),
            "source_pages": str(chapter.get("source_pages", "")),
            "summary": "",
            "role": "",
            "key_terms": [],
            "depends_on": [],
            "ambiguities": [],
        }

    return {
        "_meta": {
            "schema_version": 1,
            "status": "draft",
            **fingerprints,
            "updated": _now(),
        },
        "book_summary": {field: [] if field in {"core_concepts", "translation_priorities"} else "" for field in BOOK_SUMMARY_FIELDS},
        "chapters": chapters,
        "unresolved": [],
    }


def _write_context(path: Path, context: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(context, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def init_context(root: Path, *, force: bool = False) -> Path:
    output = root / CONTEXT_PATH
    if output.exists() and not force:
        raise ContextError(f"翻譯脈絡已存在：{output}（如需重建，請加上 --force）")
    _write_context(output, build_context(root))
    return output


def context_status(root: Path) -> dict[str, Any]:
    context_path = root / CONTEXT_PATH
    if not context_path.is_file():
        return {"status": "full_refresh_required", "reasons": ["context_missing"]}

    context = _read_json(context_path)
    meta = context.get("_meta")
    if not isinstance(meta, dict):
        return {"status": "full_refresh_required", "reasons": ["context_metadata"]}

    current = current_fingerprints(root)
    full_reasons = [
        name
        for name in ("source_fingerprint", "chapters_fingerprint")
        if meta.get(name) != current[name]
    ]
    if full_reasons:
        return {"status": "full_refresh_required", "reasons": full_reasons}

    decision_reasons = [
        name
        for name in ("glossary_fingerprint", "style_fingerprint")
        if meta.get(name) != current[name]
    ]
    if decision_reasons:
        return {"status": "decision_refresh_required", "reasons": decision_reasons}

    if meta.get("status") != "ready":
        return {"status": "full_refresh_required", "reasons": ["context_not_ready"]}
    return {"status": "ready", "reasons": []}


def _is_populated(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return value is not None


def _validation_errors(
    context: dict[str, Any], expected_targets: list[str]
) -> list[str]:
    errors: list[str] = []
    summary = context.get("book_summary")
    if not isinstance(summary, dict):
        errors.append("book_summary")
    else:
        for field in BOOK_SUMMARY_FIELDS:
            if not _is_populated(summary.get(field)):
                errors.append(f"book_summary.{field}")

    chapters = context.get("chapters")
    if not isinstance(chapters, dict):
        errors.append("chapters")
    else:
        for target in expected_targets:
            if target not in chapters:
                errors.append(f"{Path(target).name}.missing")
        for target, chapter in chapters.items():
            label = Path(str(target)).name
            if not isinstance(chapter, dict):
                errors.append(str(target))
                continue
            for field in ("summary", "role"):
                if not _is_populated(chapter.get(field)):
                    errors.append(f"{label}.{field}")
            if chapter.get("ambiguities"):
                errors.append(f"{label}.ambiguities")

    if context.get("unresolved"):
        errors.append("unresolved")
    return errors


def finalize_context(root: Path) -> Path:
    path = root / CONTEXT_PATH
    context = _read_json(path)
    meta = context.get("_meta")
    if not isinstance(meta, dict):
        raise ContextError("translation-context.json 缺少 _meta。")

    current = current_fingerprints(root)
    changed_source_fields = [
        name
        for name in ("source_fingerprint", "chapters_fingerprint")
        if meta.get(name) != current[name]
    ]
    if changed_source_fields:
        raise ContextError(
            "來源或章節結構已變更，請先執行 init --force：" + ", ".join(changed_source_fields)
        )

    progress = _read_json(root / PROGRESS_PATH)
    expected_targets = [str(chapter["file"]) for chapter in _ordered_chapters(progress)]
    errors = _validation_errors(context, expected_targets)
    if errors:
        raise ContextError("翻譯脈絡尚未完成：" + ", ".join(errors))

    meta.update(current)
    meta["schema_version"] = 1
    meta["status"] = "ready"
    meta["updated"] = _now()
    _write_context(path, context)
    return path


def main() -> int:
    args = parse_args()
    root = args.project_root.resolve()
    try:
        if args.command == "init":
            path = init_context(root, force=args.force)
            print(f"已建立翻譯脈絡：{path}")
        elif args.command == "status":
            report = context_status(root)
            if args.json:
                print(json.dumps(report, ensure_ascii=False))
            else:
                reasons = ", ".join(report["reasons"])
                print(report["status"] + (f"：{reasons}" if reasons else ""))
            if args.require_ready and report["status"] != "ready":
                return 1
        elif args.command == "finalize":
            path = finalize_context(root)
            print(f"翻譯脈絡已就緒：{path}")
        return 0
    except ContextError as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
