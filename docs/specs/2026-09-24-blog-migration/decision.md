# Blog migration decisions

Outcome: one repeatable migration command for existing translation sites, with three scratch-copy proofs. The book owner and dispatched worker own this scope. The existing translated pages, components, and custom styles remain the content authority.

| Question | Answer | Basis | Status |
|---|---|---|---|
| Where are book exports served? | `/books/<slug>/` on the blog. | Dispatch contract | grounded |
| What changes in a legacy checkout? | Build/search dependencies, export tooling, workflow, deployment metadata, and Astro base/title. Existing pages, components, sidebar, and styles remain in place. | Dispatch contract and site inspection | grounded |
| How are old root URLs handled? | Rebase local root URLs in generated HTML/CSS during the site build, with a root build as a no-op. | Dispatch contract | grounded |
| How are missing metadata fields filled? | Use recorded site/project metadata and explicit source text. Report unresolved values; require a supplied translator credit when absent. Hong Wei is confirmed for the three proof sites. | Dispatch contract, three-site inspection, and main-agent relay of user decision | confirmed |
| How is progress represented without a tracker? | `null` in `book.json`. | Dispatch contract | grounded |
| What is the proof boundary? | Scratch copies only; export/build/browser comparison against live sites; Kedamono regression. | Dispatch contract | grounded |

No consequential user-owned decision is open. The authorization to begin the contract task approves this bounded contract.
