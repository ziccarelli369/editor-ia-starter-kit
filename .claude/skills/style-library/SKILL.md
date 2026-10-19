---
name: style-library
description: Style library of reusable motion-graphics cards and scene templates. Use when choosing a visual style, reusing a card or template in a HyperFrames video, adding a card, or building a new style pack.
---

# Style Library

## Reuse a card

1. Read `style-library/GUIDE.md`, then `style-library/registry.json`. Filter by
   style, tier and purpose before you open a card.
2. Read the chosen style's `DESIGN.md`, `tokens.css` and the manifest's slot
   limits.
3. Copy the card into the video's `compositions/` together with its relative
   dependencies: CSS, fonts and the GSAP file. Localize each path.
4. Fill its named `data-slot` values and wire its timing with the `hyperframes`
   skill. An overlay keeps the area outside the card transparent and clear of
   the speaker's face; a takeover gets an opaque background.
5. Treat every card as a draft until you have checked it: lint and render it at
   the project's resolution, look at its hero frame and its transition, and fill
   each slot with text at its maximum length.

**Bound:** every dependency path resolves inside the project, and the hero
frame, the transition and the maximum-length slots look right in a render.

## Start from a scene template

Use `style-templates/` for a whole-scene starting point. Read the template's
README before rendering; a media template may need the user's own
`assets/source.mp4`.

## Add a style or a card

1. Run `node scripts/style-library/new-style.mjs 03 my-style "My Style"`.
2. Complete the style's design tokens, manifest and cards. Keep copy for one
   project in that project; library cards stay generic.
3. After any manifest change, run `node scripts/style-library/build-registry.mjs`.

**Bound:** `npm run check` reports 0 errors, so every registry card and slot
resolves.
