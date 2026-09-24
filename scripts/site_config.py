"""Deployment path and Astro config updates shared by navigation and export."""

from __future__ import annotations

import re
import sys

SUBPATH_TARGETS = ("blog", "github-pages")


def deployment_base_path(style: dict) -> str:
    deployment = style.get("deployment", {})
    if deployment.get("target") not in SUBPATH_TARGETS:
        return ""
    base_path = (deployment.get("base_path", "") or "").rstrip("/")
    if base_path and not base_path.startswith("/"):
        base_path = f"/{base_path}"
    return base_path


SITE_BASE_PATTERN = re.compile(
    r"(export default defineConfig\(\{\n)(\tsite: '[^']*',\n)?(\tbase: '[^']*',\n)?",
)


def _github_pages_site_url(repo_url: str) -> str:
    match = re.search(r"github\.com[:/]([^/]+)/", repo_url)
    username = match.group(1) if match else "<github-username>"
    return f"https://{username}.github.io"


def update_astro_site_base(config_text: str, style: dict) -> str:
    deployment = style.get("deployment", {})
    target = deployment.get("target")
    if target in SUBPATH_TARGETS:
        base_path = deployment_base_path(style)
        if not base_path:
            print(f"⚠ deployment.target={target} 但 base_path 未設定，略過 site/base 寫入", file=sys.stderr)
            return config_text
        replacement = f"\\1\tbase: '{base_path}',\n"
        if target == "github-pages":
            repo_url = style.get("repository", {}).get("url", "")
            replacement = f"\\1\tsite: '{_github_pages_site_url(repo_url)}',\n\tbase: '{base_path}',\n"
    else:
        replacement = r"\1"
    return SITE_BASE_PATTERN.sub(replacement, config_text, count=1)


SITE_TITLE_PATTERN = re.compile(
    r"^(?P<lead>[\t ]*title:\s*)(?P<quote>['\"])(?:[^\\\n]|\\.)*?(?P=quote),$",
    re.MULTILINE,
)


def update_astro_site_title(config_text: str, style: dict) -> str:
    title = style.get("site", {}).get("title")
    if not title:
        return config_text
    def replace(match: re.Match[str]) -> str:
        quote = match["quote"]
        literal = title.replace("\\", "\\\\").replace(quote, f"\\{quote}")
        return f"{match['lead']}{quote}{literal}{quote},"

    return SITE_TITLE_PATTERN.sub(replace, config_text, count=1)
