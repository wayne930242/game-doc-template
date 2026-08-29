# Whole-Book Context Prompt

Use this prompt once when `translation_context.py status` reports a missing or fully stale context.

The orchestrator must substitute absolute paths and must make the complete ordered corpus available. The analyst may read the listed source paths; it must not translate or overwrite chapter files.

```text
You are preparing durable context for a complete Traditional Chinese rulebook translation.

Project root: <ABSOLUTE_PROJECT_ROOT>
Chapter map: <ABSOLUTE_CHAPTERS_PATH>
Progress map: <ABSOLUTE_PROGRESS_PATH>
Context skeleton: <ABSOLUTE_CONTEXT_PATH>

Read every unique source represented by the ordered chapter map, covering all mapped chapter/page ranges, before editing the context skeleton. Do not reread the same complete source file for each chapter. Do not stop after a sample, table of contents, or first chapter.

Populate the existing JSON keys without changing its schema:

- book_summary.subject: what the book is about
- book_summary.structure: how its parts and rules depend on one another
- book_summary.tone: source voice, register, and recurring stylistic traits
- book_summary.core_concepts: rules, setting concepts, and recurring entities needed across chapters
- book_summary.translation_priorities: meaning or consistency risks a translator must preserve
- chapters[<target path>].summary: concise account of the complete chapter content
- chapters[<target path>].role: the chapter's function in the book
- chapters[<target path>].key_terms: English glossary keys relevant to this chapter; never copy Chinese mappings here
- chapters[<target path>].depends_on: target paths whose concepts this chapter assumes
- chapters[<target path>].ambiguities: source-specific unresolved readings
- unresolved: only ambiguities that require a user decision

Terminology rules:

- glossary.json remains the only authoritative mapping.
- Record direct, high-confidence candidates for the terminology-management workflow.
- Put a term in unresolved only when multiple plausible readings affect mechanics, meaning, proper names, wordplay, cultural tone, or cross-chapter consistency.
- Include source location and competing readings for every unresolved item.

Do not produce chapter translations, summaries that omit substantial sections, or invented setting/rules. Finish only after every chapter entry has a summary and role.
```
