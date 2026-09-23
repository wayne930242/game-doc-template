"""Tests for _markdown_utils module."""

import pytest

from _markdown_utils import (
    LINKED_MARKDOWN_IMAGE_RE,
    MARKDOWN_HEADING_RE,
    MARKDOWN_IMAGE_RE,
    clean_content,
    count_page_text_tokens,
    extract_markdown_image_targets,
    find_list_continuation_items,
    find_paragraph_continuation_breaks,
    merge_list_continuation_at,
    merge_list_continuations,
    merge_paragraph_continuation_at,
    merge_paragraph_continuations,
    split_markdown_sections,
    strip_artifact_headings,
    strip_markdown_images,
    yaml_safe,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_markdown_image_re_matches_simple(self):
        assert MARKDOWN_IMAGE_RE.search("![alt](image.png)")

    def test_markdown_image_re_matches_empty_alt(self):
        assert MARKDOWN_IMAGE_RE.search("![](image.png)")

    def test_markdown_image_re_no_match_plain_link(self):
        assert not MARKDOWN_IMAGE_RE.search("[text](link)")

    def test_linked_markdown_image_re_matches(self):
        text = "[![alt](img.png)](http://example.com)"
        assert LINKED_MARKDOWN_IMAGE_RE.search(text)

    def test_linked_markdown_image_re_no_match_plain(self):
        assert not LINKED_MARKDOWN_IMAGE_RE.search("![alt](img.png)")

    def test_heading_re_matches_h1(self):
        assert MARKDOWN_HEADING_RE.match("# Title")

    def test_heading_re_matches_h2(self):
        assert MARKDOWN_HEADING_RE.match("## Section")

    def test_heading_re_matches_h3(self):
        assert MARKDOWN_HEADING_RE.match("### Sub")

    def test_heading_re_no_match_h4(self):
        assert not MARKDOWN_HEADING_RE.match("#### Deep")

    def test_heading_re_no_match_no_space(self):
        assert not MARKDOWN_HEADING_RE.match("#NoSpace")


# ---------------------------------------------------------------------------
# strip_markdown_images
# ---------------------------------------------------------------------------

class TestStripMarkdownImages:
    def test_removes_simple_image(self):
        result = strip_markdown_images("before ![alt](img.png) after")
        assert "![" not in result
        assert "before" in result
        assert "after" in result

    def test_removes_linked_image(self):
        text = "start [![alt](img.png)](http://url) end"
        result = strip_markdown_images(text)
        assert "![" not in result
        assert "start" in result
        assert "end" in result

    def test_collapses_blank_lines(self):
        text = "line1\n\n\n\n\nline2"
        result = strip_markdown_images(text)
        assert "\n\n\n" not in result

    def test_strips_whitespace(self):
        result = strip_markdown_images("  text  ")
        assert result == "text"

    def test_empty_input(self):
        assert strip_markdown_images("") == ""

    def test_no_images(self):
        assert strip_markdown_images("plain text") == "plain text"


# ---------------------------------------------------------------------------
# extract_markdown_image_targets
# ---------------------------------------------------------------------------

class TestExtractMarkdownImageTargets:
    def test_single_image(self):
        result = extract_markdown_image_targets("![alt](image.png)")
        assert result == ["image.png"]

    def test_multiple_images(self):
        text = "![a](one.png) text ![b](two.jpg)"
        result = extract_markdown_image_targets(text)
        assert result == ["one.png", "two.jpg"]

    def test_url_encoded_path(self):
        result = extract_markdown_image_targets("![alt](path%20with%20spaces.png)")
        assert result == ["path with spaces.png"]

    def test_no_images(self):
        assert extract_markdown_image_targets("no images here") == []

    def test_image_with_title(self):
        result = extract_markdown_image_targets('![alt](img.png "title")')
        assert result == ["img.png"]

    def test_image_with_angle_brackets(self):
        result = extract_markdown_image_targets("![alt](<image.png>)")
        assert result == ["image.png"]

    def test_empty_input(self):
        assert extract_markdown_image_targets("") == []


# ---------------------------------------------------------------------------
# split_markdown_sections
# ---------------------------------------------------------------------------

class TestSplitMarkdownSections:
    def test_single_section_no_heading(self):
        result = split_markdown_sections("just text")
        assert result == ["just text"]

    def test_splits_on_headings(self):
        text = "intro\n## A\ncontent a\n## B\ncontent b"
        result = split_markdown_sections(text)
        assert len(result) == 3
        assert "intro" in result[0]
        assert "## A" in result[1]
        assert "## B" in result[2]

    def test_empty_input(self):
        result = split_markdown_sections("")
        assert result == [""]

    def test_only_whitespace(self):
        result = split_markdown_sections("   \n  \n  ")
        assert result == [""]

    def test_heading_at_start(self):
        text = "## First\ncontent\n## Second\nmore"
        result = split_markdown_sections(text)
        assert len(result) == 2

    def test_preserves_content(self):
        text = "## Title\nline1\nline2"
        result = split_markdown_sections(text)
        assert "line1" in result[0]
        assert "line2" in result[0]

    def test_h3_also_splits(self):
        text = "intro\n### Sub\ncontent"
        result = split_markdown_sections(text)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# strip_artifact_headings
# ---------------------------------------------------------------------------

class TestStripArtifactHeadings:
    def test_removes_numeric_only_heading(self):
        text = "content\n\n# 33\n\nmore content"
        result = strip_artifact_headings(text)
        assert "# 33" not in result
        assert "content" in result
        assert "more content" in result

    def test_removes_empty_heading(self):
        text = "content\n\n##\n\nmore content"
        result = strip_artifact_headings(text)
        assert "##" not in result

    def test_removes_empty_heading_with_trailing_space(self):
        text = "content\n\n## \n\nmore content"
        result = strip_artifact_headings(text)
        assert "## " not in result

    def test_keeps_real_headings(self):
        text = "# Introduction\ncontent\n## Combat Rules\nmore"
        result = strip_artifact_headings(text)
        assert "# Introduction" in result
        assert "## Combat Rules" in result

    def test_keeps_heading_with_numeric_and_text(self):
        text = "## Chapter 33: The Beginning"
        assert strip_artifact_headings(text) == text

    def test_collapses_blank_lines_left_behind(self):
        text = "line1\n\n# 5\n\nline2"
        result = strip_artifact_headings(text)
        assert "\n\n\n" not in result

    def test_mixed_real_and_artifact_headings(self):
        text = "# 6\n\n### Real Section\ncontent\n\n#\n\n## Another Real One"
        result = strip_artifact_headings(text)
        lines = result.splitlines()
        assert "# 6" not in lines
        assert "#" not in lines
        assert "### Real Section" in result
        assert "## Another Real One" in result

    def test_empty_input(self):
        assert strip_artifact_headings("") == ""

    def test_no_artifact_headings(self):
        text = "just plain text"
        assert strip_artifact_headings(text) == text


# ---------------------------------------------------------------------------
# find_list_continuation_items / merge_list_continuation_at / merge_list_continuations
#
# Fixtures below are drawn from real OpenDataLoader breaks found in
# kedamono-opera/data/markdown/Kedamono_Opera.md (lines 6975-6977 and 7011-7013).
# ---------------------------------------------------------------------------

REAL_POSITIVE = (
    "But one should avoid overly graphic or grotesque representations of such "
    "fates (unless this was agreed\n"
    "\n"
    "- to during the Prelude phase). Such would not be part of the fun of "
    "Kedamono Opera.\n"
)

REAL_POSITIVE_MERGED = (
    "But one should avoid overly graphic or grotesque representations of such "
    "fates (unless this was agreed to during the Prelude phase). Such would not "
    "be part of the fun of Kedamono Opera.\n"
)

SECOND_POSITIVE = (
    "During a session, PCs can gain portents, usually called marking\n"
    "\n"
    "- them. There is no limit to the number of portents a kedamono may have "
    "marked.\n"
)


class TestFindListContinuationItems:
    def test_finds_real_break_after_agreed(self):
        assert find_list_continuation_items(REAL_POSITIVE) == [3]

    def test_ignores_list_item_after_heading(self):
        text = "###### share WiTh oThers\n\n- At last, your game has come to an end.\n"
        assert find_list_continuation_items(text) == []

    def test_ignores_uppercase_list_item(self):
        # Preceding paragraph deliberately does not end in terminal punctuation,
        # so this isolates the lowercase-first-letter gate from the punctuation gate.
        text = (
            "Sphinxes are known to have a great deal of control over their own\n"
            "\n"
            "- As mentioned, cats disappear when close to death.\n"
        )
        assert find_list_continuation_items(text) == []

    def test_ignores_item_after_sentence_ending_in_period(self):
        text = "This is a complete sentence.\n\n- lowercase item that is a genuine list.\n"
        assert find_list_continuation_items(text) == []

    def test_ignores_item_after_sentence_ending_in_question_mark(self):
        text = "Where did that mouse go?\n\n- lowercase but unrelated.\n"
        assert find_list_continuation_items(text) == []

    def test_ignores_genuine_multi_item_numbered_list(self):
        text = (
            "Continue to make checks until an ending condition is met\n"
            "\n"
            "- 1. One player makes a check\n"
            "- 2. The check generates either a Triumph or a Twist\n"
        )
        assert find_list_continuation_items(text) == []

    def test_ignores_item_after_another_list_item(self):
        text = "- first item, itself a list\n\n- second lowercase item\n"
        assert find_list_continuation_items(text) == []

    def test_ignores_item_with_no_preceding_block(self):
        text = "- to during the Prelude phase). Continuation with nothing before it.\n"
        assert find_list_continuation_items(text) == []

    def test_finds_multiple_breaks_in_one_document(self):
        text = REAL_POSITIVE + "\n" + SECOND_POSITIVE
        lines = find_list_continuation_items(text)
        assert len(lines) == 2

    def test_no_false_positive_on_plain_text(self):
        assert find_list_continuation_items("just plain text\n\nmore text\n") == []


class TestMergeListContinuationAt:
    def test_merges_with_space_separator(self):
        result = merge_list_continuation_at(REAL_POSITIVE, 3, separator=" ")
        assert result == REAL_POSITIVE_MERGED

    def test_merges_with_no_separator_for_chinese(self):
        text = "他不願意透露\n\n- 這件事的真相。\n"
        result = merge_list_continuation_at(text, 3, separator="")
        assert result == "他不願意透露這件事的真相。\n"

    def test_raises_when_no_block_at_line(self):
        with pytest.raises(ValueError):
            merge_list_continuation_at(REAL_POSITIVE, 99)

    def test_raises_when_target_is_not_a_list_item(self):
        text = "first paragraph\n\nsecond paragraph\n"
        with pytest.raises(ValueError):
            merge_list_continuation_at(text, 3)

    def test_raises_when_no_preceding_block(self):
        text = "- lone item with nothing before it\n"
        with pytest.raises(ValueError):
            merge_list_continuation_at(text, 1)


class TestMergeListContinuations:
    def test_merges_real_break_and_reports_count(self):
        cleaned, count = merge_list_continuations(REAL_POSITIVE)
        assert count == 1
        assert cleaned == REAL_POSITIVE_MERGED
        assert "- to during" not in cleaned

    def test_merges_multiple_breaks_in_one_document(self):
        text = REAL_POSITIVE + "\n" + SECOND_POSITIVE
        cleaned, count = merge_list_continuations(text)
        assert count == 2
        assert "- to during" not in cleaned
        assert "- them." not in cleaned
        assert "agreed to during the Prelude phase" in cleaned
        assert "marking them. There is no limit" in cleaned

    def test_leaves_genuine_lists_untouched(self):
        text = (
            "Continue to make checks until an ending condition is met\n"
            "\n"
            "- 1. One player makes a check\n"
            "- 2. The check generates either a Triumph or a Twist\n"
            "\n"
            "###### share WiTh oThers\n"
            "\n"
            "- At last, your game has come to an end.\n"
        )
        cleaned, count = merge_list_continuations(text)
        assert count == 0
        assert cleaned == text

    def test_no_merges_returns_original_text_and_zero_count(self):
        text = "just plain text\n\nmore text\n"
        cleaned, count = merge_list_continuations(text)
        assert count == 0
        assert cleaned == text


# ---------------------------------------------------------------------------
# find_paragraph_continuation_breaks / merge_paragraph_continuation_at /
# merge_paragraph_continuations
#
# Fixtures below are drawn from real OpenDataLoader breaks found in
# kedamono-opera/data/markdown/Kedamono_Opera.md (lines 63-67, 1244-1246,
# 7627-7629, 9-11, 1768-1770, 201-207, 7897-7899, 7907-7909, 8331-8335).
# ---------------------------------------------------------------------------

REAL_PARAGRAPH_POSITIVE = (
    "Kedamono Opera is a game that depicts nightmarish creatures with dualistic "
    "natures. While monsters perhaps, at the same time, there’s room for negotiation\n"
    "\n"
    "with these other weaker creatures. How that comes about is something entirely "
    "up to you.\n"
)

REAL_PARAGRAPH_POSITIVE_MERGED = (
    "Kedamono Opera is a game that depicts nightmarish creatures with dualistic "
    "natures. While monsters perhaps, at the same time, there’s room for negotiation "
    "with these other weaker creatures. How that comes about is something entirely "
    "up to you.\n"
)

# A three-block chain (a single sentence wrapped as three OpenDataLoader blocks);
# the third block starts with a capitalized word ("Opera.") and is intentionally
# out of scope for this lowercase-start rule, so only the first join is merged.
REAL_PARAGRAPH_CHAIN = (
    "Merely by reading this book, you will be equipped to do all of the "
    "following: \x94 Create a Kedamono Opera story, whether that’s a novel, an "
    "illustration, a\n"
    "\n"
    "manga, a movie, or even a play report of a session you’ve run. \x94 Create "
    "your own kedamono in accordance with the rules set forth \x94 Create a "
    "scenario for use during a session of Kedamono\n"
    "\n"
    "Opera.\n"
)

REAL_PARAGRAPH_CHAIN_MERGED_ONCE = (
    "Merely by reading this book, you will be equipped to do all of the "
    "following: \x94 Create a Kedamono Opera story, whether that’s a novel, an "
    "illustration, a manga, a movie, or even a play report of a session you’ve "
    "run. \x94 Create your own kedamono in accordance with the rules set forth "
    "\x94 Create a scenario for use during a session of Kedamono\n"
    "\n"
    "Opera.\n"
)

# A bulleted list rendered inline with "\x94" markers (OpenDataLoader control-
# character bullets); the wrapped bullet ending "even" is a genuine continuation,
# but "kedamono are demons?" is itself a self-contained, punctuation-terminated
# unit that still carries a "\x94" residue, so it must be reported as ambiguous
# rather than merged.
REAL_PARAGRAPH_RESIDUE = (
    "\x94 Why would the Lord of Light test Teresa in this way? Can she even\n"
    "\n"
    "maintain her faith when faced with all of this? \x94 What happens to the "
    "grail? It could still save a lot of people, after all. \x94 Would this "
    "event change the stance of the church, who teaches that the\n"
    "\n"
    "kedamono are demons? \x94 Will later generations view Teresa as a saint or "
    "as a witch?\n"
)

# A trailing page number leaked into the continuation ("225"); must be reported
# as ambiguous rather than merged with the number embedded mid-paragraph.
REAL_PARAGRAPH_PAGE_NUMBER_RESIDUE = (
    "\x94 Portents featuring things not included in the scenario’s outline, but\n"
    "\n"
    "are interesting when they happen. 225\n"
)

# A table-of-contents entry ("basiC rules") rendered without heading markup;
# looks like a lowercase-start continuation but is a decorative-caps artifact.
REAL_TOC_NEGATIVE = "Table of ConTenTs\n\nbasiC rules\n\nPg. 2\n"

# A repeated table label ("PORTENT" / "lure forms names"); too short to be a
# genuine paragraph continuation.
REAL_TABLE_LABEL_NEGATIVE = "PORTENT\n\nlure forms names\n"

# A sidebar title ("Human-Like Appendage") interleaved into the main-column
# flow by the PDF's two-column layout; neither half is a real continuation.
REAL_SIDEBAR_TITLE_NEGATIVE = (
    "Those who believe a lure is a real human cannot\n"
    "\n"
    "lure\n"
    "\n"
    "Human-Like Appendage\n"
    "\n"
    "perceive the kedamono’s main body.\n"
)


class TestFindParagraphContinuationBreaks:
    def test_finds_real_break_about_negotiation(self):
        assert find_paragraph_continuation_breaks(REAL_PARAGRAPH_POSITIVE) == ([3], [])

    def test_finds_first_join_in_a_three_block_chain(self):
        merges, ambiguous = find_paragraph_continuation_breaks(REAL_PARAGRAPH_CHAIN)
        assert merges == [3]
        assert ambiguous == []

    def test_reports_self_contained_control_char_block_as_ambiguous(self):
        merges, ambiguous = find_paragraph_continuation_breaks(REAL_PARAGRAPH_RESIDUE)
        # The first join (ending "even" / starting "maintain") is a genuine,
        # still-incomplete continuation and is merged; the second join lands on
        # a self-contained "kedamono are demons?" block still carrying a
        # control-character residue, so it is reported instead of merged.
        assert merges == [3]
        assert ambiguous == [5]

    def test_reports_trailing_page_number_as_ambiguous(self):
        merges, ambiguous = find_paragraph_continuation_breaks(
            REAL_PARAGRAPH_PAGE_NUMBER_RESIDUE
        )
        assert merges == []
        assert ambiguous == [3]

    def test_ignores_table_of_contents_entry(self):
        assert find_paragraph_continuation_breaks(REAL_TOC_NEGATIVE) == ([], [])

    def test_ignores_repeated_table_label(self):
        assert find_paragraph_continuation_breaks(REAL_TABLE_LABEL_NEGATIVE) == ([], [])

    def test_ignores_sidebar_title_fragments(self):
        merges, ambiguous = find_paragraph_continuation_breaks(REAL_SIDEBAR_TITLE_NEGATIVE)
        assert merges == []
        assert ambiguous == []

    def test_ignores_item_after_sentence_ending_in_period(self):
        text = "This is a complete sentence right here.\n\nlowercase but unrelated new paragraph.\n"
        assert find_paragraph_continuation_breaks(text) == ([], [])

    def test_ignores_heading_as_next_block(self):
        text = "An unterminated paragraph fragment right\n\n###### a heading\n"
        assert find_paragraph_continuation_breaks(text) == ([], [])

    def test_ignores_list_item_as_next_block(self):
        text = (
            "An unterminated paragraph fragment right\n\n- a genuine list item here\n"
        )
        assert find_paragraph_continuation_breaks(text) == ([], [])

    def test_ignores_short_next_fragment(self):
        text = "A long enough preceding paragraph fragment right\n\ntiny bit\n"
        assert find_paragraph_continuation_breaks(text) == ([], [])

    def test_no_false_positive_on_plain_text(self):
        text = "This is one paragraph.\n\nThis is another paragraph.\n"
        assert find_paragraph_continuation_breaks(text) == ([], [])


class TestMergeParagraphContinuationAt:
    def test_merges_with_space_separator(self):
        result = merge_paragraph_continuation_at(REAL_PARAGRAPH_POSITIVE, 3, separator=" ")
        assert result == REAL_PARAGRAPH_POSITIVE_MERGED

    def test_merges_with_no_separator_for_chinese(self):
        text = "他不願意透露這件事\n\n的真相。\n"
        result = merge_paragraph_continuation_at(text, 3, separator="")
        assert result == "他不願意透露這件事的真相。\n"

    def test_raises_when_no_block_at_line(self):
        with pytest.raises(ValueError):
            merge_paragraph_continuation_at(REAL_PARAGRAPH_POSITIVE, 99)

    def test_raises_when_no_preceding_block(self):
        text = "lone block with nothing before it\n"
        with pytest.raises(ValueError):
            merge_paragraph_continuation_at(text, 1)


class TestMergeParagraphContinuations:
    def test_merges_real_break_and_reports_count(self):
        cleaned, count, ambiguous = merge_paragraph_continuations(REAL_PARAGRAPH_POSITIVE)
        assert count == 1
        assert ambiguous == []
        assert cleaned == REAL_PARAGRAPH_POSITIVE_MERGED

    def test_stops_a_chain_at_the_capitalized_block(self):
        cleaned, count, ambiguous = merge_paragraph_continuations(REAL_PARAGRAPH_CHAIN)
        assert count == 1
        assert ambiguous == []
        assert cleaned == REAL_PARAGRAPH_CHAIN_MERGED_ONCE

    def test_merges_genuine_join_and_reports_residue_join_as_ambiguous(self):
        cleaned, count, ambiguous = merge_paragraph_continuations(REAL_PARAGRAPH_RESIDUE)
        assert count == 1
        assert ambiguous == [3]
        assert "Can she even maintain her faith" in cleaned
        assert "who teaches that the\n\nkedamono are demons?" in cleaned

    def test_leaves_toc_and_table_label_untouched(self):
        for text in (REAL_TOC_NEGATIVE, REAL_TABLE_LABEL_NEGATIVE, REAL_SIDEBAR_TITLE_NEGATIVE):
            cleaned, count, ambiguous = merge_paragraph_continuations(text)
            assert count == 0
            assert ambiguous == []
            assert cleaned == text

    def test_no_merges_returns_original_text_and_zero_count(self):
        text = "just plain text\n\nmore text\n"
        cleaned, count, ambiguous = merge_paragraph_continuations(text)
        assert count == 0
        assert ambiguous == []
        assert cleaned == text


# ---------------------------------------------------------------------------
# clean_content
# ---------------------------------------------------------------------------

class TestCleanContent:
    def test_removes_pattern(self):
        result = clean_content("hello world foo", [r"world\s*"])
        assert result == "hello foo"

    def test_multiple_patterns(self):
        result = clean_content("a b c d", [r"b ", r"d"])
        assert result == "a c"

    def test_collapses_blank_lines(self):
        text = "line1\n\n\n\n\nline2"
        result = clean_content(text, [])
        assert "\n\n\n" not in result
        assert "line1\n\nline2" == result

    def test_strips_whitespace(self):
        result = clean_content("  text  ", [])
        assert result == "text"

    def test_empty_patterns(self):
        result = clean_content("unchanged", [])
        assert result == "unchanged"

    def test_empty_input(self):
        result = clean_content("", [])
        assert result == ""


# ---------------------------------------------------------------------------
# count_page_text_tokens
# ---------------------------------------------------------------------------

class TestCountPageTextTokens:
    def test_simple(self):
        assert count_page_text_tokens("one two three") == 3

    def test_empty(self):
        assert count_page_text_tokens("") == 0

    def test_whitespace_only(self):
        assert count_page_text_tokens("   \n\t  ") == 0

    def test_mixed_whitespace(self):
        assert count_page_text_tokens("a  b\tc\nd") == 4

    def test_single_word(self):
        assert count_page_text_tokens("hello") == 1


# ---------------------------------------------------------------------------
# yaml_safe
# ---------------------------------------------------------------------------

def test_yaml_safe_quotes_fullwidth_colon():
    assert yaml_safe("戰鬥：基礎") == '"戰鬥：基礎"'


def test_yaml_safe_plain_ascii_untouched():
    assert yaml_safe("Introduction") == "Introduction"


def test_yaml_safe_escapes_quotes_and_backslash():
    assert yaml_safe('a "b" \\c:') == '"a \\"b\\" \\\\c:"'
