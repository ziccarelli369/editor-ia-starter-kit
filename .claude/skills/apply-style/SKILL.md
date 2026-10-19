---
name: apply-style
description: Apply a reverse-engineered editing style from styles/core or styles/drafts to the current project. Use when the user names a style, says "edítalo como", "con el estilo de", or project.json has a style set. Loads the style's rules before any editing skill runs.
---

# Apply a style

A style is "how it is cut": pacing, hook timing, caption behavior, transitions,
sound. A brand is "what it looks like". The style never overrides brand tokens.

## 1. Find it

List `styles/core/` then `styles/drafts/`. Match the user's words to a folder
name or to the `summary` in its `style.json`. If more than one matches, ask.
If the user asks for a style that does not exist, offer `reverse-engineer-style`.

Record the choice in `project.json` as `"style": "<tier>/<slug>"`.

## 2. Load it

Read, in this order:

1. `styles/<tier>/<slug>/SKILL.md`: the rules.
2. `styles/<tier>/<slug>/style.json`: the measured numbers.
3. `styles/<tier>/<slug>/ledger.md`: only the rows marked `observed`. Rows marked
   `inferred` are hypotheses; `unknown` rows are gaps. Say so if a rule the user
   wants depends on an inferred row.

## 3. Use it

Carry the rules into the editing skill's plan (`plan.json`, `DESIGN.md`):

- `pacing.cut_median_s` and `pacing.cut_p90_s` set the cut rhythm.
- `hook.first_cut_s` and `hook.text_on_screen_s` set the opening.
- `captions` sets words per line, position and highlight behavior.
- `transitions` lists the allowed moves. Use nothing outside the list.
- `sound` sets music presence, SFX density and where hits land.

Where the style and the brand conflict (a font, a color), the brand wins.
Where the style and the user's brief conflict, the brief wins. Say which rule
you dropped and why.

## 4. Drafts

A style from `styles/drafts/` has had one test render at most. Tell the user it
is a draft. After the project, ask whether to promote it:
`git mv styles/drafts/<slug> styles/core/<slug>`.
