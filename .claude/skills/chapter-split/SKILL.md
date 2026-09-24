---
name: chapter-split
description: Use when extracted rulebook markdown needs to be split into semantic documentation files and navigation. Trigger this skill from `init-doc`, future append/add-document flows, or whenever regenerated `_pages.md` source invalidates the existing chapter map. Do not use this skill for temporary translation chunking; that belongs to a separate draft-only translation workflow.
---

# Chapter Split

## Overview

Split one or more extracted `_pages.md` sources into semantic documentation files, then regenerate site navigation from the resulting chapter map.

**Core principle:** Keep publication structure semantic and stable; do not overload chapter split with temporary translation chunking.

**Multi-source support:** When multiple `_pages.md` files exist, each PDF is planned independently and merged into a single `chapters.json`.

## The Process

### Step 1: Resolve Scope and Preconditions

1. Resolve source pages markdown from `$ARGUMENTS` or the caller handoff.
2. Require one or more `_pages.md` sources produced by `extract_pdf.py`.
3. Require `style-decisions.json` if present; reuse existing formatting and proper-noun decisions instead of re-asking.
4. Reuse the caller's image retention decision if available:
   - `preserve_images = true` → enable image manifest handling
   - `preserve_images = false` → disable images in split config
5. Default config output is `chapters.json` unless the caller explicitly provides another path.
6. If 2 or more source files are in scope, treat them as one coordinated planning run. Do not optimize each file in isolation.

#### Multi-Source Detection

Scan `data/markdown/*_pages.md`:
- **1 file** → single PDF flow (existing logic, produce `chapters.json` directly)
- **Multiple files** → multi PDF flow:
  1. Ask user for slug, title, and order per PDF
  2. For each PDF, dispatch TOC planner + wordcount planner independently (Step 3)
  3. Each planner outputs `chapters_<name>.json`
  4. Run `uv run python scripts/merge_multi.py chapters_*.json` to produce `chapters.json`
  5. Continue with split execution as normal (Step 5)

### Step 2: Track Progress

Each stage below has its own explicit **Verification:** check (draft config paths, split/nav script exit codes, output validation in Step 6) — that is the authoritative record of what's done. If a task-tracking tool is available in this session, create one item per stage for visibility:
- topology planning
- split planning
- image split policy
- split execution
- navigation regeneration
- output validation

### Step 3: Draft Chapter Config with Three Focused Agents

Run split planning with three focused agents.
Pipeline: `topology-planner -> toc-planner -> wordcount-planner`.

Split policy for both planners:
- Prefer semantic chapter/file boundaries from the source TOC or clear in-text subheadings.
- Do not break one long chapter into generic numbered parts like `1`, `2`, `3`, `part-1`, or `一`, `二`, `三` unless those are the actual source headings.
- When a long chapter needs internal subdivision, keep the top-level section slug stable and use nested file paths inside `files` (for example `equipment/weapons`) so the output can use subdirectories.
- If no trustworthy subordinate headings exist, keep the chapter as one file and surface the risk instead of inventing arbitrary numbered splits.
- Do not create a menu group that would contain only one Markdown page unless that section is intentionally a direct-link singleton after navigation generation.
- If a section would only have one nearly empty landing page plus one real child page, collapse it before writing `chapters.json`.
- Use current docs tree and existing `chapters.json` as topology evidence when they exist.
- Never use a reserved top-level section slug (`index`, `404`, `_astro`, `pagefind`); `index/index.md` would replace the home page. `split_chapters.py` and `generate_nav.py` reject them. Name a back-of-book index `book-index`, and repair an existing project with `uv run python scripts/rename_chapter.py --from index --to book-index`, then rerun `generate_nav.py`.

1. Create draft config path:
   - `.state/chapter-split/chapters.draft.json`
2. Create draft topology path:
   - `.state/chapter-split/topology.draft.json`
3. Dispatch topology planner using `./split-topology-planner-prompt.md` to decide section grouping, direct-link singletons, and cross-document balance.
4. Dispatch toc planner using `./split-planner-prompt.md` to generate TOC-aligned draft `chapters_config`.
5. Dispatch wordcount planner using `./split-wordcount-planner-prompt.md` to rebalance file granularity based on word count while preserving TOC order.
6. If topology planner or wordcount planner reports unresolved critical issues, stop and ask user in Traditional Chinese before writing the final config.
7. Read the toc planner's `risk_notes` even when there is no `unresolved_critical` entry — `risk_notes` is where a table/list-split-across-boundary conflict (see `split-planner-prompt.md`) gets recorded when neither adjustment fits. Report any non-empty `risk_notes` to the user in Traditional Chinese before writing the final config; do not silently accept a boundary that cuts through a table.

