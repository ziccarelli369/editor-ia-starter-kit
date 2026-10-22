# Release verification

## Consolidated kit checks

Verified locally on Windows, 2026-10-22, using Node 24.14.0: `npm run check`
and `npm test`.

- All 23 skills passed frontmatter validation. The distribution check reports
  zero errors across 406 cards and the skill tree.
- All 35 behavior tests passed, including checks for caption drift, incorrect
  source mapping, scene coverage, footage reuse, missing ledger rows, changed
  footage hashes, and the film path's scaffold, guards and tool discovery.
- The film path (`character-film`, `film-engine`) is verified on Windows only.
  On macOS and Linux, only its unit tests in `npm test` cover it.
- From the previous kit check, not repeated on 2026-10-22: a clean `npm ci`
  succeeded; the starter passed preflight and HyperFrames lint with zero errors
  or warnings; the synthetic media check gave a silence output of 3.960
  seconds and a clean output of 3.673 seconds versus a 3.660-second transcript.
- No real reel or paid generation was run for this release; short-form
  verification covers its validators and resource package.

## Original pipeline release evidence

The following rendering evidence comes from the pipeline release before this
merge. Its starter and editing implementation are retained.


Verified locally on Windows, September 8, 2026, using Node 24.15.0,
FFmpeg 8.1.1, and HyperFrames 0.7.109.

- Clean dependency install succeeded; npm reported zero known vulnerabilities.
- The kit check validates JavaScript syntax, skill frontmatter and linked resources,
  registry counts, unique IDs, declared slots, and local card dependencies.
  All 406 card files resolve. Two cards construct some slots in JavaScript;
  their source declarations are checked, not their executed DOM.
- Five behavior tests pass: silence retiming, reviewed stutter removal, empty-cut
  identity behavior, invalid cut bounds, and early/late beat timing. The CLI
  accepts explicit project paths and attribute order independent of old examples.
- `node scripts/check-media.mjs` generated an eight-second test pattern with a sine tone,
  rendered both editing stages, and built the EDL review HTML. The silence output
  was 3.960 seconds; the clean output was 3.673 seconds against a 3.660-second
  transcript. A/V durations differ by less than 0.04 seconds.
- The starter passed preflight and HyperFrames lint with zero errors/warnings.
  Studio loaded and played to eight seconds. Draft render produced 240 H.264
  frames at 1920x1080 and 30fps. Extracted frames were visually inspected across
  the eight-second sequence. No black interval of 0.1 seconds or longer was detected.

## Scope and limits

This is a working toolkit, not a promise of fully automatic editorial judgment.
The library's 406 cards retain draft status; this release did not individually
render and visually approve all of them. Test each selected card with your copy.
The starter is motion graphics only, with no speech. The media check
checks timing and stream integrity with a tone, not subjective speech-cut quality.
Paid Scribe transcription was not called during release QA. The templates require
adaptation; the glass popout needs the student's footage. HyperFrames can download
font substitutions on the first render. Cross-platform checks run in GitHub CI;
local media and rendering QA were performed on Windows.

Repeat: `npm install`, `npm run check`, `npm test`, `node scripts/check-media.mjs`, then create a
new starter project and lint, preview, render, and inspect its output.

## Caption alignment and hearing check

`node scripts/align-captions.mjs <project-id> --srt <srt>` measures voice
onsets in the speech band of the final audio (a 6 dB rise that holds for the
next 100-250 ms, so ticks and clicks do not count) and snaps each cue start to
the nearest onset within 0.6 s, frame-exact. Whisper word times are estimates
spread across a chunk and are never used for timing.

`node scripts/hearing-check.mjs <project-id>` re-transcribes the final render
with local Whisper, aligns the words to the SRT, flags captions that do not
match what was said (MISMATCH), captions with no speech under them (SILENT),
cuts that land inside a word (CUT_IN_WORD), and reports loudness. It writes
`HEARING.md` in the project and exits 1 on FAIL. Timing is judged against the
measured onsets, not against Whisper.
