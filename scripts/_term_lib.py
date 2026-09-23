#!/usr/bin/env python3
"""Shared helpers for terminology scripts."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from json import JSONDecodeError
from pathlib import Path
from typing import Any

try:
    import spacy
    from spacy.lang.en import English
    from spacy.lang.en.stop_words import STOP_WORDS as SPACY_STOP_WORDS
    from spacy.tokens import Doc
    SPACY_AVAILABLE = True
except Exception:
    spacy = None  # type: ignore[assignment]
    English = Any  # type: ignore[assignment]
    SPACY_STOP_WORDS = set()  # type: ignore[assignment]
    Doc = Any  # type: ignore[assignment]
    SPACY_AVAILABLE = False

try:
    import inflect
    INFLECT = inflect.engine()
    INFLECT_AVAILABLE = True
except Exception:
    INFLECT = None
    INFLECT_AVAILABLE = False

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOCS_ROOT = PROJECT_ROOT / "docs" / "src" / "content" / "docs"
DEFAULT_MARKDOWN_ROOT = PROJECT_ROOT / "data" / "markdown"
DEFAULT_GLOSSARY = PROJECT_ROOT / "glossary.json"
DEFAULT_GLOSSARY_SCHEMA = PROJECT_ROOT / "glossary.schema.json"
CACHE_DIR = PROJECT_ROOT / ".cache" / "terminology"
CAL_CACHE = CACHE_DIR / "calculation.json"
INDEX_CACHE = CACHE_DIR / "index.json"
CANDIDATE_CACHE = CACHE_DIR / "candidates.json"

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'_-]{2,}")
STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "are", "you", "your",
    "not", "can", "all", "any", "into", "use", "using", "each", "when", "then",
    "will", "its", "they", "their", "but", "was", "have", "has", "had", "were",
}
FUNCTION_POS = {
    "ADP",   # prepositions
    "AUX",   # auxiliary verbs
    "CCONJ", # coordinating conjunctions
    "DET",   # determiners/articles
    "PART",  # particles
    "PRON",  # pronouns
    "SCONJ", # subordinating conjunctions
    "PUNCT",
    "SPACE",
}

_NLP: English | None = None
_DOC_CACHE: dict[str, Doc] = {}
_NORM_CACHE: dict[int, list[dict[str, Any]]] = {}


def get_nlp() -> English:
    if not SPACY_AVAILABLE:
        raise RuntimeError("spaCy is not available")
    global _NLP
    if _NLP is not None:
        return _NLP
    try:
        _NLP = spacy.load("en_core_web_sm", disable=["ner", "parser", "textcat"])  # type: ignore[arg-type]
        return _NLP
    except Exception:
        nlp = English()
        nlp.add_pipe("lemmatizer", config={"mode": "lookup"})
        nlp.initialize()
        _NLP = nlp
        return _NLP


def ensure_cache_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def resolve_root(root: Path | None) -> Path:
    if root is not None:
        return root.resolve()
    # Prefer extracted markdown during init flow; fall back to docs content.
    if any(DEFAULT_MARKDOWN_ROOT.rglob("*.md")):
        return DEFAULT_MARKDOWN_ROOT.resolve()
    return DEFAULT_DOCS_ROOT.resolve()


def list_markdown_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.md") if p.is_file())


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_corpus(root: Path) -> tuple[dict[str, str], str]:
    root = root.resolve()
    files = list_markdown_files(root)
    corpus: dict[str, str] = {}
    digest = hashlib.sha256()
    for path in files:
        abs_path = path.resolve()
        rel = str(abs_path.relative_to(PROJECT_ROOT))
        content = read_file(path)
        corpus[rel] = content
        digest.update(rel.encode("utf-8"))
        digest.update(b"\n")
        digest.update(sha256_text(content).encode("utf-8"))
        digest.update(b"\n")
    return corpus, digest.hexdigest()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except JSONDecodeError:
        # Corrupted cache should not break workflows.
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_glossary(path: Path) -> dict[str, Any]:
    data = load_json(path, {"_meta": {"description": "術語表", "updated": ""}})
    if "_meta" not in data:
        data["_meta"] = {"description": "術語表", "updated": ""}
    return data


def save_glossary(path: Path, glossary: dict[str, Any]) -> None:
    save_json(path, glossary)


def is_managed_term(term: str, entry: dict[str, Any] | None) -> bool:
    if not entry:
        return False
    if entry.get("is_term") is True:
        return True
    status = str(entry.get("status", "")).lower()
    return status == "approved"


def _match_case(source: str, target: str) -> str:
    if source.isupper():
        return target.upper()
    if source.istitle():
        return target.title()
    return target


def _singularize_token(token: str) -> str:
    if SPACY_AVAILABLE:
        try:
            doc = parse_doc(token)
            for tok in doc:
                if tok.is_space or tok.is_punct:
                    continue
                lemma = (tok.lemma_ or tok.text).strip()
                if lemma:
                    return _match_case(tok.text, lemma)
        except Exception:
            pass

    if INFLECT_AVAILABLE and INFLECT is not None:
        singular = INFLECT.singular_noun(token)
        if isinstance(singular, str) and singular:
            if singular.lower() != token.lower():
                cmp = INFLECT.compare_nouns(singular, token)
                if cmp in {"s:p", "eq"}:
                    return _match_case(token, singular)
    return token


def canonical_term_key(term: str) -> str:
    cleaned = " ".join(term.strip().split())
    if not cleaned:
        return cleaned
    parts = cleaned.split(" ")
    parts[-1] = _singularize_token(parts[-1])
    return " ".join(parts)


def _doc_key(text: str) -> str:
    return sha256_text(text)


def parse_doc(text: str) -> Doc:
    if not SPACY_AVAILABLE:
        raise RuntimeError("spaCy is not available")
    key = _doc_key(text)
    cached = _DOC_CACHE.get(key)
    if cached is not None:
        return cached
    nlp = get_nlp()
    required_max_length = len(text) + 1
    if getattr(nlp, "max_length", 0) < required_max_length:
        nlp.max_length = required_max_length
    doc = nlp(text)
    _DOC_CACHE[key] = doc
    return doc


def _strip_non_alnum_edges(text: str) -> tuple[str, int, int]:
    """Strip leading/trailing non-alphanumeric characters (e.g. Markdown table
    pipes) that spaCy's tokenizer leaves attached, such as ``|Bolia|``."""
    first: int | None = None
    last: int | None = None
    for i, ch in enumerate(text):
        if ch.isalnum():
            if first is None:
                first = i
            last = i
    if first is None:
        return "", 0, len(text)
    return text[first : last + 1], first, len(text) - last - 1


