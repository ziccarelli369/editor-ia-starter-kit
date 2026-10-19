# Audio air and timeline shifts

Read this when you repair cut audio, change the timeline after graphics exist,
or audit the delivered audio.

## Leave air in the cut

Aggressive pause-capping leaves near-zero gaps at sentence boundaries that the
client hears as "stutters" and jump cuts.

- **Calibrate against the speaker's own norm.** Flag sentence-boundary gaps ~10x
  tighter than their median (the reference speaker's median was 470ms; flagged
  junctions sat at 20-40ms).
- **Insert 4-8 frames of air; leave the words untouched.** Air is a donor slice
  of the track's real room tone with 10ms fades. Never use `anullsrc`: digital
  silence against a -50dBFS floor is an audible dropout.
- **Hold the video frame.** Between sentences a talking head is near-still, so a
  4-8 frame hold is invisible.
- **Respect the speech envelope at insert edges.** Splice with a 40ms
  equal-power crossfade into the word tail's own decay. A hard butt within 1ms
  amputates a decay that takes 60-120ms, and the client hears the cliff as a
  stutter.
- Insertion-only changes shift the transcript deterministically, so no
  re-transcription is needed.

## Shift baked times by script

Generators bake hundreds of proto-time literals, and section offsets, seam
tables, and root tweens all hold absolute times. Route any timeline change after
graphics exist (even a 2s air pass) through a reviewed AST- or parse-level
transform that shifts every literal after each edit point, then review the diff.
Derive every shift from the canonical edit list itself: the reference pass
caught a 2-frame error in its own audit's precomputed offsets by re-deriving.

## Audit audio at the acoustic level

A transcript from the pre-edit source is blind to artifacts the edit created; a
text sweep over it reports "clean" while the client hears stutters. What finds
them, in yield order from the reference build:

1. A whole-track dead-span scan: runs of digital-zero samples inside pauses whose
   real floor is ~-70dBFS read as dead holes. Fill them with room tone.
2. 1ms-resolution envelope forensics at every junction edge. A sample-derivative
   click check passes an envelope cliff the ear flags instantly.
3. A fresh ASR pass on the delivered audio, diffed against the expected text.

Phoneme-repeat autocorrelation found nothing: what clients call "stutters" are
usually truncation cliffs and dead holes, not doubled words.
