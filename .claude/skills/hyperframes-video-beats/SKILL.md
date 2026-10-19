---
name: hyperframes-video-beats
description: Overlay beats for long-form talking-head HyperFrames videos: glass lower thirds and paper takeovers timed to the transcript. Use when adding, improving or retiming beats, or scanning a project for coverage gaps.
---

# HyperFrames Video Beats

Turn a talking-head video plus its transcript into a paced set of **beats**:
motion graphics that support the narration and keep the speaker visible.

A beat earns its place by answering one question:

- What should the viewer remember?
- What concept needs visual structure?
- What stat, contrast or pivot deserves emphasis?
- Where is the pacing quiet enough that the viewer may drift?

A gap alone is no reason for a beat. The reason is a topic, transition, proof
point or mental model in the narration.

**Done means:** every new or retimed beat is mounted and timed to its topic
span, the coverage scan shows no gap over threshold that the transcript can
support, and lint shows 0 errors.

## 1. First pass

1. Read the project's `CLAUDE.md`, its `DESIGN.md`, and any local skill notes.
2. Inspect the root composition, the beat schedule, the shared CSS and the
   transcript.
3. Build a coverage map from the root `data-start` / `data-duration` entries,
   or from the master `SHOW` array when one exists; it is usually the
   authoritative visible range.
4. Extract transcript chunks for the requested region and every uncovered gap.
   Use fast local tools: `rg`, `Select-String`, small Node or PowerShell
   scripts.
5. Mark topic spans by narration, not by round timestamps.

**Bound:** every topic span in scope is listed with its start and end words.

## 2. Pick a beat type per topic span

- **Paper takeover:** a major thesis, list, section marker, quote or stat
  becomes the whole frame for a few seconds. Read
  [paper-takeover.md](references/paper-takeover.md) before building one.
- **Glass lower third:** the speaker stays visible and the card supports the
  current idea. Read [glass-lower-third.md](references/glass-lower-third.md)
  before building one.
- **No beat:** the narration has no concept to support.

Default to glass when the speaker's face matters. Follow the project's design
system first; the two references hold this project family's defaults.

**Bound:** every topic span has one of the three answers.

## 3. Time each beat to its topic

1. Find the first word or phrase where the topic starts.
2. Start the beat 0.2-0.6 seconds before that anchor when possible.
3. Keep it visible until the topic ends or hands off.
4. When the next beat starts at once, clear 0.1-0.5 seconds before it, unless
   the handoff is intentional.
5. Match sub-element entrances to spoken phrases.

A card lives across its whole topic. When the speaker talks about one topic for
20-40 seconds, one card holds for that span and builds a subline or list item
midway.

**Bound:** each beat's start and end trace to a transcript word.

## 4. Write the copy

Write for a glance: the viewer understands the card in under one second.
Use short noun phrases, direct labels, one mental model per card, numbers only
when they mean something, and verbs where they clarify the action. Carry the
idea, not the voiceover: one short line in place of a sentence, plain words in
place of hype, at most one highlighted word. The card speaks about the topic,
not about how to watch the video. The references hold copy patterns.

**Bound:** every card reads in one glance.

## 5. Build

When adding a beat:

1. Create `compositions/beats/NNN-short-name.html`.
2. Add the root mount in `index.html`.
3. Add or update the master visibility schedule if one exists.
4. Make the sub-composition `SLOT` match the mounted duration.
5. Check for same-track overlaps; use a separate overlay track only where the
   project already does.

Every beat follows the project's `CLAUDE.md` and the HyperFrames lint rules:

- Each mounted timed element has `data-start`, `data-duration` and
  `data-track-index`, plus the clip or layer class the project uses.
- Each sub-composition registers a paused GSAP timeline on `window.__timelines`
  and pins it with `tl.set({}, {}, SLOT);`.
- Logic is deterministic.
- Animate wrappers, never the video element's dimensions or media properties;
  those freeze renders.

**Bound:** all five steps done for every new beat.

## 6. Coverage scan

Sort beats by visible start, taken from the visibility schedule rather than DOM
order, and print every gap over 30 seconds. In the main body, 45 seconds is the
maximum acceptable gap; early in the video, aim for 20-30. Add or retime a beat
only where the transcript has a concept to support. Dense explanation sections
get roughly one lower third per topic span, not one per sentence.

**Bound:** every gap over 30 seconds is filled or has a reason in your report.

## 7. Validate

1. Run `npx hyperframes lint` and fix every error.
2. List the known, non-blocking warnings separately.
3. If the user asked for render-ready output, render or draft-render.
4. Report the exact file paths and timestamps you changed.

**Bound:** lint shows 0 errors, and the report names every changed file.

## Taste decisions win

A choice the user made in review beats any generic rule here:

- A beat the user shortened stays short; fill after it with a new, shorter card.
- An approved glass style is reused as is.
- Approved typography stays stable; adjust only local size and weight.
