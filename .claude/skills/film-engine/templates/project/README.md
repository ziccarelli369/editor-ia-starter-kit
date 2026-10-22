# Film project scaffold

Copy this folder into `video-projects/<id>/` (next to the project's `project.json`) and edit the
lines marked `# TASTE:`. The engine lives in `.claude/skills/film-engine/scripts` (env `FILM_ENGINE`
overrides it). As copied, the scaffold builds a 2.0 s grey-box film: two panels, two buttons, a
counter on the viewer, a grey toy that hops onto button A at 0.5 s and button B at 1.0 s, two clicks.

| File | Owns | TASTE slots |
| --- | --- | --- |
| `timeline.py` | format, layout, z stack, the beat sheet, events, state(t), EXTRA | fps, bpm, sizes, rects, JUMPS, theme |
| `hero_spec.py` | the hero as data | every part, pivot, expression, slide |
| `motion.py` | hero choreography: arcs, poses, tile presses, landings | styles, press response, facing, expressions |
| `shots.py` | the camera: holds, crossings, shakes, aperture | heading, elevation, lens, margins, crossing kinds |
| `look.py` | LOOK and REGISTRY: presets, lights, materials, world, cyc, bloom, mask classes | every value |
| `ui_build.py` | the app page (UI texture) | palette, font, labels |
| `comp.html`, `comp.js` | the result the viewer plays, per frame | palette, type, motion |
| `score.py` | sound handlers, music bed, mastering | every patch and level |
| `checks_config.py` | the thresholds the model check enforces | every number |
| `build.json` | mechanical knobs: stills frames, mask, crf, encode preset, animatic samples, UI font, points hook | none |
| `scene.py`, `sound.py`, `check_model.py`, `build.py` | mechanical entries into the engine | none |
| `film.json` | written by `new-video --kind film --size WxH --fps N`; `timeline.py` reads its width, height and fps; build-only (deliver rewrites `project.json`) | none |

Build (from the project folder; each step refuses to run on stale inputs and stamps its outputs):

```
python -B build.py                      # the whole chain: timeline ui comp sound blend check stills animatic final encode verify
                                        # (+ check_9x16 stills_9x16 final_9x16 encode_9x16 verify_9x16 with a build.json stills_9x16 list)
python -B build.py --upto check         # everything the GPU does not need
python -B build.py --from stills        # the render side
python -B build.py --only sound --force # one step, freshness gate off
```

Outputs: `build/` (timeline.json, ui*.png, comp/####.png, sound.wav + report, film.blend, model_report.txt,
previs.svg) and `renders/` (stills + masks + stills.json, animatic/ + animatic.mp4 + strips, frames/,
`<slug>.mp4`, verify.json). Every output stays inside this folder: the engine refuses a path outside it,
a relative path handed to Blender or one at a drive root (Blender would write there). Keep the project
path short: Blender fails past about 240 characters.
The render presets in `look.py` are tiny placeholders (25 %, 4-8 samples); a real film sets its own.

Tools: env `BLENDER`, `CHROME`, `NODE`, `FILM_PYTHON` win; otherwise the engine looks in the install
folders of this OS, then on PATH. `CYCLES_DEVICE` picks the Cycles kind (default: the first of OPTIX,
CUDA, HIP, METAL, ONEAPI with a device; `CPU` is the explicit, slow opt-in). `npm run setup -- --film`
says what is missing.
