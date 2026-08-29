# Unified Translate Flow — Requirements

## Outcome and actors

The project owner wants one primary `/translate` workflow that combines the whole-book context and semantic quality advantages of `super-translate` without its fixed multi-agent review loop. A translation operator should be able to start or resume a rulebook translation and let it continue automatically until a genuine ambiguity or execution failure requires attention.

## In scope

- Make `/translate` the primary focused-file and whole-book translation workflow.
- Read the complete ordered source corpus once, create a reusable whole-book summary, and summarize every chapter before translation begins.
- Decide unambiguous terminology before chapter translation and ask the user only about terms or source passages whose ambiguity affects meaning, mechanics, names, wordplay, or tone.
- Translate each chapter in full using the whole-book context, chapter context, glossary, and style decisions.
- Replace the fixed Markdown-review agent with deterministic structure validation.
- Keep one semantic review per chapter; use targeted repair and a second semantic review only when the first review finds unresolved semantic problems.
- Write each passing chapter back immediately, update progress, maintain translated headings/navigation data, and continue automatically.
- Run terminology consistency and content completeness checks after translation finishes.
- Deprecate `super-translate` gradually through a compatibility wrapper instead of removing the command immediately.

## Out of scope

- Translating a specific rulebook as part of this change.
- Changing the selected translation models or Codex tier defaults unless required to carry the new context.
- Redesigning PDF extraction or semantic chapter splitting.
- Automatically invoking `final-proofread`; it remains a separate release-readiness workflow.
- Removing the `super-translate` command in this change.

## Concrete scenarios

1. **New whole-book translation:** `/translate all` reads every source chapter in `chapters.json` order, creates reusable translation context, resolves terminology, then translates every pending chapter without batch confirmation prompts.
2. **Focused translation:** `/translate <file>` reuses a valid whole-book context and translates only the requested file. If context is absent or stale, it prepares or refreshes that context first.
3. **Resume:** an interrupted run processes `in_progress` chapters before `not_started` chapters and does not ask the user to re-confirm the known scope.
4. **Unambiguous terminology:** direct, high-confidence mappings are recorded through the existing glossary workflow without a user interruption.
5. **Ambiguous terminology or source:** the affected chapter pauses; questions are grouped when possible, and only unresolved items are shown to the user.
6. **Passing chapter:** deterministic structure validation and one semantic review pass; the chapter is written back, progress is updated, navigation is synchronized when its labels changed, and the next chapter starts.
7. **Failing chapter:** repair only the reported blocks, rerun deterministic checks, and request a second semantic review only when semantic findings remain relevant.
8. **Completed translation:** run glossary consistency and content completeness once. Report `final-proofread` as the separate next step for publication.
9. **Legacy invocation:** `/super-translate` reports its deprecation once and delegates to the unified `/translate` behavior without running the old reviewer/refiner pipeline.

## Confirmed decisions

- `/translate` absorbs the useful whole-book and semantic-review behavior from `super-translate`.
- `super-translate` enters a compatibility/deprecation period rather than being removed immediately.
- A normal passing chapter receives one semantic review.
- Markdown/block-shape validation becomes deterministic.
- Targeted repair replaces whole-chapter refiner passes.
- The workflow asks the user only when ambiguity or an unrecoverable failure affects correctness.
- Translation completion automatically runs consistency and completeness checks, but not `final-proofread`.

## Open questions

None.
