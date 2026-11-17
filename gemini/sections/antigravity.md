## 6. Antigravity

**First reply of a session.** Name the rules file you loaded and three skills
you can see under `.agents/skills/`. When you see none, say so and stop.

**Setup.** With `node_modules/` missing, run `npm install` yourself. A missing
whisper.cpp blocks only footage with speech: for speech-free footage, continue
past that line of `setup.mjs` and say so.

**Footage outside the kit.** When the user names a folder or files outside
the kit, copy them into `inbox/` (copy, the originals stay) and go on with
`new-video`. This copy needs no extra yes: the user asked for it.

**Commands.** Run every command from the kit root. `scripts/inbox.mjs` takes
bare file names, each in quotes: `node scripts/inbox.mjs <id> "clip 1.mp4"`.
On a permission prompt for `node`, `npm`, `npx` or `ffmpeg`, tell the user
these four are the kit's tools.

**Seeing.** You judge picture from image files. Make them with ffmpeg (a
frame, a contact sheet, a strip across a cut) and open each one. When your
file tools cannot show an image, serve the folder with
`npx hyperframes preview` and look in the browser. State in `VERIFY.md` which
way you looked.

**Action footage with no speech** (training clips, sparring, a match). Create
the project with `--mode freeform` and build the reel with ffmpeg:

1. Probe every clip with ffprobe. Make one contact sheet per clip and look at
   each.
2. Write `edl.json`: per shot, the source file, in and out times, and the
   visible action. Keep the 0.5 to 2.5 s where the action and its result
   show. Open on the strongest moment.
3. Music: a track from `music/`, cut on its beat grid
   (`node .agents/skills/motion-showreel/scripts/music-grid.mjs <track>`).
   With an empty `music/`, ask the user for a track; the clips' own sound is
   the fallback, and you say which you used.
4. Build with a script saved in the project (`build.mjs`): one ffmpeg call
   per shot, `-ss` before `-i`, re-encoded to 1080x1920 at 30 fps, then one
   concat with the audio. Aim for 7 to 20 s.
5. Delete the starter `index.html` and `compositions/` when the reel has no
   HyperFrames layer; they hold placeholder text and the text gate reads them.
   `preflight.mjs` and `hyperframes lint` check HyperFrames only, so skip them.
6. Look at a frame on every cut and on every hit. Write `VERIFY.md`, with a
   "Not run, and why" list (transcript, captions, hearing check: no speech).
7. Stage, show the user, and promote after their yes:
   `node scripts/deliver.mjs <id> --stage --video <mp4> --cover <png>`.

On-screen text (a hook line, captions) needs the text board first, then a
HyperFrames layer or ffmpeg `drawtext`.

**Text gate.** `deliver.mjs` refuses to stage or promote a project whose
on-screen text has no finished text board, and `preflight.mjs` reports it.
`.agents/hooks.example.json` adds the same check before each write; it is off
until the user turns it on (`docs/EXPERTO.md`).
