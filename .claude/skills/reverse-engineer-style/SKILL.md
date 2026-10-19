---
name: reverse-engineer-style
description: Turn a reference video the user likes into a reusable editing style skill in styles/drafts/. Use when the user says "quiero editar como este video", "copia este estilo", "analiza este reel", or gives a local video path as a reference. Measures with ffmpeg, labels every claim observed / inferred / unknown, then test-renders.
---

# Reverse-engineer a style

Input: a local video file. The skill takes a path, never a URL. If the user
gives a link, ask them to download it to `inbox/` first. Only use a video the
user has permission to study. Borrow mechanisms, never copy script or assets.

Output: `styles/drafts/<slug>/` with `SKILL.md`, `style.json`, `ledger.md`,
and `analysis/` (contact sheets and the report).

Tell the user before starting: analysis runs ffmpeg and Whisper on their
machine. A 60-second reel takes about a minute on a laptop; longer on a slow
CPU. No API call is made.

## Method (from REA: observe, then infer, then admit what is unknown)

1. **Questions first.** Write the checklist the style must answer:
   hook (what happens in the first 3 s), cut rhythm, caption behavior,
   transitions, framing and zooms, sound and music, payoff and CTA.
   Each question names the evidence that answers it.
2. **Smallest inventory first.** Probe with ffprobe: duration, size, fps, audio.
3. **Measure.** Run the analyzer from the motion-showreel skill:
   ```sh
   node .claude/skills/motion-showreel/scripts/analyze-reference.mjs <video> styles/drafts/<slug>/analysis --fps 6
   ```
   Read `report.txt` (hard cuts, luminance, audio RMS, onsets) and every
   `sheet_NN.png`. For zooms and caption changes between cuts, grab full frames
   at the moments the sheets suggest: `ffmpeg -ss <t> -i <video> -frames:v 1 f.png`.
4. **Transcribe.** `npx hyperframes transcribe <video>`. Align the spoken hook
   with the first cuts and the caption changes.
5. **Ledger.** For every claim write one row in `ledger.md`:
   `| claim | evidence (file, timestamp) | observed / inferred / unknown |`.
   A number measured from the file is `observed`. A reason why it works is
   `inferred`. Anything you could not see or hear is `unknown`. Never claim you
   heard audio from a waveform. Never say "no X" unless every frame was checked.
6. **In team profile**, Haiku subagents may run steps 2 to 4 on separate facets
   (cuts, captions, audio). Opus writes the ledger, the rules and the skill.

## style.json

```json
{
  "slug": "", "name": "", "source": "inbox/<file>", "created": "yyyy-mm-dd",
  "status": "draft", "tested": false, "summary": "",
  "probe": { "duration_s": 0, "width": 0, "height": 0, "fps": 0 },
  "hook": { "first_cut_s": 0, "text_on_screen_s": 0, "spoken_hook": "" },
  "pacing": { "cuts": 0, "cut_median_s": 0, "cut_p90_s": 0, "longest_hold_s": 0 },
  "captions": { "words_per_line": 0, "position": "", "highlight": "", "font_feel": "" },
  "transitions": [], "framing": { "zooms": 0, "crop_changes": 0 },
  "sound": { "music": true, "sfx_hits": 0, "hits_on_cuts": 0 },
  "unknowns": []
}
```

## SKILL.md of the new style

Frontmatter `name: style-<slug>` and a `description` that says when to use it.
Body: 8 to 15 rules, each one sentence, each traceable to a ledger row. Put the
row id in brackets at the end of the rule. Rules from `inferred` rows say "try".

## Test render, then keep or kill

Ask: **"save it as is, or make a lookalike to check it?"**

- Save: set `tested: false`, done. It stays a draft.
- Lookalike: pick any clip in `inbox/` or the current project. Build a 3-second
  cut that applies the hook and pacing rules (10 seconds if the user asks).
  Render at draft quality, show it in the browser pane, and ask **keep or kill**.
  Keep: set `tested: true`. Kill: delete `styles/drafts/<slug>/` and say why
  the rules did not hold.

Promotion to `styles/core/` is the user's call, by `git mv`. Never promote.
