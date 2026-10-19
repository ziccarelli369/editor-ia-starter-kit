---
name: video-storytelling
description: Visual world for a long-form talking-head video, one persistent space the camera moves through. Use when designing the visuals or motion graphics for a script, or fixing an edit judged confusing, text-heavy, or AI-made. Use hyperframes-video-beats instead for overlay cards.
---

# Video storytelling

Build the visual layer of a long-form video so a viewer is still oriented at minute nine. It fits any talking-head video with a script: a news take, a deep dive, a comparison, a tutorial, a listicle.

The failure this replaces is **scene-thinking**: a new graphic every few seconds makes the viewer restart comprehension every few seconds. No single graphic is at fault, so the feedback arrives as a vague "confusing" or "too much going on".

For a neutral practice beat sheet, read `docs/STORYTELLING-WORKBOOK.md`. Private source videos are not required.

## Order of work

1. **Lock the cut and get a word-level transcript** ([edit-video](../edit-video/SKILL.md) steps 2-3). Everything is timed to it.
   Done when: `assets/transcript.json` matches the locked video.
2. **Choose the world, the spatial grammar, and the travelling subject.** Write them down before building.
   Done when: the project `DESIGN.md` states all three.
3. **Choose the open loop** from the script shape ([open-loops.md](reference/open-loops.md)) and build its shared module first. The hook, every boundary, and the payoff use its geometry.
   Done when: the shared module renders the loop in its opening state.
4. **Build one section end to end and render it.** Prove the system there before touching the others.
   Done when: the section renders and passes the gates in [verification.md](reference/verification.md).
5. **Review that section by eye, muted**, for ornament and legibility. Fix the system, not the section.
   Done when: every shape on screen is a labelled element, a connector, the travelling subject, or ground, and every label reads at 960x540.
6. **Build the rest against the proven section.** Then namespace, assemble, render, gate, and read the assembled render.
   Done when: every gate passes on the assembled render and every transition strip is read.

Steps 4 and 5 are where the quality comes from: the reference build's whole visual system came from reviewing its first section three times.

## The four principles

### One persistent world

The video lives in one space that never resets. Everything the viewer has seen stays where they left it; new material is added to the world, not swapped in. An element, once drawn, keeps its position, shape, and label. Everything else here depends on this: the camera needs a stable space, the spotlight needs other elements, and an open loop needs a world that persists.

Decide the spatial grammar before building and hold it for the whole runtime. In the reference build: left to right is toward the outcome, up is toward a human and is the only warm thing on screen, down is into a system of record. A viewer who learns it in two minutes reads the rest for free. Break the grammar exactly once, deliberately, for meaning: the reference build's only right-to-left move is a resolved ticket reversing into the queue on the words "reopen rate".

### The camera is the edit

Move the camera through the world instead of cutting to a new graphic. Work in three altitudes (world, region, detail) and move between adjacent ones. Before writing any move, framing, or wipe, read [camera.md](reference/camera.md): it holds the rules that each cost a rebuild.

### Attention is a spotlight

**Exactly one element at full brightness at any moment; everything else already drawn stays quiet but legible.** This lets a world grow to a dozen elements without feeling busy. Hierarchy comes from the ratio between active and quiet, not from darkening everything: the first prototype's brightest pixel was 101/255 and unreadable. Target luma per state is in [design-system.md](reference/design-system.md); the `lit()` implementation and its load-bearing details are in [spotlight.md](reference/spotlight.md).

### Open loops are spatial

Leave something visibly incomplete in the world and return to it, instead of saying "we'll come back to this". A promise the viewer can see is one they feel outstanding.

1. **Plant it in the hook**, in the space, on the line that makes the promise.
2. **Re-show it at every boundary.** Any section handoff is a boundary. The re-show costs about two seconds and is the retention mechanic; without it the payoff pays off nothing.
3. **Advance it visibly.** The viewer sees the incompleteness shrink.
4. **Close on the image you opened on.**

## Discipline

- **If it doesn't get a word, it doesn't get drawn.** Every shape is a labelled element, a connector between labelled elements, the travelling subject, or the ambient ground. A mute-test review scored comprehension 7/10 and named unlabelled decoration as the cause.
- **Budget ~20 on-screen words per section.** Labels of 1-2 words under their element, no sentences. The reference section 1 used 21 words in 84 seconds.
- **Give the viewer one travelling subject** whose state visibly changes (a chip with data rows and a score bar, a document, a request). A viewer can follow a whole section by watching it. It moves along drawn connectors at constant speed.
- **Show an anti-pattern apart from the recommendation**: take the world to near-black first, or place it where the good diagram isn't.
- **Use one global token set**: strokes, type sizes, radii, five colours with fixed meanings, and motion curves, all in [design-system.md](reference/design-system.md). Gate it with a token linter that fails the build. The first build had 18 stroke weights and 9 type sizes: "every decision was made locally and correctly; no decision was made globally."
- **Enter and exit full-bleed layers by clip** on an already-opaque background, so each pixel is either graphic or footage. Never cross-fade.

## Build contract

- **One generator per section.** `scripts/build_<id>.py` writes only `compositions/<id>.html`. Edit the generator; the HTML is output. Section roots `index-*.html` are hand-maintained, so framing changes go there.
- **Shared modules stay shared.** Every section imports the shared geometry. When parallel agents build sections, give shared modules a single owner; divergent geometry breaks every handoff.
- **Namespace the SVG defs before assembly.** Each section defines its own `gEdge`, `shadow`, `edgeFade`. In one DOM, `url(#id)` resolves to the first match, so once an earlier composition unmounts, later graphics paint nothing. This cost the reference build 35 seconds of empty screen with every gate green.
- **Time everything to word starts**, entering 0.15-0.25s **ahead** of the anchor word. Place each beat on its word, never on an even division of the section.
- **Audit gaps.** Any stretch over ~1.5s with nothing happening is a dead screen; have the generator print them.
- **Leave air in the cut, and shift baked times by script.** Before repairing tight sentence joins or changing the timeline after graphics exist, read [audio-and-timeline.md](reference/audio-and-timeline.md).
- **Render with `--workers 1`.** Parallel workers paint the video layer black.

## Gates

Run every gate in [verification.md](reference/verification.md), then look anyway: read a contiguous frame strip across every transition, read legibility by eye, check each gate against a control, and verify the assembled render rather than section prototypes. Aim for ~40% speaker on screen.
