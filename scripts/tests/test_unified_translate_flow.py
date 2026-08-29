from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import draft
import translation_context


SCRIPTS = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _seed_three_chapter_project(root: Path) -> list[str]:
    source = root / "data/markdown/book.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# One\n\nAlpha.\n\n# Two\n\nBeta.\n\n# Three\n\nGamma.\n", encoding="utf-8")

    targets = [f"docs/src/content/docs/rules/{name}.md" for name in ("one", "two", "three")]
    for index, target in enumerate(targets, start=1):
        path = root / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# Chapter {index}\n\nSource {index}.\n", encoding="utf-8")

    _write_json(
        root / "chapters.json",
        {
            "source": "data/markdown/book.md",
            "output_dir": "docs/src/content/docs",
            "chapters": {
                "rules": {
                    "order": 1,
                    "files": {
                        name: {"title": name.title(), "pages": [index, index], "order": index}
                        for index, name in enumerate(("one", "two", "three"), start=1)
                    },
                }
            },
        },
    )
    _write_json(
        root / "data/translation-progress.json",
        {
            "_meta": {"total_chapters": 3, "completed": 0, "updated": ""},
            "chapters": [
                {
                    "id": name,
                    "file": target,
                    "source": "data/markdown/book.md",
                    "source_pages": f"{index}-{index}",
                    "status": "not_started",
                    "notes": "",
                }
                for index, (name, target) in enumerate(
                    zip(("one", "two", "three"), targets, strict=True), start=1
                )
            ],
        },
    )
    _write_json(root / "glossary.json", {"terms": []})
    _write_json(root / "style-decisions.json", {"translation_notes": []})
    return targets


def _complete_context(root: Path) -> None:
    translation_context.init_context(root)
    path = root / translation_context.CONTEXT_PATH
    context = json.loads(path.read_text(encoding="utf-8"))
    context["book_summary"] = {
        "subject": "A three-part rules fixture.",
        "structure": "Chapters are read in order.",
        "tone": "Direct.",
        "core_concepts": ["sequence"],
        "translation_priorities": ["preserve order"],
    }
    for chapter in context["chapters"].values():
        chapter["summary"] = f"Summary for {chapter['id']}"
        chapter["role"] = "One ordered part of the fixture."
    _write_json(path, context)
    translation_context.finalize_context(root)


def _update_progress(root: Path, target: str, status: str) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "progress_edit.py"),
            "--progress-file",
            str(root / "data/translation-progress.json"),
            "--file",
            target,
            "--status",
            status,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def _writeback(root: Path, target: str, translated: str) -> None:
    draft.cmd_path(target, "translate")
    manifest = json.loads(
        (root / ".state/translate/draft-manifest.json").read_text(encoding="utf-8")
    )
    draft_path = root / manifest["entries"][target]["draft"]
    draft_path.write_text(translated, encoding="utf-8")
    draft.cmd_writeback(target, "translate")


def _progress(root: Path) -> dict:
    return json.loads(
        (root / "data/translation-progress.json").read_text(encoding="utf-8")
    )


def test_three_chapter_writeback_progress_and_resume_order(
    tmp_path: Path, monkeypatch
) -> None:
    targets = _seed_three_chapter_project(tmp_path)
    _complete_context(tmp_path)
    monkeypatch.setattr(draft, "ROOT", tmp_path)

    assert translation_context.context_status(tmp_path)["status"] == "ready"
    assert _progress(tmp_path)["_meta"]["completed"] == 0

    _update_progress(tmp_path, targets[0], "in_progress")
    _writeback(tmp_path, targets[0], "# 第一章\n\n完整譯文。\n")

    # Writeback succeeds before completion bookkeeping is allowed to advance.
    assert (tmp_path / targets[0]).read_text(encoding="utf-8") == "# 第一章\n\n完整譯文。\n"
    assert _progress(tmp_path)["_meta"]["completed"] == 0
    _update_progress(tmp_path, targets[0], "completed")
    assert _progress(tmp_path)["_meta"]["completed"] == 1

    _update_progress(tmp_path, targets[1], "in_progress")
    resumed = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "progress_read.py"),
            "--progress-file",
            str(tmp_path / "data/translation-progress.json"),
            "--next",
            "2",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert resumed.returncode == 0, resumed.stderr
    assert [item["file"] for item in json.loads(resumed.stdout)["chapters"]] == targets[1:]

    for index, target in enumerate(targets[1:], start=2):
        _writeback(tmp_path, target, f"# 第{index}章\n\n完整譯文。\n")
        _update_progress(tmp_path, target, "completed")

    final = _progress(tmp_path)
    assert final["_meta"]["completed"] == 3
    assert all(item["status"] == "completed" for item in final["chapters"])
