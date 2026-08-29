from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

import translation_completion as completion
import translation_context


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/translation_completion.py"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _link_or_copy(source: str, target: str) -> str:
    try:
        os.link(source, target)
        return target
    except OSError:
        return shutil.copy2(source, target)


def test_completion_cli_runs_real_navigation_build_and_search(tmp_path: Path) -> None:
    bun = completion.find_bun()
    node_modules = ROOT / "docs/node_modules"
    if bun is None or not node_modules.is_dir():
        pytest.skip("Bun and installed docs dependencies are required for the real build path")

    shutil.copytree(ROOT / "scripts", tmp_path / "scripts", ignore=shutil.ignore_patterns("tests", "__pycache__"))
    shutil.copytree(
        ROOT / "docs",
        tmp_path / "docs",
        ignore=shutil.ignore_patterns("node_modules", "dist", ".astro"),
    )
    shutil.copytree(
        node_modules,
        tmp_path / "docs/node_modules",
        symlinks=True,
        copy_function=_link_or_copy,
    )
    for filename in (
        "chapters.json",
        "glossary.json",
        "glossary.schema.json",
        "style-decisions.json",
        "style-decisions.schema.json",
    ):
        shutil.copy2(ROOT / filename, tmp_path / filename)

    source = tmp_path / "data/markdown/YOUR-RULEBOOK_pages.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# Example Chapter\n\nComplete source.\n", encoding="utf-8")
    target = "docs/src/content/docs/example-section/index.md"
    progress = {
        "_meta": {"total_chapters": 1, "completed": 1},
        "chapters": [
            {
                "id": "example-section-index",
                "file": target,
                "source": "data/markdown/YOUR-RULEBOOK_pages.md",
                "source_pages": "1-2",
                "status": "completed",
            }
        ],
    }
    _write_json(tmp_path / "data/translation-progress.json", progress)
    alternate_progress = Path("data/translation-progress-bilingual.json")
    _write_json(tmp_path / alternate_progress, progress)
    target_path = tmp_path / target
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        "---\ntitle: 範例章節\ndescription: 完整內容\n---\n\n# 範例章節\n\n完整內容。\n",
        encoding="utf-8",
    )

    translation_context.init_context(tmp_path)
    context_path = tmp_path / translation_context.CONTEXT_PATH
    context = json.loads(context_path.read_text(encoding="utf-8"))
    context["book_summary"] = {
        "subject": "Integration fixture.",
        "structure": "One chapter.",
        "tone": "Direct.",
        "core_concepts": ["completion"],
        "translation_priorities": ["preserve content"],
    }
    context["chapters"][target]["summary"] = "Complete example chapter."
    context["chapters"][target]["role"] = "Exercises the completion handoff."
    _write_json(context_path, context)
    translation_context.finalize_context(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project-root",
            str(tmp_path),
            "--progress-file",
            str(alternate_progress),
            "--bun",
            str(bun),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    report = json.loads(result.stdout)
    assert report["ok"] is True
    assert report["progress_file"] == str(tmp_path / alternate_progress)
    assert len(report["checks"]) == 7
    assert (tmp_path / "docs/dist/index.html").is_file()
    assert (tmp_path / "docs/dist/pagefind/pagefind.js").is_file()
