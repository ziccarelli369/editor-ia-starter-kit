---
name: character-film
description: 3D character film of 8-20 s in Blender, the "No After Effects" format: a toy hero builds a motion graphic by hopping on the tools of a giant software UI. Use when the user wants that format, a brand swap of it, "película 3D" or "personaje que arma el video". Runs the gates and the rounds.
---

# Character film

A toy 3D hero lives on a software workspace that lies flat like a glowing
desk. Every **hit** (a landing, a press, a stamp, a strike) sits on a beat
frame and changes the RESULT that plays on the app's viewer. At the end the
app falls away, and only the result stays. The reference is the prompt pack
"No After Effects": 12 s, 1920x1080, 30 fps, 120 BPM, Blender Cycles.

One prompt yields one clip. This skill runs a studio instead: the second film
starts from a new brief and reuses the engine, the checks and the gates of
the first. Five layers split across three skills:

| Layer | Question | Skill |
| --- | --- | --- |
| Director, reference | Which one sentence stays with the viewer? Which measured look serves it? | `film-brief` |
| Timeline, renderer | Which frame holds each hit, and what does it change? What draws each frame, from which inputs? | `film-engine` |
| Critic | Which defect, on which frames, from which cause? | `film-critic` |

This skill runs the gates and the rounds between them.

## Taste and engine

Two kinds of work, two models (`kit.config.json` `models`):

- **Taste** goes to the design model (Opus 5.5): the brief, the app design,
  the result, the hero, the look, the motion, the camera, the sound, every
  critic verdict and every ruling.
- **Engine** goes to the engineer model: engine code, scene assembly, checker
  code, render and verify plumbing. It takes taste values as inputs and never
  picks a colour, a pose, a shot or a sound.

## Project

`npm run new-video -- <slug> --kind film --mode guided --brand <brand|none> --size 1920x1080 --fps 30`
copies `film-engine/templates/project/` into `video-projects/<id>/`. It
refuses when the machine check fails, and inside a git worktree: the project
folder is git-ignored and dies with the worktree. The scaffold runs as is
with grey placeholders; every `# TASTE:` line is a decision for the design
model. File owners:

| Files | Owner |
| --- | --- |
| `DESIGN.md` (brief, rulings), `timeline.py` (the contract), `checks_config.py` (every threshold), `VERIFY.md` | director |
| `ui_build.py` | UI |
| `comp.html`, `comp.js` | result |
| `hero_spec.py`, `look.py` | hero and look |
| `motion.py` | motion |
| `shots.py` | camera |
| `score.py` | sound |
| `scene.py`, `build/`, `renders/`, `reviews/` | integrator |

## Gates

Each gate needs the user's yes in chat, unless the user gave the taste
decisions to the design model for this film. Then the director decides,
writes the reason in `DESIGN.md`, and keeps going.

0. **Machine.** The film path is optional; run `npm run setup -- --film`.
   Done when it prints ok for Blender 5.x with a GPU device, Chrome,
   puppeteer-core, ffmpeg and the kit `.venv` (numpy, scipy, pedalboard,
   Pillow). For each FAIL, follow its hint: `npm run film:install` builds the
   venv; the user installs Blender. Install only after the user's yes, and
   name the download size.
1. **Brief.** Run `film-brief`. Done when the project `DESIGN.md` holds ONE
   SENTENCE, BRAND (HERO, APP, RESULT, SET), BEATS, CAMERA, LOOK, SOUND,
   VERTICAL, CHECKS and DO NOT.
2. **Contract.** The director writes `timeline.py` and `checks_config.py`.
   Every hit sits on a whole frame of the beat grid. Then run
   `python -B build.py --upto ui` and the feasibility what-if for every
   two-shot press (`film-critic`, What-if). Done when the UI contract passes,
   `build/ui_check.png` was read, and every press can frame the hero at its
   width ruling with the result upright and in frame. If a press fails, move
   the button now: in the reference, one far-away Play button cost two rounds.
