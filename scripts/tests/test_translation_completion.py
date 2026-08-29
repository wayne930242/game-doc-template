from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import translation_completion as completion


SCRIPT = Path(__file__).resolve().parents[1] / "translation_completion.py"


def _write_progress(root: Path, statuses: list[str]) -> None:
    path = root / "data/translation-progress.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "_meta": {
                    "total_chapters": len(statuses),
                    "completed": statuses.count("completed"),
                },
                "chapters": [
                    {
                        "id": f"chapter-{index}",
                        "file": f"docs/chapter-{index}.md",
                        "status": status,
                    }
                    for index, status in enumerate(statuses, start=1)
                ],
            }
        ),
        encoding="utf-8",
    )


def _passing_runner(calls: list[tuple[list[str], Path]]):
    def run(cmd: list[str], cwd: Path) -> dict:
        calls.append((cmd, cwd))
        if cmd[-2:] == ["run", "build"]:
            (cwd / "dist/index.html").parent.mkdir(parents=True, exist_ok=True)
            (cwd / "dist/index.html").write_text("", encoding="utf-8")
            (cwd / "dist/pagefind/pagefind.js").parent.mkdir(
                parents=True, exist_ok=True
            )
            (cwd / "dist/pagefind/pagefind.js").write_text("", encoding="utf-8")
        return {
            "cmd": cmd,
            "cwd": str(cwd),
            "returncode": 0,
            "stdout": "ok",
            "stderr": "",
        }

    return run


def test_completion_refuses_incomplete_progress_without_running_commands(tmp_path: Path) -> None:
    _write_progress(tmp_path, ["completed", "in_progress", "not_started"])
    calls: list[tuple[list[str], Path]] = []

    report = completion.complete_project(
        tmp_path,
        bun_executable=Path("/fake/bun"),
        runner=_passing_runner(calls),
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "translation_incomplete"
    assert report["progress"] == {"completed": 1, "total": 3}
    assert calls == []


def test_completion_runs_final_navigation_guards_build_and_search_in_order(
    tmp_path: Path,
) -> None:
    _write_progress(tmp_path, ["completed", "completed", "completed"])
    calls: list[tuple[list[str], Path]] = []
    bun = Path("/fake/bun")

    report = completion.complete_project(
        tmp_path,
        bun_executable=bun,
        runner=_passing_runner(calls),
    )

    assert report["ok"] is True
    assert report["progress"] == {"completed": 3, "total": 3}
    assert report["dist"] == str(tmp_path / "docs/dist")
    assert calls == [
        ([sys.executable, "scripts/generate_nav.py"], tmp_path),
        ([sys.executable, "scripts/validate_glossary.py"], tmp_path),
        ([sys.executable, "scripts/validate_style_decisions.py"], tmp_path),
        (
            [
                sys.executable,
                "scripts/term_read.py",
                "--fail-on-missing",
                "--fail-on-forbidden",
            ],
            tmp_path,
        ),
        (
            [
                sys.executable,
                "scripts/translation_context.py",
                "status",
                "--require-ready",
            ],
            tmp_path,
        ),
        ([str(bun), "run", "build"], tmp_path / "docs"),
        ([str(bun), "run", "verify-search"], tmp_path / "docs"),
    ]
    assert len(report["checks"]) == len(calls)


def test_completion_stops_at_first_failed_check(tmp_path: Path) -> None:
    _write_progress(tmp_path, ["completed"])
    calls: list[list[str]] = []

    def failing_runner(cmd: list[str], cwd: Path) -> dict:
        calls.append(cmd)
        return {
            "cmd": cmd,
            "cwd": str(cwd),
            "returncode": 1 if cmd[1:] == ["scripts/validate_glossary.py"] else 0,
            "stdout": "",
            "stderr": "invalid glossary",
        }

    report = completion.complete_project(
        tmp_path,
        bun_executable=Path("/fake/bun"),
        runner=failing_runner,
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "check_failed"
    assert calls == [
        [sys.executable, "scripts/generate_nav.py"],
        [sys.executable, "scripts/validate_glossary.py"],
    ]


def test_cli_reports_missing_progress_as_json(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project-root",
            str(tmp_path),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "progress_missing"


def test_find_bun_uses_home_install_when_path_lookup_fails(
    tmp_path: Path, monkeypatch
) -> None:
    home_bun = tmp_path / ".bun/bin/bun"
    home_bun.parent.mkdir(parents=True)
    home_bun.write_text("", encoding="utf-8")
    home_bun.chmod(0o755)
    monkeypatch.setattr(completion.shutil, "which", lambda _name: None)
    monkeypatch.setattr(completion.Path, "home", classmethod(lambda cls: tmp_path))

    assert completion.find_bun() == home_bun


def test_run_cmd_reports_missing_executable_instead_of_raising(tmp_path: Path) -> None:
    result = completion.run_cmd([str(tmp_path / "missing-command")], tmp_path)

    assert result["returncode"] == -1
    assert "No such file" in result["stderr"]


def test_completion_rejects_missing_deployable_artifacts(tmp_path: Path) -> None:
    _write_progress(tmp_path, ["completed"])

    def runner(cmd: list[str], cwd: Path) -> dict:
        if cmd[-2:] == ["run", "build"]:
            (cwd / "dist").mkdir(parents=True, exist_ok=True)
        return {
            "cmd": cmd,
            "cwd": str(cwd),
            "returncode": 0,
            "stdout": "",
            "stderr": "",
        }

    report = completion.complete_project(
        tmp_path,
        bun_executable=Path("/fake/bun"),
        runner=runner,
    )

    assert report["ok"] is False
    assert report["error"]["code"] == "build_artifact_missing"
    assert report["missing_artifacts"] == [
        str(tmp_path / "docs/dist/index.html"),
        str(tmp_path / "docs/dist/pagefind/pagefind.js"),
    ]


def test_completion_can_use_bilingual_progress_file(tmp_path: Path) -> None:
    _write_progress(tmp_path, ["not_started"])
    bilingual_progress = tmp_path / "data/translation-progress-bilingual.json"
    bilingual_progress.write_text(
        json.dumps(
            {
                "_meta": {"total_chapters": 1, "completed": 1},
                "chapters": [
                    {"id": "bilingual", "file": "docs/bilingual.md", "status": "completed"}
                ],
            }
        ),
        encoding="utf-8",
    )
    calls: list[tuple[list[str], Path]] = []

    report = completion.complete_project(
        tmp_path,
        progress_path=Path("data/translation-progress-bilingual.json"),
        bun_executable=Path("/fake/bun"),
        runner=_passing_runner(calls),
    )

    assert report["ok"] is True
    assert report["progress_file"] == str(bilingual_progress)
