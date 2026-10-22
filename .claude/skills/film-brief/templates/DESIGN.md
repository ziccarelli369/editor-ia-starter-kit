# <TITLE>: director brief

<Format line: duration, aspect(s), size, fps, BPM, beats, frames.>
`timeline.py` holds every number. When this file and `timeline.py` disagree,
`timeline.py` wins. Change a number in `timeline.py` only.

## SOURCES

- <Each source the user gave, and what it supplies.>

## ONE SENTENCE

<The one thing the viewer remembers.>

## TAGLINE

<The on-screen line, if any.>

## BRAND

- **HERO:** <toy shape, size in cm (wide x tall x deep), parts and joints,
  materials, colours in hex, what reads at a glance, what changes over the film>
- **APP:** <the program-style workspace: every panel and its state, the tools
  the hero uses, real labels, no logos>
- **RESULT:** <what the hero builds, in the order it accumulates>
- **SET:** <the world around the slabs and the light sources that justify the look>

## REFERENCE ANALYSIS

Palette: <hex values> · Type: <family, width, weight, scale> · Composition:
<where the eye goes first> · Pacing: <time between meaningful changes> ·
Motion: <per object class> · Texture: <grain, glass, none>

DO NOT COPY: <subjects, logos, copy, imagery of the reference>

## FACTS AND CHOICES

- Facts (never invented; missing = ask): <real labels, real subject rules,
  real assets>
- Choices (the director decides): <camera, timing, style>

## BEATS (seconds; frame = floor(t x fps + 0.5) + 1)

| Time | Frames | Picture | RESULT change | Subject move or ritual | Sound |
| --- | --- | --- | --- | --- | --- |
| <0-1.5> | <1-46> | <...> | <...> | <...> | <...> |

Every row changes the RESULT, or it is the setup or the payoff.

## CAMERA

<Shot plan. A still hold at every hit (2 frames before to 2 after); the result
in frame with the hero at every press; how the big impacts are shot.>

## LOOK

<Palette, materials, the light rig, exposure, bloom, motion blur.>

## SOUND

<Copy-ready synth prompt: the bed, one sound per hit, the master. Loudness
contour per half second.>

## VERTICAL (9:16)

<What changes: fewer elements, stronger vertical hierarchy, its own holds.>

## RULINGS

Thresholds the checker enforces (`checks_config.py` mirrors these numbers):

- Hero width, measured on the silhouette: >= <x> % of the frame width at
  presses, >= <y> % elsewhere, >= <z> % in big leaps.
- Hero margin to the frame edge: >= 5 % on every frame.
- At every press, each result text box is 100 % in frame with >= 2 % margin.
- <Director's rulings added during the rounds, each with its date and reason.>

## CHECKS

UI texture and its contract, the result contact sheet, the model check, the
feasibility what-if per press, 18 half-res stills with masks, the animatic
with sound, the sound check, then the final.

## DO NOT

- <Clichés to avoid.>
- <Wrong facts about the subject.>
- <Legal risks: real names, real logos, real likenesses.>

## FILES

| File | Owner | Writes |
| --- | --- | --- |
| `timeline.py`, `checks_config.py`, `DESIGN.md`, `VERIFY.md` | director | `build/timeline.json` |
| `ui_build.py` | UI | `build/ui*.png` |
| `comp.html`, `comp.js` | result | `build/comp/####.png` |
| `hero_spec.py`, `look.py` | hero and look | `renders/lookdev/` |
| `motion.py` | motion | |
| `shots.py` | camera | `build/model_report.txt` (via build.py) |
| `score.py` | sound | `build/sound.wav` |
| `scene.py` | integrator | `build/*.blend`, `renders/`, `reviews/` |
