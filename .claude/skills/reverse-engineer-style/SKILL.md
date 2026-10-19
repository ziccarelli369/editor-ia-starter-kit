---
name: reverse-engineer-style
description: Reverse-engineer a reference video into a reusable editing style in styles/drafts/. Use when the user gives a local video and says "edita como este", "copia este estilo" or "analiza este reel". Measures with ffmpeg, writes an evidence ledger, test-renders.
---

# Reverse-engineer a style

Input: a local file the user may study. A link is a request to download it to
`inbox/` first. Borrow mechanisms; the script and assets stay the creator's.

Output: `styles/drafts/<slug>/` with `SKILL.md`, `style.json`, `ledger.md` and
`analysis/`.

Say before starting: ffmpeg and Whisper run on this machine, about a minute per
minute of video on a laptop, no API call.

## Method

REA's discipline: **observe**, then **infer**, then admit **unknown**.

1. **Questions.** Write the checklist the style must answer, each with the
   evidence that answers it: hook (first 3 s), cut rhythm, captions,
   transitions, framing and zooms, sound and music, payoff and CTA.
2. **Probe.** ffprobe: duration, size, fps, audio streams.
3. **Measure.**
   ```sh
   node .claude/skills/motion-showreel/scripts/analyze-reference.mjs <video> styles/drafts/<slug>/analysis --fps 6
   ```
   Read `report.txt` (hard cuts, luminance, audio RMS, onsets) and every
   `sheet_NN.png`. For zooms and caption changes between cuts, grab full frames
   at the moments the sheets suggest: `ffmpeg -ss <t> -i <video> -frames:v 1 f.png`.
4. **Transcribe.** `npx hyperframes transcribe <video>`. Align the spoken hook
   with the first cuts and caption changes.
5. **Ledger.** One row per claim in `ledger.md`:
   `| id | claim | evidence (file, timestamp) | observed / inferred / unknown |`.
   A number measured from the file is observed. A reason it works is inferred.
   A thing you could not see or hear is unknown; a waveform is not hearing.
   An absence claim ("no zoom cuts") needs every frame checked.
6. **Team profile:** Haiku subagents may run steps 2 to 4 on separate facets.
   Opus writes the ledger, the rules and the skill.

Done when every checklist question has a ledger row, or an `unknown` row that
says what was missing.

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

Every number comes from an observed ledger row.

## SKILL.md of the new style

Frontmatter: `name: style-<slug>`, a `description` with the triggers for when
this style fits. Body: 8 to 15 one-sentence rules, each ending with its ledger
row id in brackets. A rule from an inferred row starts with "Try".

## Test, then keep or kill

Ask: **save as is, or make a lookalike to check it?**

- Save: `tested: false`. It stays a draft.
- Lookalike: a 3-second cut (10 on request) from any clip in `inbox/` or the
  current project, applying the hook and pacing rules. Draft-quality render,
  shown in the browser pane. Ask **keep or kill**. Keep: `tested: true`.
  Kill: delete `styles/drafts/<slug>/` and say which rules failed.

Promotion to `styles/core/` is the user's `git mv`.
