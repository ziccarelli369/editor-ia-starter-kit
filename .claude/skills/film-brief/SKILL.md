---
name: film-brief
description: Director's brief for a code-rendered film: studies a reference (prompt pack, article, film) with an evidence ledger, runs a concept panel, and writes the BRAND block and beat sheet. Use at character-film Gate 1, or when asked to reverse-engineer a type of video into a reusable brief.
---

# Film brief

Each decision the brief leaves open, the model settles with its blandest
default, and the film turns generic. So the brief settles every one of them
before the first render. It splits **facts** (the real app, the real logo, the
real rules of the subject) from **choices** (camera, timing, style). The model
may invent choices. It never invents a fact: a missing fact is a question to
the user.

All of this is taste work for the design model.

## 1. Inventory

List what the user gave: a prompt pack, an article, a reference film, a
theme, assets (logo, screenshots, music). Read each one fully. For a PDF,
`pdftotext -layout <file> <out.txt>`; for a video, the measure step below.
Done when every source is read and listed in `DESIGN.md` under SOURCES.

## 2. Reference study

Skip when there is no reference. Use the REA discipline: **observe**, then
**infer**, then admit **unknown**.

1. Write the questions the brief must answer, each with the evidence that
   answers it: the beat structure, the payoff, colour, light and surface,
   framing, rhythm, motion classes, type, the sound shape, the render
   pipeline.
2. Measure a reference video:
   `node .claude/skills/motion-showreel/scripts/analyze-reference.mjs <video> <out> --fps 6 --bpm <bpm>`.
   Read every sheet. For a prompt pack, copy its BRAND block, its beat table
   and its follow-up notes: the follow-ups are lessons to apply from the start.
3. Write `reviews/reference-ledger.md`, one row per claim:
   `| id | claim | evidence (file, time or page) | observed / inferred / unknown |`.
   A measured number is observed. A reason it works is inferred. A thing you
   could not see or hear is unknown.
4. Write REFERENCE ANALYSIS in `DESIGN.md`, one measured line per field:
   - colour: hex values, measured from frames or quoted from the source,
     never adjectives;
   - light and surface: what makes each highlight, and the finish (grain,
     glass, clean);
   - framing: the first place the eye lands in a shot, and where the hero
     sits;
   - rhythm: seconds from one change that matters to the next, against the
     BPM grid;
   - motion: for each object class, the entry (snap or ease), any overshoot,
     and the rest (settle or hold);
   - type: family, width and weight, and cap height as a % of the frame
     height.

   Add DO NOT COPY: whatever identifies the reference, such as its subject,
   its marks, its words and its signature shots.

Done when every question has a ledger row, or an unknown row that names the
missing evidence.

## 3. Concept panel

When the idea is open, run four independent directors and one judge:

```
Workflow({ scriptPath: "<kit>/.claude/skills/film-brief/templates/concept-panel.workflow",
           args: { kit, project, theme, audience, sources, constraints } })
```

The four angles: the faithful swap (the reference structure, new subject),
the journey (an arc the subject is known for), the world (the subject's
place and spectacle), and the double meaning (one pun between the subject and
the software, paid off on every beat). The judge scores clarity, theme truth,
boldness, causality, feasibility, the sound hook and the vertical cut, then
grafts the best ideas into one brief. Read the judge's brief with your own
eyes: check every fact about the subject yourself.

Done when one brief is chosen and its subject facts are checked.

## 4. Write the brief

Copy [templates/DESIGN.md](templates/DESIGN.md) into the project and fill
every section. The rules that make it buildable:

- **One sentence** the viewer remembers.
- **BRAND** is the only block that changes between films: HERO, APP, RESULT,
  SET. The rest of the brief uses only these names.
- **HERO** is a toy: rounded rigid parts, few joints, a silhouette that reads
  at 10 % of the frame width. Give sizes in cm and colours in hex. When the
  hero must hold or wrap something (a grip, a choke, a hug), check the reach
  now: arm length against the thing's size. [A 5.6 cm reach could never close
  a choke around the 2.5 cm cursor; it cost two rounds and stayed a toy read.]
- **APP**: name every panel and its state. Real labels read as the real app;
  no logos.
- **BEATS**: every row changes the RESULT, or it is the setup or the payoff.
  A hop that presses nothing is cut. Put each hit on a whole frame of the beat
  grid; at 30 fps a BPM of 450/k (150, 112.5, 90) keeps sixteenths on frames.
- **CAMERA**: a still hold at each hit, the result in frame with the hero,
  size rulings in % of the frame width.
- **LOOK**: the light that justifies every highlight. Glossy screens and big
  area lights fight: hide the fill and rim lights from glossy rays.
- **SOUND**: a copy-ready synth prompt (no samples, no words), one sound per
  hit, and a loudness contour per half second.
- **VERTICAL**: what changes in 9:16: what drops out of the frame, how the
  hero and the result stack top to bottom, and its own holds.
- **DO NOT**: the stock AI-film look (one fade-in for every element, a title
  parked mid-frame over a soft gradient, a logo saved for the last beat),
  wrong facts about the subject, legal risks.

Done when every section has a value, every subject fact has a source or the
user's word, and the user said yes (or gave the taste decisions to the design
model, recorded in `DESIGN.md`).
