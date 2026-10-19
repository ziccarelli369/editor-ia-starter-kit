---
name: apply-style
description: Apply a reverse-engineered editing style from styles/ to a project. Use when the user names a style, says "con el estilo de", or project.json sets style. Loads the style's rules before the editing skill plans.
---

# Apply a style

A style is how the video is cut. A brand is how it looks. The style's rules
feed the plan; the brand's tokens stay as they are.

## 1. Find

List `styles/core/` then `styles/drafts/`. Match the user's words to a folder
name or a `summary` in `style.json`; ask when two match. A style that does not
exist is an offer to run `reverse-engineer-style`.

Record `"style": "<tier>/<slug>"` in `project.json`.

## 2. Load

Read in order: `SKILL.md` (rules), `style.json` (numbers), `ledger.md`.
In the ledger, `observed` rows are facts, `inferred` rows are hypotheses,
`unknown` rows are gaps. Tell the user when a rule they want rests on an
inferred row.

## 3. Carry into the plan

| style.json | Sets |
| --- | --- |
| `pacing.cut_median_s`, `pacing.cut_p90_s` | cut rhythm |
| `hook.first_cut_s`, `hook.text_on_screen_s` | the opening |
| `captions` | words per line, position, highlight |
| `transitions` | the allowed moves, this list only |
| `sound` | music presence, SFX density, where hits land |

Precedence: brief over brand, brand over style. Name each rule you dropped and
why.

Done when `plan.json` or `DESIGN.md` carries every row above.

## 4. Drafts

A `styles/drafts/` style has had one test render at most; say so. After the
project, offer promotion: `git mv styles/drafts/<slug> styles/core/<slug>`,
run by the user.
