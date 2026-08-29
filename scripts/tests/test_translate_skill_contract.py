from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TRANSLATE = ROOT / ".claude/skills/translate/SKILL.md"
SUPER = ROOT / ".claude/skills/super-translate/SKILL.md"


def test_translate_documents_unattended_order_and_bounded_review() -> None:
    text = TRANSLATE.read_text(encoding="utf-8")

    stages = [
        "### 2. Prepare or reuse whole-book context",
        "### 3. Build one complete chapter draft",
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
