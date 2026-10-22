# film-engine API

The engine for a 3D character film: a toy hero hops across a giant software UI lying flat like a glowing
desk; every hop changes a 2D result playing on the app's viewer; the app falls away at the end. Blender
5.2 Cycles renders it; an HTML page screenshotted by puppeteer becomes the UI texture; a canvas page
drawn per frame is the result; sound is synthesized in Python; ONE timeline drives every reader.

The engine makes no taste decision. Every colour, level, choreography value, camera choice and layout
number is a function argument or lives in a project file the director writes. Engine defaults are
neutral placeholders and say so. A director never edits engine code to make a creative choice.

This file is the contract as built and proven by the grey-box film (`templates/project`, every step of
the chain run end to end). Section 7 describes that scaffold.

## 1. Conventions (fixed)

- frame(t) = floor(t*fps + 0.5) + 1 (never Python round()); time(f) = (f-1)/fps; image sequences are
  1-based, 4 digits, 0001.png = t 0. fps is a whole number (`Format` rejects 29.97).
- World units metres; layout in UI px (CSS px of the app page); one ui_to_world / world_to_ui pair
  (`layout.Layout`); UI centre = world origin, UI +y (down) = world -Y, slab tops at z 0.
- Camera model: Blender sensor 36 mm, sensor_fit HORIZONTAL, no shift, no roll unless given; the Python
  pinhole model (`camera.project`) must match Blender exactly (proven to 6e-7 ndc by
  `check_camera_blender`). One Euler order everywhere: 'XYZ'. Side naming by LOCAL axis: suffix _px for
  +X, _nx for -X (never left/right).
- Modules imported by Blender AND by the plain-Python checker are STANDARD LIBRARY ONLY (math, json,
  ...). numpy/scipy/pedalboard/Pillow are allowed only in `sound/`, `measure.py`, `contact.py` and
  `verify_final.py`, which run in the kit venv; `blender/stills.py` and `blender/lookdev.py` use Blender's own numpy
  (stills.py imports `measure.py` for the region maths; its ffmpeg readers stay venv-side).
- Every Python entry script starts with `import sys; sys.dont_write_bytecode = True` before importing
  filmkit. Run python with -B. Never leave __pycache__ or .pyc in the skill folder (the kit check fails).
- JavaScript is .mjs (ESM) in the engine. A project result page is a classic .js (no import/export):
  frames-render injects the engine as globals before it runs, and a classic script passes the kit's
  `node --check` under its CommonJS package.
- No machine paths containing Users or home in any file in the kit. No folder named assets/. A test is
  named by what it checks ("quick check", "basic check"), never by the kit's banned two-word name.
  Never put "fable" or "codex" in a file or folder name.
- Determinism: no wall clock, no unseeded randomness. Seeded RNG (mulberry32) gives the same output in
  Python (`ease.mulberry32`) and JS (`ease.mjs rng`). Event seeds: `ease.seed_of(kind, n)` = crc32 + n
  (`ease.mjs seedOf`, `sound.mix.seed_of`: the same formula, asserted equal by the checks).
- Docstrings are plain and dense: what, units, inputs, outputs.

Added by the reverse-engineering reports and the integration (also fixed):

- Every hit (landing, press, stamp, payoff) sits on an exact frame time, written as `beat(n)` or
  `time(f)`, never as a decimal like 4.8333. `Events.validate` asserts frame(t) == the first frame whose
  state flips, and every event inside [0, duration]. Takeoffs may float. Named exceptions are listed by
  event id.
- Events and jumps are looked up by id, never by list index.
- The BPM is one whose sixteenth is a whole number of frames (`timebase.bpm_grid_ok`), or the project
  names the override (120 BPM at 30 fps fails it: a sixteenth is 3.75 frames; the grey box names it).
  Picture hits use `Clock.at`, musical subdivisions `Clock.exact` (event field `place="exact"`).
- Angles are continuous before baking (`ease.unwrap_to`; keep +2 pi after a flip). The 480 Hz
  continuity scan treats a spin-back as a bug.
- The UI texture shows the FINAL state. Every UI element is classified STATIC (texture only), OBJECT
  (own 3D piece UV-mapped to its rect), SCREEN (per-frame plane over a rect the texture leaves one flat
  colour) or SPRITE (own transparent PNG). Anything that visibly changes is not STATIC.
- Chrome runs headless with --force-color-profile=srgb --hide-scrollbars --font-render-hinting=none
  (+ --allow-file-access-from-files for the frames page). Fonts are proven before the first pixel;
  a silent fallback is a failure.
- Tools write outputs to temp names and rename after their checks pass. A failed run leaves no
  fresh-looking artifact behind. Every output path has one owner; nothing writes build/ while a render
  reads it.
- Blender: pass gpu.py on every call; stills render with persistent data OFF on the context scene after
  frame_set; animation renders keep it ON; never save the .blend from a stills or lookdev run; scales
  are clamped >= 1e-3 and objects hide with hide_render; bloom reads the Emission pass only; screen
  grades apply to camera rays only; only lights the look names as glossy-visible are.
- Blender resolves a plain relative `render.filepath` against the DRIVE ROOT (not the cwd) and a
  relative image load against the .blend; the engine makes every render and read-back path absolute.
  Windows refuses file writes near 260 characters: keep project paths short (about 240 for the longest
  render path).
- Measurements use frame fractions (margins, sizes, void), frame widths/s (speed), frame widths/frame^2
  (acceleration), deg/frame (turn), px at film width (blur), sRGB 8-bit medians (colour). The engine
  holds no threshold; thresholds come from the project's RULES.
- Rules are per element (each box 100 % inside plus a margin), never union or percentage rules.
- Sound: SR 48000 asserted; the WAV length is asserted after a re-read; master order high-pass,
  compressor, makeup loop, true-peak limiter, fade after the limiter; the hit table proves presence
  per kind, not only timing, and its audibility column (the kind over the rest of the mix, phone band,
  best 5 ms) is the one number that reads the mix: a mix onset on the groove's grid proves nothing. The
  onset detector cannot find a hit on sample 0: the first event of a film sits at t > 15 ms.
- Encode with an explicit BT.709 conversion and tags (`setparams` at the end of the filter graph; ffmpeg
  8.1 drops the tags otherwise). Contact sheets use Pillow, never ffmpeg drawtext.

## 2. Package layout and owners

```
.claude/skills/film-engine/
  API.md                      this contract                              [architect, now integrator]
  SKILL.md                    pointer to API.md                          [architect]
  templates/project/          the scaffold a director copies (section 7) [integrator]
  scripts/
    ease.mjs                  JS twins of ease + rng (+ crc32)           [core]
    comp-kit.mjs              browser canvas helpers (window.FilmKit)    [node]
    ui-render.mjs             UI page -> textures + layout contract      [node]
    frames-render.mjs         canvas page -> PNG sequences               [node]
    contact.py                contact sheets, grids (Pillow)             [checker]
    encode.py                 PNG + WAV -> MP4                           [checker]
    verify_final.py           probe, luma scan, audio lag                [checker]
    build.py                  the build chain runner + freshness         [checker]
    checks/run_checks.py      discovers check_*.py, PASS/FAIL, exit 1    [architect]
    checks/check_*.py         quick checks: core, motion, camera_blender, checker, build, node,
                              blender_build, blender_look, encode_venv, measure_venv, sound_venv, template
    filmkit/
      __init__.py
      timebase.py             Format, frame/time, beats, Events, export  [core]
      layout.py               Layout, rects, stacks                      [core]
      ease.py                 eases, envelopes, keyed, mulberry32        [core]
      vec.py                  vectors, matrices, Euler XYZ, hull         [core]
      arc.py                  jumps, squash, press response, culling     [motion]
      camera.py               pinhole, frame_solve, shots, focus, f-stop [motion]
      hero_points.py          hero spec -> posed surface point cloud     [motion]
      check.py                rule framework, metrics, previs SVG        [checker]
      fresh.py                stamps, require_fresh                      [checker]
      measure.py              numpy/ffmpeg pixel measurements           [checker]
      ui_html.py              HTML primitives tagged data-in             [node]
      blender/
        gpu.py                OptiX enable, every call                   [blender-build]
        bake.py               Bake: one key per frame, bulk write       [blender-build]
        geo.py                rounded_box, capsule, rect boxes, cards    [blender-build]
        hero.py               build_hero(spec), pose_channels            [blender-build]
        materials.py          screen/emission/toy/mask materials         [blender-look]
        render.py             presets, bloom, world, cyc, lights, apply  [blender-look]
        stills.py             stills + mask + measure, animatic          [blender-look]
        lookdev.py            CLI harness, selfcheck, tune, turnaround   [blender-look]
        scene_kit.py          what a project scene.py calls              [blender-look]
      sound/
        synth.py              DSP primitives, starter generators         [sound]
        mix.py                Clock, Bus, Dispatcher, master, WAV I/O    [sound]
        soundcheck.py         LUFS, true peak, onsets, hit table, PNG    [sound]
        step.py               the sound build step a project sound.py calls [sound]
```

## 3. Project files and how they meet the engine

A film lives in `video-projects/<id>/`. The director writes these files; every taste value is here.
`templates/project` holds a running copy of each one.

