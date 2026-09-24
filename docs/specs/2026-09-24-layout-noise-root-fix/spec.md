Status: approved
Approved at: 2026-09-24
Approved from: User request to begin the mandatory dispatch contract task.

# Observable contract

The template removes repeated page ornaments and redundant PDF image placements, converts dice-table image indices to text, keeps illustrations, removes duplicate body titles and page furniture, replaces the printed table of contents with route links while retaining blurbs, restores source-supported headings and spread reading order, and generates Traditional Chinese navigation from translated titles. A repeatable repair command upgrades an already translated project without changing its prose. An export gate rejects remaining known layout defects.

Compatibility: retain translated wording, document routes, image assets used by real illustrations, and valid Markdown structure. The repair is idempotent. Unknown headings and ambiguous image roles are reported rather than inferred from line length alone.

Reality anchor: run `uv run pytest scripts/tests`; repair a scratch copy of Kedamono Opera; run layout audit and chapter structure checks; export under `/books/kedamono-opera/`; inspect the listed routes against the English PDF in a browser.
