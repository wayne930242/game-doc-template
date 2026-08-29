# Unified Translate Flow — Design

## Chosen approach

The existing `/translate` workflow remains the orchestration surface. Two small deterministic modules hide the new state and structure invariants:

1. `scripts/translation_context.py` owns creation, validation, fingerprinting, and staleness reporting for `data/translation-context.json`.
2. `scripts/validate_translation_structure.py` owns source/draft Markdown block-shape comparison.
3. `scripts/translation_completion.py` owns the final all-chapters-complete guard and deterministic navigation/build/search command sequence.

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

### Draft-wave seam

The existing skill orchestration boundary remains the concurrency seam; no script attempts to spawn model workers. For each wave the orchestrator first performs every shared mutation (`in_progress`, `draft.py path`) sequentially, then dispatches up to three lower-cost workers with immutable, fully inlined chapter inputs and distinct draft paths. Returned drafts can enter independent validation/review work, but writeback and checkpoint state converge in chapter order.

This shape keeps provider-specific worker adapters behind `codex-tier.md`: Codex uses `gpt-5.6-luna` at low effort, Claude Agent fallback uses `sonnet`, and another host may supply an equivalent lower-cost translation-capable worker. The translate skills know the concurrency and isolation contract, not provider setup details.

### Initialization-routing seam

`init-doc` already owns the final verified initialization state and `translation_mode.mode`, so it performs the one routing decision after `init_handoff_gate.py` passes. It invokes the selected translation skill with `all`; downstream skills retain ownership of translation and site completion.

### Completion-handoff module

Public CLI:

- accept a project root and optional Bun executable override;
- refuse to run while any progress entry is not `completed`;
- run navigation regeneration, project validation, site build, and search verification in a fixed fail-closed order;
- emit a machine-readable report of every attempted check and the final `docs/dist/` path.

The module accepts subprocess execution and Bun resolution behind one interface so the skill does not duplicate command ordering or error handling. Semantic consistency and completeness remain skill-owned prerequisites because they require source-aware judgment; the CLI owns only deterministic completion evidence.

## Existing precedents

- `scripts/init_create_progress.py` and `progress_read.py` establish ordered project state and JSON CLIs.
- `scripts/draft.py` establishes isolated draft paths and fail-closed writeback.
- `scripts/validate_glossary.py` establishes deterministic validation before semantic work.
- `scripts/generate_nav.py` remains the navigation generator rather than adding navigation logic to translation context.
- `scripts/init_handoff_gate.py` establishes the fail-closed command-report pattern and Bun build precedent reused by the completion handoff.

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

- Draft generation now uses bounded waves of three after the reusable context and glossary are ready. Shared-state setup and ordered writeback remain sequential, preserving deterministic progress and checkpoint history.
- Checkpoint commits remain, but they no longer pause the run.
- Navigation regeneration occurs at checkpoints only when translated navigation metadata changed.
- A second semantic review is conditional, not automatic.
- `final-proofread` remains separate from translation completion.
- Final navigation/build/search verification runs only after the progress map reaches all-completed; partial translation remains cheap and does not produce a false deployable claim.

## Risks

- A structural tokenizer can misclassify unusual Markdown/MDX. Tests cover project-supported constructs, and findings fail closed before writeback.
- A stale context could cause cross-chapter drift. Fingerprints distinguish source/chapter changes from glossary/style changes so refresh work is proportional.
- A compatibility wrapper could preserve obsolete behavior accidentally. Forward testing must confirm that `super-translate` contains no reviewer/refiner loop of its own.
- A failed writeback followed by an independent progress update could create false completion. The skill must branch on the writeback exit code, and integration evidence must prove writeback precedes completion.
- A stale navigation or failed site build could leave translated Markdown committed without a deployable website. The completion CLI reruns navigation and fails closed on build/search errors.
- Concurrent workers could overwrite the draft manifest or shared decisions. The orchestrator registers paths before dispatch and workers receive read-only shared inputs plus one exclusive draft path.
- A shared ambiguity discovered mid-wave could invalidate sibling terminology. Workers report ambiguities instead of mutating the glossary; the orchestrator groups the decision at the wave boundary and revalidates affected drafts.

## Correctness method

- Red/green unit tests exercise each CLI at its public boundary.
- A three-chapter fixture exercises ordered context, writeback/progress sequencing, interruption, and resume.
- Existing script tests and docs build provide regression coverage.
- `test_translate_skill_contract.py` checks stage order, automatic continuation language, positional validator usage, bounded review, and the deprecated compatibility forward. The generic `quick_validate.py` is incompatible with the repository's established `user-invocable` frontmatter key.

## Human final check

The project owner will review whether the unified `/translate` process is understandable and whether one semantic review per chapter is an acceptable cost/quality balance.
