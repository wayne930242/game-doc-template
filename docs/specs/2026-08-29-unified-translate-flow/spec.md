# Unified Translate Flow — Specification

## Observable contract

### 1. Persistent whole-book context

- The workflow SHALL maintain `data/translation-context.json` as committed, reusable project state.
- The context SHALL contain:
  - fingerprints for the ordered source corpus, `chapters.json`, `glossary.json`, and `style-decisions.json`;
  - a whole-book summary covering subject, structure, tone, core rules/concepts, world information, and translation priorities;
  - one entry per translation-progress chapter with its path, source range, summary, role in the book, relevant terms, dependencies, and unresolved ambiguities.
- Context preparation SHALL read every source chapter in `chapters.json` order before the first translation draft is generated.
- When source or chapter structure changes, the context SHALL become stale and require a full refresh.
- A glossary/style-only change SHALL refresh the affected decision/context fields without forcing another complete source read when the stored source fingerprints still match.
- `glossary.json` remains the only authoritative term mapping. The context may reference terms but SHALL NOT duplicate authoritative translations.

### 2. Terminology preparation

- Context preparation SHALL reuse `terminology-management`, including one corpus candidate-generation/cache pass.
- Existing approved glossary entries SHALL be preserved.
- Unambiguous direct mappings may be approved automatically through the existing glossary tools.
- The workflow SHALL ask the user only when a term or passage has multiple plausible readings that affect mechanics, meaning, names, wordplay, cultural tone, or cross-chapter consistency.
- Resolved answers SHALL be written to the glossary/context before affected chapters continue and SHALL NOT be asked again while the relevant fingerprints remain valid.

### 3. Scope and automatic continuation

- `/translate <file-or-scope>` SHALL translate the explicit scope.
- `/translate`, `/translate next`, and `/translate all` SHALL select from `data/translation-progress.json` without asking for batch confirmation.
- Resume order SHALL be `in_progress` first, then `not_started`, preserving chapter order within each group.
- Checkpoint batches MAY remain for bounded work and Git commits, but SHALL NOT pause to ask whether the next batch should begin.
- The workflow SHALL continue until all selected work completes, a user-owned ambiguity blocks the affected work, an unrecoverable validation failure occurs, or the user interrupts it.

### 4. Per-chapter translation inputs and output

- Every chapter translation SHALL receive:
  - the full source content for that chapter;
  - the whole-book summary;
  - the chapter summary and cross-chapter dependencies;
  - the applicable glossary entries and unresolved-term status;
  - `style-decisions.json` and translator style constraints.
- The translation prompt SHALL require a complete translation of the chapter. Summarization, omission, condensation, and replacement with a rules digest are invalid outputs.
- Draft isolation and the existing `draft.py` manifest/writeback contract SHALL remain in force.
- Absolute project, target, and draft paths SHALL be supplied to delegated workers.

### 5. Quality gates

- A deterministic structure validator SHALL compare source and draft block shape, including frontmatter, heading levels, ordered/unordered list nesting, tables, code fences, admonitions, images, MDX/import blocks, and block order.
- A normal chapter SHALL receive exactly one semantic-review model pass covering completeness, mechanics fidelity, glossary use, natural zh-TW, and unsupported additions.
- The fixed per-chapter Markdown-review agent SHALL be removed from the default path.
- When deterministic validation fails, the workflow SHALL repair only the affected structure before semantic review.
- When semantic review fails, the workflow SHALL repair only the reported blocks. It SHALL rerun deterministic validation and dispatch a second semantic review only for findings whose correctness still requires semantic judgment.
- A chapter SHALL NOT be written back until deterministic validation passes and its semantic findings are resolved.

### 6. Incremental persistence

- After a chapter passes, the workflow SHALL:
  1. write back through `draft.py` and require an exit code of zero;
  2. update that chapter to `completed` in `data/translation-progress.json`;
  3. synchronize translated title/description metadata used by navigation when changed;
  4. regenerate navigation at the next checkpoint when navigation metadata changed;
  5. create the existing narrow `progress: X/Y` checkpoint commit;
  6. continue to the next selected chapter without user confirmation.
