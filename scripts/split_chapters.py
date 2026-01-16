#!/usr/bin/env python3
"""
章節拆分工具
根據設定檔將 Markdown 內容拆分成多個章節檔案

使用方式：
    # 產生範例設定檔
    python split_chapters.py --init

    # 根據設定檔拆分章節
    python split_chapters.py

    # 指定設定檔
    python split_chapters.py --config my_chapters.json

設定檔格式 (chapters.json)：
{
    "source": "data/markdown/rulebook_pages.md",
    "output_dir": "docs/src/content/docs",
    "chapters": {
        "rules": {
            "title": "核心規則",
            "files": {
                "index": {
                    "title": "規則總覽",
                    "description": "遊戲規則概述",
                    "pages": [1, 10]
                },
                "combat": {
                    "title": "戰鬥系統",
                    "description": "戰鬥規則說明",
                    "pages": [11, 30]
                }
            }
        }
    }
}
"""

import json
import re
import sys
from pathlib import Path


def load_config(config_path: Path) -> dict:
    """載入設定檔"""
    return json.loads(config_path.read_text(encoding="utf-8"))


def save_config(config: dict, config_path: Path):
    """儲存設定檔"""
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def create_example_config(config_path: Path):
    """建立範例設定檔"""
    example = {
        "source": "data/markdown/your_pdf_pages.md",
        "output_dir": "docs/src/content/docs",
        "clean_patterns": [
            r"\(Order #\d+\)",          # 移除訂單號
            r"Page \d+ of \d+",         # 移除頁碼標記
        ],
        "chapters": {
            "rules": {
                "title": "核心規則",
                "order": 1,
                "files": {
                    "index": {
                        "title": "規則總覽",
                        "description": "遊戲規則的基本概述",
                        "pages": [1, 10],
                        "order": 0
                    },
                    "basic-moves": {
                        "title": "基本動作",
                        "description": "角色可執行的基本動作",
                        "pages": [11, 20],
                        "order": 1
                    }
                }
            },
            "characters": {
                "title": "角色",
                "order": 2,
                "files": {
                    "index": {
                        "title": "角色創建",
                        "description": "如何創建角色",
                        "pages": [21, 40],
                        "order": 0
                    }
                }
            }
        }
    }
    save_config(example, config_path)
    print(f"✓ 已建立範例設定檔: {config_path}")
    print("\n請編輯設定檔，設定：")
    print("  - source: 來源 Markdown 檔案（使用 _pages.md 版本）")
    print("  - chapters: 章節結構與頁碼範圍")


def extract_pages(content: str) -> dict[int, str]:
    """從含頁碼標記的內容提取各頁"""
    pages = {}
    pattern = r"<!-- PAGE (\d+) -->\n\n(.*?)(?=<!-- PAGE \d+ -->|$)"

    for match in re.finditer(pattern, content, re.DOTALL):
        page_num = int(match.group(1))
        page_content = match.group(2).strip()
        pages[page_num] = page_content

    return pages


def get_page_range(pages: dict[int, str], start: int, end: int) -> str:
    """取得指定頁碼範圍的內容"""
    parts = []
    for page_num in range(start, end + 1):
        if page_num in pages:
            parts.append(pages[page_num])
    return "\n\n".join(parts)


def clean_content(text: str, patterns: list[str]) -> str:
    """清理內容"""
    for pattern in patterns:
        text = re.sub(pattern, "", text)
    # 移除多餘空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def generate_frontmatter(title: str, description: str = "", order: int | None = None) -> str:
    """生成 Starlight frontmatter"""
    lines = [
        "---",
        f"title: {title}",
    ]
    if description:
        lines.append(f"description: {description}")
    if order is not None:
        lines.append("sidebar:")
        lines.append(f"  order: {order}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def split_chapters(config: dict, project_root: Path):
    """根據設定拆分章節"""
    source_path = project_root / config["source"]
    output_dir = project_root / config["output_dir"]
    clean_patterns = config.get("clean_patterns", [])

    if not source_path.exists():
        print(f"❌ 找不到來源檔案: {source_path}")
        print("   請先執行 extract_pdf.py 提取 PDF")
        sys.exit(1)

    print(f"📖 來源檔案: {source_path}")
    content = source_path.read_text(encoding="utf-8")
    pages = extract_pages(content)
    print(f"   共 {len(pages)} 頁")
    print("-" * 50)

    total_files = 0
    for section_name, section_config in config["chapters"].items():
        section_dir = output_dir / section_name
        section_dir.mkdir(parents=True, exist_ok=True)

        section_title = section_config.get("title", section_name)
        print(f"\n📁 {section_title} ({section_name}/)")

        for filename, file_config in section_config["files"].items():
            title = file_config["title"]
            description = file_config.get("description", "")
            page_range = file_config["pages"]
            order = file_config.get("order")

            start_page, end_page = page_range
            section_content = get_page_range(pages, start_page, end_page)
            section_content = clean_content(section_content, clean_patterns)

            frontmatter = generate_frontmatter(title, description, order)
            full_content = frontmatter + "\n" + section_content

            output_path = section_dir / f"{filename}.md"
            output_path.write_text(full_content, encoding="utf-8")

            char_count = len(section_content)
            print(f"   ✓ {filename}.md - {title} (p.{start_page}-{end_page}, {char_count:,} 字)")
            total_files += 1

    print("-" * 50)
    print(f"✅ 完成！共產生 {total_files} 個檔案")


def main():
    project_root = Path(__file__).parent.parent
    default_config = project_root / "chapters.json"

    # 處理命令列參數
    if "--init" in sys.argv:
        create_example_config(default_config)
        return

    config_path = default_config
    if "--config" in sys.argv:
        idx = sys.argv.index("--config")
        if idx + 1 < len(sys.argv):
            config_path = Path(sys.argv[idx + 1])

    if not config_path.exists():
        print(f"❌ 找不到設定檔: {config_path}")
        print("   請先執行: python split_chapters.py --init")
        sys.exit(1)

    config = load_config(config_path)
    split_chapters(config, project_root)


if __name__ == "__main__":
    main()
