---
name: new-video
description: Front door for every video. Use when the user wants a video, reel or Short made, says "nuevo video" or /new-video, or drops footage in inbox/. Picks mode, brand and footage, creates the project, then routes to the editing skill.
---

# New video

Read `kit.config.json`. Speak in its `language`.

## 1. Mode

Ask one question when the user has not said: **guided** or **freeform**.

- Guided: the editing playbook, the short-form gates, the validators. The
  recommendation for anyone's first videos with the kit.
- Freeform: no workflow, no gates. The user drives and you suggest. Same tools,
  same delivery at the end.

Done when `mode` is known.

## 2. Brand

List `brands/` (hide `_template` when another brand exists) and ask which one.
For a new brand, copy `brands/_template/` to `brands/<slug>/` and collect name,
colors and fonts into its `DESIGN.md` and `tokens.css`. When `brands/<slug>/`
already exists, ask whether it is the same client; two clients never share a
folder, so a second one gets a different slug.
From here, read only that brand's folder.

Done when `brands/<slug>/DESIGN.md` and `tokens.css` hold the user's values.

## 3. Project

`npm run new-video -- <slug> --brand <brand> --mode <mode>`. Slug from the
user's one-line description: lowercase kebab-case, 2 to 4 words. For a 3D
character film, add `--kind film --size <WxH> --fps <n>` (`--brand none` is
allowed: the film's BRAND block lives in its `DESIGN.md`).

Done when the command prints the project id.

## 4. Footage

`node scripts/inbox.mjs` and show the list. Propose which files belong to this
project. After the user's yes:
`node scripts/inbox.mjs <project-id> <file> [<file>...]`.
Empty inbox: ask the user to drop footage in `inbox/` and stop here. A
character film needs no footage: skip this step.

Done when every approved file sits in `assets/` and is listed in `project.json` `sources`.

## 5. Goal

Ask once when `project.json` `goal` is empty: for the user's own account
(`personal`), to sell classes or a service (`sell`), or to grow the account
(`grow`). Write it to `project.json`. For `sell`, the brand's `DESIGN.md`
must have its Offer section filled; collect the missing lines now.
Hooks and CTAs per goal: `.claude/skills/short-form-edit/references/goals.md`.

## 6. Brief

Write `video-projects/<project-id>/DESIGN.md`: goal and its CTA, audience, platform, length
target, hook idea, CTA, brand, and style (a folder under `styles/core/` or
`styles/drafts/`, when the user names one; set `style` in `project.json`).
Set `status` to `briefed`. Run `npm run projects`.

Done when every field above has a value the user confirmed.

## 7. Route

| Situation | Load |
| --- | --- |
| Guided, a person talking, short | `short-form-edit` |
| Guided, long recording | `edit-video` |
| Guided, brief only, no footage | `make-a-video` |
| Guided, a website | `website-to-hyperframes` |
| A 3D character film: a toy hero builds the video inside a software UI | `character-film` |
| A style is set | `apply-style` first, then the row above |
| Freeform | Offer two concrete first moves, then load skills as needed |

Every route ends in `deliver`.

## Team profile

When `models.profile` is `team`, you (Opus) decide and design. Haiku 5.5
subagents take mechanical jobs only: transcription runs, ffprobe, validators,
contact sheets, file moves.
