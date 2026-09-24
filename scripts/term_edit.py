#!/usr/bin/env python3
"""Interactive glossary editor with auto --cal for unmanaged terms."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _term_lib import (
    CAL_CACHE,
    DEFAULT_GLOSSARY,
    DEFAULT_GLOSSARY_SCHEMA,
    PROJECT_ROOT,
    build_corpus,
    canonical_term_key,
    count_term,
    ensure_cache_dir,
    is_managed_term,
    load_glossary,
    load_json,
    resolve_root,
    sample_contexts,
    save_glossary,
    save_json,
)
from jsonschema import Draft202012Validator


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Edit glossary terms.")
    parser.add_argument("--glossary", type=Path, default=DEFAULT_GLOSSARY)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--term", type=str)
    parser.add_argument("--cal", action="store_true", help="Calculate full-site count for the term.")
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--remove", action="store_true")
    parser.add_argument("--set-zh", type=str, help="Set zh translation.")
    parser.add_argument("--notes", type=str, help="Set notes.")
    parser.add_argument("--status", type=str, choices=["approved", "candidate", "deprecated"])
    parser.add_argument("--mark-term", action="store_true", help="Mark as a managed term.")
    parser.add_argument("--unmark-term", action="store_true")
    parser.add_argument("--forbidden", action="append", default=[], help="Forbidden variant (repeatable).")
    parser.add_argument("--keep-english", action="store_true")
    parser.add_argument("--set-original-term", type=str, help="Set the original-language term used as the gloss.")
    parser.add_argument("--force", action="store_true", help="Bypass --cal requirement for unmanaged terms.")
    return parser.parse_args()


def require_term(args: argparse.Namespace) -> None:
    if not args.term:
        print("❌ `--term` is required for this action.")
        sys.exit(1)


def run_calculation(args: argparse.Namespace, glossary: dict[str, Any]) -> None:
    require_term(args)
    input_term = args.term
    term = canonical_term_key(input_term)
    entry = glossary.get(term) or glossary.get(input_term)
    ensure_cache_dir()

    if is_managed_term(term, entry):
        payload = {
            "term": term,
            "managed": True,
            "skipped_full_scan": True,
            "reason": "Term already marked as managed; full-site search skipped.",
            "calculated_at": now_iso(),
        }
        cache = load_json(CAL_CACHE, {"terms": {}})
        cache.setdefault("terms", {})[term] = payload
        save_json(CAL_CACHE, cache)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    corpus, fingerprint = build_corpus(args.root)
    total, per_file = count_term(corpus, term)
    contexts = sample_contexts(corpus, term, limit=8)
    payload = {
        "term": term,
        "input_term": input_term,
        "managed": False,
        "count": total,
        "files": per_file,
        "contexts": contexts,
        "root": str(args.root.relative_to(PROJECT_ROOT) if args.root.is_absolute() else args.root),
        "fingerprint": fingerprint,
        "calculated_at": now_iso(),
    }
    cache = load_json(CAL_CACHE, {"terms": {}})
    cache.setdefault("terms", {})[term] = payload
    save_json(CAL_CACHE, cache)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def has_fresh_cal(term: str, root: Path) -> bool:
    cache = load_json(CAL_CACHE, {"terms": {}})
    data = cache.get("terms", {}).get(term)
    if not data:
        return False
    if data.get("managed") is True:
        return True
    _, current_fingerprint = build_corpus(root)
    return data.get("fingerprint") == current_fingerprint


def mutate_term(args: argparse.Namespace, glossary: dict[str, Any]) -> bool:
    require_term(args)
    input_term = args.term
    term = canonical_term_key(input_term)
    if input_term != term:
        print(f"ℹ️ Canonicalized term key: {input_term} -> {term}")

    entry = glossary.get(term)
    if entry is None and input_term != term:
        legacy_entry = glossary.get(input_term)
        if legacy_entry is not None:
            entry = legacy_entry
            del glossary[input_term]
            glossary[term] = entry

    has_mutation = any(
        [
            args.set_zh is not None,
            args.notes is not None,
            args.status is not None,
            args.mark_term,
            args.unmark_term,
            bool(args.forbidden),
            args.keep_english,
            args.set_original_term is not None,
            args.remove,
        ]
    )
    if not has_mutation and not args.show:
        print("❌ No mutation requested. Use --show or set flags like --set-zh.")
        return False

    if args.remove:
        if term in glossary:
            del glossary[term]
            glossary["_meta"]["updated"] = now_iso()
            save_glossary(args.glossary, glossary)
            print(f"✓ Removed term: {term}")
        else:
            print(f"ℹ️ Term not found: {term}")
        return True

    if args.show:
        print(json.dumps({"term": term, "entry": entry}, ensure_ascii=False, indent=2))
        return False

    unmanaged_before = not is_managed_term(term, entry)
    if unmanaged_before and not args.force and not has_fresh_cal(term, args.root):
        print(f"ℹ️ Auto-running --cal for unmanaged term: {term}")
        run_calculation(args, glossary)


    if entry is None:
        entry = {}
        glossary[term] = entry

    if args.set_zh is not None:
        entry["zh"] = args.set_zh
    if args.notes is not None:
        entry["notes"] = args.notes
    if args.status is not None:
        entry["status"] = args.status
    if args.mark_term:
        entry["is_term"] = True
        if "status" not in entry:
            entry["status"] = "approved"
    if args.unmark_term:
        entry["is_term"] = False
    if args.keep_english:
        entry["keep_english"] = True
    if args.set_original_term is not None:
        entry["original_term"] = args.set_original_term
    if args.forbidden:
        existing = entry.get("forbidden", [])
        merged = []
        seen = set()
        for item in [*existing, *args.forbidden]:
            if item not in seen:
                seen.add(item)
                merged.append(item)
        entry["forbidden"] = merged

    schema = load_json(DEFAULT_GLOSSARY_SCHEMA, None)
    if schema is not None:
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(glossary), key=lambda e: list(e.path))
        if errors:
            print("❌ Schema validation failed before saving:")
            for error in errors:
                path = ".".join(str(p) for p in error.path) or "<root>"
                print(f"- {path}: {error.message}")
            return False

    glossary["_meta"]["updated"] = now_iso()
    save_glossary(args.glossary, glossary)
    print(f"✓ Updated term: {term}")
    print(json.dumps(entry, ensure_ascii=False, indent=2))
    return True


def list_terms(glossary: dict[str, Any]) -> None:
    rows = []
    for term, entry in glossary.items():
        if term == "_meta":
            continue
        status = entry.get("status", "")
        managed = "yes" if is_managed_term(term, entry) else "no"
        zh = entry.get("zh", "")
        rows.append((term, managed, status, zh))
    rows.sort(key=lambda x: x[0].lower())
    print("term\tmanaged\tstatus\tzh")
    for row in rows:
        print("\t".join(row))


def main() -> None:
    args = parse_args()
    args.root = resolve_root(args.root)
    glossary = load_glossary(args.glossary)

    if args.list:
        list_terms(glossary)
        return

    if args.cal:
        run_calculation(args, glossary)
        return

    changed = mutate_term(args, glossary)
    if not changed and not args.show:
        sys.exit(1)


if __name__ == "__main__":
    main()
