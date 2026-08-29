# Targeted Refiner Prompt

Use only after semantic review fails. Supply the reported source/draft blocks plus enough adjacent context to edit safely; do not resend or rewrite the entire chapter when findings are local.

````text
You are repairing specific findings in a Traditional Chinese rulebook translation.

Project root: <ABSOLUTE_PROJECT_ROOT>
Source path: <ABSOLUTE_TARGET_FILE>
Draft path: <ABSOLUTE_DRAFT_FILE>

## Whole-book and chapter context
<RELEVANT_CONTEXT_JSON>

## Reviewer findings
```json
<FINDINGS_JSON>
```

## Affected source and draft blocks
<AFFECTED_BLOCKS_WITH_NEIGHBOURS>

Apply only the changes required by the findings. Preserve already-correct prose and every unaffected block byte-for-byte when practical. Follow the glossary and style decisions. Do not perform general polishing, restructure the chapter, or introduce a new term mapping.

If a finding requires a genuine term/source decision, leave that block unchanged and report the ambiguity for the user.

Write the repaired draft to the same registered draft path and return JSON only:

{
  "draft_path": "<ABSOLUTE_DRAFT_FILE>",
  "changes": [{"source_location": "...", "summary": "..."}],
  "unresolved": [{"source_location": "...", "question": "...", "readings": ["..."]}]
}
````
