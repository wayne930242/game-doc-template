---
name: check-completeness
description: 缺漏校對 - 檢查規則完整性
arguments:
  - name: section
    description: 檢查特定章節（可選）
    required: false
---

# Check Completeness

Use `pdf-translation` skill for reference.

## Process

### 1. Load Source

Read original `data/markdown/<name>_pages.md` with page markers.

### 2. Compare Structure

For scope `$ARGUMENTS` or all sections:

| Check | Method |
|-------|--------|
| Page coverage | Verify all pages in chapters.json are extracted |
| Section headers | Compare H2/H3 count with original |
| Tables | Count tables in source vs output |
| Lists | Verify bullet/numbered lists preserved |

### 3. Content Verification

- **Rules coverage**: List all game rules mentioned, verify each is documented
- **Cross-references**: Check internal links resolve
- **Examples**: Verify examples are translated completely

### 4. Generate Report

```markdown
## Completeness Report

### Missing Content
- Pages 45-47 not in any chapter
- Section "Advanced Combat" header missing

### Incomplete Sections
- rules/combat.md: 2 tables in source, 1 in output
- characters/index.md: example block truncated

### Broken References
- [無效連結](/path/) in file.md:15
```

### 5. Fix Issues

For each issue:
1. Show original content from source
2. Ask user how to handle
3. Add missing content or update chapters.json

### 6. Re-verify

Run check again to confirm completeness.

## Example Usage

```
/check-completeness
/check-completeness rules
/check-completeness characters
```