def _normalized_tokens(doc: Doc) -> list[dict[str, Any]]:
    key = id(doc)
    cached = _NORM_CACHE.get(key)
    if cached is not None:
        return cached
    tokens: list[dict[str, Any]] = []
    for tok in doc:
        if tok.is_space or tok.is_punct:
            continue
        text = tok.text
        core, lead, trail = _strip_non_alnum_edges(text)
        if not core:
            continue
        if lead or trail:
            # Punctuation stuck to the word (spaCy left it as one token); match
            # on the bare surface form rather than a lemma that was never computed.
            norm = core.lower()
            lower = core.lower()
            start = tok.idx + lead
            end = tok.idx + len(text) - trail
        else:
            norm = (tok.lemma_ or tok.lower_).lower()
            lower = tok.lower_
            start = tok.idx
            end = tok.idx + len(text)
        tokens.append(
            {
                "norm": norm,
                "lower": lower,
                "start": start,
                "end": end,
            }
        )
    _NORM_CACHE[key] = tokens
    return tokens


def _term_norms(term: str) -> list[str]:
    doc = parse_doc(term)
    parts = _normalized_tokens(doc)
    return [p["norm"] for p in parts]


def _token_variants_inflect(token: str) -> set[str]:
    variants = {token}
    if not INFLECT_AVAILABLE or INFLECT is None:
        return variants

    plural = INFLECT.plural_noun(token)
    if isinstance(plural, str) and plural and plural.lower() != token.lower():
        cmp = INFLECT.compare_nouns(token, plural)
        if cmp in {"s:p", "eq"}:
            variants.add(plural)

    singular = INFLECT.singular_noun(token)
    if isinstance(singular, str) and singular and singular.lower() != token.lower():
        cmp = INFLECT.compare_nouns(singular, token)
        if cmp in {"s:p", "eq"}:
            variants.add(singular)

    return variants


def _term_pattern_inflect(term: str) -> re.Pattern[str]:
    tokens = term.split()
    if not tokens:
        return re.compile(r"$^")
    if len(tokens) == 1:
        variants = _token_variants_inflect(tokens[0])
    else:
        head = " ".join(tokens[:-1])
        tail_variants = _token_variants_inflect(tokens[-1])
        variants = {f"{head} {v}" for v in tail_variants}
        variants.add(term)
    escaped = [re.escape(v) for v in sorted(variants, key=len, reverse=True)]
    union = "|".join(escaped)
    return re.compile(rf"(?<![A-Za-z0-9_])(?:{union})(?![A-Za-z0-9_])", re.IGNORECASE)


