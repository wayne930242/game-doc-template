# Chapter Translator Prompt

Use this template for one complete chapter draft. Substitute absolute paths and inline only the relevant context; do not inline the full book source again.

````text
You are translating one complete Markdown chapter from English to Traditional Chinese (zh-TW).

Project root: <ABSOLUTE_PROJECT_ROOT>
Source path: <ABSOLUTE_TARGET_FILE>
Draft path: <ABSOLUTE_DRAFT_FILE>

## Whole-book summary

<BOOK_SUMMARY_JSON>

## Current chapter context

<CHAPTER_CONTEXT_JSON>

## Complete current source chapter

```markdown
<SOURCE_CONTENT>
```

## Applicable glossary entries

```json
<GLOSSARY_SUBSET_JSON>
```

## Style decisions

```json
<STYLE_CONTENT>
```

## Translator style

<TRANSLATOR_STYLE_CONTENT>

Translate the complete source chapter. A summary, digest, abridgement, omission, or replacement with explanatory prose is a failed result.

Hard constraints:

- Traditional Chinese only, using Taiwan wording and punctuation.
- Preserve source meaning and every rules distinction.
- Follow glossary mappings exactly.
- Preserve every source block in order: frontmatter, headings, paragraphs, lists, tables, fences, admonitions, blockquotes, images, HTML/MDX, and imports.
- Preserve frontmatter keys, heading levels, list nesting, table shape, code/dice notation, links, images, and MDX syntax.
- Do not invent or repeat a page-title heading.
- Do not invent an overview heading.
- Follow every applicable translation note and the translator-style reference.
- Write only to the registered draft path. Never overwrite the source.

If a genuine ambiguity remains, keep the safest source-faithful wording in the draft and report it. Do not create a glossary mapping by guessing.

Return JSON:

{
  "draft_path": "<ABSOLUTE_DRAFT_FILE>",
  "uncertain": [
    {"source_location": "...", "term_or_passage": "...", "readings": ["..."], "impact": "..."}
  ]
}
````
