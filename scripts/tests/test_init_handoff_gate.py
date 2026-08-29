from __future__ import annotations

import argparse

import pytest

import init_handoff_gate as gate


def _seed_required_files(root) -> None:
    for rel in gate.REQUIRED_FILES:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")


def test_missing_bun_reported(monkeypatch, tmp_path):
    monkeypatch.setattr(gate.shutil, "which", lambda _cmd: None)
    result = gate.check_bun_available()
    assert result is False


def test_run_cmd_uses_utf8(monkeypatch):
    captured = {}

    def fake_run(cmd, cwd, capture_output, text, encoding):
        captured["encoding"] = encoding

        class P:
            returncode = 0
            stdout = ""
            stderr = ""

        return P()

    monkeypatch.setattr(gate.subprocess, "run", fake_run)
    gate.run_cmd(["echo"], cwd=gate.PROJECT_ROOT)
    assert captured["encoding"] == "utf-8"


def test_check_required_files_reports_missing(tmp_path):
    missing = gate.check_required_files(tmp_path)
    assert missing == gate.REQUIRED_FILES


def test_main_passes_with_skip_docs_build(monkeypatch, tmp_path):
    _seed_required_files(tmp_path)
    calls: list[list[str]] = []

    args = argparse.Namespace(project_root=tmp_path, skip_docs_build=True, json=False)
    monkeypatch.setattr(gate, "parse_args", lambda: args)
    monkeypatch.setattr(
        gate,
        "run_cmd",
        lambda cmd, cwd: (
            calls.append(cmd),
            {"cmd": cmd, "cwd": str(cwd), "returncode": 0, "stdout": "", "stderr": ""},
        )[1],
    )

    gate.main()

    # validate_glossary + validate_style_decisions + term_read + translation context, no bun build
    assert len(calls) == 4
    assert any(
        cmd[1:] == ["scripts/translation_context.py", "status", "--require-ready"]
        for cmd in calls
    )
    assert not any(cmd[0] == "bun" for cmd in calls)


def test_main_fails_when_command_fails(monkeypatch, tmp_path):
    _seed_required_files(tmp_path)

    args = argparse.Namespace(project_root=tmp_path, skip_docs_build=True, json=False)
    monkeypatch.setattr(gate, "parse_args", lambda: args)
    monkeypatch.setattr(
        gate,
        "run_cmd",
        lambda cmd, cwd: {
            "cmd": cmd,
            "cwd": str(cwd),
            "returncode": 1,
            "stdout": "",
            "stderr": "fail",
        },
    )

    with pytest.raises(SystemExit):
        gate.main()


def test_main_fails_when_bun_missing_and_docs_build_required(monkeypatch, tmp_path):
    _seed_required_files(tmp_path)

    args = argparse.Namespace(project_root=tmp_path, skip_docs_build=False, json=False)
    monkeypatch.setattr(gate, "parse_args", lambda: args)
    monkeypatch.setattr(gate, "check_bun_available", lambda: False)
    monkeypatch.setattr(
        gate,
        "run_cmd",
        lambda cmd, cwd: {
            "cmd": cmd,
            "cwd": str(cwd),
            "returncode": 0,
            "stdout": "",
            "stderr": "",
        },
    )

    with pytest.raises(SystemExit):
        gate.main()


def test_main_fails_when_required_files_missing(monkeypatch, tmp_path):
    args = argparse.Namespace(project_root=tmp_path, skip_docs_build=True, json=False)
    monkeypatch.setattr(gate, "parse_args", lambda: args)

    with pytest.raises(SystemExit):
        gate.main()
