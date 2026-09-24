"""Align a repaired English staging copy with its translated chapters.

Kedamono's PDF uses a display font for section labels and Wingdings for
bullets. Its Markdown extraction used H6/H1 and spurious hyphens for ordinary
body text. This pass runs only when the caller supplies that PDF and both
writable chapter trees.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from _kedamono_heading_pairs import HEADING_PAIRS
from validate_translation_structure import compare_structure

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

_BASIC_LABELS = (
    ("Pretend With Rules", "帶著規則扮家家酒"),
    ("Goal of the Game", "遊戲目標"),
    ("Session Terms", "場次用語"),
    ("Creation", "創作"),
    ("Session", "場次"),
    ("Game Master", "主持人"),
    ("Scenario", "劇本"),
    ("Player", "玩家"),
    ("The Dark Forest", "暗之森"),
    ("The Lord of Light", "光之主"),
    ("The Touched", "暗獸附身者"),
    ("Fulfilling Portents", "實現預言"),
    ("Inventing Context for Portents", "為預言創造情境"),
    ("Permission is Required", "必須取得同意"),
    ("Fulfill Portents at Any Time", "隨時實現預言"),
    ("A Portent for Whom", "預言是為了誰"),
    ("Portents of Death", "死亡預言"),
    ("Clearing Portents", "消除預言"),
    ("Opera Portents are Special", "歌劇預言的特別之處"),
    ("Once All Portents Are Fulfilled…", "所有預言都實現之後……"),
)

# PDF pp. 18–25: these are small bold labels inside the character-creation,
# Ordeal, and Portent sections, rather than the display-size section heads.
_BASIC_SUBSECTIONS = {
    "kedamono species", "feats", "desire", "lure form", "kedamono name",
    "dwelling", "opera", "legend", "drive off the pursuers", "twist portents",
    "continue to make checks until an ending condition is met",
    "thegploryath of", "theapgonyath of", "base roll", "use feats",
    "fportentsor intro...", "yourwhenfeaoperatsu...singor",
    "intro portent examples", "when a twist happens...", "when breaking a taboo...",
}
_BASIC_SUBSECTIONS = {re.sub(r"[^a-z0-9]", "", label) for label in _BASIC_SUBSECTIONS}

_SCENARIO_SECTION_LABELS = (
    ("Setting", "背景設定", 2), ("Once Upon a Time…", "從前從前……", 2),
    ("Requirements", "劇本條件", 2), ("NPCs", "登場人物（NPC）", 2),
    ("Scenario Background", "劇本背景", 3),
    ("Ordeal Opportunities", "試煉安排", 3),
    ("Preparing for the Game", "遊戲準備", 3),
    ("Play Time", "遊戲時間", 3), ("Conclusion", "結局", 2),
)
_MAKING_SCENARIOS_LABELS = (
    ("The Problem", "問題"), ("The Client", "委託人"),
    ("Solution & Location", "解決方法與地點"),
    ("Intro Portents", "前奏預言"),
    ("What Makes an Ordeal?", "怎樣才算試煉？"),
    ("Ordeal Domains", "試煉的領域"),
    ("Ordeal Difficulty", "試煉難度"),
    ("Creating Twist Portents", "設計波折預言"),
    ("Number of Checks", "判定次數"),
)


def _norm(text: str) -> str:
    return re.sub(r"[^\w\u3400-\u9fff]", "", text).casefold()


def _title(lines: list[str]) -> str:
    for line in lines[1:]:
        if line == "---":
            break
        if line.startswith("title:"):
            return line[6:].strip().strip("\"'")
    return ""


def _replace_once(lines: list[str], old: str, new: str) -> bool:
    for index, line in enumerate(lines):
        if line == old:
            lines[index] = new
            return True
    return False


def _set_heading(lines: list[str], label: str, level: int) -> bool:
    for index, line in enumerate(lines):
        match = HEADING.match(line)
        if line == label or line == " " + label or (match and match.group(2) == label):
            lines[index] = "#" * level + " " + label
            return True
    return False


def _spread_callout(lines: list[str], label: str, translated: bool = False) -> None:
    for index, line in enumerate(lines):
        if line != "## " + label:
            continue
        next_index = next((i for i in range(index + 1, len(lines)) if lines[i].strip()), None)
        if next_index is None or lines[next_index].startswith(("#", "-", "!", "|")):
            return
        colon = "" if label.endswith(("!", "！")) else ("：" if translated else ":")
        lines[index] = f"- **{label}{colon}** {lines[next_index]}"
        lines[next_index] = ""
        return


def _wingdings_lists(lines: list[str], joins: tuple[tuple[str, str], ...] = ()) -> None:
    body = "\n".join(lines)
    for old, new in joins:
        body = body.replace(old, new)
    revised = []
    for line in body.splitlines():
        if " " in line:
            line = line.replace("  ", "\n- ")
            if line.startswith(" "):
                line = "- " + line[2:]
        revised.extend(line.split("\n"))
    lines[:] = revised


def _pdf_heading_pairs(rel: str, source: list[str], target: list[str]) -> None:
    """Promote only labels identified as Bahnschrift headings in this PDF."""
    used_source: set[int] = set()
    used_target: set[int] = set()
    for english, chinese, level in HEADING_PAIRS.get(rel, ()):
        source_index = next((i for i, line in enumerate(source)
                             if i not in used_source and (line == " " + english
                             or (HEADING.match(line) and HEADING.match(line).group(2) == english))), None)
        target_candidates = [i for i, line in enumerate(target)
                             if i not in used_target and (line == chinese
                             or (HEADING.match(line) and HEADING.match(line).group(2) == chinese))]
        later_caption = (
            rel == "on-the-world/the-dark-forest.md" and english in
            {"The Furthest Sea", "The Dreamcatch Shore", "The Template Kingdom"}
        ) or (rel == "session-rules/ordeals.md" and english in {"Path of Glory", "Path of Agony"})
        target_index = (target_candidates[-1] if later_caption else target_candidates[0]) if target_candidates else None
        if source_index is None or target_index is None:
            continue
        source[source_index] = "#" * level + " " + english
        target[target_index] = "#" * level + " " + chinese.removeprefix("- ")
        used_source.add(source_index)
        used_target.add(target_index)


def _special(rel: str, source: list[str], target: list[str]) -> None:
    _pdf_heading_pairs(rel, source, target)
    if rel == "session-rules/playing-with-friends.md":
        _set_heading(target, "場次中的恰當態度", 2)
        _set_heading(source, "Relish in Offered Ideas", 3)
        _set_heading(target, "欣然接受別人提出的點子", 3)
    if rel == "session-rules/ordeals.md":
        for english, chinese, level in (
            ("invesTiGaTions", "調查（Investigation）", 2),
            ("Vital Info", "關鍵資訊", 3),
            ("Veracity of Info", "資訊真偽", 3),
            ("mulTiPle ordeals", "多場試煉", 2),
            ("Shared Portents", "共用預言", 3),
            ("Switching Ordeals", "切換試煉", 3),
            ("Path of Glory", "榮光之門", 3),
            ("Path of Agony", "苦難之門", 3),
            ("Ending", "結束", 3),
        ):
            _set_heading(source, english, level)
            _set_heading(target, chinese, level)
    if rel == "on-kedamono/kedamono-species/index.md":
        for index, line in enumerate(source):
            match = HEADING.match(line)
            if match and match.group(2) == "kedamono sPeCies":
                source[index] = ""
            elif match and match.group(2) == "Legend Effects":
                source[index] = "**Legend Effects**"
        _replace_once(target, "暗獸物種", "")
        _replace_once(source, " Subspecies", "## Subspecies")
        _set_heading(target, "亞種", 2)
        _replace_once(source, " Using Your Legend", "### Using Your Legend")
        _set_heading(target, "使用傳說", 3)
        _replace_once(target, "傳說效果", "**傳說效果**")
        for lines in (source, target):
            for index, line in enumerate(lines):
                if line.startswith(("- 1. ", "- 2. ")):
                    lines[index] = line[2:]
                elif line.startswith(("- • ", "• ")):
                    lines[index] = "   - " + line.split("• ", 1)[1]
        for index, line in enumerate(source):
            if line.startswith((" When a session", " Create things for your kedamono")):
                source[index] = "- " + line[2:]
        source[:] = "\n".join(source).replace("short\n\nstories", "short stories").splitlines()
    if rel.startswith("on-kedamono/kedamono-species/") and not rel.endswith("/index.md"):
        title_s, title_t = _norm(_title(source)), _norm(_title(target))
        for lines, title in ((source, title_s), (target, title_t)):
            for index, line in enumerate(lines):
                match = HEADING.match(line)
                if match and _norm(match.group(2)) == title:
                    lines[index] = ""
    if rel == "on-kedamono/kedamono-species/mimirstrix.md":
        _replace_once(source, " Night Sentinels", "## Night Sentinels")
        _replace_once(source, " Knowledge Gluttons", "## Knowledge Gluttons")
        _replace_once(target, "知識饕客", "## 知識饕客")
        for index, line in enumerate(source):
            if line.startswith("- At the hooting of a common owl"):
                source[index] = line[2:]
        for index, line in enumerate(target):
            if line.startswith("- 只要普通的貓頭鷹一叫"):
                target[index] = line[2:]
    if rel == "scenario/index.md":
        for label in ("SCenario", "SCENARIO"):
            _replace_once(source, label, "")
        for _ in range(2):
            _replace_once(target, "劇本", "")
        for english, chinese, level in _SCENARIO_SECTION_LABELS:
            _replace_once(source, " " + english, "#" * level + " " + english)
            _replace_once(target, " " + chinese, "#" * level + " " + chinese)
        _wingdings_lists(source, (("even\n\nmaintain", "even maintain"),
                                 ("the\n\nkedamono are demons", "the kedamono are demons")))
        _wingdings_lists(target)
    if rel == "on-game-mastering/making-scenarios.md":
        for english, chinese in _MAKING_SCENARIOS_LABELS:
            _replace_once(source, " " + english, "### " + english)
            _replace_once(target, " " + chinese, "### " + chinese)
        _wingdings_lists(source, (("such as\n\nnames", "such as names"),
                                 ("but\n\nare interesting", "but are interesting")))
        _wingdings_lists(target)
        for lines, label in ((source, "Ordeal Difficulty"), (target, "試煉難度（Difficulty）")):
            indices = [index for index, line in enumerate(lines)
                       if (match := HEADING.match(line)) and match.group(2) == label]
            if indices and (len(indices) > 1 or lines[indices[-1]].startswith("###### ")):
                lines[indices[-1]] = f"**{label}**"
    if rel == "on-kedamono/apocrypha.md":
        _replace_once(source, "### aPPoCryPhaP", "")
        _replace_once(source, " Apocryphal Operas", "## Apocryphal Operas")
        _replace_once(target, "外典歌劇（Apocryphal Operas）", "## 外典歌劇（Apocryphal Operas）")
        _replace_once(source, " You have at least 1 available Legend  You have your Opera available",
                      "- You have at least 1 available Legend\n- You have your Opera available")
        _replace_once(target, "你至少有 1 個可用的傳說（Legend）。", "- 你至少有 1 個可用的傳說（Legend）。")
        _replace_once(target, "你的歌劇也處於可用狀態。", "- 你的歌劇也處於可用狀態。")
    if rel == "basic-rules/index.md":
        _replace_once(source, "###### basiC rules", "")
        _replace_once(source, " Your character is an ageless kedamono.",
                      "**Your character is an ageless kedamono.**")
        _replace_once(target, "你的角色是一隻長生不老的暗獸。", "**你的角色是一隻長生不老的暗獸。**")
        for english, chinese in (("Choose Kedamono", "選擇暗獸"),
                                 ("Define the Pack", "決定夥群"),
                                 ("Share Your Play!", "分享你的遊玩成果！")):
            _spread_callout(source, english)
            _spread_callout(target, chinese, translated=True)
        source[:] = [line.replace("**Share Your Play!:**", "**Share Your Play!**") for line in source]
        target[:] = [line.replace("**分享你的遊玩成果！：**", "**分享你的遊玩成果！**") for line in target]
        for english, chinese in _BASIC_LABELS:
            _replace_once(source, " " + english, "### " + english)
            _replace_once(target, chinese, "### " + chinese)
        # PDF page 7 has three Wingdings bullets. Its extracted text wrapped
        # between the first and third items and merged all three markers.
        body = "\n".join(source)
        if "Merely by reading this book, you will be equipped to do all of the following: " in body:
            body = body.replace("following:  ", "following:\n\n- ")
            body = body.replace("a\n\nmanga,", "a manga,")
            body = body.replace("session you’ve run.  ", "session you’ve run.\n- ")
            body = body.replace("rules set forth  ", "rules set forth\n- ")
            body = body.replace("Kedamono\n\nOpera.", "Kedamono Opera.")
            source[:] = body.splitlines()
        for chinese in (
            "創作《暗獸歌劇》的故事，例如小說、插畫、漫畫、電影，或是你所參與場次的遊玩紀錄。",
            "依照書中的規則創造自己的暗獸。",
            "創作能在《暗獸歌劇》場次中使用的劇本。",
        ):
            _replace_once(target, chinese, "- " + chinese)
    if rel == "on-the-world/and-all-the-rest.md":
        _replace_once(source, "###### aand aall TThe resTT", "")
    if rel == "on-the-world/definition-of-a-kedamono.md":
        _replace_once(source, "###### definiTion of a kedamono", "")
    if rel == "on-the-world/the-dark-forest.md":
        _replace_once(source, "###### TThe dark foresTT", "")
        for i, line in enumerate(target):
            if line.startswith("# 有時，空間扭曲"):
                target[i] = line[2:]
        hits = [i for i, line in enumerate(target) if line == "邊陲"]
        if len(hits) > 1:
            target[hits[-1]] = "## 邊陲"
    if rel == "on-kedamono/making-a-kedamono.md":
        for i, line in enumerate(source):
            if line.startswith("###### Whatever you end up using"):
                source[i] = line[7:]
        for label in ("For Creations", "For Sessions"):
            _replace_once(source, " " + label, "## " + label)
        _replace_once(target, "用於跑團", "## 用於跑團")
        _replace_once(target, "誕生", "## 誕生")


def _heading_indices(lines: list[str]) -> list[int]:
    return [i for i, line in enumerate(lines) if HEADING.match(line)]


def _remove_paired_title(source: list[str], target: list[str]) -> int:
    si, ti = _heading_indices(source), _heading_indices(target)
    if len(si) != len(ti):
        return 0

    def first_prose(lines: list[str]) -> int:
        end = next((i for i, line in enumerate(lines[1:], 1) if line == "---"), 0)
        return next((i for i, line in enumerate(lines[end + 1:], end + 1)
                     if len(line) >= 80 and not line.startswith(("!", "|", "#"))), len(lines))

    title_s, title_t = _norm(_title(source)), _norm(_title(target))
    first_s, first_t = first_prose(source), first_prose(target)
    changed = 0
    for a, b in zip(si, ti):
        heading_s, heading_t = HEADING.match(source[a]).group(2), HEADING.match(target[b]).group(2)
        if "[" in heading_s or "[" in heading_t:
            continue
        translated = _norm(re.sub(r"[（(].*[）)]", "", heading_t))
        if a < first_s and b < first_t and (translated == title_t or _norm(heading_s) == title_s):
            source[a] = target[b] = ""
            changed += 1
    return changed


def _align_headings(rel: str, source: list[str], target: list[str]) -> int:
    si, ti = _heading_indices(source), _heading_indices(target)
    if len(si) != len(ti):
        raise ValueError(f"{rel}: heading count differs: {len(si)} English, {len(ti)} translated")
    section = ""
    changed = 0
    for a, b in zip(si, ti):
        english, translated = HEADING.match(source[a]).group(2), HEADING.match(target[b]).group(2)
        if english.startswith("["):
            level = 3
        elif source[a].startswith("### ") and target[b].startswith("### "):
            level = 3
        elif rel == "basic-rules/index.md" and _norm(english) in _BASIC_SUBSECTIONS:
            level = 3
        elif (rel == "on-kedamono/apocrypha.md" or "/kedamono-species/" in rel) and section == "cards":
            level = 3
        else:
            level = 2
        clean = _norm(english)
        if rel == "on-kedamono/apocrypha.md" and "legendaryoperas" in clean:
            section = "cards"
        if "/kedamono-species/" in rel and clean in {"opera", "feats", "feat"}:
            section = "cards"
        new_s, new_t = "#" * level + " " + english, "#" * level + " " + translated
        changed += (source[a] != new_s) + (target[b] != new_t)
        source[a], target[b] = new_s, new_t
    return changed


def _pdf_has_bullet(page, rect) -> bool:
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                if ("Wingdings" in span["font"] and abs(span["bbox"][1] - rect.y0) < 7
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
        hits = [(pdf[n], rect) for n in range(pages[0] - 1, pages[1])
                for rect in pdf[n].search_for(phrase)]
        if not hits or any(_pdf_has_bullet(page, rect) for page, rect in hits):
            continue
        source[index] = line[2:]
        changed += 1
    return changed


def repair_paired_layout(source_docs: Path, translated_docs: Path, pdf_path: Path,
                         pages_by_source: dict[str, tuple[int, int]]) -> dict[str, int]:
    """Repair paired chapters using the PDF as authority for ambiguous bullets."""
    if pdf_path.name != "Kedamono_Opera.pdf" or not pdf_path.is_file():
        return {}
    import pymupdf

    stats = Counter()
    with pymupdf.open(pdf_path) as pdf:
        for source_path in sorted(source_docs.rglob("*.md")):
            rel = str(source_path.relative_to(source_docs))
            target_rel = "book-index/index.md" if rel == "index/index.md" else rel
            target_path = translated_docs / target_rel
            if not target_path.is_file() or rel not in pages_by_source:
                continue
            original_s, original_t = source_path.read_text(encoding="utf-8"), target_path.read_text(encoding="utf-8")
            source, target = original_s.splitlines(), original_t.splitlines()
            _special(rel, source, target)
            stats["paired_titles_removed"] += _remove_paired_title(source, target)
            stats["headings_aligned"] += _align_headings(rel, source, target)
            _pdf_heading_pairs(rel, source, target)
            stats["false_list_markers_removed"] += _strip_false_lists(
                source, target, source_path, target_path, pdf, tuple(pages_by_source[rel]))
            revised_s, revised_t = "\n".join(source).rstrip() + "\n", "\n".join(target).rstrip() + "\n"
            if revised_s != original_s:
                source_path.write_text(revised_s, encoding="utf-8")
                stats["source_files_changed"] += 1
            if revised_t != original_t:
                target_path.write_text(revised_t, encoding="utf-8")
                stats["translated_files_changed"] += 1
    return dict(stats)
