# Design

The migration command is the interface. It reads an existing checkout, derives metadata from its recorded style, Astro title, and homepage, reports gaps, and applies only framework-owned files plus narrow configuration updates. The caller supplies the slug and any confirmed missing title or credit.

The build seam is generated HTML/CSS after Astro and zh-TW search indexing. A small URL rebasing module transforms local root URL attributes and CSS `url()` values using Astro's configured base. This keeps authoring content unchanged and supports MD, MDX components, and homepage links through one boundary. Running with root base is a no-op; already prefixed URLs stay stable.

The export seam consumes the migrated style and optional progress tracker. Legacy style decisions remain intact. The manifest builder requires title, original title, and credits and emits `null` for absent progress. The migration does not regenerate the homepage or sidebar because those files carry book-specific work.

The site framework is pinned to the template's tested Astro/Starlight/search dependencies while retaining additional dependencies and scripts used by custom components. The migration copies only the export pipeline, search implementation, workflow, and schema support; it leaves extraction scripts alone.

## Friction Notes

- Tried: Send a three-sentence Straw Boss message; the helper rejected it. Found: dispatch messages must contain at most two sentences, with sources in `--ref`. Led by: dispatch contract.
- Tried: Clear an `awaiting-main-agent` checkpoint by reporting `in-progress`. Found: the status helper only accepts terminal and waiting states; a reply resolves the checkpoint without changing its status. Led by: dispatch contract.
- Tried: Run `python3 -m pytest`. Found: the default Homebrew Python lacks pytest; use the project `uv run pytest` environment. Led by: none.
- Tried: Import Astro config from the Node postprocessor. Found: Starlight exposes TypeScript from `node_modules`, which Node cannot strip on this runtime; read the generated top-level base value as text instead. Led by: none.
- Tried: Install migrated site dependencies with plain `bun install`. Found: local libvips detection made Sharp attempt a source build without `node-addon-api`; setting `SHARP_IGNORE_GLOBAL_LIBVIPS=1` selects its installed prebuilt binary. Led by: none.
- Tried: Start a Kedamono scratch clone command with the not-yet-created clone as working directory. Found: the command runner requires its working directory to exist before launch; clone from the parent directory. Led by: none.
- Tried: Read Urban Shadows' old progress tracker with the new `chapters` list assumption. Found: it stores per-file status at the top level; the exporter now counts that form and emits `null` for unrecognized empty data. Led by: none.
- Tried: Run `bun test` for the docs suite. Found: Bun's test runner handles these `node:test` files differently; the project's `bun run test` script invokes Node and passes. Led by: none.
- Tried: Open the three live sites for text comparison. Found: all show password gates; the main agent confirmed each live deployment's exact main SHA, so unmodified scratch builds of those SHAs are the comparison baseline. Led by: dispatch anchor.
- Tried: Assume legacy Astro titles use single quotes. Found: Brindlewood Bay uses double quotes; the shared config updater now patches either style. Led by: none.
