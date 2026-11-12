# Text board

Any on-screen text in a project needs a text board first: hook lines, labels,
countdowns, captions, CTAs. A rough preview counts. One ad-hoc line is a guess;
a board is a choice.

`.claude/hooks/text-gate.mjs` blocks any write that adds new on-screen text. `scripts/preflight.mjs` and
`scripts/deliver.mjs` block the render, the staged review and the promote. All three run
`scripts/lib/text-gate.mjs`.

## Build it

1. Read the text skills: [typography](../../hyperframes/references/typography.md),
   [captions](../../hyperframes/references/captions.md),
   [opening](opening.md), and the [style library](../../style-library/SKILL.md).
   Read the brand's `DESIGN.md` for fonts and colors.
2. Make at least 3 options. Each option is a different treatment, not the same
   look with new words: a label, a countdown, a serif line, a native caption,
   one giant word, an eye-direction cue.
3. Render every option on the real frame where the text will sit. Put the
   prototypes and one board image in `video-projects/<id>/text-board/`. Files
   in that folder are free to write.
4. Show the board to the user. Give your scores and your pick. The user decides.
5. Write `text-board/text-board.json`, then build the chosen text.

## text-board.json

```json
{
  "board": "board.png",
  "options": [
    { "id": "hud", "treatment": "tracking label", "text": "TRIANGLE // LOCKED", "source": ".claude/skills/hyperframes/references/typography.md" },
    { "id": "countdown", "treatment": "countdown, no words", "text": "0:03 UNTIL TAP", "source": ".claude/skills/short-form-edit/references/opening.md" },
    { "id": "serif", "treatment": "editorial serif", "text": "he had three seconds left.", "source": ".claude/skills/style-library/SKILL.md" }
  ],
  "pick": "countdown"
}
```

- `board`: the image, relative to `text-board/`.
- `options`: 3 or more, each with its own `id` and its own `treatment`.
- `source`: the kit file the option came from, under `.claude/skills/`,
  `style-library/` or `styles/`. The gate checks that the file exists.
- `pick`: the `id` the user chose.

The gate sees text in project source files: visible HTML text, `textContent`,
`innerText`, `innerHTML`, canvas `fillText`, and ffmpeg `drawtext` or
`subtitles=`. It skips `assets/`, `audio/`, `renders/`, `work/` and
`text-board/`. A character film (`kind: film`) is exempt: its brief owns the
UI text.
