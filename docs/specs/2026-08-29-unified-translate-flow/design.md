# Unified Translate Flow — Design

## Chosen approach

The existing `/translate` workflow remains the orchestration surface. Two small deterministic modules hide the new state and structure invariants:

1. `scripts/translation_context.py` owns creation, validation, fingerprinting, and staleness reporting for `data/translation-context.json`.
2. `scripts/validate_translation_structure.py` owns source/draft Markdown block-shape comparison.

The skill remains responsible for semantic work: reading the complete source, writing the summaries, resolving terminology through the existing glossary workflow, translating prose, dispatching one semantic review, applying targeted repairs, and sequencing writeback/progress/navigation.

## Interfaces and seams

### Translation-context module

Public CLI:

- `init`: create an ordered context skeleton from `chapters.json` and the translation progress map without overwriting an existing context unless explicitly requested.
- `status --json`: report `ready`, `full_refresh_required`, or `decision_refresh_required` by comparing stored and current fingerprints.
- `finalize`: validate that the whole-book summary and every chapter summary/role are populated, require an empty unresolved queue, stamp current fingerprints, and mark the context ready.

The module hides path normalization, chapter ordering, source fingerprint composition, required-field validation, and status classification. `/translate` only needs the reported state and context payload.

### Structure-validation module

Public CLI:

- accept one source Markdown path and one draft Markdown path;
- return zero when their protected block shapes match;
- return non-zero with structured findings when frontmatter shape, heading sequence, list nesting, table shape, fences/admonitions, images, MDX/import blocks, or major block order differ;
- support JSON output for orchestration and human-readable output for diagnosis.

The module intentionally ignores translated prose and semantic correctness. Those remain the semantic reviewer's responsibility.

### Skill seam

`/translate` consumes the two CLIs and existing `draft.py`, terminology, progress, consistency, completeness, and navigation interfaces. The default chapter path is:

`context → glossary → draft → structure validation → one semantic review → targeted repair if needed → writeback → progress → checkpoint/navigation → next chapter`

`/super-translate` becomes a compatibility adapter that forwards its scope to `/translate`; it owns no translation pipeline.

## Existing precedents

- `scripts/init_create_progress.py` and `progress_read.py` establish ordered project state and JSON CLIs.
- `scripts/draft.py` establishes isolated draft paths and fail-closed writeback.
- `scripts/validate_glossary.py` establishes deterministic validation before semantic work.
- `scripts/generate_nav.py` remains the navigation generator rather than adding navigation logic to translation context.

## Alternatives considered

### Store the summary in `style-decisions.json`

Rejected. It would mix large source-derived context with user-authored style policy and increase every existing style consumer's context burden.

### Store the summary only in `.state/`

Rejected. The summary is durable project knowledge needed across sessions and machines; `.state/` is ignored and designed for rebuildable drafts.

### Keep the Markdown reviewer as a second model gate

Rejected for the default path. Its mechanical checks overlap with the semantic reviewer and account for repeated full-document reads. Deterministic validation is cheaper and repeatable.

### Review only after the whole book is complete

Rejected. Per-chapter semantic review catches rule drift before it becomes committed progress, while one pass keeps the normal path bounded.

## Caller burden and locality

- Callers do not calculate hashes, inspect schema details, or compare Markdown blocks themselves.
- `glossary.json` remains the single term-mapping authority; translation context references term keys only.
- Context invalidation stays local to `translation_context.py`.
- Mechanical Markdown fidelity stays local to `validate_translation_structure.py`.
- Semantic decisions stay visible in the skill prompts rather than leaking into scripts.

## Decisions and trade-offs

- Sequential chapter processing is the initial default. It preserves cumulative terminology and context decisions; bounded parallel drafting can be evaluated later.
- Checkpoint commits remain, but they no longer pause the run.
- Navigation regeneration occurs at checkpoints only when translated navigation metadata changed.
- A second semantic review is conditional, not automatic.
- `final-proofread` remains separate from translation completion.

## Risks

- A structural tokenizer can misclassify unusual Markdown/MDX. Tests cover project-supported constructs, and findings fail closed before writeback.
- A stale context could cause cross-chapter drift. Fingerprints distinguish source/chapter changes from glossary/style changes so refresh work is proportional.
- A compatibility wrapper could preserve obsolete behavior accidentally. Forward testing must confirm that `super-translate` contains no reviewer/refiner loop of its own.
- A failed writeback followed by an independent progress update could create false completion. The skill must branch on the writeback exit code, and integration evidence must prove writeback precedes completion.

## Correctness method

- Red/green unit tests exercise each CLI at its public boundary.
- A three-chapter fixture exercises ordered context, writeback/progress sequencing, interruption, and resume.
- Existing script tests and docs build provide regression coverage.
- `test_translate_skill_contract.py` checks stage order, automatic continuation language, positional validator usage, bounded review, and the deprecated compatibility forward. The generic `quick_validate.py` is incompatible with the repository's established `user-invocable` frontmatter key.

## Human final check

The project owner will review whether the unified `/translate` process is understandable and whether one semantic review per chapter is an acceptable cost/quality balance.
