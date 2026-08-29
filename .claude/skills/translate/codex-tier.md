# Codex Draft Tier

Shared by `translate` and `bilingual-translate`. The deprecated `super-translate` entry forwards to `translate` and therefore inherits this behavior.

**Purpose:** delegate draft generation to a local Codex CLI when the project has opted in and Codex is usable. Draft origin never changes the calling skill's current validation, semantic-review, or writeback contract.

## 1. Resolve Codex Tiering Preference (once per project)

Check `style-decisions.json.codex_tier.enabled`.

- **Unset** → ask once, Traditional Chinese: "這個專案要在翻譯草稿階段優先使用本機 Codex（較低階模型、低 effort）以節省 Claude token 嗎？" Persist the answer:
  ```json
  { "codex_tier": { "enabled": true } }
  ```
  or `{ "enabled": false }`.
- **Set** → use it silently. Never ask again for this project.
- **`enabled: false`** → skip the rest of this file entirely for every run. Draft generation always happens in the Claude session/subagent, exactly as before this feature existed.

## 2. Codex Availability (only when tiering is enabled)

```bash
node "$(find ~/.claude/plugins/cache/openai-codex -maxdepth 4 -name codex-companion.mjs | head -1)" setup --json
```

Read `.ready`, `.codex.available`, `.auth.loggedIn`.

- **Available + authenticated** → route drafts to Codex (Section 3).
- **Not available, `npm` available, no prior decline recorded** → `AskUserQuestion`, options `Install Codex (Recommended)` / `Skip for now` (same UX as `codex:setup`). If installed, re-run the check. If declined, save a **project**-type memory entry recording the decline for this project and proceed on the Claude-only path for this run.
- **Not available, decline already on record** → proceed on the Claude-only path silently. No prompt.
- **Available but `--enabled: false` per Section 1** → unreachable; Section 1 already short-circuited.

## 3. Codex Invocation (verified working shape)

```bash
codex exec \
  -m gpt-5.6-luna \
  -c model_reasoning_effort="low" \
  -s workspace-write \
  -C "<PROJECT_ROOT>" \
  --skip-git-repo-check \
  --output-schema "<SCHEMA_FILE>" \
  -o "<RESULT_FILE>" \
  --json \
  "<PROMPT>" \
  < /dev/null
```

- `-C` the actual project root (not a scratch dir) so Codex's writes land in the real `.state/<skill>/drafts/...` path.
- `--skip-git-repo-check` is defensive; harmless when `-C` is already a trusted git repo.
- `<PROMPT>` must inline everything Codex needs — it does not have the calling skill's context. For `translate`, include the whole-book summary, current chapter context, complete current source chapter, applicable glossary subset, `style-decisions.json`, `translator-style.md`, the absolute registered draft path, and every hard constraint from `translator-prompt.md`. Do not inline the complete source corpus after `translation-context.json` is ready.
- `<SCHEMA_FILE>` / `<RESULT_FILE>`: when the calling skill needs structured output, write a JSON Schema matching that prompt's required shape, pass it via `--output-schema`, and read `<RESULT_FILE>` afterward. Ignore the noisy `--json` event stream on stdout; only the schema-constrained result file is reliable.
- Read `<RESULT_FILE>` (or the written draft file) only after the process exits; do not parse intermediate stream events.

## 4. Quality Gate (unconditional)

Whatever generated the draft, the calling skill applies its current gate:

- `translate`: deterministic Markdown structure validation followed by one semantic review; targeted repair on findings.
- `bilingual-translate`: its existing self-review checklist.

A Codex-authored draft never skips directly to writeback.

**Automated backstop:** `.claude/hooks/terminology-check.py` (PostToolUse on `Bash`) fires after every `draft.py ... writeback` call — the same choke point both Codex- and Claude-authored content pass through — and warns (via `additionalContext`, never blocking) if the written file contains a forbidden term variant from `glossary.json`. It can false-positive (e.g. a match inside a code block or proper noun), so treat it as a prompt to double-check, not a verdict.

## 5. Fallback

If the Codex invocation errors, times out, or the process exits non-zero: generate that file's draft directly in the Claude session/subagent instead, and continue the batch. Never surface this as a hard failure to the user — it's a silent per-file fallback.
