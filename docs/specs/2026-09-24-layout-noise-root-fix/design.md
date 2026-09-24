# Design

The extraction pass deduplicates image placements by page, coordinates, and identity. The split pass classifies page furniture using the manifest geometry and frequency. A separate repair command operates on translated Markdown, applies source-backed heading and spread transformations, and regenerates translated navigation. The layout checker runs before export and reports remaining actionable defects.

The repair reads `chapters.json`, translated Markdown, image manifest, source pages, and the existing staged English chapters when present. It writes only project content and generated navigation in the selected project root. A separate `--staged-source` mode repairs a writable copy of the synced English baseline. The staging tree is read-only when it corroborates translated headings. Tests cover each class, including real Kedamono counterexamples.

The source PDF shows that the repeated 9 × 9 px faces index D66 tables, and the six 14 × 14 px pairs identify D66 pack ranges. Repeated rank banners and Master symbols carry rule meaning and remain. The printed table of contents uses a physical-to-printed page offset derived from chapter ranges. The repair links entries while retaining chapter blurbs.

PDF heading fonts also appear in diagrams. The paired pass uses a PDF-verified Kedamono heading catalog and existing translated labels, then aligns heading levels on both sides. H2 starts body sections; H3 marks subsections and feat or Opera cards. It removes paired title repetitions, restores Wingdings lists, and checks PDF glyphs before removing extraction-generated hyphens from English prose. The play-overview spread renders its three stages and sixteen callouts in reading order. The source and translation remain text-preserving and idempotent.

## Verification

| Requirement | Evidence | Result |
|---|---|---|
| Repeated art and dice semantics | Scratch audit: 1666 → 307 image references; 29 → 9 hashes used more than five times, all nine source-verified rank or Master art; D66 text indices and pack ranges rendered | pass |
| Duplicate body H1 and page furniture | Scratch audit: duplicate H1, bare page numbers, running headers, and isolated drop-cap letters all zero | pass |
| Printed TOC and page references | Basic Rules browser page shows linked chapter navigation and ordered spread; audit dot leaders and page-only references zero | pass |
| Lost headings and lists | 131 PDF-verified heading pairs, Apocryphal Feats/Operas, species cards, and scenario labels repaired; body H1 and raw Wingdings markers zero; chart-label counterexamples stay prose | pass |
| Infographic spreads | PDF pp. 12–13 checked against the rendered three-stage, sixteen-step overview; D66 pack ranges and rule tables retain reading order | pass |
| Traditional Chinese navigation | Eight sidebar groups, home hero actions, and quick navigation inspected in exported site | pass |
| Translation structure and prose | Repaired staged English versus repaired translation: 106 → 0 findings across 27 chapters. 1,269 long translated lines and 1,760 English lines checked; unmatched lines are printed TOC/page furniture. All original table cells remain | pass |
| Build and browser | 669 script tests and layout checker pass; exported 29 pages under `/books/kedamono-opera/`; home, Basic Rules, Apocrypha, species index, Sphinx, scenario, GM guidance, and sidebar opened in a real browser | pass |

The chapter comparison has no residual findings. The Sphinx and scenario pages have no lower-level heading that repeats the page title.

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
  Found: OCR-damaged staged headings and translated headings need paired alignment before title removal; the paired pass now resolves the repetitions without structure regressions.
  Led by: none
- Tried: split Wingdings lists with `splitlines()`.
  Found: empty Markdown lines were discarded; splitting each line on literal newlines preserves paragraph boundaries.
  Led by: none
- Tried: browse the scratch export on port 8765.
  Found: an older process owned the IPv4 listener and served a previous export. The final proof used port 8766 after verifying the HTTP body hash against the new export file.
  Led by: none
- Tried: verify paired repair only on a previously normalized scratch copy.
  Found: raw staged source still had H6 title labels, so the initial paired rule missed them. A fresh-copy rerun exposed and fixed the mismatch.
  Led by: none

Reflexive classification: all notes are gaps in the run. PDF classification, title pairing, blank-line retention, and fresh-copy reproduction are now verified in the repair and tests. Interpreter, dependency-symlink, and port conflicts were local environment detours; no agent-system instruction owns those facts.
