---
name: film-engine
description: Taste-free engine for a code-rendered 3D film: one timeline drives an HTML UI texture (puppeteer), a canvas result sequence, a Blender 5 Cycles scene, a model check and synthesized sound. Use when building, debugging or extending a character-film project, or reusing its Blender, camera-solve or synth pieces.
---

# Film engine

The timeline and renderer layers of the studio. `character-film` runs the gates; this skill is the
machinery. The engine makes no taste decision: every colour, pose, shot, label and level is an argument
or a project file. The contract is [API.md](API.md): conventions, every public signature, the project
files, the build chain, the freshness rule and every CLI. Read its section 1 before you write code.

## Start a film

1. `npm run setup -- --film` prints `DOCTOR: ok` (it runs `scripts/doctor.py`; every FAIL line carries a
   fix hint after `→`; `npm run film:install` makes the venv). The film path is optional and heavy:
   Blender 5.x, a GPU Cycles supports, Python 3.10+, about 5 GB per film.
2. `npm run new-video -- <slug> --kind film ...` runs the doctor again, then copies
   [templates/project/](templates/project/README.md): a grey-box film that builds end to end as copied.
   Every `# TASTE:` line is a director decision.
3. From the project folder: `python -B build.py --upto check` (everything the GPU does not need), then
   `--from stills`. Each step refuses stale inputs and stamps its outputs with the timeline hash.

## The chain

`timeline` -> `ui` -> `comp` -> `sound` -> `blend` -> `check` -> `stills` -> `animatic` -> `final` ->
`encode` -> `verify`. One `timeline.py` holds the format, the layout in UI px, every event in seconds
and `state(t)`; Python readers import it, JS readers read `build/timeline.json`. The model check runs
in seconds on every edit; the stills step needs `VIOLATIONS: 0`; the final needs stills a person read.

## Rules of the contract

- `frame(t) = floor(t*fps + 0.5) + 1`; sequences are 1-based, 4 digits; every hit sits on a whole frame.
- Classify every UI element: STATIC (texture only), OBJECT (its own 3D piece UV-mapped to its rect),
  SCREEN (a per-frame plane over a rect the texture leaves one flat colour), SPRITE (its own PNG).
  Anything that visibly changes is not STATIC.
- The camera model is Blender's (36 mm sensor, horizontal fit); the checker and the solver share it.
  Pass the film size (`Format.film`) everywhere: a 9:16 cut is its own aspect, never a default.
- Spell every key of `LOOK`: an omitted key inherits a placeholder from the reference film.
- Python that Blender imports is standard library only; numpy, scipy, pedalboard and Pillow run in
  the kit `.venv`. Every entry sets `sys.dont_write_bytecode = True`. Engine JS is `.mjs`.
- Every path the engine writes goes through one fence (`render.safe_out` inside Blender,
  `filmkit.outpath.under` elsewhere): absolute and inside the project folder, or an error. gpu.py refuses
  any render whose path is relative, has no drive or sits at a drive root, before a pixel is written.
  The project path stays short (under about 240 characters in total).
- Tools: env `BLENDER` and `CHROME` win; otherwise the engine looks in the install folders of this OS,
  then on PATH (`filmkit/tools.py`, `tool-paths.mjs`). gpu.py picks the first Cycles kind with a device
  (OPTIX, CUDA, HIP, METAL, ONEAPI); `CYCLES_DEVICE=<kind>` forces one; `CYCLES_DEVICE=CPU` is the only
  CPU path and warns loudly.

## Who changes what

Engine code (this folder) belongs to the engineer model: it fixes bugs with a repro and a quick check
in `scripts/checks/`, and keeps API.md true. Project files belong to the design model. When a creative
choice needs an engine change, the request names the exact new argument; the default stays neutral.

## Checks

`python -B .claude/skills/film-engine/scripts/checks/run_checks.py --python .venv/Scripts/python.exe`
runs every quick check (Blender ones need the GPU). `npm test` covers the Node pieces in CI.
Before a change ships: both pass, and `npm run check` prints 0 errors.

## When it breaks

[references/gotchas.md](references/gotchas.md): Blender 5.2 API changes, colour under AgX, GPU timing,
tools on each OS, and the fixes already in the engine.
