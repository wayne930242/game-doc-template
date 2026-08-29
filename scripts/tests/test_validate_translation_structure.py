"""Public CLI tests for deterministic Markdown structure validation."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).parents[1] / "validate_translation_structure.py"


def run_validator(
    tmp_path: Path,
    source: str,
    draft: str,
    *,
    json_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    source_path = tmp_path / "source.md"
    draft_path = tmp_path / "draft.md"
    source_path.write_text(source, encoding="utf-8")
    draft_path.write_text(draft, encoding="utf-8")

    command = [sys.executable, str(SCRIPT), str(source_path), str(draft_path)]
    if json_output:
        command.append("--json")
    return subprocess.run(command, capture_output=True, text=True, check=False)


SOURCE_DOCUMENT = """---
title: Original title
description: Original description
sidebar:
  order: 2
tags:
  - rules
  - reference
---
import RuleCard from '../../../components/RuleCard.astro';

# First chapter

Introductory prose.

## Procedure

- Choose an action.
  - Apply one option.
- Resolve it.

1. Roll.
   1. Add modifiers.
2. Read the result.

| Roll | Result |
| --- | --- |
| 1 | Miss |
| 2 | Hit |

:::note[Remember]
Keep the fictional position clear.
:::

```python
print("source prose")
```

![Map](../../assets/map.webp)

<RuleCard title="Example" mode="compact">
  Original prose
</RuleCard>
"""


DRAFT_DOCUMENT = """---
title: 第一章
description: 本章說明
sidebar:
  order: 2
tags:
  - 規則
  - 參考
---
import RuleCard from '../../../components/RuleCard.astro';

# 第一章

這是翻譯後的引言。

## 流程

- 選擇一項行動。
  - 套用一個選項。
- 處理行動。

1. 擲骰。
   1. 加上調整值。
2. 查看結果。

| 骰值 | 結果 |
| --- | --- |
| 1 | 失敗 |
| 2 | 成功 |

:::note[提醒]
清楚交代角色當下的處境。
:::

```python
print("translated prose")
```

![地圖](../../assets/map.webp)

<RuleCard title="範例" mode="compact">
  翻譯後的文字
</RuleCard>
"""


def finding_kinds(payload: dict) -> set[str]:
    kinds: set[str] = set()
    for finding in payload["findings"]:
        for side in ("expected", "actual"):
            token = finding.get(side)
            if token:
                kinds.add(token["kind"])
    return kinds


def test_cli_accepts_equivalent_translated_block_shape(tmp_path):
    result = run_validator(tmp_path, SOURCE_DOCUMENT, DRAFT_DOCUMENT)

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["valid"] is True
    assert payload["finding_count"] == 0
    assert payload["findings"] == []


@pytest.mark.parametrize(
    ("changed_draft", "protected_kind"),
    [
        (DRAFT_DOCUMENT.replace("description: 本章說明\n", ""), "frontmatter"),
        (DRAFT_DOCUMENT.replace("## 流程", "### 流程"), "heading"),
        (DRAFT_DOCUMENT.replace("  - 套用一個選項。", "- 套用一個選項。"), "list_item"),
        (DRAFT_DOCUMENT.replace("1. 擲骰。", "- 擲骰。"), "list_item"),
        (DRAFT_DOCUMENT.replace("| 2 | 成功 |\n", ""), "table"),
        (DRAFT_DOCUMENT.replace("| 2 | 成功 |", "| 2 | 成功 | 額外 |"), "table"),
        (DRAFT_DOCUMENT.replace("```python", "```javascript"), "fence"),
        (DRAFT_DOCUMENT.replace(":::note[提醒]", ":::caution[提醒]"), "admonition_open"),
        (DRAFT_DOCUMENT.replace("../../assets/map.webp", "../../assets/other.webp"), "image"),
        (
            DRAFT_DOCUMENT.replace(
                "../../../components/RuleCard.astro",
                "../../../components/OtherCard.astro",
            ),
            "import",
        ),
        (DRAFT_DOCUMENT.replace("RuleCard", "OtherCard"), "mdx_open"),
    ],
)
def test_cli_rejects_each_protected_shape_change(
    tmp_path,
    changed_draft,
    protected_kind,
):
    result = run_validator(tmp_path, SOURCE_DOCUMENT, changed_draft)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["valid"] is False
    assert payload["finding_count"] >= 1
    assert protected_kind in finding_kinds(payload)


def test_cli_rejects_changed_major_block_order(tmp_path):
    draft = DRAFT_DOCUMENT.replace(
        "## 流程\n\n- 選擇一項行動。",
        "- 選擇一項行動。\n\n## 流程",
    )

    result = run_validator(tmp_path, SOURCE_DOCUMENT, draft)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["valid"] is False
    assert payload["findings"]


def test_empty_frontmatter_is_still_a_protected_block(tmp_path):
    result = run_validator(tmp_path, "---\n---\n# Title\n", "# 標題\n")

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert "frontmatter" in finding_kinds(payload)


def test_multiline_import_and_mdx_formatting_may_differ(tmp_path):
    source = """import {
  RuleCard,
  RuleTable,
} from '../../../components/rules';

<RuleCard
  title="Original title"
  compact
>
  Original prose
</RuleCard>
"""
    draft = """import { RuleCard, RuleTable } from '../../../components/rules';

<RuleCard title="翻譯標題" compact>
  翻譯後的文字
</RuleCard>
"""

    result = run_validator(tmp_path, source, draft)

    assert result.returncode == 0, result.stdout


def test_multiline_mdx_component_name_change_is_rejected(tmp_path):
    source = """<RuleCard
  title="Original"
>
  Prose
</RuleCard>
"""
    draft = """<OtherCard
  title="翻譯"
>
  文字
</OtherCard>
"""

    result = run_validator(tmp_path, source, draft)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert "mdx_open" in finding_kinds(payload)


def test_human_output_identifies_expected_and_actual_blocks(tmp_path):
    result = run_validator(
        tmp_path,
        "# Title\n\n## Section\n",
        "# 標題\n\n### 小節\n",
        json_output=False,
    )

    assert result.returncode == 1
    assert "Markdown structure mismatch" in result.stdout
    assert "heading(level=2)" in result.stdout
    assert "heading(level=3)" in result.stdout
    assert "source.md:3" in result.stdout
    assert "draft.md:3" in result.stdout


def test_missing_input_returns_machine_readable_error(tmp_path):
    missing = tmp_path / "missing.md"
    draft = tmp_path / "draft.md"
    draft.write_text("# 標題\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(missing), str(draft), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["valid"] is False
    assert payload["error"]["code"] == "file_not_found"
    assert str(missing) in payload["error"]["message"]
