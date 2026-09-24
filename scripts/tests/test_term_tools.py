from __future__ import annotations

import argparse
from pathlib import Path

import pytest

import term_edit as te
import term_generate as tg
import term_read as tr


# ---------------------------------------------------------------------------
# term_generate
# ---------------------------------------------------------------------------

def test_term_generate_main_filters_managed_terms(monkeypatch):
    args = argparse.Namespace(
        root=None,
        glossary=Path("glossary.json"),
        min_frequency=2,
        limit=10,
        json=False,
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(tg, "parse_args", lambda: args)
    monkeypatch.setattr(tg, "resolve_root", lambda _root: tg.PROJECT_ROOT)
    monkeypatch.setattr(
        tg, "load_glossary", lambda _path: {"_meta": {}, "Move": {"status": "approved"}}
    )
    monkeypatch.setattr(tg, "build_corpus", lambda _root: ({"docs/a.md": "x"}, "fp"))
    monkeypatch.setattr(
        tg,
        "extract_candidates",
        lambda _corpus, min_frequency: [
            {"term": "Move", "normalized": "move", "count": 5},
            {"term": "Harm", "normalized": "harm", "count": 3},
        ],
    )
    monkeypatch.setattr(tg, "save_json", lambda _path, payload: captured.update(payload=payload))

    tg.main()

    payload = captured["payload"]
    assert payload["count"] == 1
    assert payload["candidates"][0]["term"] == "Harm"


# ---------------------------------------------------------------------------
# term_edit
# ---------------------------------------------------------------------------

def _edit_args(**overrides: object) -> argparse.Namespace:
    base = {
        "glossary": Path("glossary.json"),
        "root": Path("."),
        "term": "Stress",
        "cal": False,
        "show": False,
        "list": False,
        "remove": False,
        "set_zh": "壓力",
        "notes": "",
        "status": "approved",
        "mark_term": True,
        "unmark_term": False,
        "forbidden": [],
        "keep_english": False,
        "set_original_term": None,
        "force": False,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def test_mutate_term_auto_runs_cal_for_unmanaged_term(monkeypatch):
    """Unmanaged term without a fresh --cal triggers an automatic calculation."""
    glossary = {"_meta": {"updated": ""}}
    calls: list[str] = []

    monkeypatch.setattr(te, "has_fresh_cal", lambda _term, _root: False)
    monkeypatch.setattr(te, "run_calculation", lambda _args, _glossary: calls.append("cal"))
    monkeypatch.setattr(te, "load_json", lambda _path, _default: None)
    monkeypatch.setattr(te, "save_glossary", lambda _path, _glossary: None)

    changed = te.mutate_term(_edit_args(force=False), glossary)

    assert calls == ["cal"]
    assert changed is True
    assert glossary["Stress"]["zh"] == "壓力"


def test_mutate_term_force_skips_cal_and_updates_entry(monkeypatch):
    glossary = {"_meta": {"updated": ""}}
    calls: list[str] = []

    monkeypatch.setattr(te, "run_calculation", lambda _args, _glossary: calls.append("cal"))
    monkeypatch.setattr(te, "load_json", lambda _path, _default: None)
    monkeypatch.setattr(te, "save_glossary", lambda _path, _glossary: None)

    changed = te.mutate_term(_edit_args(force=True), glossary)

    assert calls == []
    assert changed is True
    assert glossary["Stress"]["zh"] == "壓力"
    assert glossary["Stress"]["is_term"] is True


def test_mutate_term_sets_original_term_under_schema(monkeypatch):
    glossary = {"_meta": {"description": "x", "updated": ""}}
    monkeypatch.setattr(te, "save_glossary", lambda _path, _glossary: None)

    args = _edit_args(set_zh=None, notes=None, status=None, mark_term=False, set_original_term="ストレス", force=True)

    assert te.mutate_term(args, glossary) is True
    assert glossary["Stress"]["original_term"] == "ストレス"


def test_mutate_term_rejects_empty_original_term(monkeypatch):
    glossary = {"_meta": {"description": "x", "updated": ""}}
    monkeypatch.setattr(te, "save_glossary", lambda _path, _glossary: None)

    args = _edit_args(set_zh=None, notes=None, status=None, mark_term=False, set_original_term="", force=True)

    assert te.mutate_term(args, glossary) is False


def test_mutate_term_without_mutation_flags_returns_false(monkeypatch):
    glossary = {"_meta": {"updated": ""}}
    args = _edit_args(
        set_zh=None,
        notes=None,
        status=None,
        mark_term=False,
        force=True,
    )

    assert te.mutate_term(args, glossary) is False
    assert "Stress" not in glossary


def test_run_calculation_managed_term_skips_scan(monkeypatch):
    args = _edit_args(cal=True)
    glossary = {"_meta": {"updated": ""}, "Stress": {"status": "approved"}}
    saved: dict[str, object] = {}

    monkeypatch.setattr(te, "ensure_cache_dir", lambda: None)
    monkeypatch.setattr(te, "load_json", lambda _path, _default: {"terms": {}})
    monkeypatch.setattr(te, "save_json", lambda _path, payload: saved.update(payload=payload))
    monkeypatch.setattr(
        te, "build_corpus", lambda _root: pytest.fail("managed term must skip the full scan")
    )

    te.run_calculation(args, glossary)

    entry = saved["payload"]["terms"]["Stress"]
    assert entry["managed"] is True
    assert entry["skipped_full_scan"] is True


# ---------------------------------------------------------------------------
# term_read
# ---------------------------------------------------------------------------

def test_load_or_build_index_uses_cache_when_fingerprint_matches(monkeypatch):
    saves: list[object] = []

    monkeypatch.setattr(tr, "build_corpus", lambda _root: ({"docs/a.md": "x"}, "fp"))
    monkeypatch.setattr(
        tr, "load_json", lambda _path, _default: {"fingerprint": "fp", "corpus": {"docs/a.md": "x"}}
    )
    monkeypatch.setattr(tr, "save_json", lambda _path, payload: saves.append(payload))

    corpus, fingerprint = tr.load_or_build_index(Path("."), force=False)

    assert fingerprint == "fp"
    assert corpus == {"docs/a.md": "x"}
    assert saves == []


def test_load_or_build_index_rebuilds_when_fingerprint_differs(monkeypatch):
    saves: list[object] = []

    monkeypatch.setattr(tr, "build_corpus", lambda _root: ({"docs/a.md": "y"}, "new-fp"))
    monkeypatch.setattr(
        tr, "load_json", lambda _path, _default: {"fingerprint": "old-fp", "corpus": {}}
    )
    monkeypatch.setattr(tr, "save_json", lambda _path, payload: saves.append(payload))

    corpus, fingerprint = tr.load_or_build_index(Path("."), force=False)

    assert fingerprint == "new-fp"
    assert corpus == {"docs/a.md": "y"}
    assert saves and saves[0]["fingerprint"] == "new-fp"


def test_term_read_main_fails_on_missing_terms(monkeypatch):
    args = argparse.Namespace(
        root=None,
        glossary=Path("glossary.json"),
        schema=Path("glossary.schema.json"),
        json=False,
        reindex=False,
        unknown_min_frequency=3,
        unknown_limit=20,
        fail_on_forbidden=False,
        fail_on_missing=True,
        no_schema_validate=True,
    )

    monkeypatch.setattr(tr, "parse_args", lambda: args)
    monkeypatch.setattr(tr, "resolve_root", lambda _root: tr.PROJECT_ROOT)
    monkeypatch.setattr(
        tr,
        "load_glossary",
        lambda _path: {"_meta": {}, "Move": {"status": "approved", "is_term": True}},
    )
    monkeypatch.setattr(tr, "load_or_build_index", lambda _root, force: ({}, "fp"))
    monkeypatch.setattr(tr, "count_terms_batch", lambda _corpus, _terms: {"Move": (0, {})})
    monkeypatch.setattr(tr, "extract_candidates", lambda _corpus, min_frequency: [])

    with pytest.raises(SystemExit):
        tr.main()
