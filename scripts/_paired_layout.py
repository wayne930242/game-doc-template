"""Infer paired Markdown layout from a rulebook PDF and write project evidence.

The source PDF supplies typographic roles. Shared media, paragraph order, and
approved glossary entries align those roles with the existing translation.
Ambiguous matches remain reviewable in the project's layout data file.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from dataclasses import asdict, dataclass
from pathlib import Path

from validate_translation_structure import compare_structure

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
IMAGE = re.compile(r"page\d+_img[^.)\s]*")
IMAGE_PAGE = re.compile(r"page(\d+)_img")
MARKER = re.compile(r"^[\u0094\u0095•]\s*")
LIST = re.compile(r"^(\s*)([-+*]|\d+[.)])\s+(.+)$")


def normal(text: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKC", text).casefold() if char.isalnum())


def label(line: str) -> str:
    match = HEADING.match(line.strip())
    text = match.group(2) if match else line.strip()
    listed = LIST.match(text)
    return MARKER.sub("", listed.group(3) if listed else text).strip()


def _content_digest(line: str) -> str:
    content = label(line).replace("**", "")
    normalized = normal(content)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20] if normalized else ""


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.md")):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def recorded_repair(plan_path: Path, target_docs: Path, source_docs: Path | None = None) -> str | None:
    """Return why a recorded paired repair is skipped, or None when none was applied.

    The record alone marks the book as repaired. Markdown that changed since then
    holds deliberate edits, which rerunning the paired transform would overwrite.
    """
    if not plan_path.is_file():
        return None
    applied = json.loads(plan_path.read_text(encoding="utf-8")).get("applied")
    if not applied:
        return None
    changed = [name for name, key, root in (("translated Markdown", "target_sha256", target_docs),
                                            ("staged English source", "source_sha256", source_docs))
               if root is not None and applied.get(key) != _tree_digest(root)]
    if not changed:
        return "paired layout repair already applied; content unchanged since"
    return (f"{' and '.join(changed)} changed since the recorded paired layout repair; "
            "kept as is. Pass --reapply to redo the repair and overwrite those edits")


def _structural_marker(line: str) -> str:
    if match := HEADING.match(line):
        return match.group(1) + " "
    if match := LIST.match(line):
        return match.group(1) + match.group(2) + " "
    return ""


def _reviewed_overlay(lines: list[str], records: list[dict]) -> int:
    catalog: dict[str, list[tuple[float, str]]] = defaultdict(list)
    for record in records:
        catalog[record["digest"]].append((record["position"], record["marker"]))
    used: dict[str, set[int]] = defaultdict(set)
    changed = 0
    for index, line in enumerate(lines):
        digest = _content_digest(line)
        choices = [(abs(index / max(len(lines), 1) - position), j, marker)
                   for j, (position, marker) in enumerate(catalog.get(digest, []))
                   if j not in used[digest]]
        if not choices:
            continue
        _, choice, marker = min(choices)
        used[digest].add(choice)
        current = _structural_marker(line)
        if marker != current:
            lines[index] = marker + label(line) if marker else label(line)
            changed += 1
    return changed


def add_reviewed_decisions(plan_path: Path, decisions_path: Path,
                           source_docs: Path, target_docs: Path) -> dict[str, int]:
    """Apply explicit, PDF-checked decisions to individual residual lines."""
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    if not isinstance(decisions, list):
        raise ValueError("review decisions must be a JSON array")
    pending: dict[Path, list[str]] = {}
    seen: set[tuple[str, str, int]] = set()
    reviewed = plan.setdefault("reviewed", {"source": {}, "target": {}})
    residual_lines: dict[tuple[str, str], set[int]] = {}
    for chapter, target_rel in plan["targets"].items():
        source_path, target_path = source_docs / chapter, target_docs / target_rel
        findings = compare_structure(source_path.read_text(encoding="utf-8"),
                                     target_path.read_text(encoding="utf-8"), source_path, target_path)
        for side, field in (("source", "expected"), ("target", "actual")):
            residual_lines[side, chapter] = {finding[field]["line"] for finding in findings if finding[field]}
    for decision in decisions:
        side, chapter = decision["side"], decision["chapter"]
        if side not in {"source", "target"} or chapter not in plan["chapters"]:
            raise ValueError("review decision has an unknown side or chapter")
        rel = chapter if side == "source" else plan["targets"][chapter]
        root = source_docs if side == "source" else target_docs
        path = root / rel
        lines = pending.setdefault(path, path.read_text(encoding="utf-8").splitlines())
        line_number = decision["line"]
        key = side, chapter, line_number
        if key in seen or not isinstance(line_number, int) or not 1 <= line_number <= len(lines):
            raise ValueError("review decision line must be unique and in range")
        seen.add(key)
        if line_number not in residual_lines[side, chapter]:
            raise ValueError("review decision must name a residual structure finding")
        marker = decision["marker"]
        if marker not in {"", "- ", "## ", "### ", "#### ", "##### ", "###### "}:
            raise ValueError("review decision has an unsupported marker")
        reason, page = decision["reason"], decision["pdf_page"]
        if not isinstance(reason, str) or not reason.strip() or not isinstance(page, int) or page < 1:
            raise ValueError("review decision needs a PDF page and reason")
        index = line_number - 1
        if label(lines[index]) != decision["text"]:
            raise ValueError("review decision text changed; inspect the line again")
        digest = _content_digest(lines[index])
        if not digest:
            raise ValueError("review decision line has no content")
        record = {"digest": digest, "position": round(index / max(len(lines), 1), 6),
                  "marker": marker, "pdf_page": page, "reason": reason.strip(),
                  "text": decision["text"]}
        reviewed[side].setdefault(chapter, []).append(record)
        lines[index] = marker + label(lines[index])
    for path, lines in pending.items():
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    plan["applied"] = {"source_sha256": _tree_digest(source_docs),
                       "target_sha256": _tree_digest(target_docs)}
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"reviewed_overrides": len(decisions)}


def front_title(lines: list[str]) -> str:
    for line in lines[1:]:
        if line == "---":
            break
        if line.startswith("title:"):
            return line[6:].strip().strip("\"'")
    return ""


def paragraphs(lines: list[str]) -> tuple[list[str], list[int]]:
    blocks: list[str] = []
    line_for: list[int] = []
    current: list[str] = []
    start = 0
    for index, line in enumerate(lines + [""]):
        if not line.strip():
            if current:
                blocks.append("\n".join(current))
                line_for.append(start)
                current = []
        elif not current:
            start = index
            current.append(line)
        else:
            current.append(line)
    return blocks, line_for


@dataclass(frozen=True)
class PdfRole:
    text: str
    page: int
    size: float
    x: float
    y: float
    kind: str


def _pdf_roles(pdf, pages: tuple[int, int]) -> list[PdfRole]:
    roles: list[PdfRole] = []
    for number in range(pages[0], pages[1] + 1):
        page = pdf[number - 1]
        lines = [line for block in page.get_text("dict")["blocks"]
                 for line in block.get("lines", []) if line.get("spans")]
        sizes = Counter()
        for line in lines:
            for span in line["spans"]:
                if 7 <= span["size"] <= 12:
                    sizes[round(span["size"], 1)] += sum(char.isalnum() for char in span["text"])
        body = sizes.most_common(1)[0][0] if sizes else 9.0
        for line_index, line in enumerate(lines):
            spans = line["spans"]
            text = "".join(span["text"] for span in spans).strip()
            if (len(text) == 1 and not text.isalnum() and spans[0]["size"] <= body + 0.6):
                neighbor = next((candidate for candidate in lines
                                 if 8 <= candidate["bbox"][0] - line["bbox"][0] <= 30
                                 and abs(candidate["bbox"][1] - line["bbox"][1]) <= 3
                                 and candidate["spans"][0]["font"] != spans[0]["font"]
                                 and len(normal("".join(span["text"] for span in candidate["spans"]))) >= 4), None)
                if neighbor:
                    phrase = "".join(span["text"] for span in neighbor["spans"]).strip()
                    roles.append(PdfRole(phrase, number, round(spans[0]["size"], 2),
                                         round(line["bbox"][0], 1), round(line["bbox"][1], 1), "list"))
                continue
            if len(normal(text)) < 4:
                continue
            leading = spans[0]["text"].strip()
            glyph = len(leading) == 1 and not leading.isalnum() and len(spans) > 1
            size = max(span["size"] for span in spans if normal(span["text"])) if any(normal(span["text"]) for span in spans) else 0
            if glyph and size >= body + 1.4 and spans[0]["size"] >= body + 1.4:
                kind = "heading"
            elif glyph and spans[0]["size"] <= body + 0.6:
                kind = "list"
            elif (abs(size - body) <= 0.6 and len(text) <= 46
                  and all(span["flags"] & 16 for span in spans if normal(span["text"]))
                  and line_index + 1 < len(lines)
                  and abs(lines[line_index + 1]["bbox"][0] - line["bbox"][0]) < 8
                  and 8 <= lines[line_index + 1]["bbox"][1] - line["bbox"][1] <= 18
                  and any(not (span["flags"] & 16) for span in lines[line_index + 1]["spans"]
                          if normal(span["text"]))):
                kind = "callout"
            elif size >= body * 1.75 and line["bbox"][1] < page.rect.height * 0.92:
                kind = "display"
            else:
                continue
            roles.append(PdfRole(MARKER.sub("", text).strip(), number, round(size, 2),
                                 round(line["bbox"][0], 1), round(line["bbox"][1], 1), kind))
    return roles


def _anchors(source: list[str], target: list[str]) -> list[tuple[int, int]]:
    hits: list[dict[str, list[int]]] = [{}, {}]
    for side, blocks in enumerate((source, target)):
        for index, block in enumerate(blocks):
            for image in IMAGE.findall(block):
                hits[side].setdefault(image, []).append(index)
    points = [(0, 0), (len(source), len(target))]
    for image, indices in hits[0].items():
        if len(indices) == len(hits[1].get(image, [])) == 1:
            points.append((indices[0], hits[1][image][0]))
    return sorted(set(points))


def match_chapter_paths(source_docs: Path, target_docs: Path,
                        target_pages: dict[str, tuple[int, int]]) -> dict[str, tuple[str, tuple[int, int]]]:
    """Pair renamed chapters by shared paths, then PDF page evidence."""
    sources = {str(path.relative_to(source_docs)): path for path in source_docs.rglob("*.md")}
    targets = {rel for rel in target_pages if (target_docs / rel).is_file()}
    matched = {rel: (rel, target_pages[rel]) for rel in sources.keys() & targets}
    unmatched_targets = targets - set(matched)
    for rel in sorted(sources.keys() - set(matched)):
        text = sources[rel].read_text(encoding="utf-8")
        first_page = next((int(page) for page in IMAGE_PAGE.findall(text)), None)
        candidates = [target for target in unmatched_targets
                      if first_page is not None and target_pages[target][0] <= first_page <= target_pages[target][1]]
        if len(candidates) != 1 and len(unmatched_targets) == 1:
            candidates = list(unmatched_targets)
        if len(candidates) == 1:
            target = candidates[0]
            matched[rel] = (target, target_pages[target])
            unmatched_targets.remove(target)
    return matched


def _position(index: int, points: list[tuple[int, int]]) -> float:
    left = max((point for point in points if point[0] <= index), default=points[0])
    right = min((point for point in points if point[0] >= index), default=points[-1])
    return left[1] if right[0] == left[0] else left[1] + (index - left[0]) * (right[1] - left[1]) / (right[0] - left[0])


def _approved_terms(path: Path) -> list[tuple[str, str]]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [(normal(english), entry["zh"]) for english, entry in data.items()
            if isinstance(entry, dict) and entry.get("status") == "approved" and entry.get("zh")]


def _candidate(block: str) -> bool:
    clean = label(block)
    return ("\n" not in block and len(clean) <= 56 and bool(clean)
            and not block.startswith(("!", "|", "<"))
            and (HEADING.match(block) is not None or not clean.endswith(("。", "，", ".", ","))))


def _match_cost(source: dict, target: dict, terms: list[tuple[str, str]]) -> float:
    english, chinese = source["text"], target["text"]
    distance = abs(source["expected"] - target["block"])
    score = distance * 0.85
    if target["heading"]:
        score -= 1.2
    if source.get("source_level"):
        score += -3.0 if target["heading"] else 1.5
    if normal(english) in normal(chinese):
        score -= 7
    else:
        hits = sum(1 for term, translated in terms if len(term) >= 4 and term in normal(english) and translated in chinese)
        score -= min(5, hits * 1.5)
    if normal(chinese) == normal(source["page_title"]):
        score += 3
    if len(chinese) > 38:
        score += 2
    return score


def _pair_candidates(source: list[dict], target: list[dict], terms: list[tuple[str, str]]) -> tuple[list[tuple[int, int]], list[int]]:
    """Monotonic alignment with a stronger cost for dropping PDF evidence."""
    n, m = len(source), len(target)
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    trace = [[""] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + 7
        trace[i][0] = "source"
    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + 1.5
        trace[0][j] = "target"
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            options = ((dp[i - 1][j] + 7, "source"),
                       (dp[i][j - 1] + 1.5, "target"),
                       (dp[i - 1][j - 1] + _match_cost(source[i - 1], target[j - 1], terms), "pair"))
            dp[i][j], trace[i][j] = min(options)
    pairs: list[tuple[int, int]] = []
    missing: list[int] = []
    i, j = n, m
    while i or j:
        choice = trace[i][j]
        if choice == "pair":
            pairs.append((i - 1, j - 1)); i -= 1; j -= 1
        elif choice == "source":
            missing.append(i - 1); i -= 1
        else:
            j -= 1
    return list(reversed(pairs)), list(reversed(missing))


def _source_candidates(source: list[str], roles: list[PdfRole]) -> list[dict]:
    blocks, _ = paragraphs(source)
    used: set[int] = set()
    selected: list[dict] = []
    for role in roles:
        if role.kind not in {"heading", "display"}:
            continue
        choices = [(index, block) for index, block in enumerate(blocks)
                   if index not in used and normal(label(block)) == normal(role.text)]
        if not choices:
            continue
        index, block = choices[0]
        if normal(label(block)) == normal(front_title(source)):
            continue
        if role.kind == "display" and (not HEADING.match(block)
                                       or (index + 1 < len(blocks) and blocks[index + 1].startswith("|"))):
            continue
        used.add(index)
        selected.append({"block": index, "text": label(block), "page": role.page,
                         "size": role.size, "kind": role.kind, "x": role.x, "y": role.y})
    return sorted(selected, key=lambda item: item["block"])


def _text_source_candidates(source: list[str], relative_path: str = "") -> tuple[list[dict], list[dict]]:
    """Read existing Markdown structure before asking the PDF about glyphs."""
    blocks, _ = paragraphs(source)
    title = normal(front_title(source))
    parts = Path(relative_path).with_suffix("").parts
    route = normal(parts[-2] if parts and parts[-1] == "index" and len(parts) > 1 else parts[-1]) if parts else ""
    certain: list[dict] = []
    ambiguous: list[dict] = []
    for index, block in enumerate(blocks):
        if "\n" in block:
            continue
        match = HEADING.match(block)
        marked = MARKER.match(block)
        if not match and not marked:
            continue
        text = label(block)
        normalized = normal(text)
        if (not normalized or normalized == title or len(text) > 76 or "](" in text
                or (len(route) >= 5 and abs(len(normalized) - len(route)) <= 4
                    and SequenceMatcher(None, normalized, route).ratio() >= 0.77)):
            continue
        # A sentence or an OCR paragraph promoted to H1 is prose, not a title.
        if len(text.split()) > 11 or (marked and text.endswith((".", "。", "!", "！"))):
            continue
        item = {"block": index, "text": text, "source_level": len(match.group(1)) if match else None,
                "marker": bool(marked), "expected": float(index)}
        if marked and (len(text.split()) <= 1 or text.endswith((":", "：", "?", "？"))):
            ambiguous.append(item)
        else:
            certain.append(item)
    return certain, ambiguous


def _text_target_candidates(blocks: list[str]) -> list[dict]:
    selected = []
    for index, block in enumerate(blocks):
        if not _candidate(block):
            continue
        text = label(block)
        heading = bool(HEADING.match(block))
        listed = bool(LIST.match(block))
        if len(text) > (76 if heading else 30) or (not heading and text.endswith(("。", "！", ".", "!"))):
            continue
        selected.append({"block": index, "text": text, "heading": heading,
                         "level": len(HEADING.match(block).group(1)) if heading else None,
                         "listed": listed})
    return selected


def _block_page(blocks: list[str], index: int, first_page: int) -> int:
    for block in reversed(blocks[:index + 1]):
        if match := IMAGE_PAGE.search(block):
            return int(match.group(1))
    return first_page


def _text_pairs(source: list[dict], target: list[dict], terms: list[tuple[str, str]]) -> tuple[list[tuple[int, int]], list[int]]:
    """Pair short standalone labels in order, bounded by shared media positions."""
    pairs, missing = _pair_candidates(source, target, terms)
    accepted = []
    for source_index, target_index in pairs:
        left, right = source[source_index], target[target_index]
        distance = abs(left["expected"] - right["block"])
        if distance > 4 and _match_cost(left, right, terms) > 1:
            missing.append(source_index)
            continue
        if right["listed"] and not left["marker"]:
            missing.append(source_index)
            continue
        accepted.append((source_index, target_index))
    return accepted, sorted(missing)


def _corroborated_display_candidates(source_blocks: list[str], target_blocks: list[str],
                                     roles: list[PdfRole], anchors: list[tuple[int, int]],
                                     terms: list[tuple[str, str]], selected: list[dict]) -> list[dict]:
    """Admit plain PDF display text only when an aligned glossary heading confirms it."""
    glossary = {english: normal(chinese) for english, chinese in terms}
    used = {item["block"] for item in selected}
    added: list[dict] = []
    for role in roles:
        if role.kind != "display" or normal(role.text) not in glossary:
            continue
        wanted = glossary[normal(role.text)]
        target_positions = [index for index, block in enumerate(target_blocks)
                            if HEADING.match(block) and normal(label(block)) == wanted]
        if len(target_positions) != 1:
            continue
        choices = [(abs(_position(index, anchors) - target_positions[0]), index)
                   for index, block in enumerate(source_blocks)
                   if index not in used and normal(label(block)) == normal(role.text)
                   and not (index + 1 < len(source_blocks) and source_blocks[index + 1].startswith("|"))]
        if not choices:
            continue
        distance, index = min(choices)
        if distance > 1.5:
            continue
        used.add(index)
        added.append({"block": index, "text": label(source_blocks[index]), "page": role.page,
                      "size": role.size, "kind": role.kind, "x": role.x, "y": role.y})
    return added


def _level(candidate: dict, prior: list[dict]) -> int:
    previous = next((item for item in reversed(prior) if item["kind"] in {"heading", "display"}), None)
    if previous is None:
        return 2
    if candidate["kind"] == "display" and candidate["size"] < 24:
        if previous["kind"] == "heading" or previous.get("level") == 3:
            return 3
    return 3 if candidate["size"] < previous["size"] - 1.5 else 2


def _spread_evidence(roles: list[PdfRole]) -> list[dict]:
    """Find dense two-page diagrams with large stages and body-size bold labels."""
    pages = sorted({role.page for role in roles})
    for start in pages:
        window = [role for role in roles if start <= role.page <= start + 1]
        stages = [role for role in window if role.kind == "display" and role.size >= 24]
        labels = [role for role in window if role.kind == "callout"]
        unique_stages = {(role.page, normal(role.text)) for role in stages}
        unique_labels = {(role.page, round(role.y), normal(role.text)) for role in labels}
        if len(unique_stages) >= 3 and len(unique_labels) >= 8:
            seen: set[tuple[int, str]] = set()
            result = []
            for role in sorted(labels, key=lambda item: (item.page, item.y, item.x)):
                key = (role.page, normal(role.text))
                if key not in seen:
                    result.append(asdict(role))
                    seen.add(key)
            return result
    return []


def derive_layout_plan(source_docs: Path, translated_docs: Path, pdf_path: Path,
                       target_pages: dict[str, tuple[int, int]], glossary: Path,
                       plan_path: Path) -> dict:
    import pymupdf

    plan: dict = {"version": 2, "pdf_sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
                  "chapters": {}, "spreads": {}, "unresolved": [], "pdf_tiebreaks": []}
    terms = _approved_terms(glossary)
    paired_paths = match_chapter_paths(source_docs, translated_docs, target_pages)
    with pymupdf.open(pdf_path) as pdf:
        for source_path in sorted(source_docs.rglob("*.md")):
            rel = str(source_path.relative_to(source_docs))
            if rel not in paired_paths:
                continue
            target_rel, page_range = paired_paths[rel]
            target_path = translated_docs / target_rel
            source_lines = source_path.read_text(encoding="utf-8").splitlines()
            target_lines = target_path.read_text(encoding="utf-8").splitlines()
            source_blocks, _ = paragraphs(source_lines)
            target_blocks, _ = paragraphs(target_lines)
            anchors = _anchors(source_blocks, target_blocks)
            target_candidates = _text_target_candidates(target_blocks)
            certain, ambiguous = _text_source_candidates(source_lines, rel)
            for item in certain + ambiguous:
                item["expected"] = _position(item["block"], anchors)
                item["page_title"] = front_title(target_lines)
            # PDF typography decides only short glyph labels that the paired
            # Markdown leaves equally plausible as a heading or a list item.
            roles = _pdf_roles(pdf, tuple(page_range)) if ambiguous or any(
                block.startswith(("# ", "## ", "### ")) for block in source_blocks) else []
            for item in ambiguous:
                nearby = [candidate for candidate in target_candidates
                          if abs(candidate["block"] - item["expected"]) <= 2]
                if len(nearby) == 1 and nearby[0]["heading"]:
                    certain.append(item)
                    continue
                if len(nearby) == 1 and nearby[0]["listed"]:
                    continue
                matches = [role for role in roles if normal(role.text) == normal(item["text"])]
                evidence_page = matches[0].page if matches else _block_page(source_blocks, item["block"], page_range[0])
                plan["pdf_tiebreaks"].append({"chapter": rel, "source": item["text"],
                                               "pdf_page": evidence_page})
                if any(role.kind in {"heading", "display"} for role in matches):
                    certain.append(item)
                elif not matches:
                    plan["unresolved"].append({"chapter": rel, "source": item["text"],
                                               "pdf_page": evidence_page,
                                               "reason": "short glyph label has no text or PDF role match"})
            candidates = sorted(certain, key=lambda item: item["block"])
            spread = _spread_evidence(roles)
            if spread:
                plan["spreads"][rel] = spread
            pairs, missing = _text_pairs(candidates, target_candidates, terms)
            entries: list[dict] = []
            prior: list[dict] = []
            for source_index, target_index in pairs:
                source_item, target_item = candidates[source_index], target_candidates[target_index]
                matched_role = next((role for role in roles if normal(role.text) == normal(source_item["text"])
                                     and role.kind in {"heading", "display"}), None)
                if source_item["source_level"]:
                    level = source_item["source_level"]
                elif target_item["level"] and target_item["level"] > 1:
                    level = target_item["level"]
                else:
                    previous_level = prior[-1]["level"] if prior else 0
                    level = 3 if previous_level == 2 else 2
                source_item["level"] = level
                prior.append(source_item)
                entry = {"source": source_item["text"], "target": target_item["text"], "level": level,
                         "source_block": source_item["block"], "target_block": target_item["block"],
                         "pdf": (asdict(matched_role) if matched_role else
                                 {"page": page_range[0], "size": 0, "kind": "text", "x": 0, "y": 0}),
                         "alignment_cost": round(_match_cost(source_item, target_item, terms), 2)}
                entries.append(entry)
            plan["chapters"][rel] = entries
            plan.setdefault("targets", {})[rel] = target_rel
            plan["unresolved"].extend({"chapter": rel, "source": candidates[index]["text"],
                                       "pdf_page": _block_page(source_blocks, candidates[index]["block"], page_range[0]),
                                       "reason": "no structural match"}
                                      for index in missing)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    if not plan_path.is_file() or plan_path.read_text(encoding="utf-8") != text:
        plan_path.write_text(text, encoding="utf-8")
    return plan


def _set_label(lines: list[str], wanted: str, level: int, block_hint: int) -> bool:
    blocks, line_for = paragraphs(lines)
    choices = [(abs(index - block_hint), line_for[index]) for index, block in enumerate(blocks)
               if normal(label(block)) == normal(wanted) and len(label(block)) <= 80]
    if not choices:
        return False
    _, index = min(choices)
    revised = "#" * level + " " + label(lines[index])
    if lines[index] != revised:
        lines[index] = revised
        return True
    return False


def _restore_paired_glyph_lists(source: list[str], target: list[str]) -> int:
    """Recover raw bullet glyphs when the translation shows nearby list evidence."""
    source_blocks, source_lines = paragraphs(source)
    target_blocks, target_lines = paragraphs(target)
    anchors = _anchors(source_blocks, target_blocks)
    selected_source: set[int] = set()
    selected_target: set[int] = set()
    for block_index, block in enumerate(source_blocks):
        if "\u0094" not in block and "\u0095" not in block:
            continue
        expected = round(_position(block_index, anchors))
        nearby = range(max(0, expected - 4), min(len(target_blocks), expected + 5))
        target_matches = [index for index in nearby
                          if LIST.match(target_blocks[index]) or "\u0094" in target_blocks[index]
                          or "\u0095" in target_blocks[index]]
        if not target_matches:
            continue
        end = source_lines[block_index] + len(block.splitlines())
        selected_source.update(index for index in range(source_lines[block_index], end)
                               if "\u0094" in source[index] or "\u0095" in source[index])
        for index in target_matches:
            end = target_lines[index] + len(target_blocks[index].splitlines())
            selected_target.update(line for line in range(target_lines[index], end)
                                   if "\u0094" in target[line] or "\u0095" in target[line])

    def rewrite(lines: list[str], selected: set[int]) -> int:
        changed = 0
        for index in sorted(selected, reverse=True):
            pieces = re.split(r"(?:^|\s)[\u0094\u0095]\s*", lines[index])
            if len(pieces) < 2:
                continue
            prefix = pieces[0].strip()
            replacement = ([prefix] if prefix and prefix != "-" else []) + ["- " + part.strip() for part in pieces[1:] if part.strip()]
            lines[index:index + 1] = replacement
            changed += len(replacement)
        return changed

    return rewrite(source, selected_source) + rewrite(target, selected_target)


def _join_unproved_list_continuations(lines: list[str]) -> int:
    """Join OCR line breaks that promoted the tail of a list item to a heading."""
    changed = 0
    for index, line in enumerate(lines):
        match = HEADING.match(line)
        if not match or len(match.group(2)) > 16:
            continue
        previous = next((j for j in range(index - 1, max(-1, index - 4), -1) if lines[j].strip()), None)
        if previous is None or not lines[previous].startswith("- ") or len(label(lines[previous])) <= 25:
            continue
        if lines[previous].rstrip().endswith((".", "!", "?", ":", "。", "！", "？")):
            continue
        lines[previous] = lines[previous].rstrip() + " " + match.group(2)
        lines[index] = ""
        changed += 1
    return changed


def _align_post_spread_list(source: list[str], target: list[str], callout_count: int) -> int:
    """Align an extracted bullet immediately following a proved spread."""
    if not callout_count:
        return 0
    source_callouts = [index for index, line in enumerate(source) if line.startswith("- **")]
    target_callouts = [index for index, line in enumerate(target) if line.startswith("- **")]
    if len(source_callouts) < callout_count or len(target_callouts) < callout_count:
        return 0
    source_next = next((index for index in range(source_callouts[callout_count - 1] + 1, len(source))
                        if source[index].strip()), None)
    target_next = next((index for index in range(target_callouts[callout_count - 1] + 1, len(target))
                        if target[index].strip()), None)
    if source_next is None or target_next is None:
        return 0
    if not source[source_next].startswith(("- ", "\u0094 ", "\u0095 ")):
        return 0
    if target[target_next].startswith(("#", "-", "!", "|", "<")) or len(target[target_next]) > 100:
        return 0
    target[target_next] = "- " + target[target_next]
    return 1


def _strip_title_headings(lines: list[str]) -> int:
    title = normal(front_title(lines))
    if not title:
        return 0
    changed = 0
    for index, line in enumerate(lines):
        if re.match(r"^#{1,6}\s+\[.+\]\(.+\)", line):
            continue
        visible = re.sub(r"[（(][^）)]*[）)]", "", label(line)).strip()
        if HEADING.match(line) and normal(visible) == title:
            lines[index] = ""
            changed += 1
    return changed


def _strip_source_title_headings(source: list[str], target: list[str]) -> int:
    """Keep a source page heading when a distinct translated heading occupies it."""
    title = normal(front_title(source))
    source_blocks, source_starts = paragraphs(source)
    target_blocks, _ = paragraphs(target)
    anchors = _anchors(source_blocks, target_blocks)
    changed = 0
    for block_index, block in enumerate(source_blocks):
        match = HEADING.match(block)
        if not match or normal(label(block)) != title:
            continue
        expected = _position(block_index, anchors)
        level = len(match.group(1))
        counterpart = any(HEADING.match(other) and len(HEADING.match(other).group(1)) == level
                          and abs(index - expected) <= 2
                          for index, other in enumerate(target_blocks))
        if not counterpart:
            source[source_starts[block_index]] = ""
            changed += 1
    return changed


def _demote_prose_headings(lines: list[str]) -> int:
    changed = 0
    for index, line in enumerate(lines):
        match = HEADING.match(line)
        if not match:
            continue
        text = match.group(2)
        if (len(text) >= 80 and text.endswith((".", "。", "!", "！", "?", "？"))) or re.fullmatch(
                r"(?:第\s*\d+\s*章|Chapter\s+\d+)", text, re.IGNORECASE):
            lines[index] = text
            changed += 1
    return changed


def _clean_remaining_glyphs(lines: list[str]) -> int:
    """Preserve words in glyph lines whose paired list role is unproved."""
    changed = 0
    for index, line in enumerate(lines):
        if "\u0094" not in line and "\u0095" not in line:
            continue
        parts = [part.strip() for part in re.split(r"[\u0094\u0095]", line) if part.strip()]
        cleaned = "；".join(parts)
        if cleaned != line:
            lines[index] = cleaned
            changed += 1
    return changed


def _join_lowercase_list_tails(lines: list[str]) -> int:
    changed = 0
    for index, line in enumerate(lines):
        if not re.match(r"^- [a-z]", line):
            continue
        previous = next((lines[j] for j in range(index - 1, max(-1, index - 3), -1)
                         if lines[j].strip()), "")
        if previous and not previous.startswith(("#", "-", "|", "!")) and not previous.endswith((".", "!", "?", ":")):
            lines[index] = line[2:]
            changed += 1
    return changed


def _align_unpaired_h1(source: list[str], target: list[str], source_path: Path,
                       target_path: Path) -> int:
    changed = 0
    findings = compare_structure("\n".join(source), "\n".join(target), source_path, target_path)
    for finding in findings:
        expected, actual = finding["expected"], finding["actual"]
        if not actual or actual["kind"] != "heading" or actual["detail"]["level"] != 1:
            continue
        index = actual["line"] - 1
        if not target[index].startswith("# "):
            continue
        content = target[index][2:]
        if expected and expected["kind"] == "list_item":
            target[index] = "- " + content
        elif expected and expected["kind"] == "heading":
            target[index] = "#" * expected["detail"]["level"] + " " + content
        else:
            target[index] = content
        changed += 1
    return changed


def _align_short_label_lists(source: list[str], target: list[str], source_path: Path,
                             target_path: Path) -> int:
    """Match a short orphan label to its translated standalone label."""
    source_blocks, source_starts = paragraphs(source)
    target_blocks, target_starts = paragraphs(target)
    anchors = _anchors(source_blocks, target_blocks)
    changed = 0
    for finding in compare_structure("\n".join(source), "\n".join(target), source_path, target_path):
        expected, actual = finding["expected"], finding["actual"]
        if not expected or actual or expected["kind"] != "list_item":
            continue
        source_line = expected["line"] - 1
        match = LIST.match(source[source_line])
        if not match or len(match.group(3)) > 24 or len(match.group(3).split()) > 3:
            continue
        source_block = next((index for index, start in enumerate(source_starts) if start == source_line), None)
        if source_block is None:
            continue
        prior = next((HEADING.match(source[index]) for index in range(source_line - 1, max(-1, source_line - 10), -1)
                      if HEADING.match(source[index])), None)
        if prior is None:
            continue
        expected_target = _position(source_block, anchors)
        choices = [(abs(index - expected_target), index) for index, block in enumerate(target_blocks)
                   if abs(index - expected_target) <= 2 and "\n" not in block
                   and not block.startswith(("#", "-", "|", "!", "<"))
                   and 1 <= len(block) <= 16 and not block.endswith(("。", "！", "？"))]
        if len(choices) != 1:
            continue
        target_line = target_starts[choices[0][1]]
        level = len(prior.group(1))
        source[source_line] = "#" * level + " " + match.group(3)
        target[target_line] = "#" * level + " " + target[target_line]
        changed += 1
    return changed


def _strip_source_route_titles(lines: list[str], relative_path: str, proved_headings: set[str]) -> int:
    parts = Path(relative_path).with_suffix("").parts
    route_title = normal(parts[-2] if parts[-1] == "index" and len(parts) > 1 else parts[-1])
    if len(route_title) < 5:
        return 0
    changed = 0
    for index, line in enumerate(lines):
        match = HEADING.match(line)
        if match and normal(match.group(2)) in proved_headings:
            continue
        if match and abs(len(normal(match.group(2))) - len(route_title)) <= 4:
            if SequenceMatcher(None, normal(match.group(2)), route_title).ratio() >= 0.77:
                lines[index] = ""
                changed += 1
    return changed


def _format_pdf_callouts(lines: list[str], labels: list[dict]) -> int:
    changed = 0
    cursor = 0
    for item in labels:
        prefix = item["text"]
        index = next((i for i in range(cursor, len(lines))
                      if label(lines[i]).casefold().startswith(prefix.casefold())
                      and (len(label(lines[i])) == len(prefix)
                           or label(lines[i])[len(prefix):len(prefix) + 1].isspace())), None)
        if index is None:
            continue
        cursor = index + 1
        if lines[index].lstrip().startswith("- **"):
            continue
        content = label(lines[index])
        description = content[len(prefix):].strip()
        if not description:
            next_index = next((i for i in range(index + 1, len(lines)) if lines[i].strip()), None)
            if next_index is None or lines[next_index].startswith(("#", "-", "!", "|")):
                continue
            description = lines[next_index].strip()
            lines[next_index] = ""
        suffix = "" if prefix.endswith(("!", "?", ".")) else ":"
        lines[index] = f"- **{prefix}{suffix}** {description}"
        changed += 1
    return changed


def _format_translated_spread(lines: list[str], entries: list[dict], labels: list[dict]) -> int:
    """Format translated callouts inside a PDF-proved illustrated spread."""
    if not labels:
        return 0
    stages = [entry for entry in entries if entry["pdf"]["kind"] == "display"
              and entry["pdf"]["size"] >= 24
              and min(item["page"] for item in labels) <= entry["pdf"]["page"] <= max(item["page"] for item in labels)]
    if len(stages) < 2:
        return 0
    stage_lines = []
    for entry in stages:
        choices = [index for index, line in enumerate(lines)
                   if HEADING.match(line) and normal(label(line)) == normal(entry["target"])]
        if len(choices) == 1:
            stage_lines.append(choices[0])
    if len(stage_lines) < 2:
        return 0
    start = min(stage_lines)
    end = len(lines)
    changed = 0
    seen = 0
    for index in range(start, end):
        if seen >= len(labels):
            break
        if index in stage_lines:
            continue
        line = lines[index]
        if line.startswith("- **"):
            seen += 1
            continue
        match = re.match(r"^(?:- )?([^#|!\n]{2,30})　([^　\n].+)$", line)
        if match:
            title = match.group(1).strip()
            description = match.group(2).strip()
            suffix = "" if title.endswith(("！", "？", "!", "?", "：", ":")) else "："
            lines[index] = f"- **{title}{suffix}** {description}"
            changed += 1
            seen += 1
        elif HEADING.match(line):
            next_index = next((j for j in range(index + 1, end) if lines[j].strip()), None)
            if next_index is None or lines[next_index].startswith(("#", "-", "!", "|")) or re.match(
                r"^[^#|!\-\n]{2,30}　[^　\n].+", lines[next_index]):
                continue
            title = label(line)
            suffix = "" if title.endswith(("！", "？", "!", "?", "：", ":")) else "："
            lines[index] = f"- **{title}{suffix}** {lines[next_index].strip()}"
            lines[next_index] = ""
            changed += 1
            seen += 1
    return changed


def _pdf_has_bullet(page, rect) -> bool:
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                if (len(span["text"].strip()) == 1 and not span["text"].strip().isalnum()
                        and span["size"] <= 10 and abs(span["bbox"][1] - rect.y0) < 7
                        and span["bbox"][0] < rect.x0):
                    return True
    return False


def _strip_false_lists(source: list[str], target: list[str], source_path: Path,
                       target_path: Path, pdf, pages: tuple[int, int]) -> int:
    findings = compare_structure("\n".join(source), "\n".join(target), source_path, target_path)
    changed = 0
    for finding in findings:
        token = finding["expected"]
        if not token or token["kind"] != "list_item" or finding["actual"] is not None:
            continue
        index = token["line"] - 1
        line = source[index]
        if not line.startswith("- "):
            continue
        phrase = line[2:26]
        hits = [(pdf[n], rect) for n in range(pages[0] - 1, pages[1]) for rect in pdf[n].search_for(phrase)]
        if hits and not any(_pdf_has_bullet(page, rect) for page, rect in hits):
            source[index] = line[2:]
            changed += 1
    return changed


def repair_paired_layout(source_docs: Path, translated_docs: Path, pdf_path: Path,
                         target_pages: dict[str, tuple[int, int]], glossary: Path,
                         plan_path: Path) -> dict[str, int]:
    if not pdf_path.is_file():
        return {}
    import pymupdf

    if plan_path.is_file():
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if plan.get("pdf_sha256") != hashlib.sha256(pdf_path.read_bytes()).hexdigest():
            raise ValueError("layout evidence PDF does not match the current source")
    else:
        plan = derive_layout_plan(source_docs, translated_docs, pdf_path, target_pages, glossary, plan_path)
    stats = Counter()
    with pymupdf.open(pdf_path) as pdf:
        for rel, entries in plan["chapters"].items():
            target_rel = plan.get("targets", {}).get(rel, rel)
            source_path, target_path = source_docs / rel, translated_docs / target_rel
            if not source_path.is_file() or not target_path.is_file():
                continue
            prior_stats = stats.copy()
            original_s, original_t = source_path.read_text(encoding="utf-8"), target_path.read_text(encoding="utf-8")
            initial_findings = len(compare_structure(original_s, original_t, source_path, target_path))
            source, target = original_s.splitlines(), original_t.splitlines()
            for entry in entries:
                stats["headings_aligned"] += _set_label(source, entry["source"], entry["level"], entry["source_block"])
                stats["headings_aligned"] += _set_label(target, entry["target"], entry["level"], entry["target_block"])
            stats["spread_callouts_formatted"] += _format_pdf_callouts(
                source, plan.get("spreads", {}).get(rel, []))
            stats["translated_spread_callouts_formatted"] += _format_translated_spread(
                target, entries, plan.get("spreads", {}).get(rel, []))
            stats["paired_titles_removed"] += _strip_title_headings(target)
            stats["paired_titles_removed"] += _strip_source_title_headings(source, target)
            surviving_targets = {normal(label(line)) for line in target if HEADING.match(line)}
            stats["paired_titles_removed"] += _strip_source_route_titles(
                source, rel, {normal(entry["source"]) for entry in entries
                              if normal(entry["target"]) in surviving_targets
                              and entry["alignment_cost"] <= -1.0})
            # The extracted glyph is source evidence. Leave it intact until its
            # translated counterpart has a corroborated list match.
            stats["false_list_markers_removed"] += _strip_false_lists(
                source, target, source_path, target_path, pdf, tuple(target_pages[target_rel]))
            reviewed = plan.get("reviewed", {})
            stats["reviewed_markers_applied"] += _reviewed_overlay(
                source, reviewed.get("source", {}).get(rel, []))
            stats["reviewed_markers_applied"] += _reviewed_overlay(
                target, reviewed.get("target", {}).get(rel, []))
            stats["paired_glyph_lists_recovered"] += _restore_paired_glyph_lists(source, target)
            stats["unproved_list_tails_joined"] += _join_unproved_list_continuations(source)
            stats["unproved_list_tails_joined"] += _join_lowercase_list_tails(source)
            stats["post_spread_lists_aligned"] += _align_post_spread_list(
                source, target, len(plan.get("spreads", {}).get(rel, [])))
            stats["unpaired_h1_aligned"] += _align_unpaired_h1(source, target, source_path, target_path)
            stats["short_labels_aligned"] += _align_short_label_lists(source, target, source_path, target_path)
            stats["prose_headings_demoted"] += _demote_prose_headings(source)
            stats["prose_headings_demoted"] += _demote_prose_headings(target)
            revised_s, revised_t = "\n".join(source).rstrip() + "\n", "\n".join(target).rstrip() + "\n"
            if len(compare_structure(revised_s, revised_t, source_path, target_path)) > initial_findings:
                stats = prior_stats
                source, target = original_s.splitlines(), original_t.splitlines()
                stats["paired_titles_removed"] += _strip_title_headings(target)
                stats["paired_titles_removed"] += _strip_source_route_titles(source, rel, set())
                stats["remaining_glyphs_cleaned"] += _clean_remaining_glyphs(target)
                revised_s, revised_t = "\n".join(source).rstrip() + "\n", "\n".join(target).rstrip() + "\n"
                if len(compare_structure(revised_s, revised_t, source_path, target_path)) > initial_findings:
                    source, target = original_s.splitlines(), original_t.splitlines()
                    stats = prior_stats
                    stats["remaining_glyphs_cleaned"] += _clean_remaining_glyphs(target)
                    revised_s, revised_t = original_s, "\n".join(target).rstrip() + "\n"
                stats["chapters_preserved"] += 1
            if revised_s != original_s:
                source_path.write_text(revised_s, encoding="utf-8")
                stats["source_files_changed"] += 1
            if revised_t != original_t:
                target_path.write_text(revised_t, encoding="utf-8")
                stats["translated_files_changed"] += 1
    stats["unresolved_layout_matches"] = len(plan.get("unresolved", []))
    plan["applied"] = {"source_sha256": _tree_digest(source_docs),
                       "target_sha256": _tree_digest(translated_docs)}
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dict(stats)
