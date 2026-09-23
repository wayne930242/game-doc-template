# Split Planner Prompt Template

Brief for the split planner work unit.

**Purpose:** Produce an initial deterministic split config draft based on source TOC landmarks.

````text
You are planning chapter split configuration for one extracted markdown source.

## Inputs

- Source pages file: <SOURCE_PAGES_FILE>
- Draft config output path: <DRAFT_CONFIG_PATH>
- style-decisions.json (document_format, proper_nouns)
- Existing chapters.json and docs tree summary when available
- Topology planner output when available

## Hard Constraints

- Do not ask the user whether to split.
- Build config compatible with `scripts/split_chapters.py`.
- Use lowercase kebab-case ASCII for section/file slugs.
- Use semantic TOC-derived or heading-derived slugs for every file.
- Never invent generic numeric-only file slugs or titles such as `1`, `2`, `3`, `part-1`, `part-2`, `一`, `二`, or `三` unless the source itself uses that numbered label as the real heading.
- Preserve TOC order from source.
- Use contiguous, non-overlapping page ranges derived from TOC boundaries.
- If splitting is not necessary, produce one section with one `index` file covering full range.
- When a long chapter needs internal subdivision, prefer nested semantic file paths in `files` (for example `combat/damage`) so output can use subdirectories without changing the top-level section grouping.
- Do not create a section with a near-empty `index` file plus a single child page.
- If a section would otherwise contain only one real page, prefer that page as the section's primary file and rely on navigation flattening instead of fabricating a one-item menu.
- When multiple source files are being planned together, keep the full `chapters_config` balanced across all of them instead of optimizing this source in isolation.

## Critical: Page Number Mapping

Page numbers in `pages` arrays MUST be PDF physical page numbers matching `<!-- PAGE N -->` markers in the source file, NOT print page numbers from the book's TOC or footer.

To determine correct page numbers:
1. Scan the source file for `<!-- PAGE N -->` markers.
2. Find which PAGE marker contains each TOC heading or section start.
3. Use THAT marker number as the page number.

Print page numbers and PDF page numbers often differ (e.g., cover, TOC, or blank pages shift the offset). Always verify by locating the actual heading text within the `<!-- PAGE N -->` block.

## Critical: Never Split a Table or Enumerated List Across a File Boundary

Before finalizing any page-range boundary between two files, check the source content on both sides of that boundary page for an in-progress numbered/lettered table or list (e.g. a d100 random-roll table, an equipment list, a background/traits table) whose numbering continues past the boundary into the next file's page range.

If you find one:
- Prefer extending the EARLIER file's page range to include the entire table, even if this pushes that file above the normal target size.
- If extending the earlier file is not workable, move the boundary earlier so the whole table starts in the LATER file instead.
- If neither adjustment fits (the table alone would force one file far outside any reasonable size), keep the split where it must be, but add a `risk_notes` entry naming the exact table, the item-number range that would land at the start of the next file, and which resolution you chose and why — this is a human-reviewable tradeoff, never a silent split.

A useful self-check after drafting page ranges: for each file boundary, would the resulting NEXT file's first content (right after frontmatter) be a bare list/table item whose number is greater than 1 (e.g. it starts at item "91" instead of "1")? If so, that file is very likely opening mid-table from the previous file's content — treat it as a rule violation and resolve it per the adjustments above before finalizing.

## Planning Basis

- Basis is source TOC structure and heading landmarks.
- Prefer actual subordinate headings from the source over arbitrary page-count splits.
- Avoid purely semantic refactoring not present in source TOC.
- If a chapter is long but lacks trustworthy subordinate headings, keep it as one file and report that risk instead of fabricating numbered parts.

## Index File Policy (Critical)

Only add an `index` file to a section when AT LEAST ONE of the following is true:
1. The source has ≥150 words of prose between the section heading and the first subsection heading (meaningful introductory content).
2. The section is a navigation-only grouping that has no prose content of its own, and a landing/overview page is needed to orient the reader.

DO NOT add an `index` file when:
- The section's content immediately begins with a subsection heading with little or no prose before it.
- The content that would go into `index` is simply a restatement of the section title.
- An `index` page would be nearly empty (fewer than 100 words of actual content).

When omitting the index, map the first subsection directly as the first file in the section's `files`. The section title becomes the directory grouping only.

## Required Output (JSON Only)

{
  "draft_config_path": "<DRAFT_CONFIG_PATH>",
  "chapters_config": {
    "source": "<SOURCE_PAGES_FILE>",
    "output_dir": "docs/src/content/docs",
    "chapters": {
      "section-slug": {
        "title": "...",
        "order": 1,
        "files": {
          "index": {
            "title": "...",
            "description": "...",
            "pages": [1, 10],
            "order": 0
          },
          "subtopic-slug/detail-slug": {
            "title": "...",
            "description": "...",
            "pages": [11, 16],
            "order": 1
          }
        }
      }
    }
  },
  "planning_notes": ["..."],
  "toc_evidence": [{ "toc_item": "...", "start_page": 1, "end_page": 10 }],
  "risk_notes": ["..."]
}
````
