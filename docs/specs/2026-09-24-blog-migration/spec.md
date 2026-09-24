Status: approved
Approved at: 2026-09-24
Approved from: User instruction to begin the mandatory dispatch contract task.

# Observable contract

1. A repeatable command migrates an existing book checkout to the template's blog build, search, export, and release workflow while retaining its translated pages, custom components, styling, and sidebar.
2. Generated local root URLs in HTML and CSS resolve under `/books/<slug>/`; root deployment still resolves at `/`.
3. `book.json` has recorded title, original title, and credit. Missing values are reported and never invented. A missing progress file yields `null` progress.
4. The migration can be run again without duplicating configuration or changing source content.
5. Template tests cover URL rebasing and metadata derivation.
6. Vaesen, Legend in the Mist, and Cyberpunk Red are migrated in scratch copies, exported, served under their blog paths, and checked in a browser against live page count/text and representative links, images, and zh-TW search. Kedamono's existing export remains usable.

## Compatibility and scope

The 18 original repositories, their Git state, and the blog repository are read-only in this task. The template's extraction scripts are outside scope. A migration reports source data that cannot establish a translator rather than using the repository owner or Git author as a proxy.

## Standards and evidence

The template's `AGENTS.md`, existing `scripts/export_site.py`, `scripts/generate_nav.py`, `docs/search/`, and `.github/workflows/book-export.yml` define current behavior. The deployment brief fixes the three proof sites and their live URLs.

## Reality anchor

Checkpoint: run template tests; execute each scratch migration and `export_site.py`; serve each export at `/books/<slug>/`; inspect real browser pages and search; compare page count and rendered text with the named live site; inspect each `book.json`; verify Kedamono's export; review the diff; commit named files without pushing.
