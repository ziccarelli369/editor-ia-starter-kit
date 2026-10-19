---
name: motion-showreel
description: Motion showreel or brand reel, 10-30 seconds, one motif pushed through labeled craft chapters and cut to a 120-130 BPM grid. Use when asked for a showreel, sizzle reel or brand intro cut to music, or to study a reference reel and rebuild its energy.
---

# Motion Showreel

A showreel promises that every frame was a decision. Pick one **motif**, push it
through six or seven craft chapters that each look nothing alike, cut on the
beat, and end on the motif.

Read [the reference breakdown](references/reference-breakdown.md) first: a
measured second-by-second analysis of the reel this skill was built from. Per-chapter techniques and a worked brand mapping:
[the chapter library](references/chapter-library.md).

**Done means:** the render passes every check in step 7, and `VERIFY.md` holds
the evidence.

## The grammar

1. **One motif, transformed.** The brand's most reduced element (a dot, a play
   triangle, a letter, a logo corner) opens the reel, becomes each chapter's
   material, and lands as punctuation in the lockup. Each transition turns the
   current object into the next one; the flurry alone uses hard cuts.
2. **Labeled craft chapters.** Six or seven, each named in the HUD by its
   discipline (`01 · SQUASH & STRETCH`), in the brand's own words when it has
   them.
3. **Show the work.** Each chapter gets one tool overlay: a physics readout, a
   selection box with a cursor, a parameter panel, a bezier graph, or a
   brand-native equivalent (a search bar, a counter, a settings menu).
4. **Persistent HUD.** Start from [the HUD template](templates/hud.html): crop
   marks, title, spec line with the measured BPM, timecode, a progress ruler
   with chapter gaps, and the chapter label. It flips ink/paper with the
   background.
5. **Ink, paper, one accent, one held-back color.** The held-back color appears
   only in the flurry. Every chapter change flips value (dark/light) or
   saturation (neutral/full-bleed accent).
6. **Cut on the beat, animate on the off-beats.** 120-130 BPM. Every hard cut,
   flash and invert lands within 2 frames of a grid line. One pre-drop gap
   (music ducked for half a beat) comes before the midpoint hit.
7. **Accelerate, then hold.** For 15s at about 129 BPM (32 beats): physics intro
   4 beats, type chapter 8 beats with an internal invert, three 4-beat chapters
   (drop in the middle), a flurry of about 6 cuts in 4 beats (one beat each,
   then half beats), then about 4 beats of lockup. Roughly 75% development, 13%
   flurry, 12% resolve.
8. **Density breathes.** One object, a wall of type, a grid of 100, thousands of
   particles, one object, the flurry, one word.
9. **Three type voices.** Heavy display for statements, a contrasting accent
   (an italic serif, or the brand's UI face), and wide-tracked mono for the
   machine layer. Type also works as texture: repeated, banded, inverted.
10. **Physical finish.** Squash and stretch, motion blur, bloom on dark, slight
    chromatic fringe, grain, vignette, a dot grid on dark frames: photographed.
11. **Bookend.** The lockup resolves from noise, a rule draws, the subtitles type
    on with a block cursor, the motif lands last with a squash, and a quiet
    tagline follows.

## Workflow

Run the scripts from the kit root; they need Node 22+ and FFmpeg with ffprobe.
Kie.ai and ElevenLabs are optional. Without their keys, use the user's own music
and SFX, and design the hero object as a motion graphic in HyperFrames.

### 1. Study the reference (when one is given)

```sh
node .claude/skills/motion-showreel/scripts/analyze-reference.mjs path/to/reference.mp4 video-projects/<project-id>/qa/reference --fps 6 --bpm 128
```

**Bound:** you read every contact sheet and `report.txt`, and wrote the timeline
in the shape of the reference breakdown.

### 2. Brand intake: `BRAND.md`

Collect exact colors (from the current logo file), typography (the brand face
plus the closest free substitute), official logo SVGs, signature UI and
objects, and 3-5 verified facts with dates for kinetic type. Gather imagery the
user owns or may use. Use only brand marks the user has the right to use for
this purpose.

**Bound:** every field is filled; the motif and held-back color are named.

### 3. Chapter map: `STORYBOARD.md`

Create the project with `npm run new-video -- <slug> --brand <brand>`; it lands
in `video-projects/<yyyy-mm-dd>-<slug>/`. Fill in
[the storyboard template](templates/storyboard.md): per chapter, the discipline
label, the brand-native object, the tool overlay, the in- and out-transform, the
value (dark/paper/accent), and the SFX.

**Bound:** every checkbox in the template's "Checks before building" passes.

### 4. Music, beat grid, SFX and mix

Follow [the audio pipeline](references/audio-pipeline.md): source the music,
measure the kick-band phase, splice a 32-beat bed, print the beat sheet with
`beatgrid.mjs`, place SFX in `events.json`, and premix with `mix.mjs`.

**Bound:** the bed's kick phase is within about 25 ms of 0, the beat sheet is in
`STORYBOARD.md`, and `master.wav` exists at -14 LUFS.

### 5. Assets

- **Hero lookdev object.** Generate it with `kie.mjs`, or design it in
  HyperFrames; both paths are under "Lookdev / hero object" in the chapter
  library.
- **Fonts.** Download them into the project's `assets/fonts/`.

**Bound:** every asset the storyboard names is in the project's `assets/`.

### 6. Build (HyperFrames)

Load `hyperframes` and `gsap`. Read `MOTION_PHILOSOPHY.md` (showreel pacing is
its fast sizzle mode) and `video-storytelling` for persistent-world camera
moves. Read [the seek-safe build rules](references/seek-safe-build.md) before
writing HTML.

Build one `index.html` with one paused GSAP timeline. Chapters are timed `.clip`
layers, and the HUD sits on top.

**Bound:** every rule in the seek-safe list holds.

### 7. Verify

- `npx hyperframes lint`, then Studio preview, then a draft render
  (`hyperframes-cli`).
- Run `analyze-reference.mjs` on your render with `--bpm` and `--phase`: cut
  offsets within about 35 ms of a beat or half beat, luminance alternating by
  chapter, and the pre-drop dip visible in the audio.
- Look at a 10-frame strip across every transition (snapshots miss ghost
  layers):
  `ffmpeg -i render.mp4 -vf "select='between(n\,440\,449)',scale=384:-1,tile=layout=5x2" -frames:v 1 -fps_mode passthrough strip.png`
- Brand test: 6 random frames each read as the brand with the HUD covered.
- About -14 LUFS after the `master.wav` remux.
- Save the evidence in `VERIFY.md`.

**Bound:** every item passes, with evidence in `VERIFY.md`.