| File | Exports | Read by |
| --- | --- | --- |
| `timeline.py` | `FORMAT` (timebase.Format), `LAYOUT` (layout.Layout), `EVENTS` (timebase.Events), `JUMPS` (the beat sheet, section 4), `Z` (z stack), `state(t) -> dict`, `EXTRA` (JSON-safe: hero spec, theme, ...); `__main__` validates and calls `export_timeline` | every Python reader imports it; every JS reader reads `build/timeline.json` |
| `hero_spec.py` | `HERO` spec dict (section 4), `BODY_PIVOT_Z` | `blender/hero.py` via scene.py, `hero_points.py` via motion.py |
| `motion.py` | pure functions of t: `hero_pose(t)`, `hero_points(t)`, `hero_blocks(t)`, `hero_centre(t)`, `tile_state(button, t)`, `landings()`, `channels(t)`; tables `STYLES`, `PRESS`, `JUMPS` (resolved records) | scene.py (bake), shots.py, check_model.py |
| `shots.py` | `SHOTS`, `CROSSINGS`, `SHAKES`, `FSTOP`, `SHOTLIST`; `camera_state(t)`, `camera_raw(t)`, `holds()`, `whip_windows()`, `channels(t)` | scene.py (bake), check_model.py |
| `look.py` | `LOOK` dict (section 4), `REGISTRY` {role: names}, `STUDIO_INDEX` | scene.py; stills.py and lookdev.py re-read the stored copy from the .blend |
| `ui_build.py` | builds `build/ui.html` with `ui_html.Page`; owns palette, fonts, labels | ui-render.mjs |
| `comp.html` + `comp.js` | the result page; exposes `window.FilmPage` (section 6); draws with `window.FilmKit` | frames-render.mjs |
| `score.py` | `HANDLERS` {kind: fn(event, ctx)}, `SILENT`, `music(ctx)`, `bus_chain(buses)` (optional), `MASTER`, `REFERENCE`, `MARKER_COLOURS` | sound.py |
| `checks_config.py` | `RULES` dict of thresholds (section 4), `PREVIS_MOMENTS` | check_model.py |
| `build.json` | mechanical knobs (below) | build.py |
| `scene.py` | Blender entry: load_timeline, build, bake, apply_look, save | build.py step blend |
| `sound.py`, `check_model.py`, `build.py` | thin entries calling the engine (`sound.py` is `filmkit.sound.step.run(HERE, score)`) | build.py |
| `film.json` | `width`, `height`, `fps` (whole numbers, written by `new-video --kind film --size WxH --fps N`; build-only: `project.json` carries the same values for the kit but deliver rewrites it, so the timeline step stamps film.json) | the template `timeline.py` (film size and fps; a fractional fps raises) |

Bootstrap at the top of every project Python entry (the engine folder comes from env `FILM_ENGINE`,
default `<project>/../../.claude/skills/film-engine/scripts`):

```python
import sys; sys.dont_write_bytecode = True
import os
HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.environ.get("FILM_ENGINE") or os.path.normpath(os.path.join(HERE, "..", "..", ".claude", "skills", "film-engine", "scripts"))
sys.path[:0] = [p for p in (HERE, ENGINE) if p not in sys.path]
from filmkit import timebase, layout
```

Blender entries use the same lines (scene.py also `os.chdir(HERE)` so `build/ui.png` resolves);
`scene_kit.bootstrap(project_dir)` does it for scripts that can already import filmkit. Blender is
called as `blender -b --python-exit-code 1 --factory-startup -P <ENGINE>/filmkit/blender/gpu.py -P <project>/scene.py -- <args>`.

### Build chain (order is the rule)

