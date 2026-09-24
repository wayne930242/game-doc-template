Status: approved
Approved at: 2026-09-24
Approved from: User request to begin the mandatory dispatch contract task; subsequent main-agent redirect requiring a book-independent template.

# Observable contract

The template removes repeated page ornaments and redundant PDF image placements, converts dice-table image indices to text, keeps illustrations, removes duplicate body titles and page furniture, replaces the printed table of contents with route links while retaining blurbs, restores source-supported headings and spread reading order, and generates Traditional Chinese navigation from translated titles. A repeatable repair command upgrades an already translated project without changing its prose. An export gate rejects remaining known layout defects.

The shared scripts contain no book title, document path, chapter slug, or rulebook phrase. The heading hierarchy is inferred from PDF typography and position at runtime. Source headings align to translated headings through chapter order, surrounding Markdown blocks, and approved glossary entries. A generic command records any remaining book-specific judgment as project data with PDF evidence.

Compatibility: retain translated wording, document routes, image assets used by real illustrations, and valid Markdown structure. The repair is idempotent. Unknown headings and ambiguous image roles are reported rather than inferred from line length alone.

Reality anchor: run `uv run pytest scripts/tests`; repair a scratch copy of Kedamono Opera; run layout audit and chapter structure checks; export under `/books/kedamono-opera/`; inspect the listed routes against the English PDF in a browser.
