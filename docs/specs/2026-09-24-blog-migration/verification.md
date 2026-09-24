# Verification

The main agent confirmed that the live Vercel deployments use the repository `main` commits listed below. Their unmodified scratch builds are the live-content baseline; direct public browsing reaches password gates.

| Requirement | Evidence | Result |
|---|---|---|
| Repeatable migration retains book content and custom presentation | The command ran twice in an automated fixture without changing homepage, CSS, or extra dependencies. Three scratch migrations built with their own sidebars and styling. | pass |
| Root URLs work under a book base and at root | Two URL-rebasing tests pass; all four exports have zero URLs outside their bases. The template root build changed zero HTML/CSS files. Browser homepage/deep links resolve under the correct base. | pass |
| Manifest uses recorded metadata and real translation credit | Three `book.json` files contain derived titles and original titles, the confirmed translator credit, correct slug/base/source repo, and `null` where no progress file exists. Legend reports 16/16. Kedamono retains Hazmole alongside the translator and reports 27/27. | pass |
| Old progress schema and absent style file are handled | Automated tests cover top-level path-keyed statuses and creation of a missing style file. | pass |
| Template tests and build pass | Final `uv run pytest -q`: 669 passed. `bun run test`: 60 passed. `bun run build`: 2 pages and root-base postprocessor no-op. | pass |
| Vaesen scratch proof | Unmodified `8ccf6a7` and migrated export both have 41 HTML files, including 404; visible `.sl-markdown-content` text matches exactly on all 41. Browser homepage, introduction, internal link, `靈視` search/result, and OG image loaded. Archive and manifest validated. | pass |
| Legend in the Mist scratch proof | Unmodified `0168745` and migrated export both have 97 HTML files; visible content text matches exactly on all 97. Browser homepage, tutorial link, hero image, and `迷霧` search loaded. Archive and manifest validated. | pass |
| Cyberpunk Red scratch proof | Unmodified `652b4f6` and migrated export both have 54 HTML files; visible content text matches exactly on all 54. Browser homepage, introduction link, hero image, and `夜城` search loaded. Archive and manifest validated. | pass |
| All local links and referenced assets resolve | Static crawl checked 2,003 Vaesen, 11,727 Legend, 3,471 Cyberpunk, and 2,685 Kedamono local `href`/`src` references; zero targets missing. | pass |
| Kedamono remains usable | A sparse scratch copy exported 29 HTML pages and a valid archive; browser homepage and book links loaded. The manifest retains both translation credits and 27/27 progress. | pass |
| Original repositories remain untouched | `git status --short` returned empty for Vaesen, Legend, Cyberpunk, and Kedamono originals. | pass |
| Release publication | The workflow was reviewed locally; no push or CI release was authorized in this dispatch. | unknown |

## Additional dry-run findings

The migration command inspected the other 15 repositories without writing to them. It derives all required metadata for Cairn, Rapscallion, Apocalypse Keys, and Year Zero Engine. The remaining fields require a confirmed input: `original_title` for BitD Deep Cuts and Hearts of Wulin; translator for Urban Shadows, BitD Deep Cuts, Avatar, Household, Brindlewood Bay, Beneath Cursed Moon, Michtim, Into the Shadows, Wandering Heroes, and Pasión de las Pasiones. Hearts of Wulin explicitly credits `zuzu` for the core translation and Hong Wei for compilation. BitD and Into the Shadows mention an existing translation; review their attribution before applying another translator credit.

## Commands and evidence

Example command sequence is in `README.md` under “遷移既有書站”. Scratch exports, archives, and screenshots are under `/private/tmp/game-doc-blog-migration/`. The exported site was served from `http://127.0.0.1:8765/books/<slug>/` for browser proof.

## Reflexive

| Friction | Classification | Solid-loop action |
|---|---|---|
| Dispatch message sentence limit | gap | The contract already states the rule; corrected the message. |
| `in-progress` is not a reportable task status | gap | The contract's wait/reply lifecycle covers this; continued without an extra status. |
| Default Python lacks pytest and Beautiful Soup | gap | Used the project `uv run` environment; general tool-use slip. |
| Node cannot import this Astro config during postprocessing | gap | Resolved by reading the configured base as text in the build module. |
| Sharp attempted a source build on this host | gap | Recorded `SHARP_IGNORE_GLOBAL_LIBVIPS=1` in README and workflow. |
| Scratch clone working directory did not yet exist | gap | Cloned from its existing parent; general tool-use slip. |
| Urban Shadows uses a path-keyed progress tracker | gap | Resolved by the exporter compatibility branch and test. |
| `bun test` is not this project's `node:test` command | gap | Used the existing `bun run test` script; general tool-use slip. |
| Live sites have password gates | gap | Resolved by the main agent's exact-deployment-SHA baseline decision. |
| Brindlewood Bay uses a double-quoted Astro title | gap | Resolved in the shared config updater and focused test. |

No agent-system instruction changed. Each project fact was resolved in source or the deployment procedure; the remaining slips need no durable instruction.
