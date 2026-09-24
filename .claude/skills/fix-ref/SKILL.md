---
name: fix-ref
description: Convert page-number references in Markdown documentation into link-based cross references. Use when docs contain patterns such as "第 12 頁", "見 12 頁", "page 12", "pages 12-13", "p. 12", or similar page-based wording that should point to real routes or anchors instead of printed page numbers.
---

# Fix Ref

## Overview

Replace navigational page references with verified Markdown links. Work file by file, resolve each page reference to a real section, and replace each match individually instead of using blind global edits.

## Workflow

### Step 1: Resolve Scope and Source Context

1. Default scope to `docs/src/content/docs/**/*.md` unless the user gives a narrower target.
2. Read the target files and the nearby headings before editing.
3. If source mapping is needed, use the extracted markdown, table of contents, or source PDF to map printed page numbers to actual section titles or document routes.

### Step 2: Detect Candidate Patterns

Search for page-reference patterns such as:

- `第 12 頁`
- `見第 12 頁`
- `參見 12 頁`
- `第12頁`
- `page 12`
- `pages 12-13`
- `12 page`
- `p. 12`
- `pp. 12-13`

Treat only navigational references as candidates. Skip:

- references that are already Markdown links
- literal citations, print-layout notes, indexes, or examples where page numbers are content rather than navigation
- filenames, image names, or table values unless the sentence clearly points the reader somewhere

### Step 3: Resolve the Link Target

For each candidate:

1. Find the destination section that lives on that printed page.
2. Prefer a document route such as `/rules/combat/` when the destination is a full page.
3. Use an anchor such as `#damage` or `/rules/combat/#damage` when the sentence points to a subsection.
4. Use the destination title as the link text whenever possible instead of keeping the raw page number.
5. If a page range maps to multiple sections, replace it with one precise link or a small set of precise links that matches the sentence.
6. If the target remains ambiguous after reasonable checking, stop and report the unresolved cases instead of guessing.

### Step 4: Replace Individually

Replace one occurrence at a time. Keep the original sentence meaning, but rewrite the wording so the link reads naturally.

Examples:

- `詳見第 12 頁。` -> `詳見[戰鬥流程](/rules/combat/)。`
- `See page 34.` -> `See [Character Creation](/rules/character-creation/).`
- `見第 18-19 頁。` -> `見[傷害與恢復](/rules/combat/#damage-and-recovery)。`

Prefer descriptive links over patterns like `[第 12 頁](...)` unless the page number itself is semantically important.

### Step 5: Verify the Edited Scope

After editing:

1. Confirm every new route or anchor exists.
2. Re-scan the edited files for leftover page-reference patterns.
3. Preserve frontmatter, headings, tables, lists, and existing Markdown structure.
4. Re-read each changed sentence to make sure the wording still reads naturally.

## Link Rules

- Before writing any absolute route, read `style-decisions.json.deployment`: the base path is `base_path` when `target` is `blog` or `github-pages`, and empty otherwise. Astro/Starlight does NOT auto-prepend the deploy base to literal `[text](/path/)` links written into page content — only Starlight-native constructs (sidebar `slug` entries, generated routes) resolve it automatically. A hardcoded absolute route missing this prefix 404s on any sub-path deploy (the blog export at `/books/<slug>/`, or a GitHub Pages project site); `export_site.py` rejects the build when one remains.
- Use absolute internal routes from the docs root, prefixed with the base path: `<base_path>/rules/basic-moves/` (e.g. `/rules/basic-moves/` when the base path is empty, `/books/my-game/rules/basic-moves/` when it is `/books/my-game`)
- Use anchors for same-page references: `#damage` (anchors never need the base path — they don't change the route)
- Use combined route plus anchor for cross-page subsections: `<base_path>/rules/combat/#damage`
- Do not invent routes or anchors that do not exist

## Red Flags

Never:

- run blind global replacement across all files
- guess a destination when the page mapping is ambiguous
- convert non-navigational numbers
- keep the raw page number as the main link text when a real section title is known
- change mechanics meaning while rewriting the sentence

## Output

Report:

- files changed
- page references converted
- unresolved references that still need user input or source mapping

## Example Usage

```text
/fix-ref
/fix-ref docs/src/content/docs/rules/combat.md
/fix-ref "replace page refs in chapter 3"
```
