# Setup and troubleshooting

Short version for a first run: `docs/ONBOARDING.md`.

Start with [tools, accounts, and API keys](TOOLS-AND-API-KEYS.md) for the kit's
local Whisper default, the optional ElevenLabs and Kie.ai paths, and optional services.

## Install

1. Install Node 22+ (required by the pinned HyperFrames CLI).
2. Install FFmpeg with ffprobe. On Windows, reopen your terminal after you
   install FFmpeg to refresh PATH.
3. Install whisper.cpp for free local transcription: on Windows download
   `whisper-bin-x64.zip` from https://github.com/ggml-org/whisper.cpp/releases,
   unzip it and add the folder to PATH; on macOS `brew install whisper-cpp`.
   Or set `HYPERFRAMES_WHISPER_PATH` to the `whisper-cli` binary. Recent whisper.cpp
   releases ship no Windows build; v1.8.3 does (`whisper-blas-bin-x64.zip`).
4. Run `npm install` in the repository root.
5. Run `npx hyperframes doctor`. It reports Node, FFmpeg, Chrome and whisper-cpp.
   If Chromium is unavailable, follow `npx hyperframes browser --help`.
6. Copy `.env.example` to `.env`. Fill only the keys your chosen services need.
7. Open `kit.config.json` and set two languages: `language` (how the agent talks
   to you, `es` or `en`) and `transcription.languages` (what your footage is in:
   `["en"]`, `["es"]`, or `["en", "es"]` if you record in both). The agent asks
   these on its first run if you skip this step.

The repository pins HyperFrames 0.7.109 and GSAP 3.14.2. Keep package-lock.json
with package.json. Upgrade deliberately, then repeat the render checks.

## Film path (optional)

The 3D character film (`character-film`) needs more tools. Install them once:

1. Install Blender 5.x. If Blender is not in its default folder, set `BLENDER`
   to the `blender` binary.
2. In the repository root, run `python -m venv .venv`.
3. Install the four packages into the venv:
   `.venv/Scripts/python -m pip install numpy scipy pedalboard Pillow`
   (on macOS and Linux, `.venv/bin/python`).
4. Run `npm install` (it installs puppeteer-core; Chrome renders the UI texture).
5. Run `python -B .claude/skills/film-engine/scripts/doctor.py`. It prints one
   ok or FAIL line for Blender with a GPU device, Chrome, Node, ffmpeg and the venv.

`.venv/` stays out of Git. Cycles renders on the GPU; a 12 s film at 1080p
takes about 11 minutes on an RTX 5070 Ti.

## Projects and skills

`npm run new-video -- <slug> --brand <brand> --mode guided|freeform` creates
`video-projects/<yyyy-mm-dd>-<slug>/` with the 9:16 starter, local GSAP, the
brand tokens and a `project.json`. Existing project names are refused so nothing is
overwritten. Replace the starter with your recording and planned compositions.
The left glass template needs your own `assets/source.mp4` with an audio stream.

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
