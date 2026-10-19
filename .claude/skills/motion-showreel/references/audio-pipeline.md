# Audio pipeline: music, beat grid, SFX, mix

Read this at step 4 of the showreel workflow. Run the scripts from the kit root. They need Node 22+ and FFmpeg with ffprobe.

## Music source

Music is the user's own licensed track from `music/` or `brands/<slug>/music/`, or a generated one. Generation (Kie.ai) and the SFX kit (ElevenLabs) are paid calls: read `docs/TOOLS-AND-API-KEYS.md`, name the cost, and run them only after the user's yes. Without `KIE_API_KEY` or `ELEVENLABS_API_KEY`, use the user's own track and SFX library; say so when you fall back.

```sh
node .claude/skills/motion-showreel/scripts/kie.mjs music --title "Reel" --style "punchy electronic showreel, instrumental, 128 bpm, starts instantly, riser into a big drop" --out video-projects/<project-id>/assets/audio
node .claude/skills/motion-showreel/scripts/music-grid.mjs video-projects/<project-id>/assets/audio/take-0.mp3 --bpm 128 --beats
```

## Beat grid

`music-grid` prints the period, the **kick-band phase** (use it), and per-bar and per-beat energy. The full-band phase can lock onto off-beat hats and put every splice half a beat late; the script warns when the two disagree.

In the per-beat low-band column, find the riser, the drop (a jump of 10+ dB), the break, and the return. Then splice 32 beats: intro and build (16, ending on the drop's downbeat), drop (8), break (4, under the flurry), and the return hit plus a tail:

```sh
node .claude/skills/motion-showreel/scripts/splice-music.mjs take-0.mp3 --period 0.4644 --phase 0.085 --segments "4-28,48-56.7" --length 15 --gap 16 --out music-bed.wav
node .claude/skills/motion-showreel/scripts/music-grid.mjs music-bed.wav --bpm 129
node .claude/skills/motion-showreel/scripts/beatgrid.mjs --period 0.4644 --length 15 --chapters "01 Physics:4, 02 Type:8, 03 Grid:4, 04 Drop:4, 05 Lookdev:4, Flurry:4, 07 End:rest"
```

The re-measured bed's kick phase should be within about 25 ms of 0. Put the measured BPM in the HUD (129, not 128). `beatgrid` prints the frame sheet for `STORYBOARD.md`.

## SFX and the mix

Generate a kit with `scripts/sfx.mjs` (pops, clicks, whooshes, glitch, ticks, shimmer, sub boom, final hit, and brand-native sounds), or use the user's own library. Place cues on the beat sheet in an `events.json` and premix:

```sh
node .claude/skills/motion-showreel/scripts/mix.mjs --bed music-bed.wav --events events.json --out master.wav
```

Use `master.wav` as the composition's single `<audio>` track. It targets -14 LUFS and -1.2 dBTP. HyperFrames re-encodes audio slightly quieter, so after the render remux `master.wav` into it (the command is in the header of `mix.mjs`).
