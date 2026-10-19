---
name: cut-mistakes
description: Mistake removal for a talking-head recording, review-gated. Use after cut-silences, or when asked to cut stutters, repeated words, false starts, or retakes, or to keep the best take. Proposes each cut with context, then renders only approved cuts.
---

# Cut mistakes

The second stage of the edit pipeline, after [cut-silences](../cut-silences/SKILL.md). It removes what a human editor cuts on a second pass: stutters ("the the", "I- I-"), repeated words, false starts (an abandoned phrase that restarts), and retakes (a re-recorded line: keep the clean take).

A mistake is a **judgment**, not a pattern. Emphatic repetition ("never, never") and rhetorical doubling ("the piece is, is this") look like stutters to the detector. So every cut passes a review gate before it renders.

Timestamps follow the timeline rule in [cut-silences](../cut-silences/SKILL.md#timeline-rule): the input is `raw.silence-transcript.json`, so cut times are on the silenced timeline. All paths are in `video-projects/<yyyy-mm-dd>-<slug>/assets/`.

## 1. Find candidates

```bash
node .claude/skills/cut-mistakes/scripts/find-cut-candidates.mjs \
  raw.silence-transcript.json --out-dir <assets>
```

It writes `raw.cut-candidates.json` (type, confidence, proposed `cut` range, `removes` and `keeps` text, context, recommendation) and a readable `raw.cut-candidates.md`. Types: `stutter` (immediate word repeat), `retake` (near-duplicate segment by Jaccard similarity), `false_start` (short abandoned phrase).

Done when: both files exist.

## 2. Review

Read each candidate's `removes` and `context` against the speech, and decide cut or keep. Treat `recommend` as a hint. Read the whole transcript too: the detector misses some retakes, so a zero-candidate report proves nothing. Keep emphatic repetition, a copula before a question, and lists.

Present each candidate to the user with your recommendation, then write the approved cuts:

```json
{ "cuts": [ { "start": 100.93, "end": 101.06, "reason": "I- false start" } ] }
```

You can widen a range: for a retake, cut from the start of the bad take to the clean restart. An empty `cuts` array is a valid result; a clean delivery needs no cuts.

Done when: every candidate has a decision, every spoken line is read, and `approved-cuts.json` exists.

## 3. Apply

```bash
node .claude/skills/cut-mistakes/scripts/apply-cuts.mjs raw.silence-transcript.json \
  --cuts approved-cuts.json --video silenced.mp4 \
  --out-dir <assets> --output clean.mp4 --apply
```

It writes `raw.mistakes-edl.json`, `raw.mistakes-transcript.json`, a decisions log, and with `--apply` the cut video. Omit `--apply` for a dry run. A cut between two words is a hard join; if a join clicks, add a 20-30 ms fade.

Check the joins in the EDL review page:

```bash
node scripts/build-edl-review.mjs raw.mistakes-edl.json \
  --original silenced.mp4 --edited clean.mp4 --output mistakes-review.html
npx serve . -p 8080 -n
```

Done when: `clean.mp4` exists and every join is heard. Copy `raw.mistakes-transcript.json` to `assets/transcript.json` and hand it with `clean.mp4` to the graphics stage.
