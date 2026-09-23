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
    merge_list_continuation_at,
    merge_list_continuations,
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