| Step | Command (from the project folder) | Reads | Writes (stamped) |
| --- | --- | --- | --- |
| timeline | `python -B timeline.py` | timeline.py + the project .py it imports (hero_spec.py), film.json | build/timeline.json (+hash) |
| ui | `python -B ui_build.py` then `node <ENGINE>/ui-render.mjs --html build/ui.html --timeline build/timeline.json --out build [--font <ui_font>]` | timeline.json, ui_build.py | build/ui.html, ui.png, ui_base.png, ui_check.png, sprites |
| comp | `node <ENGINE>/frames-render.mjs --page comp.html --timeline build/timeline.json --out build --contact comp_contact.png --contact-every <n>` | timeline.json, comp.html, comp.js | build/comp/####.png (one folder per sequence), comp_bbox.json, comp_contact.png |
| sound | `<venv> -B sound.py` (= `filmkit.sound.step.run`) | timeline.json, sound.py + what it imports (score.py, ...), checks_config.py + what it imports (its `SOUND` dict gates the step, so a tightened gate stales sound.wav) | build/sound.wav, sound_report.txt (with the MUTATION lines), sound_check.png |
| blend | `blender -b --python-exit-code 1 --factory-startup -P gpu.py -P scene.py` | timeline.json, ui.png, comp_bbox.json, every build/ sequence folder (comp/, clock/, ...), every sprite PNG the layout names, scene.py + every project .py it imports (motion, shots, look, hero_spec, set, poses, shots_9x16, ...) | build/film.blend |
| check | `python -B check_model.py` | timeline.json, comp_bbox.json, check_model.py + what it imports (motion, shots, checks_config, ...) | build/model_report.txt, previs.svg |
| check_9x16 | `python -B check_model.py --shots <shots_9x16>` (only with build.json `stills_9x16`; the project's check_model.py takes `--shots <module>` and writes the `_9x16` report) | timeline.json, comp_bbox.json, check_model.py + <shots_9x16>.py + what they import | build/model_report_9x16.txt, previs_9x16.svg |
| stills | `blender -b --python-exit-code 1 build/film.blend -P gpu.py -P <ENGINE>/filmkit/blender/stills.py -- --frames a,b,c --out renders/stills --json stills.json [--mask] [--points motion:hero_points]` | film.blend, model_report.txt, the points module + what it imports | renders/stills/f####.png, mask_####.png, stills.json |
| stills_9x16 | `... stills.py -- --frames a,b,c --camera <camera_9x16> --film WxH --out renders/stills_9x16 --json stills.json [--mask] [--points ...]` (only with build.json `stills_9x16`) | film.blend, model_report_9x16.txt (VIOLATIONS: 0), the points module, <shots_9x16>.py + what they import | renders/stills_9x16/f####.png, mask_####.png, stills.json |
| animatic | `... stills.py -- --animatic --out renders/animatic --samples n` then `encode.py` then `contact.py --strips` | film.blend, sound.wav | renders/animatic/####.png, animatic.mp4, animatic_strip_*.png |
| final | `blender -b --python-exit-code 1 build/film.blend -P gpu.py -a` | film.blend, stills.json | renders/frames/####.png |
| encode | `python -B <ENGINE>/encode.py ...` | frames, sound.wav | renders/<slug>.mp4 |
| verify | `<venv> -B <ENGINE>/verify_final.py ...` | mp4, sound.wav | renders/verify.json |
| final_9x16 | `blender -b --python-exit-code 1 build/film.blend -P gpu.py -P <ENGINE>/filmkit/blender/stills.py -- --final --camera <camera_9x16> --film WxH --out renders/frames_9x16` (only with build.json `stills_9x16`; every frame through the vertical camera at the look's final preset, persistent data on, the .blend never saved) | film.blend, renders/stills_9x16/stills.json | renders/frames_9x16/####.png |
| encode_9x16 | `python -B <ENGINE>/encode.py --frames renders/frames_9x16 ...` | frames_9x16, sound.wav | renders/<slug>-9x16.mp4 |
| verify_9x16 | `<venv> -B <ENGINE>/verify_final.py --mp4 renders/<slug>-9x16.mp4 --expect-size WxH ...` | mp4, sound.wav | renders/verify_9x16.json |

`build.py <project> [--from step] [--upto step] [--only step] [--force] [--dry]` runs the chain
(`--from` and `--upto` together give a range). The model check needs the comp boxes (step comp) before the
camera solve reads them; the blend step needs the sequences; stills need a clean model check
(`VIOLATIONS: 0` in build/model_report.txt; stills_9x16 the same line in build/model_report_9x16.txt); the
final needs fresh stills the director has looked at (final_9x16: fresh vertical stills). The five 9x16 steps
(`build.STEPS_9X16`) print `skipped` and exit 0 when build.json has no `stills_9x16` list.
Tool paths: env `BLENDER`, `CHROME`, `NODE`, `FILM_ENGINE`, `FILM_PYTHON` (default: the kit's `.venv`
when the engine sits in the kit, else the running interpreter).

`build.json` (project folder, every key optional; the values are placeholders, none is taste):

```json
{"slug": "<folder name>", "stills": [1, "<mid>", "<last>"], "mask": true, "crf": 17, "preset": "slow",
 "vignette": null, "animatic_samples": 16, "audio_kbps": 320, "ui_font": null, "contact_every": 15,
 "points": "motion:hero_points",
 "stills_9x16": [frames], "shots_9x16": "shots_9x16", "camera_9x16": "camera_9x16", "film_9x16": [1080, 1920]}
```
`stills_9x16`: the vertical review stills (absent = no 9x16 steps); `shots_9x16`: the vertical shot module
`check_model.py --shots` takes (its sources feed the stills_9x16 stamp; default `shots_9x16`); `camera_9x16`: the
camera object the project's scene.py built for it (default `camera_9x16`), which final_9x16 renders through;
`film_9x16`: its size (default the master film turned on its side), which verify_9x16 asserts on the mp4.
`mask`: stills also render the class mask and measure it (needs `LOOK['mask']['classes']`); `ui_font`: the
face ui-render proves (null = "fonts: none named, not proven"); `contact_every`: comp contact sheet step;
`points`: the project function `f(t) -> world points` the stills step passes as `--points`, so stills.json
carries `silhouette.model_w` next to `mask_w` (the key absent: `motion:hero_points` when the project has
a motion.py; `null`: no model width).

### Freshness rule

`build/timeline.json` carries `hash` (sha1 of its canonical JSON, 12 hex). Every step stamps its outputs
in `build/stamps.json` with that hash and its inputs' mtimes (`fresh.stamp`, keys project-relative). A
step calls `fresh.require_fresh` on every artifact it reads under build/ or renders/ and refuses to run
(exit 2, listing what to rerun) when an input is older than one of its own inputs, carries another hash,
has no stamp, or depends on a stale stamped input (transitive). Sources outside build/ and renders/ only
feed the stamp. The stamp holds the input mtimes `build.py` read before the step's first command ran
(`fresh.input_mtimes`), so a source edited while the step runs (an owner saving motion.py during the
integrator's chain) leaves the artifact 'changed since the stamp': it was built from the old source. A
render never starts on stale textures, sequences or sound. Critics check that renders
are newer than the .blend and the .blend newer than timeline.json before they look at a frame.

Inputs are complete, never a hand list: a step's sources are its entry script plus every project .py it
imports, followed through the project by a static scan (`build.project_sources`: `import a`,
`from a import b`, `importlib.import_module('a')` with a literal name; a name counts when
`<project>/<name>.py` exists); the blend step also reads every sequence folder under build/ (a folder
with a 0001.png, one per sequence the comp page renders: `build.sequence_dirs`) and every sprite PNG
the timeline layout names (`build.sprite_pngs`); the ui step stamps those sprites and the comp step
stamps every sequence folder it wrote (the output list is re-read after the step runs). So touching
set.py, poses.py, shots_9x16.py, build/clock/ or a sprite marks build/film.blend stale, and the stills
and final steps refuse until the blend step reruns. A project stamped before this rule has no stamp for
its sprites and extra sequences: rerun from `ui` once (or pass `--force`).

## 4. Project data formats

### Hero spec (`hero_spec.py: HERO`, bpy-free)

```python
HERO = {
  "name": "hero", "euler_order": "XYZ", "facing": "-Y",          # local axis facing forward at yaw 0
  "parts": [
    {"name": "body", "parent": None, "shape": "rbox", "size": (sx, sy, sz), "r": 0.012, "k": 7,
     "pivot": (0, 0, z), "offset": (0, 0, 0), "axis": None, "material": "body", "pass_index": 1},
    {"name": "arm_px", "parent": "body", "shape": "capsule", "a": (0,0,0), "b": (0,0,-l), "r": 0.01,
     "pivot": (px, py, pz), "offset": (0, 0, -hidden), "axis": "Y", "material": "body", "pass_index": 1},
    {"name": "eye_px_open", "parent": "body", "shape": "rbox", ..., "pass_index": 2, "expression": "open"},
  ],
  "expressions": {"open": ["eye_px_open", "eye_nx_open"], "happy": ["eye_px_happy", "eye_nx_happy"]},
  "default_expression": "open",                                        # else the first set
  "slides": {"lift_px": {"part": "arm_px", "delta": (dx, dy, dz)}},    # keyed pivot translation 0..1
  "materials": {"body": "toy", "eye": "toy"},                          # roles the look fills
}
```
shape: `rbox` (size, r, k), `capsule` (a, b, r), `sphere` (r). pivot is in the parent part's local space
(world for the root part); offset moves the mesh from its pivot (hidden length inside the parent). axis
is the joint's rotation axis ('X' | 'Y' | 'Z' | None = full Euler). Transform chain (built by
blender/hero.py, measured by hero_points.py): root Empty (pos, euler XYZ) -> squash Empty (scale) ->
parts at their pivots (+ slide deltas), joint rotation about the axis, mesh = shape + offset:
`world = root_T + root_R . (S * (T_part + R_part . p))`. A pose:
`{'root': {'pos', 'euler'}, 'squash': (sx, sy, sz), 'joints': {part: angle | (rx, ry, rz)},
'slides': {name: 0..1}, 'expression': name, 'visible': bool}`; a pose may omit joints, slides or the
expression (0 / 0 / the default); expression None shows no set; an unknown name raises ValueError. The
soles sit at the root origin, so the root position is the sole.

### The beat sheet and jump rows (`timeline.py: JUMPS`, `motion.py`)

`timeline.JUMPS = [(id, takeoff_t, land_t, target_button, apex_m, style)]` is the director's beat sheet;
the events (takeoff, land, press) are derived from it so one source holds every hit time. motion.py turns
it into arc rows `(id, t0, t1, to_xy_world, apex, style, target, surface_z)` (to via `LAYOUT.ui_to_world`
of the button centre) and resolves them with `arc.resolve_jumps(rows, start, surface_z_fn, STYLES, fps)`.
`STYLES = {style: {'crouch', 'c_a', 'st', 'c_l', 'lean', ...}}`: every key in the arc.py docstring, every
number taste; a style that omits an envelope key (crouch_share, air_fade, pre_land, land, land_fade, unload,
tuck, crouch_min, ground_speed) takes the engine placeholder, which is the reference film's value, so the
template spells every key. A pressed tile lowers the surface: `surface_z(target, t) = tile_top - press_depth(...)`.

### Shots (`shots.py`)

```python
SHOTS = [camera.Hold("open", t0, t1, A_deg, E_deg, lens_mm, groups_fn, bias=(0.5, 0.0), cap=None, solve_at=[t...]),
         camera.Rig("ride", t0, t1, anchor_fn, keys=[(t, A_deg, E_deg, dist_m, lens), ...]), ...]
CROSSINGS = {("open", "peel"): ("ease", {"ease": "smooth"}), ("glow", "kick"): "orbit", ("tools", "glow"): ("truck", {...})}
SHAKES = [(t_hit, amp_deg, decay_s, f_heading_hz, f_elev_hz)]
BLUR = {"windows": [(t0, t1, points_name, blur_px)], "fstop_range": (1.4, 11.0), "flat_holds": ["glow"]}
```
groups_fn(t) -> [(points, margin)]; the first group is the subject (the cap reads its depth). A Rig sits
at `anchor - forward(A, E) * dist` and aims at the anchor; past t1 the anchor runs on at its last speed.
Crossing params are listed in the camera.py module docstring.

### Look constants (`look.py: LOOK`, read by `render.apply_look`)

```python
LOOK = {
  "view": {"transform": "AgX", "look": "None", "exposure": 0.0, "gamma": 1.0},
  "preset": "final",
  "presets": {"preview": (50, 16, 0.05, True), "stills": (50, 40, 0.03, True),
              "animatic": (50, 16, 0.05, True), "final": (100, 64, 0.01, True)},   # (percent, samples, adaptive, denoise)
  "shutter": 0.5, "bounces": {...}, "clamp_indirect": 6.0, "blur_glossy": 1.0,     # Filter Glossy (0 = sharp reflections)
  "bloom": {"threshold": .., "smoothness": .., "strength": .., "size": .., "quality": "High"},
  "world": {"light": (r, g, b), "strength": 1.0, "camera": (r, g, b)},
  "cyc": {"floor_z": -4.0, "material": {"base": (r, g, b), "roughness": 0.75}, "wall_y": .., "cove_r": .., "top": .., "half_x": ..},
  "lights": {"key": {"loc": .., "aim": .., "size": .., "watts": .., "color": .., "glossy": True}, ...},
  "light_track": {"full_deg": 25, "symmetry": 4, "sigma": 4, "gain_sigma": 2, "gain_clamp": (0.6, 1.6)},
                                        # read by the project's scene.py (render.light_rig_track), not by apply_look
  "turnaround": {"views": [(name, az_deg, elev_deg), ...]},                       # lookdev turnaround (else its placeholders)
  "materials": {"body": {"base": (r, g, b), "roughness": .., "specular": .., "coat": .., "coat_roughness": ..},
                "screen": {"spec": .., "rough": .., "strength": ..}, "side": {...}},
  "grades": {"screen:comp": (h, s, v)}, "glow_highlights": {"lo": 0.1, "hi": 0.6},
  "mask": {"classes": {name: {index, channel, level[, normal, material, near, dist, white, alpha, band]}},
           "target": "RRGGBB", "orange": [[r, g, b], ...]},
}
REGISTRY = {"screen": [mat names], "side": [...], "body": [...], "glow_highlights": [mat names],
            "cyc": ["studio_cyc"], "light_rig": ["light_rig"], "light_follow": ["hero"], "hero_root": ["hero"]}
```
apply_look stores LOOK and REGISTRY as JSON on the scene (`render.stored_look`), so stills.py and
lookdev.py read presets, mask classes and the target from the saved .blend without the project module.
The z stack lives in `timeline.Z` (`{"slab", "bevel", "tile": (z0, z1), "screen", ...}`).

### Score handlers (`score.py`)

```python
def land(ev, ctx):                      # one handler per event kind; ctx.seed, ctx.n, ctx.clock, ctx.tl, ctx.event
    sig = synth.thwack(ctx.clock.sr, ctx.seed, dur=0.12)
    ctx.add("fx", sig, ctx.clock.at(ev["t"]), gain_db=MIX["land"], pan=pan_of(ev))
HANDLERS = {"land": land, "takeoff": takeoff, ...}      # Dispatcher asserts every kind has one
SILENT = ("press",)                                     # kinds that make no sound, on purpose (no stem)
def music(ctx): ...                                     # optional: fills the music buses (event None, n 0)
def bus_chain(buses) -> (2, n): ...                     # optional: pre-master sum (default: plain sum)
MASTER = {"target_lufs": -14.0, "window_s": (t0, t1), "ceiling_dbtp": -1.0, "fade_s": (f0, f1),
          "fade_pow": 2.6, "hp_hz": 25.0, "comp": {"threshold_db": -22, "ratio": 3, "attack_ms": 10, "release_ms": 120}}
REFERENCE = [-28, -21, ...] or None    # LUFS per 0.5 s block, None = unchecked
```
An event with the field `place="exact"` (set through `Events.add(..., place="exact")`) is a sub-frame
event: its handler and the hit table place it with `clock.exact(t)`; every other hit sits on `clock.at(t)`.

### Check thresholds (`checks_config.py: RULES`)

```python
RULES = {
  "hero_margin": {"min": 0.05, "visible_only": True},
  "hero_width": {"default": 0.13, "zones": [(t0, t1, min_w, max_w_or_None[, why])], "exempt": [(t0, t1)]},
  "content_boxes": {"at_kinds": ["press"], "effect_end_field": "effect_end", "margin": 0.02, "boxes": ["title", "subtitle"],
                    "min_in_frame": 0.95, "max_tilt_deg": 11.0, "max_hidden": 0.05},   # max_hidden optional (a number or
                    # {box: limit, "default": limit}): share of the
                    # in-frame box the hero blocks hide (1 - visible_share / area_in_frame), per frame through that
                    # frame's camera over the effect window, reported per frame, the worst flagged; needs hero_blocks
  "still_at_hits": {"kinds": ["land", "press"], "window_frames": 2, "max_fw_per_s": 0.30},
  "camera_smooth": {"max_accel": 0.04, "max_turn_deg": {"default": 4.0, "crane": 1.0}},
  "ease_into_holds": {"frames": 4, "ratio": 0.3},
  "fstop_discipline": {"jitter": 0.02, "hold_tol": 0.01, "flat_holds": ["glow"]},
  "void": {"max": 0.20, "at_kinds": ["press"], "cols": 33},
  "blur_budget": {"windows": [(t0, t1, "comp", 10.0)]},
  "continuity": {"rate": 480, "ratio": 4.0, "floors": {"pos": 5e-4, "angle": 5e-3, "lens": 0.05, "fstop": 0.02, "scale": 5e-3}},
  "landings": {"on_beat": True, "exceptions": ["step#1"], "xy_mm": 1.0, "z_mm": 1.0, "pitch_rad": None},
  "camera_floor": {"min_z": 0.1}, "feet_above_ground": {"min_mm": -1.0, "ground_z": 0.0},
}
```
A rule absent from RULES (or set to None) does not run. The checker never lowers a number; it reports
the conflict. `camera_smooth.max_turn_deg` as a dict: a named hold's limit covers the crossing into that
hold plus the hold itself; "default" covers the rest outside whip windows. `continuity.floors` maps a
channel's floor class ("pos", "angle", ...) to its unit; a class named "angle" wraps.

The model protocol (what `check_model.py` passes to `check.run`): fmt (fps, duration, frames, film, bpm),
layout (optional), events (`of_kind`), camera(t) -> dict {pos, target, lens, fstop, focus_distance} (shaken),
camera_raw(t) -> (pos, target, lens[, heading]) (the heading rolls a vertical view; a 3-tuple reads as None),
hero_points(t), hero_blocks(t) (optional), content_boxes(f) ->
{name: [4 world pts SW, SE, NE, NW] | None} (optional), points_of(name, t) (optional), ground_poly,
holds() -> [(name, t0, t1)], whip_windows() -> [(t0, t1)], landings() -> [{'id', 't', 'target': (X, Y),
'sole_xyz', 'surface_z', 'pitch', 'rect_ok'?}], channels(t) -> {name: (value, floor | floor_class[, 'angle'])},
probes() -> [world pts]. The rules receive a `check.Memo` (cached cam/raw/pts/flow per frame).

## 5. Module APIs

Units are in the docstrings. Items added by the builders beyond the skeleton are marked (added).

### filmkit/timebase.py [core]
```
Format(fps, duration, bpm=None, film=(1920,1080), ui=(1280,720), ui_scale=3, px_to_m=0.0025, comp=None)
  .frames (= frame(duration) - 1) .beat .beat_frames .to_json()      fps must be a positive int (ValueError)
frame(t, fps) -> int                      time(f, fps) -> float            snap(t, fps) -> float
is_whole_frame(t, fps, eps) -> bool       first_frame_at_or_after(t, fps) -> int  (1e-9 guard)
beat(n, bpm) -> s     beats_of(t, bpm)    on_beat(t, bpm, fps, eps) -> bool
sixteenth_frames(bpm, fps) -> float       bpm_grid_ok(bpm, fps) -> bool    bpm_candidates(fps, lo, hi) -> [bpm]
timecode(seconds, fps) -> 'H:MM:SS:FF'   (total = floor(t*fps + 0.5), FF = total % fps; same as comp-kit)
jsonable(x) (added, public)               tuples -> lists, keys -> str, recursively
Events(fmt): add(t, kind, id=None, **fields) -> ev ('<kind>#<n>' ids; dup id or end < t raise); get(id); of_kind(kind);
  kinds(); sorted(); __len__; __iter__ (sorted)
  validate(whole_frame_kinds, on_beat_kinds, exceptions, no_overlap, eps) -> [problems]  (+ t in [0, duration], end <= duration)
  hit_table(kinds); to_json()
bake_frames(fmt, state_fn, round_dp=4) -> [dict]  (f, t first; floats to 4 dp)     timeline_hash(doc) -> 12 hex
export_timeline(fmt, layout, events, state_fn, extra=None, out=None) -> {format, layout, events, frames, extra, hash}
  (temp name -> os.replace, indent 1, utf-8, LF, allow_nan=False)
load_timeline(path) -> dict (hash verified)              print_hits(doc, kinds)
```
Event dict: `{id, t, kind, frame, **fields}`; interval events carry `end`.

### filmkit/layout.py [core]
```
Layout(ui, px_to_m, panels, buttons, screens, stacks, sprites, points, nested, owners)   (attributes of those names)
  ui_to_world(x, y) -> (X, Y)   world_to_ui(X, Y) -> (x, y)   uv_of(x, y) -> (u, v)
  rect_world(rect, z) -> 4 corners SW,SE,NE,NW   rect_of(name)   owner_of_point(pt, fallback)   owner_of(name)
  nested_to_ui(name, cx, cy)   ui_to_nested(name, x, y)   nested_to_world(name, cx, cy)   to_json()
rect_center, rect_contains(rect, pt, eps), rect_inside(inner, outer, eps), rect_inset, rect_union, rect_scale
stack_tops(t, items, y0, row_h, slide_s, ease) -> {id: y|None}  (slide_s <= 0 is a step)   stack_final_tops(items, y0, row_h)
ruler_x(value, x0, px_per_unit)
```
Rect = (x, y, w, h) UI px. screens = {name: (rect, flat_hex)}; stacks = {name: {rect, y0, row_h, slide_s,
items: [(id, rows, created_t)]}}; sprites = {name: (w, h)}; nested = {name: (rect, scale)}.
`owner_of_point` tests panels in table order and skips the fallback panel.

### filmkit/ease.py [core] and scripts/ease.mjs [core]
```
clamp(x, a, b)  lerp(a, b, u)  smoothstep(u)  smootherstep(u)  out_cubic(u)  in_out_cos(u)  trap(u, r)
win(t, a, b)  bell(t, a, b)  impulse(tau, tp, decay, period)  spring(tau, start, peak_t, peak)
spring_step(tau, zeta, wn)  keyed(keys, t, ease)  catmull(keys, t)  (tuple values allowed)  wrap(a) -> (-pi, pi]
unwrap_to(target, current)  unwrap_series([angles]) -> continuous copy (each within pi of the one before)
hash01(i, j)  mulberry32(seed) -> next()  seed_of(kind, n)
```
JS names are camelCase (outCubic, inOutCos, springStep, unwrapTo, seedOf); `rng(seed)` is mulberry32;
`crc32(s)` (added, JS only; Python uses zlib.crc32). `FilmEase` is the default export and
`globalThis.FilmEase` in a page. ease.mjs keeps one-line named imports/exports (engineBundle's rule).

### filmkit/vec.py [core]
```
add sub mul dot cross length norm lerp3 mat_vec mat_mul mat_t rot_x rot_y rot_z   IDENTITY
rot_xyz(rx, ry, rz) = Rz Ry Rx      euler_xyz(m) -> (rx, ry, rz)     transform(R, T, p)    compose(R1, T1, R2, T2)
hull2d(pts) -> ccw hull             in_hull2d(pt, hull)  (either winding)
```

### filmkit/arc.py [motion]
```
ballistic(p0, p1, t0, t1, apex, v0=None, ground_speed=None) -> Arc;  Arc(t) -> ((x,y,z), u); Arc.z_of_u(u)
  Arc fields: t0 t1 p0 p1 zp kz uv v0 ground_speed duration g_eff travel (heading rad, 0 = -Y; None for a hop in
  place under 1e-9 m of ground travel: the template's yaw keys keep the running yaw)
duration_from_apex(z0, z1, apex, g) -> s   (apex 0 between equal heights -> 0.0)
  ballistic with apex 0 between equal heights is a flat slide (kz 0, uv 0.5, g_eff 0)
resolve_jumps(rows, start_xy, surface_z_fn, styles, fps) -> [records]   phase(jumps, t) -> (phase, jump)
  record keys: id k arc style S target t0 t1 crouch crouch_t0 to from surface_z apex c_l frame
  (surface_z_fn may be None or return None; start_xy may carry z; raises on overlap / unknown style)
compression(t, jumps, styles, idle_fn) -> c      squash_scale(c, floor=0.45, pin=0) -> (s_xy, s_xy, s_z)
pose_about_pivot(anchor, pivot_local, R_full, R_yaw) -> pos
yaw_track(keys, air_bias_fn, idle_fn, ease) -> callable(t) with .keys (unwrapped) and .keyed(t)
travel_bias(jumps, keyed_fn, bias_of) -> callable(t)   (added; for yaw_track(air_bias_fn=...); 0 over a hop in place, travel None)
press_intervals(landings, release_after) -> {button: [(t0, t1)]}   (landings (t, button[, t_leave]); release None = until the next landing elsewhere)
press_depth(t, intervals, hit_fn, release_fn)   hit_fn(tau, dur); after the end hit_fn(dur, dur) * release_fn(tau_since_end)
exit_time(corners_fn, camera_fn, t0, t_end, rate=240, floor_z=None, occluder_fn=None, film=(1920,1080), sensor_w=36.0) -> t|None
```

### filmkit/camera.py [motion]
```
cam_basis(A, E) -> (r, u, f)    basis_from_dir(f, heading=None)    heading_elev(f) -> (A, E)    look_at_euler(pos, target, heading=None) -> (rx, ry, rz)
VERTICAL_EPS = 1e-9 (added): within it of straight down/up the basis is cam_basis(heading, ±90°) (heading None = 0,
  north up) and look_at_euler -> (0 | pi, 0, wrap(-heading)); a view that is not vertical ignores heading (bit-identical)
tan_half(lens, sensor_w)
project(pos, target, lens, X, film, sensor_w, heading=None) -> (nx, ny, depth)  ((99, 99, depth) behind the lens)
unproject(pos, target, lens, s, plane_z, film, sensor_w, heading=None)      aim_dir(P, lens, X, s, film, sensor_w) -> f
frame_solve(A, E, lens, groups, film, sensor_w, bias_r, bias_u, near=0.2, cap=None) -> (P, f)  (cap reads the first group's depth)
Hold(name, t0, t1, A_deg, E_deg, lens, groups_fn, bias=(0.5, 0.0), cap=None, position=None, solve_at=None)
  .merged_groups() (added)  after solve: .P .f .groups
Rig(name, t0, t1, anchor_fn, keys=[(t, A_deg, E_deg, dist_m, lens)])   P = anchor - forward(A, E) * dist; .eval(t)
  (.eval clamps the keyed E to +-90: Catmull-Rom overshoots a top-down key (60 -> 90 -> 90) and past vertical the
  no-roll basis flips 180 deg; at 90 the roll comes from Rig.heading, continuous with the basis just under 90)
ShotList(shots, crossings, subject_fn, film, sensor_w, ease_fn): solve(); eval(t) -> (P, f, lens); shot_at(t); holds(); whip_windows()
  .by_name {name: shot}  .crossing(a, b) -> (kind, params)  .truck_shift(name_b, t)  (added)
Hold.heading(t) / Rig.heading(t) (keyed A) / ShotList.heading(t) -> rad (added; a crossing eases the two headings)
  A crossing (any kind) with a vertical or steep end (|E| >= STEEP_DEG = 80 deg, `_steep`) takes its direction
  from the same (heading, elevation) blend (ShotList._blend_dir), so the roll turns into the steep hold's heading
  in one turn instead of popping by the heading difference on the last frame (vertical end) or spinning and
  spinning back near the pole (an orbit from E 85 into an oblique hold: 42 -> 4 deg/frame image spin in the
  tap-to-submit 9:16 open, 9.7 -> 0.4 in its 16:9 open); a crossing between two holds under 80 deg is
  unchanged (bit-identical). `checks/check_motion.py` holds the E 85 -> oblique orbit case (spin <= 10 deg/frame).
add_shake(P, f, lens, t, shakes) -> (P, f, lens)   (the shaken E is clamped to +-90: no flip past vertical)
focus_distance(P, f, point) -> m     fstop_for(points, P, f, df, lens, blur_px, film, sensor_w, heading=None) -> N
fstop_track(need_fn, t0, t1, rate=120, smooth=(0.1, 0.1), fstop_range, camera_holds, flat_holds, hold_ramp=0.15) -> callable(t)
  (.grid .need .rate .t0; raises if the mean window exceeds the max window)
camera_state(shots, t, focus_fn, fstop_fn, shakes, film, sensor_w) -> {pos, target, lens, fstop, focus, focus_distance, rot,
  heading, raw: {pos, target, lens, heading}}   (pass cam['heading'] to project; filmkit.check does)
```
Degrees in Hold/Rig/shakes (taste-facing), radians inside. Shake is added after the aperture is solved.
Known limit: a shake that drives a steep or top-down hold past E = 90° clamps at the pole (no 180° flip);
on those samples the view is vertical, its roll comes from the shot's heading, and the heading part of the
shake (under its amplitude) leaves the roll, a jitter of at most the amplitude. `checks/check_motion.py`
holds the rig 60 -> 90 -> 90 and the shaken E 88 cases (rz within the amplitude of -A, no flip).

### filmkit/hero_points.py [motion]
```
rbox_points(centre, half, r) -> 56 pts   capsule_points(a, b, r, n_ring, n_cap)   sphere_points(c, r, n)  (26-set or Fibonacci)
part_points(part)   root_frame(pose) -> (R_root, T_root, S) (added)
part_transforms(spec, pose) -> {name: (R, T)} in the SQUASH frame (root and squash applied by root_frame)
hero_points(spec, pose, parts=None) -> [pts]   hero_blocks(spec, pose) -> [(centre, half, R)] (squash approximated per axis)
cylinder_points(centre, r, h, n)   silhouette(points, cam, film, sensor_w) -> {width, height, margin, cx, cy}   extent_width(spec)
  (cam may carry 'heading')
expression_sets(spec) -> {name: [parts]}   default_expression(spec)   active_expression(spec, pose)   (added; bpy-free;
  blender/hero.py reads them, so the model points and the render show the same set)
```

### filmkit/check.py [checker]
```
Report: violation(text) line(text) section(title, lines) row(f, **cols) text() write(path) -> exit code; exit_code
Rule(name, fn, needs)   Memo(model)   run(model, rules_cfg, rules=None, scan=True) -> Report   standard_rules() -> {name: Rule}
margin_of screen_size project_poly clip_rect clip_convex area area_in_frame box_margin baseline_tilt grid_coverage void_above
hit_stillness(camera_fn, hits, probes, window_frames, h, fps, film) -> [(name, t, fw_per_s)]
camera_flow(cams, film, depth=8.0) -> (speed, accel, turn) lists indexed 1..n (index 0 unused)
ease_ok(speed, holds, fps, n, ratio, floor=0.004) -> [problems]
aperture_audit(fstops, camera_holds, flat_holds, fps, jitter, hold_tol, eps) -> [problems]
defocus_px(cam, points, film=(w, h), sensor_w)   ray_box(o, d, c, half, R)   occluded(cam_pos, X, blocks)   visible_share(faces, cam, blocks, n, film)
landing_audit(landings, fps, bpm, on_beat_exceptions, xy_mm, z_mm, pitch_rad=None) -> rows
continuity_scan(channels_fn, duration, rate=480, ratio=4) -> [(t, name, step)]
tune(model, hold, heads, elevs, lenses, score_fn, filters, film) -> ranked
write_previs_svg(model, moments, layers, out, safe=0.05, width=1800)   layers: [(name, polys_fn(t) -> [[pts]], css)]
```
Report line 1 names the rules; one line reads `VIOLATIONS: N`; exit 1 on any violation. The library
covers the generic rules; set-piece, acting and fall rules stay project rules written with these metrics.

### filmkit/fresh.py [checker]
```
file_hash(path)  newest_mtime(paths)  load_stamps(build_dir)  current_hash(build_dir) -> hash|None
input_mtimes(build_dir, inputs) -> {rel: mtime|None}   (read before a step runs; build.py hands it to stamp)
stamp(build_dir, artifact, inputs, tl_hash, step=None, mtimes=None)   (a missing input is left out of the stamp; mtimes: the
    inputs' mtimes as input_mtimes read them before the step ran, default read now)
status(build_dir, artifact, tl_hash) -> ('fresh'|'stale', reasons)   require_fresh(build_dir, artifacts, tl_hash)  (SystemExit 2)
CLI: python -B -m filmkit.fresh <project_dir> [--require a,b] [--status]
```

### filmkit/measure.py [checker, venv]
```
sequence_signature(pattern, frames, params) -> md5
content_bboxes(pattern, frames, size=(960,540), level=150, rule='R>=B'|'any'|callable, opening=3, ignore=[(t0,t1,t_use,fps)],
               cache=None, fps=30, source_size=None) -> {f: box|None}
luma_scan(pattern_or_mp4, frames_or_n, size, fps=30) -> {f: luma}   black_frames(lumas, below)   biggest_steps(lumas, n)
region_medians(beauty, mask, classes, erode, min_px, thin_px=200) -> {name: {n, median}}   mask_extent(mask, channel, thresh, min_px) -> (w, h)
hot_pixels(beauty, mask, level=245, grow=3, ...) -> (count, bbox)   decode_audio(path, sr, seconds)   audio_lag(mp4, wav, sr, seconds) -> samples
erode_mask(m, n) / dilate_mask(m, n)  (bool (h, w), 4-neighbour, the frame border keeps its edge value: no wrap)   band_region(msk8, (ch, lo, hi)) -> bool (h, w)
class_erosion(reg, erode, thin_px) -> px  (added: `erode`, or 1 for a thin class: its band eroded 1 px holds fewer than thin_px pixels)
measure_arrays(img, msk, bands, target_srgb=None, erode=2, hot=245, grow=3, hero="body", studio="studio", min_px=30, studio_guard=8, thin_px=200)
    -> {colour, silhouette, hot, void, studio_luma, max}   (the maths behind stills.measure_regions, arrays (h, w, 3) 0..255; numpy only)
```
`thin_px` (r3-23): a class is thin when its band eroded by 1 px holds fewer than thin_px pixels; it is eroded 1 px
instead of `erode`, so a 3 px belt bar or tape stripe reaches stills.json (tap-to-submit f331 16:9: belt_bar 0 ->
40 px, tape 0 -> 33 px; 9:16 0 -> 38 / 52). The raw band count is not the measure: the anti-aliased ramps between
neighbouring levels on the same channel fall into every band they cross (about 290 raw px for that 40 px bar) and
vanish under the first px. Wide classes (>= thin_px after 1 px) keep the full erosion, bit-identical; 0 turns it off.
`studio_guard`: the studio class is eroded by max(erode, studio_guard) px. A motion-blurred edge of a bright class
on the studio's channel sweeps its level through the studio band and leaves a thin ring of no class next to it; a
2 px erosion keeps that ring (the tap-to-submit f141 still: 84 "studio" px with median (56, 44, 61) where no cyc
was in frame), the guard drops it (no entry). `void` stays on the raw band. `checks/check_measure_venv.py` proves it.

### filmkit/ui_html.py [node]
```
Page(layout | layout.to_json() dict, css, font_css, title): box(rect, own, bg, style, inner, cls)
  text(x, cy, s, own, size, color, weight, align, font, style)  svg(rect, body, own, color, view_box, stroke, style)
  hline(x, y, w, own, color, thickness)  vline(x, y, h, own, color, thickness)
  layer(inner, cls) / sprite(name, inner): with inner -> html, without -> a `with` context manager
  register(name, rect, kind="extra") (added)  .points  texture_px_svg(rect, scale, marks, own, color)  check_overlay(rects, points)
  modes_css()  registries_js()  html()  write(path) -> n_elements
esc(s)
```
The registry is built from the Layout tables (panels, buttons, screens -> UI_EMPTY, nested, stacks plus
'<stack>:<id>' at their final tops, sprites as (0, 0, w, h)); a duplicate name raises. Modes: '' final,
'base' hides .layer, 'check' shows #check, '<sprite>' shows that sprite alone on a transparent background.
The page embeds window.UI_SIZE, UI_RECTS, UI_EMPTY (screens + flat hex), UI_SPRITES.

### filmkit/blender/gpu.py [blender-build]
Runs on import/-P: `enable_gpu(kind)` -> device names; sets every scene to GPU; load_post handler;
raises when no device. Env `CYCLES_DEVICE` (default OPTIX). Sets dont_write_bytecode first.
The raise stops Blender only with `--python-exit-code 1` (exit 1, later -P and -a skipped); without
the flag Blender exits 0 and renders on the CPU.

### filmkit/blender/bake.py [blender-build]
```
LINEAR = 1  CONSTANT = 0
Bake(n_frames): put(idb, path, f, value, index=-1, interp)  (f outside 1..n raises)  vec(idb, path, f, values, interp)
  hide(ob, f, hidden)  prop(idb, name, f, value)  (creates the property on first key)  write() -> (keyed, constant)
  (RuntimeError listing the missing frames; a constant channel is assigned once, no keys; every rotation_euler
  channel is unwrapped (ease.unwrap_series) before keying, so a look_at rz that wraps at +-pi when the view
  crosses due south never spins the camera the long way inside one frame)
fcurve(idb, path, index) -> FCurve|None     ensure_prop(idb, name, default)
```

### filmkit/blender/geo.py [blender-build]
```
rounded_box(name, size, r, k=6, centre, flat_step=None)  capsule(name, a, b, r, seg, ring)  (a == b: a sphere)  sphere(name, r, seg, ring)
arc_tube(name, radius, tube, a0_deg, a1_deg, flat_y, seg, ring, cap, plane='XZ'|'XY'|'YZ')
box_from_rect(name, rect, z0, z1, top_mat, side_mat, collection, layout, uv_rect, origin, bevel, unit_uv)  (slot 0 top, 1 sides; sets no props)
plane_from_rect(name, rect, z, mat, collection, layout, origin, thickness)
prism(name, outline_xy, z_top, z_bot)  stadium(w, h, n_cap, inset)  annulus(r, width, n)  ring_growing(name, r0, r1, width, n)
shard_meshes(n_shapes, size, thick, rnd)  fix_normals(mesh)  empty(name, collection, location, parent)
parent_keep_world(child, parent, parent_rest_world)  (Matrix, (x, y, z), 16 floats or 4 rows)
shape_key_from_points(ob, name, points)
curl_card(name, image_w, image_h, nx, ny, curl_fn={key: angle_fn(v) -> rad}) -> (Object, {key: ShapeKey})  (v = height share from the hinge)
collection(name, scene)
```

### filmkit/blender/hero.py [blender-build]
```
build_hero(spec, collection, materials, name=None) -> {root, squash, body, parts, expressions, slides, spec,
  axes, pivots, part_slides, default_expression, expression_parts}       (materials: {role: Material})
pose_channels(rig, pose, f, bake)   set_pose(rig, pose)   show_expression(rig, name)   assert_sides(rig)
```
Every part is keyed every frame (rotation; location only with a slide; hide_render CONSTANT). Expression
visibility (the baked poses and show_expression alike) compares spec part names (hero_points.expression_sets),
never object names, so a second hero built from the same spec (renamed objects, body.001) shows its set too.

### filmkit/blender/materials.py [blender-look]
```
load_image(path, sequence, frames, start, offset)   set_sequence(node, frames, start=1, offset=0) (added)
set_props(ob, **props)   prop_or_default(node_tree, prop, default, location)
make_screen_material(name, image, strength, sequence, frames, spec, rough, glow_prop, power_prop, grade, start=1, offset=0,
                     interpolation="Linear", extension="EXTEND")
make_tinted_screen_material(name, image, tint, gain, **kw)   set_power_specular(material, spec, ramp, prop)
set_grade(material, grade|None)   set_glow_highlights(material, lo, hi)
make_toy_material(name, base_linear, roughness, specular, coat, coat_roughness)
make_flat_emissive(name, color_linear, strength, roughness, specular, glow_prop, power_prop, base_share=0.0)
make_side_material(name, base_linear, specular, roughness, power_prop)
make_card_material(name, image_rgba, strength, grade, roughness=0.32, specular=0.0, glow_prop, power_prop)
make_mask_material(name, classes, orange_targets)   mask_bands(classes, margin=10) -> {name: (channel, lo, hi)}
srgb8(v)  srgb_to_linear(c)  set_principled(material, values)  PRINCIPLED_KEYS
```
classes: `{name: {index, channel 'R'|'G'|'B', level, normal '+X'.., material, near, dist, white, alpha, band}}`
(make_mask_material docstring). Object properties `ui_glow` (1 rest) and `ui_power` (1 on, 0 black) drive
emission; a missing property reads as 1.0. Every builder is idempotent (same name updates values).

### filmkit/blender/render.py [blender-look]
```
PRESETS = {name: (percent, samples, adaptive, denoise)}   BOUNCES   (neutral placeholders; LOOK overrides)
setup_render(scene, preset, presets, film, fps, frames, view, look, exposure, shutter, persistent, bounces, clamp_indirect,
             out_path, denoiser="OPENIMAGEDENOISE", blur_glossy=1.0)
add_emission_bloom(scene, threshold, smoothness, strength, size, quality, name="film_bloom") -> NodeTree
setup_world(scene, light_color, strength, camera_color, name) -> World
make_cyc(scene, floor_z, material, wall_y, cove_r, top, half_x, name)
setup_lights(scene, lights, follow, rig_name) -> {rig, name: obj}    set_light_power(light_ob, watts)
key_yaw_of(loc) -> rad (added)   light_rig_track(hero_yaws, cam_rz, key_yaw, full_deg, symmetry, sigma, gain_sigma, gain_clamp) -> (rig_rz[], gain[])
camera_object(scene, name, sensor_w, lens)   apply_look(scene, look, registry)   stored_look(scene) -> (look, registry) (added)
save_blend(path) -> {objects, non_relative}   (frame_set(1), relative paths, no .blend1 backup)
```

### filmkit/blender/stills.py [blender-look]
```
render_still(scene, f, path, percent, samples, adaptive, denoise=True) -> s   (paths made absolute)
render_mask(scene, f, path, mask_material, samples=32)   (Standard view, exposure 0, gamma 1: the look's view gamma is set
    aside and restored, as materials.mask_bands holds gamma-1 codes; objects with ob['mask_skip'] are camera-invisible for it, then restored)
mask_skipped(scene) -> [Object]
read_png(path) -> (h, w, 4) float   measure_regions(beauty, mask, bands, target_srgb, erode=2, hot=245, grow=3, hero="body", studio="studio", min_px=30, studio_guard=8)
model_width(scene, points) -> float   load_points_fn("module:function", project_dir=None) -> callable(t) | None
render_stills(scene, frames, out_dir, percent, samples, adaptive, mask_material, bands, target_srgb, points_fn, json_out,
              prefix="f", extra_fn=None, mask_samples=32, measure_kw=None, denoise=True) -> [dicts]
render_animatic(scene, out_dir, percent, samples, adaptive, frames=None, denoise=True)   (frames None: one animation render, persistent ON)
mask_from_look(look, target=None, classes=None) -> (mask_material, bands, target_srgb)   parse_cli(argv)   main(argv)
```
stills.json entries: `{frame, t, seconds_render, path, colour: {class: {n, median, err}}, silhouette: {mask_w, mask_h,
model_w}, hot: {n, bbox, max_outside}, void: {top, all}, studio_luma, max, content_in_frame, mask_path}`; the
model-vs-mask width difference is reported and a project check may bound it (about 1 pp; the grey box
measured 9.2 % model vs 8.4 % mask at f1). `model_w` needs a points function: the CLI takes
`--points module:function` (build.json `points`, default `motion:hero_points`), imported from the project
folder (`--project`, default the parent of the .blend's folder); without it `model_w` is null and the
cross-check never runs. Erode is 2 px absolute: at tiny sizes pass measure_kw={'erode': n}. `mask_skip`: a
project sets `ob['mask_skip'] = 1` on a camera-only effect (a haze cone) that must not occlude the classes.

### filmkit/blender/lookdev.py [blender-look]
```
apply_overrides(scene, props, mats, lights, grades, world)   render_frames(scene, frames, out_dir, tag, percent, samples, mask, bands, target_srgb, adaptive, points_fn)
selfcheck(out_dir) -> dict   tune_base(scene, material, shots, target_srgb, bands, rounds, tol, damping, mask_material, band, out_dir, percent, samples, adaptive) -> (r, g, b)
turnaround(scene, rig, views=[(name, az_deg, elev_deg)], pose_fn, out_path, percent, samples, dist, lens, fstop, height, adaptive)
numbered_sequence(seq_dir, n, size)   decode_frame(rgb_linear)
```
selfcheck's out_dir and numbered_sequence's seq_dir may be relative to the cwd: both are made absolute
before any bpy path (Blender resolves a plain relative path against the drive root).

### filmkit/blender/scene_kit.py [blender-look]
```
bootstrap(project_dir, engine_dir=None) -> (project_dir, engine_dir)   load_timeline(project_dir) -> (doc, Layout)   clear_scene(scene)
build_slabs(layout, z0, z1, top_mats, side_mat, collection, bevel, pivot) -> {name: Object}
build_tiles(layout, z0, z1, mat, side_mat, collection, slabs, bevel) -> {id: Object}   (origin at the rect centre, z 0)
build_stacks(layout, z0, z1, mat, side_mat, collection, slabs, bevel=0.0) -> {(stack, id): Object}
build_screens(layout, z, sequences={name: (first_png, n_frames)}, collection, slabs, strength, spec, rough, grades) -> {name: Object}
build_sprite(name, png_path, size_ui, layout, z, collection, mat, outline, inset_px, thick=0.0025, n_cap=10) -> Object
rest_world(ob) -> Matrix   bake_states(bake, n_frames, fps, channels_fn)   camera_channels(cam_ob, state)   object_channels(ob, state)
  (camera_channels skips dof.aperture_fstop when state['fstop'] is None; the previs label then prints f/-)
summary(scene, bake_result) -> dict
```
Object names: `panel:<name>`, `tile:<id>`, `stack:<stack>:<id>`, `screen:<name>`, `sprite:<name>`,
`camera`, `light_rig`, hero parts by spec name. Children are parented with parent_keep_world, so state
functions speak rest-world coordinates while a slab falls; every built object carries ob['rest_world']
(16 floats) and ui_glow / ui_power at 1. Image paths are relative to the project folder (scene.py chdir).

### filmkit/sound/synth.py [sound, venv]
```
db mtof rng(seed) tvec ramp phase(f_hz, sr, n=None) nrm sine saw square tri fm noise env_adsr env_exp lp hp bp
sweep(x, fc_hz, sr, q, kind, block)  pan(x, p)  delay(x, sr, time_s, feedback, mix)  tanh_drive(x, drive)
click thump boing thwack whoosh bell blip riser zap chord(sr, notes_midi, dur, osc, detune_cents, cutoff_hz, attack_s, release_s)
```
Generic starters, every number an argument; all mono, peak 1, 0 on sample 0. Nobody has listened to them.

### filmkit/sound/mix.py [sound, venv]
```
seed_of(kind, n) (= ease.seed_of)
Clock(fps, sr, duration): spf n at(t) exact(t) frame_of(sample)
Bus(n, sr=48000): add(sig, start, gain_db, pan, pre, tail_ms)  peak_db()
fx_board(x, sr, *plugins)   duck_curve(times_s, n, sr, depth_db, attack_s, tau_s, place)
Dispatcher(events, handlers, clock, buses, tl, silent, stems=True, mute=()): run() -> {count, kinds, stems}; check_no_overlap(a, b)
master(mix, sr, target_lufs, window_s, ceiling_dbtp, fade_s, fade_pow, hp_hz, comp, rounds, safety) -> (out, makeup_db)
tp_limit(x, sr, ceiling_db, look_ms, release_ms)   write_wav(path, x, sr, bits=24) -> n   read_wav(path) -> (x, sr)
build(score, clock, tl, buses=("music", "fx", "verb"), mute=()) -> (out, makeup_db, stems, pre)
```
ctx (passed to handlers): `clock, buses, tl, event, seed, n, add(bus, sig, start, gain_db, pan, pre, tail_ms)`.
`mute` kinds keep an all-zero stem (the mutation check).

### filmkit/sound/soundcheck.py [sound, venv]
```
k_weight(x, sr)  block_lufs(x, sr, block_s)  integrated_lufs(x, sr)  true_peak(x, sr)
onsets(x, sr, bands, rise_db, floor_ms, refractory_ms, merge_ms) -> samples
PHONE_BAND = (300, 8000) Hz   AUDIBLE_WIN_MS = 40   AUDIBLE_BEST_MS = 5   (measurement constants)
audibility(contrib, rest, targets, sr, band, win_ms, best_ms) -> [dB | None]  (the contribution's phone-band level over
    the rest's in the best 5 ms window (1 ms hop) inside [target, target + 40 ms); None: no contribution there)
hit_table(events, mix, stems, clock, tol_ms, min_db, pre=None, rests=None) -> rows (id kind t frame target mix_ms stem_ms
    stem_db present ok audible_db)   (audible_db = audibility(pre - rests[kind], rests[kind]) with the pre-master `pre`
    and `rests` {kind: the pre-master built with that kind muted}; None without them; 'ok' never reads it)
presence(events, stems, clock, tol_ms) -> [ids]
mutation_check(build_fn(muted) -> (mix, stems[, pre]), kinds, clock, events, stems=None, pre=None, audible=None) -> {kind: caught}
determinism_check(build_fn() -> (2, n)) -> bool
contour_deltas(lufs_blocks, reference)   ffmpeg_ebur128(path) -> dict   check_png(wav, png, markers, width, tick_s, wave_color)
report(path, lufs_blocks, reference, tp_db, n_samples, n_expected, makeup_db, rows, ffmpeg, ceiling_dbtp=None, mutation=None,
       contour_lu=None, tap_ms=None, tap_kinds=("tap",), audible_db=None, audible_kinds=None) -> exit code
```
`CONTOUR: x.x LU max |K-ref| over n blocks (limit y) OK|OVER`, `TAPS: x.x ms max |mix| over n tap rows (limit y)
OK|OVER` and `AUDIBLE: x.x dB min over m/n measured rows of <kinds> (floor y) OK|UNDER` are always printed; OVER /
UNDER (a tap row without an onset, a listed row without a measured audibility) is exit 1 only when the limit is
given. Report lines: `HITS: ok/n`, `PRESENCE MISSING: k`, `TRUE PEAK: x dBTP`, `LENGTH: n OK`, one `<kind>
caught|ESCAPED` line per kind and `MUTATION: caught/n kinds caught` (`MUTATION: not run` without the dict); an
escaped kind is exit 1. The hit table carries an `aud dB` column (`none` = not measured).

The mutation check (r3-11): `mutation_check` builds once per kind with that kind muted in the MIX (its stem all
zero) and puts only its events through the hit table. Without `stems` the muted build's own stems score them, so
the zero stem fails them: that proves the stem path only, and a kind missing from the mix with its stem intact
escapes (every row finds a groove onset on its own 16th grid). With `stems` (the unmuted stems) and `pre` (the
unmuted pre-master; build_fn then returns the muted pre-master third) the muted mix is scored against the intact
stems with the muted pre-master as the rest (its contribution there is zero by construction), and the same
muted build measures the REAL audibility of every row, audibility(pre - muted pre, muted pre): caught = every
row fails on the muted build AND every row has a measured real audibility (muting the kind changed the
pre-master at each target). A kind never in the mix reads None on every row and is ESCAPED: muting it changes
nothing, so the detector could not tell the real mix from the muted one. `audible` is filled {event id: that
real dB}: `step.run` writes it into the hit table's column, fails every row that reads None (a dropped sound is
a fact, no floor needed: 'aud none NO', HITS short, exit 1) and enforces the director's floor on the rest
(`SOUND['audible_db']` over `SOUND['audible_kinds']`). The measure is the critics' (round 3): the kind over
the rest of the pre-master mix in the phone band, best 5 ms; tap-to-submit round 3 read slap2 -4.6, bump2 -9.4,
guard -4.7 dB on it. `checks/check_sound_venv.py` holds the dropped-fx-bus case (stems intact, a hi-hat groove
on the grid): thump and click ESCAPED, HITS 2/5, exit 1 with no SOUND dict.

### filmkit/sound/step.py [sound, venv]
```
run(project_dir, score, mutation=True, log=print, rules=None) -> exit code     sound_rules(project_dir) -> dict
```
`rules` (default `sound_rules`: the project's `checks_config.SOUND`, `{}` without it) = `{'contour_lu': 1.0,
'tap_ms': 5.0, 'tap_kinds': ('tap',), 'audible_db': -3.0, 'audible_kinds': [...]}`: the step exits 1 when a
block's K misses `score.REFERENCE` by more than contour_lu, a tap row's mix onset is off by more than tap_ms, or
a row of audible_kinds (default every kind) reads under audible_db (checks_config.py, the director's thresholds).
checks_config.py is therefore a stamped input of the sound step (build chain). Independent of any rule, a row
whose measured audibility is None (the kind adds nothing to the mix at its target) fails: `r['ok'] = False`, its
kind ESCAPED, exit 1.
The sound build step: `mix.build` from build/timeline.json and the score module, `write_wav`, the hit table,
block loudness vs `score.REFERENCE`, true peak vs `score.MASTER['ceiling_dbtp']`, `ffmpeg_ebur128`, the check
PNG with `MARKER_COLOURS`, then `mutation_check` over every kind that has a stem (`sorted(stems)`, scored against
the unmuted stems and pre-master, filling every row's audible_db), and `report(..., mutation=..., audible_db=...)`.
A project's `sound.py` is the thin entry `step.run(HERE, score)`; the tap-to-submit score (25 kinds, 12 s) takes
about 75 s with the mutation check. `mutation=False` skips the muted builds, so no audibility is measured and an
audible_db floor reads UNDER.

### scripts/comp-kit.mjs [node] (window.FilmKit)
```
box grow shift union inFrame(b, W, H) margin(b, W, H) pad4 timecode(seconds, fps)
makeCanvas loadFonts(faces, sample) (throws listing missing faces)
typeOnPrefixes(ctx, font, trackingPx, text, anchor, baselineOffset) -> {pen, ascent, descent, prefixes: [{text, ink, caretX}]}
makeRibbon(anchors, widthFn, n) -> {points, length, pointAt, centre, outline, box, shape, path}
drawGlow(ctx, src, k, opts) drawSelection(ctx, b, color, alpha, anchor, displayScale, sizes) drawPenHandles(...)
lumaStats(ctx, step=1) drawTimecode(spec, text) contact(urls, labels, cols, cell, labelH, gap, font)   rng smoothstep springStep
```

## 6. Tool CLIs

```
node ui-render.mjs --html build/ui.html --timeline build/timeline.json --out build
    [--modes ui.png:,ui_base.png:base,ui_check.png:check] [--sprites chip.png:chip] [--font "Segoe UI"]
    [--scale 3] [--flat comp:#000000,timecode:#232323]
  Writes the mode PNGs (temp -> rename on pass), prints sizes, font widths, contract line. Exit 1 on a violation
  (element outside its rect, a screen rect not flat, a panel/button/screen rect that differs from the timeline).

node frames-render.mjs --page comp.html --timeline build/timeline.json --out build [--pages 4]
    [--frames 1,31,61] [--api FilmPage] [--contact comp_contact.png --contact-every 15 --cols 5] [--bbox comp_bbox.json]
  Page contract: loadFonts(), init(tl), render(f) -> {seq: {name: dataURL}, bounds, luma, checks[]}, bboxes().
  window.FilmEase and window.FilmKit are injected before the page script runs (the page is a classic script).
  Bounds and drawn boxes must stay inside format.comp. Exit 1 on any check; a full run prunes stale ####.png.
  Exit 1 (temps removed) when a sequence misses any requested frame (the --frames list, else 1..n);
  export missingFrames(seqs, temps, frames, outDir) -> {seq: [f...]}.

python -B contact.py --out sheet.png --cols 6 [--cell 640x360] [--label-h 40] img.png[:label] ...
python -B contact.py --seq renders/frames --every 15 --fps 30 --out sheet.png [--cols 6] [--label "f{f} {t:.2f}s"] [--last]
python -B contact.py --strips renders/animatic --every 2 --per-sheet 60 --cols 10 --out-prefix strip

python -B encode.py --frames renders/frames --wav build/sound.wav --out renders/film.mp4 --fps 30 --n 360
    --duration 12.0 [--crf 17] [--preset slow] [--vignette PI/5] [--size 1080x1920 --fit pad|crop|scale]
    [--no-audio] [--audio-kbps 320]
  H.264 High, yuv420p, scale=trunc(iw/2)*2:trunc(ih/2)*2:out_color_matrix=bt709:out_range=tv (an odd frame size rounds
  down to even, as does an odd --size; libx264 refuses odd), setparams bt709, -colorspace/-color_primaries/-color_trc
  bt709, AAC 48 kHz, -t duration, +faststart. Refuses on a missing frame or WAV; renamed after a frame-count probe.

python -B verify_final.py --mp4 renders/film.mp4 --wav build/sound.wav --fps 30 --n 360 --duration 12.0
    [--frames-dir renders/frames] [--steps 10] [--black-below 2] [--json renders/verify.json] [--expect-size 1920x1080]
  Exit 1 when a probe value, a black frame or a non-zero audio lag fails the expectation.

python -B build.py <project_dir> [--from step] [--upto step] [--only step] [--force] [--dry]
  Steps: timeline ui comp sound blend check check_9x16 stills stills_9x16 animatic final encode verify final_9x16
  encode_9x16 verify_9x16. Env: BLENDER, CHROME,
  FILM_PYTHON (kit venv; default the kit's .venv), NODE, FILM_ENGINE. Defaults: Blender 5.2 in Program Files,
  Chrome in Program Files, node on PATH.

python -B -m filmkit.fresh <project_dir> [--require a,b] [--status]

blender -b --python-exit-code 1 film.blend -P gpu.py -P filmkit/blender/stills.py -- --frames 1,31 --out renders/stills
    [--percent 50 --samples 40 --adaptive 0.03] [--mask] [--target D97757] [--classes file.json] [--json stills.json] [--prefix f]
    [--points motion:hero_points] [--project <dir>] [--camera camera_9x16 --film 1080x1920]
  --json: a bare name lands in --out, a path with a folder is used as given. Presets come from the stored look.
  --camera: render through another camera object the scene built (the 9:16 one); --film WxH: its resolution.
  --points: the project function f(t) -> world points behind stills.json silhouette.model_w, imported from --project
  (default the parent of the .blend's folder). Objects with ob['mask_skip'] are left out of the mask render.
blender -b --python-exit-code 1 film.blend -P gpu.py -P filmkit/blender/stills.py -- --animatic --out renders/animatic [--samples 16]
blender -b --python-exit-code 1 film.blend -P gpu.py -P filmkit/blender/stills.py -- --final --out renders/frames_9x16
    [--camera camera_9x16 --film 1080x1920] [--preset final] [--percent p --samples n --adaptive a]
  --final: every frame at the look's final preset (or --preset, a name in the stored presets), persistent data on,
  like `-a` on the saved scene but through another camera and film size; the .blend is never saved (the final_9x16 step).
blender -b --python-exit-code 1 film.blend -P gpu.py -P filmkit/blender/lookdev.py -- frames 1 31 [--prop obj.prop=v] [--mat name.socket=v]
    [--light name=watts] [--grade mat:h,s,v] [--world r,g,b] [--percent 50 --samples 32] [--tag t] [--out dir] [--mask --target hex]
blender -b --python-exit-code 1 --factory-startup -P gpu.py -P filmkit/blender/lookdev.py -- selfcheck [--out dir]
blender -b --python-exit-code 1 film.blend -P gpu.py -P filmkit/blender/lookdev.py -- tune <material> --target hex [--rounds 4 --tol 2] [--frames ...]
blender -b --python-exit-code 1 film.blend -P gpu.py -P filmkit/blender/lookdev.py -- turnaround [--out dir] [--root name --dist m --lens mm]
blender -b --python-exit-code 1 film.blend -P gpu.py [-s A -e B] -a            final or partial render (persistent data on)

python -B checks/run_checks.py [--only name] [--python <kit venv python>]
  Runs every checks/check_*.py; PASS/FAIL per check; exit 1 on any fail; *_venv.py need --python (a relative
  path is taken from the caller's cwd, so `--python .venv/Scripts/python.exe` from the kit root works; a
  --python that does not exist prints one line and exits 2). Children get PYTHONDONTWRITEBYTECODE=1 and -B.
```

Tool paths: engine code reads env `BLENDER` (default `C:/Program Files/Blender Foundation/Blender 5.2/blender.exe`),
`CHROME` (default `C:/Program Files/Google/Chrome/Application/chrome.exe`), `FILM_PYTHON` (kit venv), `NODE`.
puppeteer-core resolves from the kit's node_modules. GPU test renders stay tiny: <= 320x180, <= 8 samples,
a few frames.

## 7. The template project (`templates/project`)

The scaffold is the grey-box fixture that proved the chain: 2.0 s, 30 fps, 120 BPM, a 1280x720 film of a
640x360 UI (texture scale 2), two panels, two buttons, one 480x270 result screen showing a counter, a grey
toy from `hero_spec.py` that hops onto button A at beat 1 and button B at beat 2, a 2-hold shot list with
an eased crossing, three check rules (hero_margin, hero_width, landings), one click per landing over a
chord bed, a 3-light grey look, mask classes body/eyes/studio. Every render preset is tiny (25 %, 4-8
samples) so the whole chain runs in about 40 s on the shared GPU; a real film sets its own presets.

Every line a director decides carries `# TASTE:` (JS: `// TASTE:`). The mechanical entries (scene.py,
sound.py, check_model.py, build.py) carry none. `python -B build.py` from a copy runs the whole chain;
`checks/check_template.py` runs its Python half (timeline with and without a film.json, check_model,
dry run, stale refusal) on every `run_checks.py` pass. Keep the project path short (section 1).

`timeline.py` reads `film.json` next to it when present (`new-video --kind film --size WxH --fps N`
writes `width`, `height`, `fps`, whole numbers; a fractional one raises): the film size and the fps come
from there, the scaffold's 1280x720 at 30 fps stand without it. The beat sheet stays on 120 BPM, so an fps whose sixteenth is not a whole number
of frames fails `EVENTS.validate` until the director moves the landings (the message names them).
`build.json` carries `"points": "motion:hero_points"`, so the scaffold's stills.json fills `model_w`.
