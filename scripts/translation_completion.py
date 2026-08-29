#!/usr/bin/env python3
"""完成全書翻譯後，重建導覽並驗證可部署網站。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROGRESS_PATH = Path("data/translation-progress.json")

CommandResult = dict[str, Any]
Runner = Callable[[list[str], Path], CommandResult]


class CompletionError(RuntimeError):
    """最終網站 handoff 的前置狀態無效。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="完成全書翻譯的導覽、驗證與網站建置 handoff。"
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--bun", type=Path, help="Bun 執行檔路徑。")
    parser.add_argument("--json", action="store_true", help="輸出 JSON 報告。")
    return parser.parse_args()


def _read_progress(root: Path) -> dict[str, Any]:
    path = root / PROGRESS_PATH
    if not path.is_file():
        raise CompletionError("progress_missing", f"找不到翻譯進度：{path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompletionError("progress_invalid", f"無法讀取翻譯進度：{exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("chapters"), list):
        raise CompletionError("progress_invalid", "翻譯進度缺少 chapters 陣列。")
    return payload


def _progress_summary(progress: dict[str, Any]) -> dict[str, int]:
    chapters = progress["chapters"]
    completed = sum(
        1
        for chapter in chapters
        if isinstance(chapter, dict) and chapter.get("status") == "completed"
    )
    return {"completed": completed, "total": len(chapters)}


def find_bun(explicit: Path | None = None) -> Path | None:
    """依明確路徑、PATH、標準使用者安裝位置尋找 Bun。"""
    if explicit is not None:
        if explicit.is_file():
            return explicit
        resolved = shutil.which(str(explicit))
        return Path(resolved) if resolved else None

    resolved = shutil.which("bun")
    if resolved:
        return Path(resolved)

    candidates = [
        Path.home() / ".bun/bin/bun",
        Path.home() / ".bun/bin/bun.exe",
    ]
    return next(
        (
            candidate
            for candidate in candidates
            if candidate.is_file() and os.access(candidate, os.X_OK)
        ),
        None,
    )


def run_cmd(cmd: list[str], cwd: Path) -> CommandResult:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except OSError as exc:
        return {
            "cmd": cmd,
            "cwd": str(cwd),
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
        }
    return {
        "cmd": cmd,
        "cwd": str(cwd),
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def _base_report(root: Path) -> dict[str, Any]:
    return {
        "ok": False,
        "project_root": str(root),
        "progress": {"completed": 0, "total": 0},
        "checks": [],
        "dist": str(root / "docs/dist"),
    }


def complete_project(
    root: Path,
    *,
    bun_executable: Path | None = None,
    runner: Runner = run_cmd,
) -> dict[str, Any]:
    """執行全書完成後的 deterministic 網站 handoff。"""
    root = root.resolve()
    report = _base_report(root)
    try:
        progress = _read_progress(root)
    except CompletionError as exc:
        report["error"] = {"code": exc.code, "message": str(exc)}
        return report

    report["progress"] = _progress_summary(progress)
    if (
        report["progress"]["total"] == 0
        or report["progress"]["completed"] != report["progress"]["total"]
    ):
        report["error"] = {
            "code": "translation_incomplete",
            "message": "仍有章節尚未完成，不能建立最終網站。",
        }
        return report

    bun = bun_executable
    if bun is None:
        bun = find_bun()
    if bun is None:
        report["error"] = {
            "code": "bun_missing",
            "message": "找不到 Bun；請安裝 Bun 或使用 --bun 指定執行檔。",
        }
        return report

    python_checks = [
        [sys.executable, "scripts/generate_nav.py"],
        [sys.executable, "scripts/validate_glossary.py"],
        [sys.executable, "scripts/validate_style_decisions.py"],
        [
            sys.executable,
            "scripts/term_read.py",
            "--fail-on-missing",
            "--fail-on-forbidden",
        ],
        [
            sys.executable,
            "scripts/translation_context.py",
            "status",
            "--require-ready",
        ],
    ]
    commands = [(cmd, root) for cmd in python_checks]
    commands.extend(
        [
            ([str(bun), "run", "build"], root / "docs"),
            ([str(bun), "run", "verify-search"], root / "docs"),
        ]
    )

    for cmd, cwd in commands:
        result = runner(cmd, cwd)
        report["checks"].append(result)
        if result.get("returncode") != 0:
            report["error"] = {
                "code": "check_failed",
                "message": f"完成檢查失敗：{' '.join(cmd)}",
            }
            return report

    dist = root / "docs/dist"
    required_artifacts = [
        dist / "index.html",
        dist / "pagefind/pagefind.js",
    ]
    missing_artifacts = [str(path) for path in required_artifacts if not path.is_file()]
    if missing_artifacts:
        report["missing_artifacts"] = missing_artifacts
        report["error"] = {
            "code": "build_artifact_missing",
            "message": "建置命令成功，但缺少可部署的首頁或搜尋索引。",
        }
        return report

    report["ok"] = True
    return report


def _print_human(report: dict[str, Any]) -> None:
    if report["ok"]:
        progress = report["progress"]
        print(f"✓ 全書完成：{progress['completed']} / {progress['total']}")
        print(f"✓ 網站已建置：{report['dist']}")
        return
    error = report.get("error", {})
    print(f"❌ {error.get('message', '最終網站 handoff 失敗。')}", file=sys.stderr)


def main() -> int:
    args = parse_args()
    explicit_bun = find_bun(args.bun) if args.bun is not None else None
    if args.bun is not None and explicit_bun is None:
        report = _base_report(args.project_root.resolve())
        report["error"] = {
            "code": "bun_missing",
            "message": f"找不到指定的 Bun：{args.bun}",
        }
    else:
        report = complete_project(
            args.project_root,
            bun_executable=explicit_bun,
        )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