- A failed writeback SHALL prevent the corresponding progress entry from becoming `completed`.
- Page headings SHALL remain in the translated document so Starlight can build each page's table of contents incrementally.

### 7. Completion and release boundary

- After the selected translation scope completes, the workflow SHALL run glossary validation and terminology consistency.
- When the whole book completes, the workflow SHALL invoke content completeness checking once.
- When and only when every translation-progress chapter is `completed`, the workflow SHALL run one fail-closed completion handoff that:
  1. regenerates navigation from the root `chapters.json`;
  2. rechecks glossary, style decisions, forbidden/missing terminology, and reusable context readiness;
  3. runs the documentation production build;
  4. verifies the generated search index;
  5. requires `docs/dist/index.html` and `docs/dist/pagefind/pagefind.js` to exist;
  6. reports the deployable `docs/dist/` path.
- A partial scope SHALL stop after its scoped checks and SHALL NOT claim that the final website is complete.
- Any navigation, validation, build, or search-verification failure SHALL return non-zero and prevent the workflow from reporting whole-book completion.
- `final-proofread` SHALL be reported as a separate publication step and SHALL NOT run automatically from `/translate`.

### 8. `super-translate` deprecation

- The `super-translate` skill SHALL become a thin compatibility wrapper around the unified `/translate` flow.
- It SHALL no longer describe or execute the translator → dual reviewer → refiner loop.
- Project documentation SHALL mark it deprecated and direct new work to `/translate`.
- The wrapper SHALL preserve existing invocations during the transition; removal is a future explicit change.

## Compatibility constraints

- Preserve `glossary.json`, `style-decisions.json`, `chapters.json`, `data/translation-progress.json`, `.state/<skill>/draft-manifest.json`, and `progress: X/Y` commits.
- Preserve the optional Codex draft-tier path; extend its prompt context rather than changing the opt-in/model policy.
- Preserve Traditional Chinese and project terminology laws in `AGENTS.md`/`CLAUDE.md`.
- Do not weaken source completeness, Markdown fidelity, or writeback isolation.

## Non-goals

- No automatic translation prose is generated by deterministic scripts.
- No parallel chapter drafting is required by this change. Concurrency may be introduced later after the sequential context flow is proven.
- No replacement for `final-proofread` is introduced.

## Applied standards and evidence

- `AGENTS.md` and `CLAUDE.md`: Traditional Chinese, glossary authority, terminology consultation, progress commits, and project workflow.
- `.claude/skills/terminology-management/SKILL.md`: corpus candidate generation and glossary mutation.
- `.claude/skills/translate/SKILL.md`: existing draft/writeback/progress contract to preserve.
- `dogfood-report/cairn-barebones-findings.md`: observed cost of heavyweight sequential agents, skipped review risk, and false-completion risk after failed writeback.
- `docs/specs/2026-08-29-unified-translate-flow/requirements.md`: confirmed user decisions.

## Verification strategy

### Agent-owned correctness

- Unit tests for context creation, fingerprint reuse/invalidation, ordered chapter mapping, and unresolved-term persistence.
- Unit tests for deterministic Markdown structure comparison, including a passing equivalent document and failures for dropped/reordered headings, lists, tables, fences, images, frontmatter, and MDX blocks.
- CLI tests for the whole-book completion handoff, including incomplete-progress refusal, ordered fail-closed checks, successful build/search verification, and failure propagation.
- Regression test that resume order is `in_progress` before `not_started`.
- Integration test over a three-chapter fixture proving context preparation, `0/3 → 1/3 → 3/3` persistence, writeback-before-completed ordering, and interruption/resume.
- Navigation tests proving translated metadata is reflected at checkpoints without hiding untranslated chapters.
- Skill ordering and compatibility-forward contract tests for a realistic `/translate all` request. The generic `quick_validate.py` is not used because this repository's established skill frontmatter includes `user-invocable`, which that validator does not accept.
- Existing Python suite and relevant docs build remain green.

### Human-owned appropriateness

- After implementation, the project owner judges whether the unified `/translate` instructions are clear enough to trust for an unattended whole-book run and whether the retained semantic-review cost is acceptable.

## User confirmation

Confirmed by the project owner on 2026-08-29.
