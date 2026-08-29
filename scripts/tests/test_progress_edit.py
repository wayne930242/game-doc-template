from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import progress_edit


def _sample() -> dict:
    return {
        "_meta": {"total_chapters": 0, "completed": 0, "updated": ""},
        "chapters": [
            {"id": "a", "file": "docs/a.md", "status": "not_started"},
            {"id": "b", "file": "docs/b.md", "status": "completed"},
        ],
    }


def test_recalculate_meta_counts():
    data = _sample()
    progress_edit.recalculate_meta(data)
    assert data["_meta"]["total_chapters"] == 2
    assert data["_meta"]["completed"] == 1


def test_find_entry_by_file_and_id():
    data = _sample()
    assert progress_edit.find_entry(data, "docs/a.md")["id"] == "a"
    assert progress_edit.find_entry(data, "b")["id"] == "b"
    assert progress_edit.find_entry(data, "missing") is None


def test_cli_status_update(tmp_path: Path):
    progress = tmp_path / "progress.json"
    progress.write_text(json.dumps(_sample(), ensure_ascii=False), encoding="utf-8")
    script = Path(progress_edit.__file__)
    proc = subprocess.run(
        [sys.executable, str(script), "--progress-file", str(progress),
         "--file", "docs/a.md", "--status", "completed"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(progress.read_text(encoding="utf-8"))
    assert data["chapters"][0]["status"] == "completed"
    assert data["_meta"]["completed"] == 2


def test_progress_read_next_prioritizes_in_progress(tmp_path: Path):
    progress = tmp_path / "progress.json"
    payload = {
        "_meta": {"total_chapters": 3, "completed": 0, "updated": ""},
        "chapters": [
            {"id": "new-a", "file": "docs/new-a.md", "status": "not_started"},
            {"id": "resume", "file": "docs/resume.md", "status": "in_progress"},
            {"id": "new-b", "file": "docs/new-b.md", "status": "not_started"},
        ],
    }
    progress.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    script = Path(progress_edit.__file__).with_name("progress_read.py")

    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--progress-file",
            str(progress),
            "--next",
            "2",
            "--json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert proc.returncode == 0, proc.stderr
    selected = json.loads(proc.stdout)["chapters"]
    assert [entry["id"] for entry in selected] == ["resume", "new-a"]
