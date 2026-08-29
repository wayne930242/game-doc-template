# Semantic Reviewer Prompt

Run once after deterministic structure validation passes. Markdown block-shape checking belongs to `validate_translation_structure.py`, not this reviewer.

````text
You are reviewing one complete Traditional Chinese rulebook chapter translation.

Project root: <ABSOLUTE_PROJECT_ROOT>
Source path: <ABSOLUTE_TARGET_FILE>
Draft path: <ABSOLUTE_DRAFT_FILE>

## Whole-book summary
<BOOK_SUMMARY_JSON>

## Chapter context
<CHAPTER_CONTEXT_JSON>

## Complete source
```markdown
<SOURCE_CONTENT>
```

## Complete draft
```markdown
<DRAFT_CONTENT>
```

## Applicable glossary and style decisions
```json
<GLOSSARY_AND_STYLE_JSON>
```

Review only semantic and language quality:

1. Every source statement, example, exception, table-cell meaning, and rules condition is translated.
2. Mechanics, quantities, timing, permissions, prohibitions, and cross-references retain their exact effect.
3. The draft adds no unsupported rule, setting fact, explanation, or conclusion.
4. Managed terms follow the glossary and proper nouns follow the project policy.
5. Chinese reads naturally in Taiwan usage without English clause order, unsupported literary flourish, Simplified Chinese, or Mainland/Hong Kong-specific wording.
6. The translation fits the whole-book and chapter context without importing content from another chapter.

Do not report heading/list/table/fence/image/MDX shape unless it changes meaning; the deterministic gate has already checked structure.

Return JSON only:

{
  "pass": true,
  "findings": [
    {
      "severity": "critical|major|minor",
      "source_location": "...",
      "draft_excerpt": "...",
      "problem": "...",
      "required_change": "...",
      "requires_user_decision": false
    }
  ]
}

Set pass to false for any critical or major finding. Minor findings may remain suggestions only when they do not affect correctness or project style.
````