def find_term_spans(content: str, term: str) -> list[tuple[int, int]]:
    if not SPACY_AVAILABLE:
        pattern = _term_pattern_inflect(term)
        return [(m.start(), m.end()) for m in pattern.finditer(content)]

    term_norms = _term_norms(term)
    if not term_norms:
        return []

    doc = parse_doc(content)
    norm_tokens = _normalized_tokens(doc)
    tlen = len(term_norms)
    spans: list[tuple[int, int]] = []
    if len(norm_tokens) < tlen:
        return spans

    for i in range(0, len(norm_tokens) - tlen + 1):
        window = norm_tokens[i : i + tlen]
        if [w["norm"] for w in window] == term_norms:
            spans.append((window[0]["start"], window[-1]["end"]))
    return spans


def count_term(corpus: dict[str, str], term: str) -> tuple[int, dict[str, int]]:
    per_file: dict[str, int] = {}
    total = 0
    for rel, content in corpus.items():
        count = len(find_term_spans(content, term))
        if count > 0:
            per_file[rel] = count
            total += count
    return total, per_file


def count_terms_batch(
    corpus: dict[str, str], terms: list[str]
) -> dict[str, tuple[int, dict[str, int]]]:
    """Count many terms in a single pass per file using a first-token index."""
    # Pre-compute normalised token sequences for each term.
    term_norms_map: dict[str, list[str]] = {}
    first_idx: dict[str, list[tuple[str, list[str]]]] = defaultdict(list)
    for term in terms:
        norms = _term_norms(term)
        if norms:
            term_norms_map[term] = norms
            first_idx[norms[0]].append((term, norms))

    results: dict[str, tuple[int, dict[str, int]]] = {t: (0, {}) for t in terms}

    for rel, content in corpus.items():
        if not SPACY_AVAILABLE:
            # Fall back to per-term regex when spacy is absent.
            for term in terms:
                count = len(find_term_spans(content, term))
                if count > 0:
                    total, pf = results[term]
                    pf[rel] = count
                    results[term] = (total + count, pf)
            continue

        doc = parse_doc(content)
        norm_tokens = _normalized_tokens(doc)
        norms_list = [t["norm"] for t in norm_tokens]
        ntlen = len(norms_list)

        file_counts: Counter[str] = Counter()
        for i, norm in enumerate(norms_list):
            candidates = first_idx.get(norm)
            if not candidates:
                continue
            for term, tnorms in candidates:
                tlen = len(tnorms)
                if i + tlen > ntlen:
                    continue
                if norms_list[i : i + tlen] == tnorms:
                    file_counts[term] += 1

        for term, count in file_counts.items():
            total, pf = results[term]
            pf[rel] = count
            results[term] = (total + count, pf)

    return results


def sample_contexts(corpus: dict[str, str], term: str, limit: int = 5) -> list[str]:
    contexts: list[str] = []
    for rel, content in corpus.items():
        for start_idx, end_idx in find_term_spans(content, term):
            start = max(0, start_idx - 24)
            end = min(len(content), end_idx + 24)
            snippet = content[start:end].replace("\n", " ")
            contexts.append(f"{rel}: ...{snippet}...")
            if len(contexts) >= limit:
                return contexts
    return contexts


def extract_candidates(corpus: dict[str, str], min_frequency: int = 2) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    surfaces: defaultdict[str, Counter[str]] = defaultdict(Counter)
    if SPACY_AVAILABLE:
        combined_stopwords = {w.lower() for w in SPACY_STOP_WORDS} | STOPWORDS
        for content in corpus.values():
            doc = parse_doc(content)
            for tok in doc:
                if tok.is_space or tok.is_punct:
                    continue
                # If POS is available, keep only noun-like candidates.
                # If POS is unavailable (lightweight pipeline), fall back to lexical filtering.
                if tok.pos_:
                    if tok.pos_ in FUNCTION_POS:
                        continue
                    if tok.pos_ not in {"NOUN", "PROPN"}:
                        continue
                lemma = (tok.lemma_ or tok.text).strip().lower()
                if not lemma or lemma in combined_stopwords:
                    continue
                if len(lemma) < 3:
                    continue
                if not re.match(r"^[a-z][a-z0-9'_-]*$", lemma):
                    continue
                counts[lemma] += 1
                surfaces[lemma][tok.text] += 1
    else:
        for content in corpus.values():
            for token in WORD_RE.findall(content):
                key = token.lower()
                if key in STOPWORDS:
                    continue
                counts[key] += 1
                surfaces[key][token] += 1
    results: list[dict[str, Any]] = []
    for key, cnt in counts.items():
        if cnt < min_frequency:
            continue
        surface = surfaces[key].most_common(1)[0][0]
        results.append({"term": surface, "normalized": key, "count": cnt})
    results.sort(key=lambda x: (-x["count"], x["normalized"]))
    return results
