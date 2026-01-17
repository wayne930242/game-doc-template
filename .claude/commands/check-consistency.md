---
name: check-consistency
description: 一致性校對 - 檢查術語使用是否一致
arguments:
  - name: scope
    description: 檢查範圍（all/section-name）
    required: false
---

# Check Terminology Consistency

Use `terminology-management` skill.

## Process

### 1. Load References

Read `glossary.json` for approved terms.

### 2. Scan Documents

Scope: `$ARGUMENTS` or all files in `docs/src/content/docs/**/*.md`

For each file:
- Extract English terms (capitalized, quoted)
- Find Chinese translations used
- Compare against glossary

### 3. Generate Report

Report format:

```markdown
## Consistency Report

### Missing from Glossary
- `Term` (files: path:line, path:line)

### Inconsistent Usage
- `Term`: "翻譯A" (3x), "翻譯B" (2x)
  - path:line uses "翻譯A"
  - path:line uses "翻譯B"

### Untranslated Terms
- "English" in path:line
```

### 4. Fix Issues

For each issue, ask user:
1. **Missing**: Add to glossary?
2. **Inconsistent**: Which translation to use?
3. **Untranslated**: Provide translation?

Apply fixes with batch replace.

### 5. Verify

Re-run scan to confirm all issues resolved.

## Example Usage

```
/check-consistency
/check-consistency rules
```
