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

## 4. Sync, align, then hear

First, the render itself: does the picture show and the sound play what the
edit list says, together? One probe per shot, a second after each cut, as
`reelTime:sourceTime` pairs from your EDL:

```sh
node scripts/av-sync-check.mjs <project-id> --source <source video> --probes 1.0:58.75,9.0:66.75,...
```

`AVSYNC.md` must say PASS for every full-bleed shot. A deliberate voice-over
(sound from one moment, picture from another) and a square-window layout are
known exceptions: record the probe and a direct frame match in `VERIFY.md`. A PICTURE_OFF_EDL flag means the video was cut on
a keyframe, not on the frame: re-cut that shot with `-ss` before `-i` and
re-encode, never stream-copy. An AV_OFFSET flag means audio and video were
cut from different places: cut both from the same EDL numbers.

Caption times: Scribe word starts are the base (`npm run transcribe`). The
waveform aligner is the check:

```sh
node scripts/align-captions.mjs <project-id> --srt renders/subtitles.srt --audio renders/final.mp4
```

It snaps a cue to a measured voice onset within 0.2 s and prints each shift.
A shift above 0.15 s means the Scribe time and the waveform disagree: look at
that word (a soft first word stays on the Scribe time). Apply accepted shifts
to the on-screen captions too (they share the timing map), re-render, and use
`renders/subtitles.aligned.srt` as the SRT.
Then the ear:

```sh
node scripts/hearing-check.mjs <project-id> --video renders/final.mp4 --srt renders/subtitles.aligned.srt
```

Read `HEARING.md`. `PASS` goes on. MISMATCH means the caption text is not what
was said: fix the text. When the user has confirmed a line by ear and Whisper
still hears it differently, put the exact cue text in `VERIFIED.json` in the
project folder; the ear outranks the transcriber. CUT_IN_WORD means a cut lands
on speech: move the cut. LATE/EARLY after alignment means an on-screen caption
was not re-timed.

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
