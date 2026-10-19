---
name: deliver
description: Deliver a finished video to the outbox. Use when a final render is approved, the user says "entregar", "listo" or "final", or an editing skill reaches its last step. Enforces the delivery contract in kit.config.json.
---

# Deliver

The outbox is the end of every project.

## 1. Final render

A reviewed final exists in `video-projects/<id>/renders/` and `VERIFY.md`
records the review. Otherwise return to the editing skill.

## 2. Cover

`compositions/cover.html`: one frame at the project's width and height. The
hero still (`ffmpeg -ss <t> -i <render> -frames:v 1 cover-frame.png`), the hook
sentence in the brand's `--font-display`, logo bottom-right, brand tokens only.
Render to `renders/cover.png` (`npx hyperframes render --format png`, or frame 0
of a 1-second render).

Done when `renders/cover.png` opens and the hook text is readable at phone size.

## 3. Caption and subtitles

- `renders/caption.txt`: hook line, one or two lines of body, 3 to 5 hashtags,
  in the brand's language. Emoji only when the brand's `DESIGN.md` allows them.
- `renders/subtitles.srt`: from the retimed transcript of the final cut, at most
  5 words per line, matching the on-screen captions.

Both ship unless the user drops one. Say which extras were dropped.

## 4. Hearing check

You cannot listen; this script is the ear.

```sh
node scripts/hearing-check.mjs <project-id> --video renders/final.mp4 --srt renders/subtitles.srt
```

Read `HEARING.md`. `PASS` goes on. `FAIL` means a caption does not match what
was said, or a cut lands inside a word: fix the cut or the SRT and re-render.
A steady offset above 1 s is Whisper drift under music; note it in `VERIFY.md`
and tell the user to listen to the first 5 s once.

## 5. Deliver

```sh
node scripts/deliver.mjs <project-id> --video renders/final.mp4 --cover renders/cover.png --caption renders/caption.txt --srt renders/subtitles.srt
```

One run per deliverable (`--name <name>`) when a project ships several cuts.

Done when the script prints the outbox path and `project.json` `status` is
`delivered`.

## 6. Close

`npm run projects`. Tell the user the outbox path and the file names.
The files stay in the outbox; publishing is the user's step.