### Step 4: Finalize Config and Image Policy

Before writing the final config:
- if `preserve_images = true`, include:

```json
{
  "images": {
    "enabled": true,
    "assets_dir": "docs/src/assets/extracted",
    "repeat_file_size_threshold": 5
  }
}
```

- if `preserve_images = false`, include:

```json
{
  "images": {
    "enabled": false
  }
}
```

#### Bilingual mode

Read `style-decisions.json` for `translation_mode.mode`.
If `mode == "bilingual"`, add to the final config:

```json
{
  "mode": "bilingual"
}
```

`split_chapters.py` will resolve the effective output path as `<output_dir>/bilingual/`. Do NOT manually set `output_dir` to include `bilingual/` — the script handles that automatically.

Write the final config to `chapters.json` unless the caller explicitly provided another config path.

### Step 5: Execute Split and Regenerate Navigation

Run:

```bash
uv run python scripts/split_chapters.py
uv run python scripts/generate_nav.py
```

If a non-default config path is used, pass it to `split_chapters.py --config <CONFIG_PATH>`.
Current limitation: `generate_nav.py` still reads root `chapters.json`, so callers using another config path must sync it back to root before regenerating navigation.

Navigation behavior:
- `generate_nav.py` flattens single-file sections into direct sidebar links.
- Multi-file sections use Starlight autogenerate groups.
- `split_chapters.py` generates `_meta.yml` files for all group nodes (chapters and nested file groups), used by the `starlight-auto-sidebar` plugin for sidebar label, ordering, and nesting.
- For multi-source projects, the sidebar is fully driven by `_meta.yml` files rather than manual sidebar entries in `astro.config.mjs`.

### Step 6: Validate Output Quality

Validate:
- heading continuity
- page coverage completeness
- image path integrity
- frontmatter correctness
- no table or enumerated list split across a file boundary: for every generated file, check whether its first content block right after frontmatter is a bare list/table item whose number is greater than 1 (e.g. it starts at "91" instead of "1"). This is a strong signal that a table was cut mid-way by the page-range boundary and the planner's own self-check (in `split-planner-prompt.md`) was missed or its `risk_notes` was ignored. If found, do not treat it as acceptable output — move the orphaned rows into the file that owns the rest of the table (matching its existing table/list format exactly) before handing off.

Preview if needed:

```bash
cd docs && bun dev
```

### Step 7: Handoff

Return the finalized chapter map and generated docs to the caller:
- `init-doc` should continue with progress tracker creation and final gate
- manual invocations: if `translation_mode.mode == "bilingual"`, next skill is `/bilingual-translate`; otherwise continue to `/translate` or `/super-translate`

## Work Units

Each planner is one delegated work unit, dispatched in pipeline order. Its brief is colocated with this skill:

| Unit | Brief | Placeholders |
| --- | --- | --- |
| topology-planner | `./split-topology-planner-prompt.md` | `<SOURCE_PAGES_FILE>`, `<CURRENT_CHAPTERS_JSON>`, `<DOCS_TREE_SUMMARY>`, `<DRAFT_TOPOLOGY_PATH>` |
| toc-planner | `./split-planner-prompt.md` | `<SOURCE_PAGES_FILE>`, `<DRAFT_CONFIG_PATH>` |
| wordcount-planner | `./split-wordcount-planner-prompt.md` | `<SOURCE_PAGES_FILE>`, `<DRAFT_CONFIG_PATH>` |

## Progress Sync Contract (Required)

1. If using task tracking, keep it updated at every step.
2. Mark blockers immediately and include failing command/context.
3. Mark split complete only after output validation succeeds.

## When to Stop and Ask for Help

Stop when:
- extracted source is unreadable or page markers are broken
- chapter split planners cannot produce a usable config
- split output corrupts structure repeatedly
- navigation regeneration cannot be reconciled safely

## When to Revisit Earlier Steps

Return to earlier steps when:
- source markdown is regenerated
- TOC interpretation changes
- image retention policy changes

## Red Flags

Never:
- use this skill for temporary translation chunking
- invent arbitrary numbered split files when the source has no matching heading
- skip validation before handing results back to the caller