3. **Build round.** Run the round workflow in `build` mode (below). Done when
   the critic verdict exists for round 1.
4. **Rulings.** The director reads the verdict, the contact sheets and the
   animatic. For each issue: fix (with an owner and a predicted number) or
   accept (a written ruling in `DESIGN.md`). Route every OPEN item to an owner.
5. **Fix rounds.** Run the round workflow in `fix` mode with the top three
   defects and every blocker. Repeat steps 4 and 5 until the critic lists no
   blocker. When the film holds together, render a 1080p v1 as insurance and
   send it to the user.
6. **Final.** `python -B build.py --upto final`, then encode, then
   `verify_final.py`. Make each format its own composition: the 9:16 cut
   gets its own `shots.py` holds and its own model check, never a crop of
   16:9. Done when `VERIFY.md` holds every measurement and the critic of the
   final frames lists no blocker.

## Round workflow

```
Workflow({ scriptPath: "<kit>/.claude/skills/character-film/templates/round.workflow",
           args: { kit, project, film, round, mode, roles, integrator, critic, reportLines } })
```

The args shape is in the file header. The director writes every owner's
brief: numbered notes, each with a measurable target. Keep the report cap
shrinking (60, 45, 35 lines). Split motion and camera into two owners: in
the reference, one owner for both was the long pole of every round.

Mark motion and camera roles `stage: "motion"`. The scene assembly then
starts as soon as the other owners finish, while motion is still in work,
and four lens critics (framing, look, story, sound) judge in parallel before
a head critic merges one verdict. A role that carries `report` (its finished
report) runs no agent: give every role its report to resume a stalled round
from its integration. Give every role an `until` timebox ("HH:MM"): the
motion owner runs longest, and an owner without a deadline polishes forever.

## Cost

On an RTX 5070 Ti, 1080p at 64 samples costs about 1.8 s a frame: 11 min for
12 s of film. The review rounds cost the time: about 1 to 2 h each. The
reference took 5 rounds, 24 agents, 7 M tokens and 8.5 h. Give the user the
round count, not only the render time.

## Rules the reference paid for

Read [references/production-rules.md](references/production-rules.md) before
round 1 and before each director note. The short form:

- The director owns the contract and every threshold. An owner reports a
  conflict with numbers and options; the critic also checks the thresholds
  in the check code.
- After a contract change, one rebuild: `build.py` refuses stale inputs.
- One GPU job at a time. Time a render only on an idle GPU.
- Gate the final on "no blocker". A major goes to the director: fix or a
  written accept.

## Kit checks

For a film project, `node scripts/preflight.mjs video-projects/<id>` runs the machine check
and the build dry run (the stale steps). `hyperframes lint`,
`align-captions`, `hearing-check` and `av-sync-check` check HyperFrames and
speech, so they do not apply. Name them in a "Kit checks that do not apply"
section of `VERIFY.md`. The replacements: the UI contract, the result contact
sheet, the model check, `stills.json`, the sound check and `verify_final.py`.

## Deliver

First make the two files no build step makes. The cover is the poster
still of each final, chosen by the director:
`ffmpeg -ss <t> -i renders/<slug>.mp4 -frames:v 1 renders/cover.png` (and
`renders/cover-9x16.png` from the vertical cut). The caption follows the
`deliver` skill's caption rules, written to `renders/caption.txt`.

Then, from the kit root, with no `--srt` (the film has no voice):
`node scripts/deliver.mjs <id> --video video-projects/<id>/renders/<slug>.mp4 --cover video-projects/<id>/renders/cover.png --caption video-projects/<id>/renders/caption.txt`.
Deliver the vertical cut with `--name <slug>-9x16` and its own cover, and a
fix with `--name <slug>-v2`. Ask the user to listen: a measured mix is not
a heard mix. Before you move or archive the project folder, run
`npm run unlock -- <id>` and stop only the processes this session started.
