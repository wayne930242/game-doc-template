---
name: super-translate
description: Deprecated compatibility entry for older whole-book translation requests; forwards them to the unified translate skill.
user-invocable: true
---

# Super Translate Compatibility Entry

`super-translate` is deprecated. The primary [`translate`](../translate/SKILL.md) skill now provides whole-book context, complete chapter translation, deterministic Markdown validation, and bounded semantic review.

## Forwarding contract

1. Preserve the user's arguments and scope.
2. Tell the user once for this invocation that `super-translate` now uses the unified `/translate` process.
3. Invoke `translate` with the same scope:
   - no arguments → `/translate all`;
   - file, section, `next`, or `all` → pass it through unchanged.
4. Do not run a separate translator, Markdown reviewer, refiner, or review loop from this skill.
5. Return the unified workflow's progress and verification results.

This compatibility entry may be removed only in a future explicit migration.
