---
name: short-form-edit
description: Short-form edit of talking-head footage into a reel, YouTube Short, or short ad, with a curiosity-led opening, story-driven cuts, synced motion graphics, B-roll, captions, music, and SFX. Use edit-video instead for long form and cut-silences for pause removal alone.
---

# Short form edit

Input: a source-video path and an optional reference-reel path. Output: every requested format plus the editable project in `video-projects/<yyyy-mm-dd>-<slug>/`. Default to 1080x1920; when requested, also compose 1920x1080 with its own framing and text placement, and verify each ratio on its own, opening and CTA included. Work locally unless the user asks for delegation.

## The reason to stay

The first gate, above effects, asset volume, and polish: **"In the first 3 seconds is someone convinced they need to watch until the end?"** Plant a specific reason to stay and earn its payoff inside the video. Until audience data exists, the answer is editorial judgment: record it as judgment, never as a retention score, an audience A/B test, or a guaranteed viral result.

## House style, notes, and authorization

Read `docs/EDITING-PLAYBOOK.md` before planning. It holds the kit's measured reel style, its variants, and the lessons that cost time. Use it when the user gives no style; the user's brief wins.

When the user gives a note on a draft, fix the edit, then offer to write the note into the relevant skill or reference as a rule, check, or script change. Record the note and the resulting rule together.

Authorization persists. "Make a finished video and iterate" authorizes local editing, rendering, and automated review. An explicit request for Kie B-roll authorizes those generations. Ask only for an approval that is still missing. Posting the reel or contacting anyone needs its own explicit approval.

## Steps

1. **Read and probe.** Read the workspace guide, `MOTION_PHILOSOPHY.md`, the `hyperframes` skill, and [video-storytelling](../video-storytelling/SKILL.md). Probe the source and reference: duration, dimensions, frame rate, audio, and transcript identity. Preserve originals and use this exact take. Transcribe per [cut-silences](../cut-silences/SKILL.md).
   Done when: `assets/raw.json` matches the source take.

2. **Analyse the reference** (when one is supplied). Inspect the whole reel with contact sheets, full-size frames, and contiguous strips at representative transitions. Review its sound when an audio-capable surface exists; a waveform is not listening. Follow [reference-analysis.md](references/reference-analysis.md). Borrow editorial mechanisms, never branded copy.
   Done when: `REFERENCE-ANALYSIS.md` holds timestamped observations, inferred principles, and stated limits.

3. **Shortlist assets.** Inspect the footage, brand assets, and source demos before you lock the concept, and let a distinctive moment shape the idea. Prefer what reads in one glance; fit the complete action and result before a tighter crop.
   Done when: the shortlist gives every usable asset an exact interval, visible action, consequence, provenance, and possible story role.

4. **Cut.** Run [cut-silences](../cut-silences/SKILL.md) and [cut-mistakes](../cut-mistakes/SKILL.md). Remove abandoned takes; keep meaningful qualifications, the payoff, and natural breath at joins. Render the clean cut once and derive word timing from the frame-aligned EDL.
   Done when: every spoken line is read, the source-time cut reasons are saved, and `assets/edit-decisions.json` exists.

5. **Design the journey.** Write `DESIGN.md` and a beat plan before HTML: hook, open loop, escalation, evidence, payoff, CTA, and a reason for every shot. Follow [curiosity-and-entertainment.md](references/curiosity-and-entertainment.md) for the open loops, rhythm, and duplication audit, and [opening.md](references/opening.md) for the three openings.
   Done when: `OPEN-LOOPS.json` closes every loop before the CTA, and three openings are compared with the choice recorded.

6. **Animatic and cut lock.** Render a low-resolution moving animatic with speech and rough sound. Fix predictability, missing context, and weak payoffs here; reused approved materials still get reviewed in the new sequence. Lock the cut after this animatic. Every later timing change rebuilds captions, graphics, and sound from the same map.
   Done when: the animatic is reviewed end to end and the cut is locked.

7. **Build the visual world.** Follow [visual-world.md](references/visual-world.md): direction, safe region, layers and actions, named people, product footage, brand logos, and the footage ledger. For a minimal brief, add [premium-motion-and-footage.md](references/premium-motion-and-footage.md).
   Done when: every shot names its attention target and its action's outcome, and every logo traces to a saved source file.

8. **Generate and assemble.**
   - Generated inserts follow [generation-and-sound.md](references/generation-and-sound.md).
   - Animate graphics from the retimed words. Store each shot's anchor phrase and time, and bind each sub-element reveal to its own spoken noun rather than an `index * 0.4` stagger. Captions and impact events land within 2 frames of word onset, with at most 0.15 s of deliberate anticipation.
   - Follow the HyperFrames timeline contract: one registered paused timeline per composition, full duration coverage, local assets, muted video with separate audio. Animate the footage wrapper. Use real 3D only when the metaphor needs it. Keep the source editable.
   - Music: normalize the voice, start an instrumental bed about 14-20 dB below it, duck under speech, fade cleanly. Aim for about -16 LUFS and at most -1 dBTP, adapting to source dynamics. Save the bed's provenance. Score SFX and any music revision per [generation-and-sound.md](references/generation-and-sound.md).
   Done when: `assets/plan.json` passes `validate-plan.mjs` and every cue has a purpose.

9. **Render.** Run lint and inspect the live preview. Browser automation is headless, with Pointer Lock and pointer capture disabled in every context. Render a draft, inspect, revise, then render final quality. Gotchas:
   - If framework capture stalls, a deterministic graphics export plus FFmpeg assembly is acceptable.
   - Await local fonts before capturing a canvas.
   - Normalize every video input to one frame time base before overlaying, and inspect every encoded cut for one-frame mismatches.
   - Build final face crops from the native-resolution source, not the editing proxy.
   Done when: the final renders in every requested ratio.

10. **Gates.** Run both validators; they catch structure, not taste, motion, or listening:

    ```powershell
    node .claude/skills/short-form-edit/scripts/validate-plan.mjs video-projects/<yyyy-mm-dd>-<slug>
    node .claude/skills/short-form-edit/scripts/validate-footage.mjs video-projects/<yyyy-mm-dd>-<slug>
    ```

    They read `assets/plan.json`, `assets/transcript.json`, and `assets/edit-decisions.json` in the [plan schema](references/plan-schema.md). For another implementation, export that schema or adapt the validator explicitly, so every check still runs.

    Then apply every gate in [quality-gates.md](references/quality-gates.md) to the encoded final: hero frames at full size and phone scale, contiguous strips across every cut, speech joins, fresh ASR from the final audio, voice and bed balance, SFX timing, clipping, and the last syllable. Run the uninterrupted entertainment review into `ENTERTAINMENT-REVIEW.md` (see the review section of [curiosity-and-entertainment.md](references/curiosity-and-entertainment.md)), fix the weakest sequences, and recheck them in context. State each review modality you lacked. After every fix, rerun the checks that change affects.
    Done when: both validators exit 0 and `VERIFY.md` gives every gate measured evidence, plus the output hash, inspected artifacts, revisions, and open limits. Code inspection, file existence, or an empty validator result is not a pass.

## Delivery

Archive superseded versions. Return a playable final MP4, its absolute path, and the skill path. Keep the composition, assets, source and retimed transcripts, EDL, shot and event plan, audio stems, reference analysis, and QA evidence in the project. Label only the verified render as final.
