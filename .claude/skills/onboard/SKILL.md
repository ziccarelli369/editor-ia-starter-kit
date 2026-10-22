---
name: onboard
description: First-run onboarding. Use on a fresh install, when the user says "primera vez", "instalar", "configurar", /onboard, or when node_modules or .env is missing. Checks the machine, fills kit.config.json and the first brand, creates no project.
---

# Onboard

Speak in the user's language. Create no project, no example, no render.

## 1. Check the machine

```sh
node scripts/setup.mjs
```

Read the lines marked FALTA (missing). For each, give the user the one install
step from `docs/SETUP.md` and wait until they say it is done; run the check
again. Then:

```sh
npx hyperframes doctor
```

Done when `setup.mjs` prints "Todo listo" and doctor shows Node, FFmpeg and
Chrome green.

## 2. Two languages

Ask two questions, one message:
- In which language should I talk to you? (`language`: `es` or `en`)
- In which language is your footage? (`transcription.languages`: `["es"]`,
  `["en"]` or `["en","es"]`)

Write both to `kit.config.json`. Done when the file holds the answers.

## 3. Transcription

If `.env` has `ELEVENLABS_API_KEY`, keep `provider: elevenlabs` (measured word
times, a few cents per video). If not, set `provider: whisper` and confirm
whisper.cpp is found; otherwise walk them through `docs/SETUP.md` step 3.

## 4. First brand

Copy `brands/_template/` to `brands/<slug>/` and fill `DESIGN.md` and
`tokens.css` from four answers: brand name, two colors (background, accent),
one display font, audience in one line. For a gym or a service, also fill the
Offer section (place, schedule, offer, how to start, proof).
If `brands/<slug>/` already exists, ask whether it is the same client before
touching it.

Done when `brands/<slug>/DESIGN.md` has no placeholder text left.

## 5. Optional: 3D character films

Ask once: do you want 3D character films (`character-film`)? They are heavy:
Blender 5.x, a GPU that Cycles supports, Python 3.10+, about 5 GB per film and
about 11 min of GPU render per 12 s. If no, skip to step 6.

If yes, name the downloads: Python packages about 35-65 MB (about 230 MB on
disk), Blender about 350-400 MB (about 900 MB installed). After the user's yes:

```sh
npm run film:install
npm run setup -- --film
```

The user installs Blender from https://www.blender.org/download/; you never
install it. Done when `setup -- --film` prints "DOCTOR: ok".

## 6. Hand over

Say: drop a video in `inbox/`, then type `/new-video`. Nothing else.
