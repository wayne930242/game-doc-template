from __future__ import annotations

import _term_lib as tl


def test_canonical_term_key_collapses_whitespace_and_singularizes_last_token(monkeypatch):
    monkeypatch.setattr(tl, "_singularize_token", lambda _token: "Move")
    assert tl.canonical_term_key("  Basic   Moves  ") == "Basic Move"


def test_canonical_term_key_returns_empty_for_blank():
    assert tl.canonical_term_key("   ") == ""


def test_parse_doc_expands_nlp_max_length_for_large_text(monkeypatch):
    class FakeNLP:
        def __init__(self) -> None:
            self.max_length = 1_000_000

        def __call__(self, text: str) -> dict[str, int]:
            if len(text) > self.max_length:
                raise ValueError("text exceeds max_length")
            return {"length": len(text)}

    large_text = "a" * 1_000_010
    fake_nlp = FakeNLP()

    monkeypatch.setattr(tl, "SPACY_AVAILABLE", True)
    monkeypatch.setattr(tl, "get_nlp", lambda: fake_nlp)
    monkeypatch.setattr(tl, "_DOC_CACHE", {})

    doc = tl.parse_doc(large_text)

    assert doc == {"length": len(large_text)}
    assert fake_nlp.max_length >= len(large_text)


def test_extract_candidates_fallback_without_spacy(monkeypatch):
    monkeypatch.setattr(tl, "SPACY_AVAILABLE", False)
    result = tl.extract_candidates({"docs/a.md": "Move move harm move"}, min_frequency=2)
    assert "move" in {item["normalized"] for item in result}


def test_count_term_fallback_case_insensitive(monkeypatch):
    monkeypatch.setattr(tl, "SPACY_AVAILABLE", False)
    monkeypatch.setattr(tl, "INFLECT_AVAILABLE", False)

    total, files = tl.count_term({"docs/a.md": "move MOVE moves"}, "move")

    assert total == 2
    assert files["docs/a.md"] == 2


def test_is_managed_term_requires_flag_or_approved_status():
    assert tl.is_managed_term("Move", {"is_term": True}) is True
    assert tl.is_managed_term("Move", {"status": "approved"}) is True
    assert tl.is_managed_term("Move", {"status": "candidate"}) is False
    assert tl.is_managed_term("Move", None) is False


def test_count_term_matches_term_inside_markdown_table_cell():
    if not tl.SPACY_AVAILABLE:
        import pytest

        pytest.skip("spaCy not available")

    corpus = {
        "docs/a.md": (
            "| Faction | Ally |\n"
            "| --- | --- |\n"
            "| Bolia | Naus |\n"
        )
    }

    total, files = tl.count_term(corpus, "Bolia")

    assert total == 1
    assert files["docs/a.md"] == 1


def test_normalized_tokens_strips_markdown_table_pipes_from_edges(monkeypatch):
    if not tl.SPACY_AVAILABLE:
        import pytest

        pytest.skip("spaCy not available")

    doc = tl.parse_doc("| Bolia | Naus |")
    tokens = tl._normalized_tokens(doc)
    norms = [t["norm"] for t in tokens]

    assert "bolia" in norms
    assert "naus" in norms
    assert not any(norm.startswith("|") or norm.endswith("|") for norm in norms)
