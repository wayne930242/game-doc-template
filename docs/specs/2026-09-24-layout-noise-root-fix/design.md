# Design

The extraction pass deduplicates image placements by page, coordinates, and identity. The split pass classifies page furniture using the manifest geometry and frequency. A separate repair command operates on translated Markdown, applies source-backed heading and spread transformations, and regenerates translated navigation. The layout checker runs before export and reports remaining actionable defects.

The repair reads `chapters.json`, translated Markdown, image manifest, source pages, and the existing staged English chapters when present. It writes only project content and generated navigation in the selected project root. A separate `--staged-source` mode repairs a writable copy of the synced English baseline. The staging tree is read-only when it corroborates translated headings. Tests cover each class, including real Kedamono counterexamples.

The source PDF shows that the repeated 9 × 9 px faces index D66 tables, and the six 14 × 14 px pairs identify D66 pack ranges. Repeated rank banners and Master symbols carry rule meaning and remain. The printed table of contents uses a physical-to-printed page offset derived from chapter ranges. The repair links entries while retaining chapter blurbs.

PDF heading fonts also appear in diagrams. A translated plain paragraph becomes a heading only when PDF typography, extracted Markdown, and a missing heading in the synced staging chapter agree. Chart labels with numeric callouts remain paragraphs. Existing H1 title duplicates are removed; lower-level title repetitions remain where the staged English and translation cannot be paired without structural regression.

## Verification

| Requirement | Evidence | Result |
|---|---|---|
| Repeated art and dice semantics | Scratch audit: 1666 → 307 image references; 29 → 9 hashes used more than five times, all nine source-verified rank or Master art; D66 text indices and pack ranges rendered | pass |
| Duplicate body H1 and page furniture | Scratch audit: duplicate H1, bare page numbers, running headers, and isolated drop-cap letters all zero | pass |
| Printed TOC and page references | Basic Rules browser page shows linked chapter navigation and ordered spread; audit dot leaders and page-only references zero | pass |
| Lost headings | Apocryphal Feats and Running the Prelude recovered from three matching source signals; chart-label counterexamples stay plain | pass |
| Traditional Chinese navigation | Eight sidebar groups, home hero actions, and quick navigation inspected in exported site | pass |
| Translation structure and prose | Repaired staged English versus repaired translation: 106 → 93 findings; each of 27 chapters at or below its original count. 1,261 long paragraphs checked; six unmatched blocks are page references or rebuilt tables, and all original table cells remain | pass |
| Build and browser | `659 passed`; layout checker zero; exported 29 pages under `/books/kedamono-opera/`; home, Basic Rules, Apocrypha, species index, Sphinx, scenario, and sidebar opened in a real browser | pass |

The remaining 93 structure findings are listed by chapter in `/private/tmp/kedamono-layout-evidence.md`. All reflect source/translation structural mismatches that preceded the repair, including five whose diagnostic wording changed when a duplicate H1 was removed. The Sphinx and scenario pages still repeat their titles in lower-level headings; the contract's duplicate H1 class is clean.

## Friction Notes

- Tried: import `fitz` with system `python3` to inspect the PDF.
  Found: the system interpreter lacks PyMuPDF; the project `uv run python` environment provides it.
  Led by: none
- Tried: infer missing headings from the PDF display font alone.
  Found: the same font marks chart labels such as Difficulty and Authority, so the repair must corroborate staged source structure.
  Led by: none
- Tried: build the isolated book with symlinked `docs/node_modules`.
  Found: Astro/Vite resolves the symlink outside the project and loses compile metadata; a local dependency copy builds successfully.
  Led by: none
- Tried: remove all lower-level headings matching a page title.
  Found: OCR-damaged staged headings and translated headings do not pair consistently, causing chapter-level structure regressions; the H1 fix meets the defined class.
  Led by: none

Reflexive classification: all four notes are gaps in the run. The PDF-font gap is resolved by source corroboration in the repair, and the lower-level-title gap is resolved by retaining the bounded H1 rule and reporting the residual. The interpreter and symlink notes are local tool-environment detours; no agent-system instruction owns those facts.
