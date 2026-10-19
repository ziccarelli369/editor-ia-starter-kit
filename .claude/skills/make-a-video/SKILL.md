---
name: make-a-video
description: Motion-graphics video from a brief, no footage. Use when the user brings a concept, script, or outline and wants a finished MP4, or when new-video routes a brief-only project here. Runs a one-pass interview, then a gated build.
---

# Make a Video

Two phases, eight gates, in order. A gate stays open until its **bound**
holds.

**Done means:** `renders/<slug>-final.mp4` exists, the user signed off on the
draft MP4, and the `deliver` skill has put the final in the outbox.

## Routes

- The input is a URL: load `website-to-hyperframes`.
- The brief is a 9:16 talking head with face-cam and scene overlays: run Gates
  1-4 here, then hand `BRIEF.md` to `short-form-edit` at Gate 5.
- The user wants framework rules, not a video: load `hyperframes`.

Sound, music, stills and B-roll need no paid service. Without `KIE_API_KEY` or
`ELEVENLABS_API_KEY`, they are motion graphics you design in HyperFrames; say
so when you fall back.

## Phase 1 · Interview (Gates 1-4)

Ask one question per `AskUserQuestion` call, from the question bank in
[interview-questions.md](references/interview-questions.md). Read it before
Gate 1; it holds every option and the sequencing rules.

### Gate 1 · Intent and format

Ask Q1-Q6: purpose, audience, duration, aspect ratio, frame rate (30
default), and delivery constraints.

**Bound:** all six answers captured. A 9:16 face-cam answer marks the
`short-form-edit` route.

### Gate 2 · Script and voice

Ask Q7-Q10: script source, TTS voice and pace (offer voices from
`npx hyperframes tts --help`), face-cam path and placement, and caption style.

**Bound:** a script or outline exists, and the audio plan and the caption plan
are written down.

### Gate 3 · Style intake

Inventory first: `node scripts/inbox.mjs`, the project's `raw/` and `assets/`
if it exists, and `brands/<brand>/`. Name what you found and ask only for what is missing.

Then ask Q11-Q20: style guide, palette, fonts, logo, reference videos, other
assets, aesthetic, pacing, music level, and outro CTA.

The user's style wins, then the project's brand, then the MOTION_PHILOSOPHY
defaults. Use a default only for a question the user declined, and flag each
default in the brief. The decision tree and the defaults are in
[style-intake.md](references/style-intake.md).

**Bound:** each of the ten questions has an answer, a found asset, or a flagged
default.

### Gate 4 · Brief (hard gate)

1. Read `MOTION_PHILOSOPHY.md`.
2. If the project does not exist yet, create it:
   `npm run new-video -- <slug> --brand <brand> --mode guided`. It lives at
   `video-projects/<yyyy-mm-dd>-<slug>/`; that folder is the project folder.
3. Write `<project-folder>/BRIEF.md`: slug, intent, audience, dimensions, fps,
   duration, script, voice, captions, face-cam plan, style profile (palette
   hex, fonts, logo path, reference videos), pacing, asset inventory with
   paths, and outro CTA.
4. Show the brief and wait.

**Bound:** every field in step 3 is filled, and the user said "yes, build it"
in chat.

## Phase 2 · Build (Gates 5-8)

### Gate 5 · Scaffold and storyboard

1. On the face-cam route, hand off to `short-form-edit` now.
2. Set the slug, dimensions and fps in `meta.json`.
3. Copy the supplied assets into `<project-folder>/assets/`.
4. Write `assets/style-profile.md` from Gate 3: the one source for palette,
   fonts and logo.
5. Write `STORYBOARD.md` from
   [storyboard-template.md](references/storyboard-template.md): a timing table,
   then one block per beat with its visuals, motion, 3-4 eases, exit and audio.
   Use three acts: hook about 20%, body about 55%, payoff about 25% with a 4-6
   second outro hold.
6. Map each beat to catalog blocks with
   [catalog-intent-map.md](references/catalog-intent-map.md).

**Bound:** every beat has all six fields, the acts sum to the duration, and the
user approved the storyboard.

### Gate 6 · Compositions

Load `hyperframes` for framework rules. Start every sub-composition from
[composition-scaffold.md](references/composition-scaffold.md): scoped CSS, an
IIFE GSAP timeline registered on `window.__timelines`, and the anchor tween
`tl.to({}, { duration: SLOT_DURATION }, 0)` (MOTION_PHILOSOPHY Law 11).

- Put an ambient background on `data-track-index="0"` for the full duration.
- Stagger kinetic-type openers per word, 0.06-0.10s.
- Mount captions as body-level siblings in `index.html`, each on
  `data-track-index` 20 or higher.
- Install catalog blocks with `npx hyperframes add <name>`, then scope their
  `html, body` CSS under `[data-composition-id="..."]`.
- Apply only the palette, fonts and logo in `style-profile.md`.
- Make render logic deterministic: seeded hashes for every random value, and
  all data inlined before render (MOTION_PHILOSOPHY §3.10).
- On a 9:16 face-cam build, see the vertical face-cam section of the scaffold.

**Bound:** one file per storyboard beat, each with the anchor tween.

### Gate 7 · Preview gate 1: Studio

1. Run `node scripts/preflight.mjs <project>` and `npx hyperframes lint`. Fix
   every error; list the warnings you keep.
2. Start `npx hyperframes preview` in the background and wait for "Studio
   running" on `http://localhost:3002`.
3. Give the user that URL and each composition URL
   (`http://localhost:3002/?comp=<id>`). With WebGL shader blocks, lead with
   the composition URLs; the software fallback can stall the master.

**Bound:** lint shows 0 errors, and the user said "render a draft" in chat.
Silence is not approval.

### Gate 8 · Draft, verify, preview gate 2, final

1. `npx hyperframes render --quality draft --output renders/<slug>-draft.mp4`
2. Extract one frame per beat hero moment and one per transition:
   `ffmpeg -y -ss <t> -i renders/<slug>-draft.mp4 -frames:v 1 -q:v 2 renders/frames/t<t>.png`
3. Open every PNG with the `Read` tool and check it against the visual
   verification list in [build-checklist.md](references/build-checklist.md).
   Fix, re-render and re-check until every frame passes. Record what you saw
   in `VERIFY.md`.
4. Serve with `npx serve renders -p 8080 -n`; it supports the range requests
   that scrubbing needs. Give the user `http://localhost:8080/<slug>-draft.mp4`
   and wait for sign-off on playback and audio sync.
5. `npx hyperframes render --quality standard --output renders/<slug>-final.mp4`
6. Load `deliver`.

**Bound:** every extracted frame passes step 3, the user signed off in chat,
and the final is in the outbox.

## Guardrails

- Run both preview gates on every build: Studio, then the rendered MP4.
- Call a render done only after you opened its frames with `Read`.
- Build inside the project folder; `index.html` never sits at the kit root.
- Keep `<video>` tags free of `class="clip"`; it breaks them.
