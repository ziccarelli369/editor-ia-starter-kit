# Styles

Editing styles reverse-engineered from reference videos. A style is "how it is
cut"; a brand is "what it looks like". Any brand can use any style.

- `drafts/`: created by the `reverse-engineer-style` skill. Tested at most once.
- `core/`: the ones you trust. Promote by hand: `git mv styles/drafts/<slug> styles/core/<slug>`.

Each style folder holds `SKILL.md` (the rules), `style.json` (the numbers),
`ledger.md` (every claim marked observed / inferred / unknown) and `analysis/`.
Use a style with the `apply-style` skill.
