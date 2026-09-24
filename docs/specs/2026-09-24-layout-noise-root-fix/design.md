# Design

The extraction pass deduplicates image placements by page, coordinates, and identity. The split pass classifies page furniture using the manifest geometry and frequency. A separate repair command operates on translated Markdown, applies source-backed heading and spread transformations, and regenerates translated navigation. The layout checker runs before export and reports remaining actionable defects.

The repair reads `chapters.json`, translated Markdown, image manifest, source pages, and the existing staged English chapters when present. It writes only project content and generated navigation in the selected project root. A separate `--staged-source` mode repairs a writable copy of the synced English baseline. The staging tree is read-only when it corroborates translated headings. Tests cover each class, including real Kedamono counterexamples.

The source PDF shows that the repeated 9 × 9 px faces index D66 tables, and the six 14 × 14 px pairs identify D66 pack ranges. Repeated rank banners and Master symbols carry rule meaning and remain. The printed table of contents uses a physical-to-printed page offset derived from chapter ranges. The repair links entries while retaining chapter blurbs.

The PDF layout seam produces per-page evidence from text spans: font size relative to body text, visible weight, leading glyph, and position. A generic paired pass matches these source lines to translated blocks in order. Shared image references anchor position; existing Markdown headings and approved glossary terms strengthen a match. The command writes its evidence, resolved pairings, and uncertain candidates to `data/layout-repair.json` in the selected project. A PDF-reviewed copy may add project-owned structural marker decisions through `--reviewed-source` and `--reviewed-target`; the automatic pass alone is not claimed to resolve every ambiguous line. Subsequent repairs validate the PDF fingerprint. After writeback, source and translation digests make an unchanged rerun a no-op and require a newly derived plan when either side changes. The template contains no book labels, paths, or heading-pair table. H2 starts body sections and H3 marks a subsection where the preceding PDF display heading establishes a parent.

## Verification

| Requirement | Evidence | Result |
|---|---|---|
| Repeated art and dice semantics | Scratch audit: 1666 → 307 image references; 29 → 9 hashes used more than five times, all nine source-verified rank or Master art; D66 text indices and pack ranges rendered | pass |
| Duplicate body H1 and page furniture | Scratch audit: duplicate H1, bare page numbers, running headers, and isolated drop-cap letters all zero | pass |
| Printed TOC and page references | Basic Rules browser page shows linked chapter navigation and ordered spread; audit dot leaders and page-only references zero | pass |
| Lost headings and lists | PDF roles and structural pairing restore body headings; raw English glyphs are paired with translated list evidence. One translated H3 retains PDF support despite the English extraction leaving that line plain. | pass with one justified structure difference |
| Infographic spreads | PDF pp. 12–13 checked against the rendered three-stage, sixteen-step overview; D66 pack ranges and rule tables retain reading order | pass |
| Traditional Chinese navigation | Eight sidebar groups, home hero actions, and quick navigation inspected in exported site | pass |
| Translation structure and prose | Repaired staged English versus repaired translation: 106 → 1 findings across 27 chapters; only Basic Rules remains above zero, below its baseline of 46. The other 26 chapters are zero, including all zero-baseline chapters. All 1,269 long translated lines and 1,760 English lines were checked; 10 unmatched lines are printed TOC leaders or page-reference clusters. All 178 substantive table cells remain. | pass with one justified difference |
| Build and browser | 667 script tests and layout checker pass; `export_site.py` exported 29 pages and 274 files under `/books/kedamono-opera/`. Home, Basic Rules, Apocrypha, species index, Sphinx, scenario, GM guidance, and Traditional Chinese sidebar opened in a real browser. | pass |
| Repeatability and generic code | A second staged-source run returned `already_applied: 1`; `rg -i 'kedamono\|basic-rules\|Kedamono_Opera' scripts/*.py` returned no match. | pass |

The sole residual is `basic-rules/index.md`: the translated `### 歌劇` appears as an unexpected H3 at line 342. The English staged extraction has `oPera` as plain text at line 351, while PDF page 17 renders “Opera” as a 20 pt display label and the approved glossary maps it to `歌劇`. Keeping the translated H3 follows the PDF. The content and ordering are preserved.

## Friction Notes

- Tried: import `fitz` with system `python3` to inspect the PDF.
  Found: the system interpreter lacks PyMuPDF; the project `uv run python` environment provides it.
  Led by: none
- Tried: infer missing headings from the PDF display font alone.
  Found: the same font marks chart labels, so the repair corroborates staged source structure and approved glossary terms.
  Led by: none
- Tried: build the isolated book with symlinked `docs/node_modules`.
  Found: Astro/Vite resolves the symlink outside the project and loses compile metadata; a local dependency copy builds successfully.
  Led by: none
- Tried: remove all lower-level headings matching a page title.
  Found: OCR-damaged staged headings and translated headings need paired alignment before title removal; the paired pass now resolves the repetitions without structure regressions.
  Led by: none
- Tried: infer a spread from repeated full-width spaces throughout a chapter.
  Found: ordinary tables and species fields also use those spaces. The checker and formatter now require a PDF-proved spread.
  Led by: none
- Tried: repeat the paired repair against already repaired chapters.
  Found: applying the same structural overlays twice could alter source headings. The project plan now records both output digests and makes an unchanged rerun a no-op.
  Led by: none
- Tried: verify paired repair only on a previously normalized scratch copy.
  Found: raw staged source still had H6 title labels, so the initial paired rule missed them. A fresh-copy rerun exposed and fixed the mismatch.
  Led by: none

Reflexive classification: PDF classification, title pairing, spread scope, repeatability, and fresh-copy reproduction are verified in the repair and tests. Interpreter and dependency-copy issues were local environment detours.
