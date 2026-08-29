# Unified Translate Flow — Verification

## Scope and environment

- Branch: `main`
- Baseline: `2c7097d`
- Environment: Ubuntu 20.04 under WSL, project-managed Python through `uv`, Bun 1.3.10
- Scope: reusable whole-book context, deterministic Markdown structure validation, bounded semantic review instructions, `super-translate` compatibility forwarding, automatic init routing, three-worker isolated draft waves, ordered writeback, bilingual completion, and project documentation

## Exercised flows

| Flow | Evidence | Result |
| --- | --- | --- |
| Context create, finalize, ready reuse, source/chapter invalidation, glossary/style refresh | `scripts/tests/test_translation_context.py` | Pass |
| Supported Markdown/MDX structure equivalence and protected-shape failures | `scripts/tests/test_validate_translation_structure.py` | Pass |
| `in_progress` resumes before `not_started` | `scripts/tests/test_progress_edit.py` | Pass |
| Three-chapter `0/3 → 1/3 → 3/3`, writeback before completion, interruption/resume | `scripts/tests/test_unified_translate_flow.py` | Pass |
| Unified skill stage order, bounded second review, positional validator CLI, completion handoff, deprecated forward, init auto-routing, max-three isolated drafts, ordered writeback, and lower-cost provider policy | `scripts/tests/test_translate_skill_contract.py` | Pass |
| Completion refusal, fail-closed command order, Bun resolution, error capture, artifact requirements, and alternate bilingual progress selection | `scripts/tests/test_translation_completion.py` | Pass |
| Real completion CLI over an isolated project using the bilingual progress path: navigation, all deterministic guards, Astro build, Pagefind build and verification | `scripts/tests/test_translation_completion_integration.py` — `docs/dist/index.html` and `docs/dist/pagefind/pagefind.js` produced | Pass |
| Init handoff requires a ready context; sample cleanup removes generated context | `scripts/tests/test_init_handoff_gate.py`, `scripts/tests/test_clean_sample_data.py` | Pass |
| Python regression suite | `uv run pytest -q` — 413 passed | Pass |
| Python compilation | `uv run python -m compileall -q scripts` | Pass |
| Documentation site | `/home/weihung/.bun/bin/bun run build && /home/weihung/.bun/bin/bun run verify-search` — 2 pages built, search verification passed | Pass |
| Patch hygiene | `git diff --check` | Pass |

## Findings and resolution

1. The project skill frontmatter uses the established `user-invocable` key, while the generic Codex `quick_validate.py` rejects that key. No project skill schema regression was found. Replaced this incompatible check with `test_translate_skill_contract.py`, which verifies the behavior changed by this work.
2. The initial shell PATH did not expose Bun. The repository build succeeded with the existing WSL installation at `/home/weihung/.bun/bin/bun`; this was an environment-path issue, not a source failure.
3. The first isolated completion fixture omitted schema files and valid page frontmatter, so deterministic guards and Astro correctly rejected it. The fixture now carries the same required inputs as a real initialized project.
4. Symlinking the original `node_modules` into the isolated project caused Astro virtual-module cache paths to disagree. The integration harness now hard-links dependency files when possible and falls back to copying; the completion CLI then passed through its real subprocess path.
5. The first final Python compilation command was launched from `docs/`, so `compileall` could not find `scripts`. It was not accepted as evidence; the command was rerun from the repository root and passed.

## Deferred findings

None. No unresolved finding contradicts the confirmed release criteria.
