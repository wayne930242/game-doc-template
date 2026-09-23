# Split Wordcount Planner Prompt Template

Brief for the split wordcount planner work unit.

**Purpose:** Rebalance TOC-based split draft by word count while keeping TOC order.

````text
You are rebalancing chapter split config by word count.

## Inputs

- Source pages file: <SOURCE_PAGES_FILE>
- Draft config path: <DRAFT_CONFIG_PATH>
- Draft config JSON content (from TOC planner)

## Core Principle

Fewer, larger files are better than many small files. Only split when content
clearly represents a distinct major topic. When in doubt, merge.

## Rules

- Keep TOC order and TOC boundaries as first priority.
- Adjust split granularity using word count as second priority.
- Preferred target is roughly 1200-3500 words per file.
- Below 800 or above 4500 words is allowed only with explicit TOC-based reason.
- Keep config compatible with `scripts/split_chapters.py`.
- Do not ask user whether to split.
- Avoid keeping a section topology that would render as a one-item sidebar menu unless it is intentionally a direct-link singleton.

## Heading-Level Constraint (Critical)

Only split at heading levels that appear in the source TOC or are H2-level
(## headings) in the source. NEVER use H3 (###) or lower headings as split
boundaries. If the only subdivision options are H3 or lower, keep the content
in one file.

## Merge Preference

When two or more adjacent files share a parent section AND their combined word
count is ≤ 3500, STRONGLY prefer merging them into one file. A merged file
with 2500 words is better than two separate files with 800 words each.
If one of those files is only a thin landing page for the other, collapse the
topology instead of preserving a one-child section.

## File Slug Policy

- When merging files that had nested paths, promote to the parent section slug.
- When a long chapter needs multiple files, use nested semantic file paths in
  `files` (for example `equipment/armor`) instead of generic numbered parts.
- Never produce numeric-only or generic part slugs/titles such as `1`, `2`,
  `3`, `part-1`, `part-2`, `一`, `二`, or `三` unless that numbering is the
  actual source heading.

## Exceptions

If no trustworthy H2-level subordinate heading exists, keep the oversized file
and record the reason in `exceptions` or `unresolved_critical`. Do not invent
splits.

## Output JSON Only

{
  "draft_config_path": "<DRAFT_CONFIG_PATH>",
  "chapters_config": {
    "source": "<SOURCE_PAGES_FILE>",
    "output_dir": "docs/src/content/docs",
    "chapters": {}
  },
  "wordcount_estimate": [{ "file": "section-slug/subtopic-slug", "words": 1800 }],
  "exceptions": [{ "file": "...", "reason": "TOC constraint" }],
  "unresolved_critical": []
}
````
