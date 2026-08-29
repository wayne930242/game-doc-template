from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TRANSLATE = ROOT / ".claude/skills/translate/SKILL.md"
SUPER = ROOT / ".claude/skills/super-translate/SKILL.md"
BILINGUAL = ROOT / ".claude/skills/bilingual-translate/SKILL.md"
INIT_DOC = ROOT / ".claude/skills/init-doc/SKILL.md"
CODEX_TIER = ROOT / ".claude/skills/translate/codex-tier.md"


def test_translate_documents_unattended_order_and_bounded_review() -> None:
    text = TRANSLATE.read_text(encoding="utf-8")

    stages = [
        "### 2. Prepare or reuse whole-book context",
        "### 3. Build a bounded wave of complete chapter drafts",
        "### 4. Validate structure deterministically",
        "### 5. Review semantics once",
        "### 6. Write back and continue",
        "### 7. Verify the completed scope",
    ]
    assert [text.index(stage) for stage in stages] == sorted(
        text.index(stage) for stage in stages
    )
    assert "without a confirmation pause" in text
    assert "dispatch a second semantic review only when" in text
    assert "final-proofread` is a separate" in text
    assert text.index("invoke `check-completeness`") < text.index(
        "scripts/translation_completion.py --json"
    )
    assert "Partial scopes do not run this handoff" in text
    validator_block = text[text.index("validate_translation_structure.py") :]
    assert validator_block.index("<ABSOLUTE_SOURCE_PATH>") < validator_block.index(
        "<ABSOLUTE_DRAFT_PATH>"
    )
    assert "--source <ABSOLUTE_SOURCE_PATH>" not in validator_block


def test_super_translate_is_only_a_compatibility_forward() -> None:
    text = SUPER.read_text(encoding="utf-8")

    assert "deprecated" in text.lower()
    assert "[`translate`](../translate/SKILL.md)" in text
    assert "Invoke `translate` with the same scope" in text
    assert "Do not run a separate translator" in text
    assert len(text.splitlines()) < 40
    for obsolete in ("translator-prompt.md", "reviewer-prompt.md", "refiner-prompt.md"):
        assert not (SUPER.parent / obsolete).exists()


def test_init_doc_routes_to_translation_only_after_the_final_gate() -> None:
    text = INIT_DOC.read_text(encoding="utf-8")

    gate = text.index("uv run python scripts/init_handoff_gate.py")
    full_route = text.index("/translate all")
    bilingual_route = text.index("/bilingual-translate all")
    assert gate < full_route
    assert gate < bilingual_route
    assert "translation_mode.mode" in text[gate:]
    assert "Do not dispatch either translation skill when the gate fails" in text
    assert "One task for automatic translation dispatch" in text
    assert "close automatic translation dispatch only after the downstream translation skill returns" in text


def test_translation_skills_use_isolated_three_worker_draft_waves() -> None:
    translate = TRANSLATE.read_text(encoding="utf-8")
    bilingual = BILINGUAL.read_text(encoding="utf-8")
    codex_tier = CODEX_TIER.read_text(encoding="utf-8")

    for text in (translate, bilingual):
        assert "maximum of 3 lower-cost draft workers" in text
        assert "Register every draft path sequentially before dispatch" in text
        assert "write back in chapter order" in text
        assert "must not modify glossary" in text
    assert "gpt-5.6-luna" in codex_tier
    assert "Claude Agent fallback uses `sonnet`" in codex_tier
    assert "Never run more than 3 draft workers concurrently" in codex_tier
