# editor-ia-starter-kit

A starter kit for short-form video editing (Reels, Shorts) with Claude Code and
HyperFrames. Footage goes into `inbox/`, finals come out of `outbox/`.
Built on Herk Edit Kit by Nate Herk (MIT) and HyperFrames by HeyGen (Apache-2.0).

## 1. Identity

Claude Code only. No other agent runtime, no model routing files.
Read `kit.config.json` before any task. It sets the language, the model profile,
the transcription provider, the default brand and the delivery contract.
Speak to the user in `language` from the config (default `es`). Skills, docs and
code stay in English.

## 2. Always rules

Folders:

- `inbox/`: the user drops any footage, audio, references here. Nothing is sorted.
  At project start, list it with `node scripts/inbox.mjs`, propose which files
  belong to the project, and move them only after the user confirms.
- `video-projects/<yyyy-mm-dd>-<slug>/`: all work in progress. `raw/` holds the
  moved sources. `project.json` is the truth about the project. Run HyperFrames
  from this folder.
- `outbox/<project-id>/`: finals only. Every project ends here with a video and
  a cover; `caption` and `srt` by default. `node scripts/deliver.mjs` enforces it.
- `brands/<slug>/`: one folder per client. `DESIGN.md`, `tokens.css`, `fonts/`,
  logo. A project names one brand in `project.json`. Read that brand only.
  Never read, copy or reuse another brand's files in this project.
- `styles/drafts/` and `styles/core/`: editing styles reverse-engineered from
  reference videos. Any brand can use any style. Promotion to core is manual.
- `PROJECTS.md`: generated index. Rebuild with `npm run projects`. Never edit it.

Create a project with `npm run new-video -- <slug> --brand <brand> --mode guided|freeform`.
Preserve raw files. Write each editing stage to a new filename. Never print
secrets. Never copy private media into the kit's examples or styles.

## 3. Models

The design model is Claude Opus 5.5. It owns taste: story, cuts, graphics, sound.
Profile `solo` (default): one Opus agent does everything.
Profile `team`: Opus orchestrates and decides; Claude Haiku 5.5 subagents run
mechanical parallel work only (transcripts, probes, validators, contact sheets).
Switch to `team` when the user says usage is low, or when the config says so.
Never use Fable. Never let a Haiku subagent make a design decision.

## 4. Map

The front door is `/new-video`. It asks one question: guided or freeform.

Guided: the kit's known path, Nate's playbook and gates. Load `new-video`, then:

| Need | Skill |
| --- | --- |
| Reel, Short, short ad from footage | `short-form-edit` |
| Full raw-video edit, long form | `edit-video` |
| Silence removal | `cut-silences` |
| Retakes, false starts, stutters | `cut-mistakes` |
| Brand reel cut to music, intros | `motion-showreel` |
| Motion-graphics video from a brief, no footage | `make-a-video` |
| Video from a website (browser pane capture) | `website-to-hyperframes` |
| Narrative arc, persistent world | `video-storytelling` |
| Overlay beats, glass cards, paper takeovers | `hyperframes-video-beats` |
| Pick or extend motion-graphics cards | `style-library` |
| Apply a reverse-engineered editing style | `apply-style` |
| Turn a reference video into a new style | `reverse-engineer-style` |
| Put finals in the outbox | `deliver` |
| HTML compositions and media timing | `hyperframes` |
| Preview, lint, render, transcribe | `hyperframes-cli` |
| Timeline animation | `gsap` |
| Install HyperFrames catalog blocks | `hyperframes-registry` |

Freeform: no workflow, no playbook, no gates. The user drives. Suggest, ask,
try things. The same tools are available. The delivery contract still applies.

Before creative work read `MOTION_PHILOSOPHY.md`, the brand's `DESIGN.md`, and
the project's `DESIGN.md`. The brand and the project brief win over defaults.

Transcription: `npx hyperframes transcribe <video>` (local Whisper) unless the
config says `elevenlabs`. Without `ELEVENLABS_API_KEY` or `KIE_API_KEY`, the
fallback for sound, music, stills and B-roll is motion graphics designed by the
agent in HyperFrames. Say which fallback was used. Analysis and rendering run on
the user's machine; speed depends on its CPU, ffmpeg and Chrome.

## 5. Gates

- Never move files out of `inbox/` without the user's yes.
- Never make a paid API call the user did not ask for. Name the cost first.
- Never publish, upload, post or contact anyone. The outbox is the end.
- Never delete raw footage or a delivered outbox file.
- Cut silences first, then cut mistakes on the retimed transcript. Never mix
  original timestamps with edited footage.
- Run `node scripts/preflight.mjs <project>` and `npx hyperframes lint` before
  a draft render. Review the draft in Studio (browser pane), inspect hero frames
  and transitions, listen to the joins. Record evidence in `VERIFY.md`.
- A lint pass is not visual proof. Only a reviewed render is.
- A style skill leaves `styles/drafts/` only after one test render and the
  user's "looks right".
