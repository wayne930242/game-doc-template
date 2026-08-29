from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "translation_context.py"


def write_project(root: Path) -> None:
    (root / "data" / "markdown").mkdir(parents=True, exist_ok=True)
    (root / "data" / "markdown" / "book.md").write_text(
        "# First\n\nAlpha.\n\n# Second\n\nBeta.\n", encoding="utf-8"
    )
    (root / "chapters.json").write_text(
        json.dumps(
            {
                "source": "data/markdown/book.md",
                "output_dir": "docs/src/content/docs",
                "chapters": {
                    "rules": {
                        "order": 1,
                        "files": {
                            "second": {"title": "Second", "pages": [3, 4], "order": 2},
                            "first": {"title": "First", "pages": [1, 2], "order": 1},
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "data" / "translation-progress.json").write_text(
        json.dumps(
            {
                "_meta": {"total_chapters": 2},
                "chapters": [
                    {
                        "id": "first",
                        "file": "docs/src/content/docs/rules/first.md",
                        "source": "data/markdown/book.md",
                        "source_pages": "1-2",
                        "status": "not_started",
                    },
                    {
                        "id": "second",
                        "file": "docs/src/content/docs/rules/second.md",
                        "source": "data/markdown/book.md",
                        "source_pages": "3-4",
                        "status": "not_started",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "glossary.json").write_text(
        json.dumps({"terms": [{"source": "Move", "target": "行動"}]}), encoding="utf-8"
    )
    (root / "style-decisions.json").write_text(
        json.dumps({"voice": "natural zh-TW"}), encoding="utf-8"
    )


def run_cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--project-root", str(root)],
        text=True,
        capture_output=True,
        check=False,
    )


def load_context(root: Path) -> dict:
    return json.loads((root / "data" / "translation-context.json").read_text(encoding="utf-8"))


def complete_context(root: Path) -> None:
    context = load_context(root)
    context["book_summary"] = {
        "subject": "A rules reference.",
        "structure": "Rules in play order.",
        "tone": "Direct and practical.",
        "core_concepts": ["Moves", "outcomes"],
        "translation_priorities": ["Preserve mechanical distinctions"],
    }
    for chapter in context["chapters"].values():
        chapter["summary"] = f"Summary for {chapter['id']}"
        chapter["role"] = "Introduces one part of the rules."
    (root / "data" / "translation-context.json").write_text(
        json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def test_init_creates_ordered_context_without_copying_glossary_mappings(tmp_path: Path) -> None:
    write_project(tmp_path)

    result = run_cli(tmp_path, "init")

    assert result.returncode == 0, result.stderr
    context = load_context(tmp_path)
    assert list(context) == ["_meta", "book_summary", "chapters", "unresolved"]
    assert context["_meta"]["schema_version"] == 1
    assert context["_meta"]["status"] == "draft"
    assert all(context["_meta"][name].startswith("sha256:") for name in (
        "source_fingerprint",
        "chapters_fingerprint",
        "glossary_fingerprint",
        "style_fingerprint",
    ))
    assert list(context["chapters"]) == [
        "docs/src/content/docs/rules/first.md",
        "docs/src/content/docs/rules/second.md",
    ]
    assert context["chapters"]["docs/src/content/docs/rules/first.md"] == {
        "id": "first",
        "source": "data/markdown/book.md",
        "source_pages": "1-2",
        "summary": "",
        "role": "",
        "key_terms": [],
        "depends_on": [],
        "ambiguities": [],
    }
    assert "行動" not in json.dumps(context, ensure_ascii=False)


def test_init_refuses_to_overwrite_existing_context_without_force(tmp_path: Path) -> None:
    write_project(tmp_path)
    assert run_cli(tmp_path, "init").returncode == 0

    result = run_cli(tmp_path, "init")

    assert result.returncode != 0
    assert "已存在" in result.stderr


def test_finalize_marks_complete_context_ready_and_status_reports_ready(tmp_path: Path) -> None:
    write_project(tmp_path)
    assert run_cli(tmp_path, "init").returncode == 0
    complete_context(tmp_path)

    finalized = run_cli(tmp_path, "finalize")
    status = run_cli(tmp_path, "status", "--json")

    assert finalized.returncode == 0, finalized.stderr
    assert load_context(tmp_path)["_meta"]["status"] == "ready"
    assert status.returncode == 0, status.stderr
    assert json.loads(status.stdout) == {"status": "ready", "reasons": []}


def test_status_require_ready_fails_for_draft_context(tmp_path: Path) -> None:
    write_project(tmp_path)
    assert run_cli(tmp_path, "init").returncode == 0

    status = run_cli(tmp_path, "status", "--require-ready")

    assert status.returncode != 0
    assert "full_refresh_required" in status.stdout


def test_finalize_rejects_incomplete_or_unresolved_context(tmp_path: Path) -> None:
    write_project(tmp_path)
    assert run_cli(tmp_path, "init").returncode == 0
    context = load_context(tmp_path)
    context["book_summary"]["subject"] = "Rules"
    context["chapters"]["docs/src/content/docs/rules/first.md"]["summary"] = "Summary"
    context["chapters"]["docs/src/content/docs/rules/first.md"]["role"] = "Opening"
    context["unresolved"] = ["What does Move mean here?"]
    (tmp_path / "data" / "translation-context.json").write_text(
        json.dumps(context), encoding="utf-8"
    )

    result = run_cli(tmp_path, "finalize")

    assert result.returncode != 0
    assert "book_summary.structure" in result.stderr
    assert "second.md.summary" in result.stderr
    assert "unresolved" in result.stderr
    assert load_context(tmp_path)["_meta"]["status"] == "draft"


def test_finalize_rejects_a_context_that_dropped_a_progress_chapter(tmp_path: Path) -> None:
    write_project(tmp_path)
    assert run_cli(tmp_path, "init").returncode == 0
    complete_context(tmp_path)
    context = load_context(tmp_path)
    del context["chapters"]["docs/src/content/docs/rules/second.md"]
    (tmp_path / "data" / "translation-context.json").write_text(
        json.dumps(context), encoding="utf-8"
    )

    result = run_cli(tmp_path, "finalize")

    assert result.returncode != 0
    assert "second.md" in result.stderr


def test_status_requires_full_refresh_for_source_or_chapter_changes(tmp_path: Path) -> None:
    write_project(tmp_path)
    assert run_cli(tmp_path, "init").returncode == 0
    complete_context(tmp_path)
    assert run_cli(tmp_path, "finalize").returncode == 0

    (tmp_path / "data" / "markdown" / "book.md").write_text("changed", encoding="utf-8")
    source_status = json.loads(run_cli(tmp_path, "status", "--json").stdout)
    assert source_status == {
        "status": "full_refresh_required",
        "reasons": ["source_fingerprint"],
    }

    write_project(tmp_path)
    chapters = json.loads((tmp_path / "chapters.json").read_text(encoding="utf-8"))
    chapters["chapters"]["rules"]["files"]["first"]["title"] = "Changed title"
    (tmp_path / "chapters.json").write_text(json.dumps(chapters), encoding="utf-8")
    chapter_status = json.loads(run_cli(tmp_path, "status", "--json").stdout)
    assert chapter_status == {
        "status": "full_refresh_required",
        "reasons": ["chapters_fingerprint"],
    }


def test_status_requires_only_decision_refresh_for_glossary_or_style_changes(tmp_path: Path) -> None:
    write_project(tmp_path)
    assert run_cli(tmp_path, "init").returncode == 0
    complete_context(tmp_path)
    assert run_cli(tmp_path, "finalize").returncode == 0

    (tmp_path / "glossary.json").write_text(json.dumps({"terms": []}), encoding="utf-8")
    glossary_status = json.loads(run_cli(tmp_path, "status", "--json").stdout)
    assert glossary_status == {
        "status": "decision_refresh_required",
        "reasons": ["glossary_fingerprint"],
    }

    write_project(tmp_path)
    (tmp_path / "glossary.json").write_text(json.dumps({"terms": []}), encoding="utf-8")
    (tmp_path / "style-decisions.json").write_text(json.dumps({"voice": "formal"}), encoding="utf-8")
    both_status = json.loads(run_cli(tmp_path, "status", "--json").stdout)
    assert both_status == {
        "status": "decision_refresh_required",
        "reasons": ["glossary_fingerprint", "style_fingerprint"],
    }

    refreshed = run_cli(tmp_path, "finalize")

    assert refreshed.returncode == 0, refreshed.stderr
    assert json.loads(run_cli(tmp_path, "status", "--json").stdout) == {
        "status": "ready",
        "reasons": [],
    }
