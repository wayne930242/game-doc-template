from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

import _style_decisions_lib as sdl
import style_decisions as sd
import validate_style_decisions as vsd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = PROJECT_ROOT / "style-decisions.schema.json"


def _seed_style(style_path: Path) -> None:
    sdl.save_style_decisions(
        style_path,
        sdl.default_style_decisions_payload(),
        schema_path=SCHEMA_PATH,
    )


def test_cmd_init_creates_default_file(tmp_path):
    style_path = tmp_path / "style-decisions.json"
    args = argparse.Namespace(
        style=style_path,
        schema=SCHEMA_PATH,
        force=False,
        description="測試 style decisions",
    )

    sd.cmd_init(args)

    payload = json.loads(style_path.read_text(encoding="utf-8"))
    assert payload["_meta"]["description"] == "測試 style decisions"
    assert payload["translation_mode"]["mode"] == "full"


def test_cmd_set_document_format_for_document(tmp_path):
    style_path = tmp_path / "style-decisions.json"
    _seed_style(style_path)

    args = argparse.Namespace(
        style=style_path,
        schema=SCHEMA_PATH,
        document_key="Household_1.2",
        layout_profile="double-column",
        page_text_engine="markitdown",
        pymupdf_sort_text=None,
        watermarks=None,
        symbol_glyphs=None,
        aside_note=None,
        aside_tip=None,
        aside_caution=None,
        aside_danger=None,
        cards_usage=None,
        tabs_usage=None,
        tables_convention=None,
        dice_tables_convention=None,
    )
    sd.cmd_set_document_format(args)

    payload = json.loads(style_path.read_text(encoding="utf-8"))
    entry = payload["document_format"]["documents"]["Household_1.2"]
    assert entry["layout_profile"] == "double-column"
    assert entry["page_text_engine"] == "markitdown"


def test_cmd_add_translation_note_upserts_by_key(tmp_path):
    style_path = tmp_path / "style-decisions.json"
    _seed_style(style_path)

    def make(note: str) -> argparse.Namespace:
        return argparse.Namespace(
            style=style_path,
            schema=SCHEMA_PATH,
            document_key=None,
            key="tone",
            topic="語氣",
            note=note,
        )

    sd.cmd_add_translation_note(make("保持冷靜、正式。"))
    sd.cmd_add_translation_note(make("保持冷靜、正式，避免過度口語。"))

    payload = json.loads(style_path.read_text(encoding="utf-8"))
    notes = payload["translation_notes"]["global"]
    assert len(notes) == 1
    assert notes[0]["note"] == "保持冷靜、正式，避免過度口語。"


def test_cmd_set_translation_mode_bilingual(tmp_path):
    style_path = tmp_path / "style-decisions.json"
    _seed_style(style_path)

    args = argparse.Namespace(
        style=style_path,
        schema=SCHEMA_PATH,
        mode="bilingual",
        reason="test",
    )
    sd.cmd_set_translation_mode(args)

    payload = json.loads(style_path.read_text(encoding="utf-8"))
    assert payload["translation_mode"]["mode"] == "bilingual"
    assert payload["translation_mode"]["reason"] == "test"


def test_cmd_set_theme_persists_all_fields(tmp_path):
    style_path = tmp_path / "style-decisions.json"
    _seed_style(style_path)

    args = argparse.Namespace(
        style=style_path,
        schema=SCHEMA_PATH,
        mode="dark-forced",
        overlay="0",
        palette="冷色系：primary=217 藍、secondary=180 青",
        bg_h="268",
        bg_l="14%",
    )
    sd.cmd_set_theme(args)

    payload = json.loads(style_path.read_text(encoding="utf-8"))
    theme = payload["theme"]
    assert theme["mode"] == "dark-forced"
    assert theme["overlay"] == "0"
    assert theme["bg_h"] == "268"
    assert theme["bg_l"] == "14%"
    assert theme["palette"].startswith("冷色系")


def test_cmd_set_deployment_records_blog_base_path(tmp_path):
    style_path = tmp_path / "style-decisions.json"
    _seed_style(style_path)

    sd.cmd_set_deployment(
        argparse.Namespace(style=style_path, schema=SCHEMA_PATH, target="blog", base_path="/books/kedamono-opera")
    )
    sd.cmd_set_site(
        argparse.Namespace(
            style=style_path,
            schema=SCHEMA_PATH,
            title="暗獸歌劇",
            original_title="Kedamono Opera",
            description=None,
            tagline=None,
            intro=None,
        )
    )

    payload = json.loads(style_path.read_text(encoding="utf-8"))
    assert payload["deployment"] == {"target": "blog", "base_path": "/books/kedamono-opera"}
    assert payload["site"] == {"title": "暗獸歌劇", "original_title": "Kedamono Opera"}


def test_cmd_set_credits_records_acknowledgements_separately(tmp_path):
    style_path = tmp_path / "style-decisions.json"
    _seed_style(style_path)
    parser = sd.build_parser()

    args = parser.parse_args(
        [
            "--style", str(style_path),
            "--schema", str(SCHEMA_PATH),
            "set-credits",
            "--entry", "翻譯:譯者甲",
            "--acknowledgement", "Reference Author: 參考了先前的社群翻譯",
            "--show-on-homepage", "true",
        ]
    )
    args.func(args)

    credits = json.loads(style_path.read_text(encoding="utf-8"))["credits"]
    assert credits == {
        "entries": [{"role": "翻譯", "name": "譯者甲"}],
        "acknowledgements": [{"name": "Reference Author", "note": "參考了先前的社群翻譯"}],
        "show_on_homepage": True,
    }


