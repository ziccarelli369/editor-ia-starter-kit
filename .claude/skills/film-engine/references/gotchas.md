# Engine gotchas

Each item cost the reference film or the engine build time. The fix is already in the engine unless the
item says "project". Production rules (ownership, the critic loop) are in
`character-film/references/production-rules.md`.

## Blender 5.2

- No `scene.node_tree` and no Composite node. The compositor is a CompositorNodeTree group assigned to
  `scene.compositing_node_group`, with an Image output socket made by `interface.new_socket` and wired
  into NodeGroupOutput. Glare type, quality and size are input sockets. Do not set `use_nodes`.
- AgX looks carry a prefix ("AgX - Punchy"). Light ray visibility is on the object (`visible_glossy`).
  The Attribute node's output is "Factor".
- Layered actions: reach an F-curve through the slot's channelbag (`bake.fcurve`).
- The GPU device is a user preference, not part of the .blend: pass `-P gpu.py` on every render. It picks
  the first kind with a device (OPTIX, CUDA, HIP, METAL, ONEAPI) and turns the other kinds off, so an AMD
  iGPU next to an NVIDIA card never joins the render. `CYCLES_DEVICE=CPU` is the only CPU path.
- A raise inside a `render_init` handler does not stop the render (Blender prints it and renders on);
  `sys.exit(1)` inside the handler does. gpu.py's render guard uses that.
- Stills rendered out of order with persistent data on lose keyed state (shards vanished). Stills: persistent
  data off, `frame_set` on the context scene. A second scene rendered with `render(scene=...)` keeps image
  sequences on frame 1. Never save the .blend after a stills or lookdev run.
- A relative render path resolves against the DRIVE ROOT, not the project (a stills run wrote to
  `C:\renders\`). The engine now refuses: every bpy write goes through `render.safe_out` (absolute, inside
  the project folder, else a ValueError) and gpu.py exits 1 before any render whose path is relative,
  has no drive or sits at a drive root. Project: pass paths relative to the project folder or absolute
  inside it; `//`-relative render paths stay with the .blend.
- Blender fails past about 240 characters of path. Project: keep `video-projects/<id>/` short; a deep
  scratch folder needs a directory junction.
- Blender writes `__pycache__` next to every module it imports: every entry starts with
  `sys.dont_write_bytecode = True` (the kit check fails on any .pyc).

## Colour and light

- AgX needs a deeper, more saturated base than the hex suggests. Solve the base colour by measurement
  (`lookdev tune`); never trust the hex.
- Bloom the Emission pass only; blooming the beauty tints black details and washes out the brand colour.
- Grade an emissive screen on camera rays only, so its spill on the hero stays true.
- Glossy screens mirror big area lights as white blocks: only the key is glossy-visible; fade the specular
  with the panel's power so a tumbling slab stops mirroring the key.
- The world is near-black to camera rays only, so a new heading never sees the studio's open side.
- The MP4 vignette darkens off-centre colours by about 27 %: measure colour on the decoded MP4 too.

## Time and sound

- Python `round()` rounds halves to even: `frame(t) = floor(t*fps + 0.5) + 1` everywhere.
- At 30 fps pick BPM = 450/k (150, 112.5, 90) so a sixteenth is whole frames; 120 BPM puts eighths on
  half frames.
- A hit check that only times onsets passes with sounds missing: the hit table proves presence per kind,
  the mutation check silences each kind once, and a row whose kind adds nothing to the mix (stem intact,
  bus dropped) fails on its audibility (`none`), floor or not.
- After a `timeline.py` change, rebuild everything downstream (`build.py` refuses stale inputs).

## Tools and platforms

- Blender and Chrome: env `BLENDER` / `CHROME` first, then the install folders of this OS (Windows
  `Program Files`, macOS `/Applications`, Linux PATH and snap), then PATH (`filmkit/tools.py`,
  `tool-paths.mjs`). When nothing is found the doctor names the first place it looked. Never hard-code
  a tool path in engine code, a template or a check.
- `python -B scripts/doctor.py` (or `npm run setup -- --film`) says what is installed; every FAIL line
  carries a fix hint after `→`, and a warn says when the kit root has under 10 GB free (a finished film
  took 5.2 GB).
- scipy, pedalboard and Pillow live in the kit `.venv` (`npm run film:install`); system Python may have
  numpy only. Blender's Python is separate (3.13): modules it imports are standard library only.
- Printing reports with non-ASCII characters crashes a cp1252 Windows console: set
  `PYTHONIOENCODING=utf-8` (doctor.py reconfigures its own stdout).
- ffmpeg `drawtext` segfaults on the Windows build (no fontconfig): label contact sheets with Pillow.
- puppeteer has no bundled browser: puppeteer-core with the system Chrome, launched with
  `--force-color-profile=srgb --hide-scrollbars --font-render-hinting=none`. Prove every font face before
  the first frame; a silent fallback is a failure.
- A `.js` file with `import` fails the kit's syntax check (the package is CommonJS): engine JS is `.mjs`.
  A workflow script ends with a top-level `return`, so it is saved as `.workflow`, not `.mjs`.
- `pdftotext -layout` reads a PDF brief; the Read tool needs poppler for page images.
- A workflow's task notification truncates results: read the run's `journal.jsonl`, one result per agent.
- An agent that writes one giant response hits the output limit and dies: tell large-file authors to write
  in parts of about 300 lines.

## GPU and time

- Render times measured while other agents use the GPU are about 5x too high. Check `nvidia-smi` first.
- Idle RTX 5070 Ti, 1080p, 64 samples, OIDN: about 1.8 s a frame (11 min for 360 frames). Animation
  renders with persistent data on are about 37 % faster per frame after frame 1.
- Never write `build/` sequences while a Blender render reads them: frame 356 rendered with a black screen.
