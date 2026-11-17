## 6. Antigravity

**Seeing.** You judge picture from image files. Make them with ffmpeg
(a frame, a contact sheet, a strip across a cut) and open each one. When your
file tools cannot show an image, serve the folder with
`npx hyperframes preview` and look in the browser. State in `VERIFY.md` which
way you looked.

**Action footage with no speech** (training clips, sparring, a match). Route to
`short-form-edit` and change three steps:

- Step 1: skip the transcript. Probe every clip and build one contact sheet
  per clip.
- Step 4: there is no speech to cut. Pick the strongest 0.5 to 2.5 s of each
  clip by its visible action and its result. Save the picks as `edl.json`.
- Step 8: the cut follows the beat grid of the music track
  (`music-grid.mjs`). With an empty `music/`, ask the user for a track before
  the animatic; the clips' own sound is the fallback, and you say so.

Captions are on-screen text you write, so the text board gate applies.

**Text gate.** `.agents/hooks.json` blocks a write that adds on-screen text
before `text-board/text-board.json` is complete. `scripts/preflight.mjs` and
`scripts/deliver.mjs` run the same check, so the gate holds with the hook off.

**Commands.** Run every command from the kit root. On a permission prompt for
`node`, `npm`, `npx` or `ffmpeg`, tell the user these four are the kit's tools.
