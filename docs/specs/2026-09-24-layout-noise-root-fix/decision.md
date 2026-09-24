# Layout noise root fix

The published Kedamono Opera rules expose PDF furniture, duplicated image placements, printed navigation, lost heading structure, and untranslated navigation labels. The repair acts in the template and on a scratch copy of the translated project. The existing translated wording is the content source of truth; the English PDF is the layout source of truth.

| Question | Answer | Basis | Status |
|---|---|---|---|
| How are repeated images classified? | Use PDF geometry, image identity, and page context. Page ornaments are removed; D66 die faces become text indices; meaningful illustrations remain. | Dispatch contract and Kedamono PDF pages 71 and 154 | grounded |
| How are printed references mapped? | Resolve printed page numbers through chapter page ranges and the source PDF page offset, then emit base-aware site routes. | Dispatch contract and fix-ref skill | grounded |
| How are translated pages repaired? | Rewrite Markdown structure and generated navigation in place on a scratch copy; preserve translated prose. | Dispatch contract | grounded |
| What blocks publication? | A checker reports unresolved layout noise and invalid navigation before export. | Dispatch contract | grounded |

No open user-owned decision blocks implementation.
