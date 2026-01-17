---
paths: docs/src/content/docs/**/*.md
---

# Markdown Format

## Frontmatter
```yaml
---
title: 頁面標題
description: SEO 描述（一句話）
sidebar:
  order: 0  # Lower = higher position
---
```

## Headings
- H1: Reserved for title (from frontmatter)
- H2: Main sections
- H3: Subsections
- Never skip levels (H2 → H4)

## Links
- Internal: `/rules/combat/` (absolute from docs root)
- Cross-reference: `[基本動作](/rules/basic-moves/)`
- Anchor: `[見下方](#section-name)`

## Images
- Path: `../../assets/image-name.jpg` (relative from .md)
- Alt text: Always provide descriptive alt
- Store in: `docs/src/assets/`

## Starlight Components
- Asides: `:::note[標題]`, `:::tip`, `:::caution`, `:::danger`
- Cards: Import from `@astrojs/starlight/components`
- Tabs: Use for alternative content views

## Tables
- Use for structured data, stats, quick reference
- Keep columns concise
- Align consistently