@pytest.mark.parametrize("value", ["沒有冒號", ":只有說明", "只有名稱:"])
def test_parse_acknowledgement_rejects_incomplete(value):
    with pytest.raises(argparse.ArgumentTypeError):
        sd.parse_acknowledgement(value)


def test_schema_rejects_acknowledgement_without_note():
    payload = sdl.default_style_decisions_payload()
    payload["credits"] = {"acknowledgements": [{"name": "Reference Author"}]}
    schema = sdl.load_style_decisions_schema(SCHEMA_PATH)

    errors = sdl.validate_style_decisions_payload(payload, schema)

    assert any("note" in error for error in errors)


def test_cmd_set_theme_merges_without_dropping_existing(tmp_path):
    style_path = tmp_path / "style-decisions.json"
    _seed_style(style_path)

    first = argparse.Namespace(
        style=style_path,
        schema=SCHEMA_PATH,
        mode="dark-forced",
        overlay=None,
        palette=None,
        bg_h=None,
        bg_l=None,
    )
    sd.cmd_set_theme(first)

    second = argparse.Namespace(
        style=style_path,
        schema=SCHEMA_PATH,
        mode=None,
        overlay=None,
        palette=None,
        bg_h=None,
        bg_l="16%",
    )
    sd.cmd_set_theme(second)

    theme = json.loads(style_path.read_text(encoding="utf-8"))["theme"]
    assert theme["mode"] == "dark-forced"
    assert theme["bg_l"] == "16%"


def test_cmd_set_theme_requires_at_least_one_field(tmp_path):
    style_path = tmp_path / "style-decisions.json"
    _seed_style(style_path)

    args = argparse.Namespace(
        style=style_path,
        schema=SCHEMA_PATH,
        mode=None,
        overlay=None,
        palette=None,
        bg_h=None,
        bg_l=None,
    )
    with pytest.raises(SystemExit):
        sd.cmd_set_theme(args)


@pytest.mark.parametrize("value", ["-0.1", "1.5", "abc"])
def test_parse_overlay_rejects_out_of_range(value):
    with pytest.raises(argparse.ArgumentTypeError):
        sd.parse_overlay(value)


def test_parse_overlay_accepts_bounds():
    assert sd.parse_overlay("0") == "0"
    assert sd.parse_overlay("0.7") == "0.7"
    assert sd.parse_overlay("1") == "1"


@pytest.mark.parametrize("value", ["-1", "361", "abc"])
def test_parse_hue_rejects_out_of_range(value):
    with pytest.raises(argparse.ArgumentTypeError):
        sd.parse_hue(value)


def test_parse_hue_accepts_bounds():
    assert sd.parse_hue("0") == "0"
    assert sd.parse_hue("360") == "360"


@pytest.mark.parametrize("value", ["-1%", "101%", "abc", "%"])
def test_parse_lightness_rejects_invalid(value):
    with pytest.raises(argparse.ArgumentTypeError):
        sd.parse_lightness(value)


def test_parse_lightness_normalizes_to_percent():
    assert sd.parse_lightness("6") == "6%"
    assert sd.parse_lightness("14%") == "14%"
    assert sd.parse_lightness(" 16 % ") == "16%"


def test_validate_style_decisions_reports_invalid_payload(monkeypatch, tmp_path):
    style_path = tmp_path / "style-decisions.json"
    style_path.write_text(
        json.dumps(
            {"_meta": {"description": "x", "updated": ""}, "repository": {"visibility": "internal"}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    args = argparse.Namespace(style=style_path, schema=SCHEMA_PATH)
    monkeypatch.setattr(vsd, "parse_args", lambda: args)

    with pytest.raises(SystemExit):
        vsd.main()


def test_validate_style_decisions_accepts_default_payload(monkeypatch, tmp_path):
    style_path = tmp_path / "style-decisions.json"
    _seed_style(style_path)

    args = argparse.Namespace(style=style_path, schema=SCHEMA_PATH)
    monkeypatch.setattr(vsd, "parse_args", lambda: args)

    vsd.main()


@pytest.mark.parametrize("language", ["ja", "en", "zh-Hant", "none"])
def test_set_term_gloss_records_language(tmp_path, language):
    style_path = tmp_path / "style-decisions.json"
    _seed_style(style_path)

    args = sd.build_parser().parse_args(
        ["--style", str(style_path), "--schema", str(SCHEMA_PATH), "set-term-gloss", "--language", language]
    )
    args.func(args)

    payload = json.loads(style_path.read_text(encoding="utf-8"))
    assert payload["translation"]["term_gloss"] == language
    assert payload["translation_mode"]["mode"] == "full"


@pytest.mark.parametrize("language", ["Japanese", "", "JA", "source"])
def test_set_term_gloss_rejects_non_language_values(tmp_path, language):
    style_path = tmp_path / "style-decisions.json"
    _seed_style(style_path)

    args = sd.build_parser().parse_args(
        ["--style", str(style_path), "--schema", str(SCHEMA_PATH), "set-term-gloss", "--language", language]
    )
    with pytest.raises(ValueError, match="translation.term_gloss"):
        args.func(args)


def test_set_term_gloss_requires_language():
    with pytest.raises(SystemExit):
        sd.build_parser().parse_args(["set-term-gloss"])


def test_schema_rejects_unknown_translation_field():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    payload = {"_meta": {"description": "x", "updated": ""}, "translation": {"gloss": "ja"}}

    errors = sdl.validate_style_decisions_payload(payload, schema)

    assert errors
