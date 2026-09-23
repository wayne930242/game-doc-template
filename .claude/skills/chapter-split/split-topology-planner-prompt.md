# Split Topology Planner Prompt Template

Brief for the topology planner work unit.

**Purpose:** Decide the best section/file topology before editing `chapters.json`.

````text
You are planning the documentation topology for chapter splitting.

## Inputs

- Source pages file(s): <SOURCE_PAGES_FILE>
- Existing chapters.json content: <CURRENT_CHAPTERS_JSON>
- Current docs tree summary: <DOCS_TREE_SUMMARY>
- Draft topology output path: <DRAFT_TOPOLOGY_PATH>

## Core Goal

Produce the best section/file layout before anyone edits `chapters.json`.
Optimize for reader navigation, not raw TOC fidelity alone.

## Hard Constraints

- Build a plan compatible with `scripts/split_chapters.py` and `scripts/generate_nav.py`.
- Use lowercase kebab-case ASCII for section/file slugs.
- Consider all target source files together when 2 or more files are being added or re-split.
- Reuse stable existing routes when they are already good enough.
- Do not force a section landing page or `index` file just to preserve a menu group.

## Navigation Topology Rules

1. Avoid creating a sidebar group that would contain only one Markdown page.
2. If a section would contain only one file, prefer a direct-link singleton section unless there is meaningful landing-page prose that justifies an `index` file.
3. If a section has one near-empty landing page plus one real child page, collapse it into one primary page instead of keeping a one-item menu.
4. If two or more target docs are being planned together, check whether adjacent sections should stay parallel, merge, or be nested so the overall sidebar remains balanced.
5. Preserve semantic boundaries from the source TOC; never merge unrelated chapters just to reduce item count.
6. Use nested file paths only when they create a clearer multi-page topic cluster, not when they merely add one more directory level.

## Planning Basis

- Existing `chapters.json`
- Current docs directory shape
- Source TOC landmarks and visible heading structure
- Expected sidebar outcome after `generate_nav.py`

## Required Output (JSON Only)

{
  "draft_topology_path": "<DRAFT_TOPOLOGY_PATH>",
  "section_strategy": [
    {
      "section": "combat",
      "decision": "group|direct-link|merge-into-neighbor|keep-existing",
      "reason": "..."
    }
  ],
  "topology_notes": ["..."],
  "singleton_risks": [{ "section": "...", "reason": "..." }],
  "unresolved_critical": []
}
````
