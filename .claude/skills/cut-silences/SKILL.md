---
name: cut-silences
description: Silence removal for a talking-head recording with a word-level transcript. Use when asked to cut silences, trim pauses or dead air, or tighten pacing. Writes an EDL, a retimed transcript, and optionally the cut video. Use cut-mistakes instead for stutters, repeats, and retakes.
---

# Cut silences

The first stage of the edit pipeline. It removes **only silence**: dead air before the first word and after the last word, plus inter-word pauses longer than a threshold. Every spoken word stays; mistakes are the job of [cut-mistakes](../cut-mistakes/SKILL.md).

All paths below are in the project folder `video-projects/<yyyy-mm-dd>-<slug>/assets/`.

## 1. Get a word-level transcript

Reuse a word-level transcript that matches this exact recording. Otherwise transcribe with the kit default, local Whisper, then convert it to the kit format:

```bash
npx hyperframes transcribe <video>
node scripts/whisper-to-kit.mjs <transcript.json> <raw.json>
```

ElevenLabs Scribe (`npm run transcribe -- <video>`) is the optional paid path; it uploads audio and spends credits, so get approval first. Read `docs/TOOLS-AND-API-KEYS.md` for provider setup and the transcript format.

Done when: `raw.json` holds `words: [{ text, start, end }]` on the timeline of `raw.mp4`.

## 2. Plan and render the cut

```bash
node .claude/skills/cut-silences/scripts/cut-silences.mjs raw.json \
  --video raw.mp4 --out-dir <assets> --output silenced.mp4 --apply
```

Omit `--apply` for a plan only (EDL and transcript, no render); omit `--video` too for no ffmpeg command. Run the script with no arguments for the full flag list.

The silence rules:

- A pause shorter than `--gap` (default 0.55 s) is natural rhythm and stays.
- A longer pause keeps a **breath**: 0.24 s for pauses of 2 s or more, 0.20 s after a sentence ender (`. ! ?`), 0.14 s otherwise. The breath leans toward the end of the previous phrase.
- Head and tail dead air trim to `--head-pad` (0.22 s) and `--tail-pad` (0.34 s).
- The render uses an ffmpeg `trim`/`atrim` + `concat` filtergraph, so audio and video stay in sync.

Tuning: the default removes about 15-20% of a typical raw take. Lower `--gap` for a punchier cut; raise it to keep more breathing room. If sentence joins sound tight, raise `--gap`. Keep a pause that carries meaning.

Outputs, written to `--out-dir`:

| File | Purpose |
| --- | --- |
| `raw.silence-edl.json` | Keep and delete ranges, durations, parameters |
| `raw.silence-transcript.json` | Words retimed onto the silenced timeline |
| `raw.silence-decisions.md` | Summary and the largest pauses trimmed |
| `raw.silence-filter.txt` | The ffmpeg filtergraph (with `--video`) |
| `silenced.mp4` | The cut video (with `--apply`) |

Done when: the script exits 0, `raw.silence-decisions.md` is read, and every join you listen to keeps a breath.

## Timeline rule

Each stage writes a retimed transcript on the timeline of the video that stage outputs. Pair a transcript only with its own video: `raw.silence-transcript.json` with `silenced.mp4`, `raw.mistakes-transcript.json` with `clean.mp4`. The next stage reads this stage's transcript, so its times are already on the edited timeline, and beat timing and `scripts/validate-beat-sync.mjs` need no further adjustment.

Hand `raw.silence-transcript.json` and `silenced.mp4` to [cut-mistakes](../cut-mistakes/SKILL.md).
