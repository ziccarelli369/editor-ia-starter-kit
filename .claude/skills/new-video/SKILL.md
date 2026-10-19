---
name: new-video
description: The front door of the kit. Use when the user wants to make a video, reel, Short, or says "nuevo video", "quiero hacer un video", or /new-video. Creates the project, assigns inbox footage, picks the brand, and routes to guided or freeform mode.
---

# New video

Read `kit.config.json` first. Speak in its `language`.

## 1. Mode

Ask one question: **guided** or **freeform**.

- Guided: the known path. Nate's playbook, the short-form gates, the validators.
  Recommend it to anyone making their first videos with the kit.
- Freeform: no workflow, no gates. The user drives and you suggest. Same tools,
  same delivery contract at the end.

If the user already said which, do not ask.

## 2. Brand

List `brands/` (skip `_template` unless it is the only one). Ask which brand this
project is for. If the brand does not exist, copy `brands/_template/` to
`brands/<slug>/` and ask the user for name, colors and fonts before continuing.
From here, read only that brand's folder.

## 3. Project

Run `npm run new-video -- <slug> --brand <brand> --mode <mode>`. Pick the slug
from the user's one-line description: lowercase, kebab-case, 2 to 4 words.

## 4. Footage

Run `node scripts/inbox.mjs`. Show the list. Propose which files belong to this
project and which stay. Move only after the user says yes:
`node scripts/inbox.mjs <project-id> <file> [<file>...]`.
If the inbox is empty, ask the user to drop the footage in `inbox/` and stop.

## 5. Brief

Write `video-projects/<project-id>/DESIGN.md` with: goal, audience, platform,
length target, hook idea, CTA, the brand, and the style (if the user names one
from `styles/core/` or `styles/drafts/`). Set `style` in `project.json`.
Update `project.json` `status` to `briefed`. Run `npm run projects`.

## 6. Route

- Guided, footage of a person talking, short: load `short-form-edit`.
- Guided, long recording: load `edit-video`.
- Guided, no footage, a brief only: load `make-a-video`.
- Guided, a website: load `website-to-hyperframes`.
- A style was chosen: load `apply-style` before the editing skill.
- Freeform: ask what the user wants to try first. Suggest two concrete options.
  Load skills as needed. Keep every file inside the project folder.

Every path ends with the `deliver` skill. Never skip it.

## Model profile

If `models.profile` is `team`, you (Opus) decide and design. Hand Haiku 5.5
subagents only mechanical jobs: transcription runs, ffprobe, validators,
contact sheets, file moves. Never a cut decision, never a design choice.
