---
name: edit-video
description: Complete long-form edit of a raw talking-head video, from transcript to verified HyperFrames render. Use when asked to edit a whole video end to end. Use short-form-edit instead for a reel or Short, and the specialist skill for a single operation.
---

# Edit a video

Keep the project in `video-projects/<yyyy-mm-dd>-<slug>/` and preserve the source recording. Read the project's brief or `DESIGN.md`. If it gives no style, propose one from `style-library/registry.json` that suits the footage.

1. **Probe.** Read duration, streams, and resolution with ffprobe. Copy the source into the project's `assets/`, or reference a local path the user gave.
   Done when: the probe values are in the project notes.
2. **Cut silences.** Follow [cut-silences](../cut-silences/SKILL.md): it holds the transcription commands and the timeline rule.
   Done when: `silenced.mp4` and `raw.silence-transcript.json` exist.
3. **Cut mistakes.** Follow [cut-mistakes](../cut-mistakes/SKILL.md).
   Done when: every candidate has a decision and `clean.mp4` matches `assets/transcript.json`.
4. **Plan the visuals.** Read [video-storytelling](../video-storytelling/SKILL.md) for the visual world and `hyperframes-video-beats` for overlays. Write a beat sheet: one transcript anchor and one visual idea per beat, with deliberate callbacks.
   Done when: every beat has an anchor word that exists in `assets/transcript.json`.
5. **Author.** Read `MOTION_PHILOSOPHY.md`, the `hyperframes` skill, and the relevant GSAP references. Select or adapt cards with the `style-library` skill. Localize every asset the composition uses.
   Done when: the composition loads with no remote asset.
6. **Check.** Run preflight and `npx hyperframes lint` from the project, and `npm run validate-beats` for anchored sub-compositions. Review the preview in Studio.
   Done when: all three report 0 errors.
7. **Render and inspect.** Render a draft. Inspect encoded frames at every transition, listen across every cut, and check face framing, text legibility, black frames, and A/V sync. Fix each failure, then render the final.
   Done when: every check passes on the final render.

Follow review approvals the user already gave; ask only for an approval that is still missing.

Deliver the final MP4 path, the edit decisions, the retimed transcript, the composition, and `VERIFY.md` with what you checked and what remains limited. The detectors propose edits; the editorial decision stays yours.
