# Translator Voice & Style

Shared by `translate` and `bilingual-translate`. The deprecated `super-translate` entry inherits these rules by forwarding to `translate`.

**Purpose:** the project owner's personal translation voice, distilled directly from the owner in interview. Applies as the default register/terminology voice across every project cloned from this template — on top of it, `style-decisions.json.translation_notes` may add project-specific notes, but must not contradict these rules without an explicit owner decision recorded there.

## Rules

1. **Proper nouns** (place names, character names, faction names): default to literal/direct translation. Exception — when the game's own fictional setting is itself Japanese- or Chinese-flavored, flip to localized/idiomatic translation instead of literal.
2. **Slang, cultural references, game jargon**: always localize/adapt to natural Traditional Chinese equivalents; never translate literally.
3. **Register (rule text, procedures, general prose)**: refined colloquial (典雅口語化). Never Mainland Chinese wording (支語). Never sloppy internet-casual phrasing. Never classical/literary Chinese (文言) — this applies to prose AND to proper-noun/terminology translations specifically; an archaic-sounding term name is a defect, not a flourish.
4. **Register exception — play examples**: dialogue-style "example of play" sections (GM/players talking through a scene) loosen up: casual, relaxed, slang-inheriting, like an actual table conversation. Do not apply rule 3's elegant-colloquial baseline inside these blocks.
5. **Point of view**: preserve the source's second-person address ("you") exactly; do not convert to third-person ("the player").
6. **Terminology glossing**: on a mechanic term's first occurrence in a document, follow the Chinese term with the original English in parentheses, e.g. 守密人（Warden）. Do not repeat the gloss on later occurrences in the same document.
7. **Sentence structure**: break long source sentences into multiple short Chinese sentences. Never mirror the source's clause structure/length 1:1.
8. **Biggest red flag**: forcing English grammar onto Chinese (translation-ese/Europeanized Chinese) — the single most common failure mode; actively hunt for it in self-review.

## Where this applies

- `translate` Step 3 translator prompt and Step 5 semantic review
- `super-translate` through its compatibility forward to `translate`
- `bilingual-translate` Step 4 point 3 (placeholder filling) and point 5 (self-review checklist) — applies to the Chinese half of each block only; the English blockquote line stays byte-for-byte untouched regardless
- Codex-routed drafts (`codex-tier.md` §3): inline these rules into the Codex prompt exactly like any other hard constraint — draft origin does not change which voice applies
