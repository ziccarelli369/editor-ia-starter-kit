# Setup and troubleshooting

Short version for a first run: `docs/ONBOARDING.md`.

Start with [tools, accounts, and API keys](TOOLS-AND-API-KEYS.md) for the kit's
local Whisper default, the optional ElevenLabs and Kie.ai paths, and optional services.

## Install

1. Install Node 22+ (required by the pinned HyperFrames CLI).
2. Install FFmpeg with ffprobe. On Windows, reopen your terminal after you
   install FFmpeg to refresh PATH.
3. Install whisper.cpp for free local transcription: on Windows download
   `whisper-blas-bin-x64.zip` from release v1.8.3 at
   https://github.com/ggml-org/whisper.cpp/releases (the newest releases ship
   no Windows build), unzip it and add the `Release` folder to PATH; on macOS
   `brew install whisper-cpp`; on Linux build it from source per its README
   (`cmake -B build && cmake --build build -j --config Release`, binary in
   `build/bin/whisper-cli`) or install your distro's package if it has one.
   Or set `HYPERFRAMES_WHISPER_PATH` to the `whisper-cli` binary.
4. Run `npm install` in the repository root.
5. Run `npm run setup`. It checks the core tools, creates `.env` from
   `.env.example` when `.env` is missing, and prints one optional line for the film path.
6. Run `npx hyperframes doctor`. It reports Node, FFmpeg, Chrome and whisper-cpp.
   If Chromium is unavailable, follow `npx hyperframes browser --help`.
7. In `.env`, fill only the keys your chosen services need.
8. Open `kit.config.json` and set two languages: `language` (how the agent talks
   to you, `es` or `en`) and `transcription.languages` (what your footage is in:
   `["en"]`, `["es"]`, or `["en", "es"]` if you record in both). The agent asks
   these on its first run if you skip this step.

The repository pins HyperFrames 0.7.109 and GSAP 3.14.2. Keep package-lock.json
with package.json. Upgrade deliberately, then repeat the render checks.

## Film path (optional)

The 3D character film (`character-film`) is optional and heavy. The short-form
path needs none of these tools. You need:

- Blender 5.x: https://www.blender.org/download/
- A GPU that Cycles supports: NVIDIA (OptiX or CUDA), AMD (HIP), Apple Silicon
  (Metal) or Intel Arc (oneAPI).
- Python 3.10+: https://www.python.org/downloads/
- About 5 GB of free disk per film.

Measured on one machine: a 12 s film at 1080p rendered in about 11 minutes on
an RTX 5070 Ti.

Install it once:

1. Install Blender 5.x.
2. Run `npm install` (it installs puppeteer-core; Chrome renders the UI texture).
3. Run `npm run film:install`. It creates `.venv` in the kit root with Python
   3.10+ and installs `.claude/skills/film-engine/requirements.txt` (numpy, scipy,
   pedalboard, Pillow). Then it runs the film check and prints an install hint
   for each item that still fails. It never installs Blender or Chrome.
4. Run `npm run setup -- --film`. It runs the core check and the film check
   (`doctor.py`). The film check prints one `ok`, `warn` or `FAIL` line per
   tool, and each `FAIL` line ends with a fix after `→`. The command exits 1
   on any `FAIL`.

`npm run new-video -- <slug> --kind film` runs the same film check before it
creates anything. On a failure it prints the `FAIL` lines and the install steps,
and stops. `--skip-doctor` creates the project anyway; it cannot render until
the check passes. For a film project, `node scripts/preflight.mjs <project>`
runs the film check and the build dry run, which lists the stale steps.

`.venv/` stays out of Git.

### Tool discovery

The engine looks for each tool in this order:

1. The environment variable: `BLENDER` for the Blender binary, `CHROME` for
   Chrome or Chromium.
2. The default install folder for your OS (Windows, macOS or Linux).
3. `PATH`.

Set `BLENDER` or `CHROME` when the tool is in another folder.

### GPU device

`CYCLES_DEVICE` sets the Cycles device. When it is not set (the default), the
engine uses the first kind that has a device, in this order: OptiX, CUDA, HIP,
Metal, oneAPI. `CYCLES_DEVICE=CPU` renders on the CPU. Use it only when you
have no supported GPU: it is many times slower, and the engine prints a warning.
The engine never moves to the CPU on its own.

## Projects and skills

`npm run new-video -- <slug> --brand <brand> --mode guided|freeform` creates
`video-projects/<yyyy-mm-dd>-<slug>/` with the 9:16 starter, local GSAP, the
brand tokens and a `project.json`. Existing project names are refused so nothing is
overwritten. Replace the starter with your recording and planned compositions.
The left glass template needs your own `assets/source.mp4` with an audio stream.

Create projects in the main checkout of the kit, not in a git worktree.
`video-projects/` and `outbox/` are git-ignored, so removing a worktree deletes
the projects in it. `new-video` and `deliver` refuse inside a linked worktree and
name the main checkout. `--allow-worktree` overrides that.

On Windows, a running process locks a folder that it holds open, for example a
log monitor that an agent did not stop. Before you move or archive a project
folder, run `npm run unlock -- <project-id>`. It lists the processes whose
command line names the folder. Add `--stop` to stop them.

Claude Code reads CLAUDE.md and `.claude/skills/`. It needs no special
MCP server for local editing. The root `npm run check` validates the distribution;
it does not lint personal work under video-projects.

To update a skill, edit `.claude/skills/<name>/`, then run `npm run check`.

## Troubleshooting

Scribe errors: a 401 generally means invalid authentication; a 403 can mean
missing speech_to_text access. Check the key's permissions without printing it.
No key is required for `npm test`, local Whisper transcription, starter preview,
or starter rendering.
For speech-free sources, supply a separate audio track before using the cutting
renderers: they expect one video stream and one audio stream.
