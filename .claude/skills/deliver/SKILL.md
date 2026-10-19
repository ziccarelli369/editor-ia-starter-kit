---
name: deliver
description: Put a finished video in the outbox. Use when a render is approved, the user says "entregar", "listo", "final", or any editing skill reaches its final render. Enforces the delivery contract from kit.config.json: video and cover required, caption and srt by default.
---

# Deliver

The outbox is the end of every project. Nothing leaves the kit any other way.

## 1. Final render

The final render must already exist in `video-projects/<id>/renders/` and must
have been reviewed by the user (see `VERIFY.md`). If not, stop and go back to
the editing skill. A lint pass is not a review.

## 2. Cover

Build a one-frame HyperFrames composition `compositions/cover.html` at the
project's width and height: the hero frame (a still from the render, extracted
with `ffmpeg -ss <t> -i <render> -frames:v 1 cover-frame.png`) plus the hook
sentence in the brand's `--font-display`, logo bottom-right, brand tokens only.
Render it to `renders/cover.png` with `npx hyperframes render --format png`
or by extracting frame 0 of a 1-second render.

## 3. Caption and subtitles

- `renders/caption.txt`: the post text in the brand's language. Hook line first,
  then one or two lines, then 3 to 5 hashtags. No emoji unless the brand says so.
- `renders/subtitles.srt`: from the retimed transcript of the final cut. Lines of
  at most 5 words, matching the on-screen captions.

Skip an extra only if the user says so. Say which extras were skipped.

## 4. Deliver

```sh
node scripts/deliver.mjs <project-id> --video renders/final.mp4 --cover renders/cover.png --caption renders/caption.txt --srt renders/subtitles.srt
```

For more than one deliverable (for example a 9:16 and a 16:9 cut), run it once
per deliverable with `--name <name>`.

## 5. Close

Run `npm run projects`. Tell the user the outbox path and the file names.
Never upload, post or send anything.
