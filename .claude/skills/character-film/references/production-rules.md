# Production rules

Each rule cost the reference film ("No After Effects", 5 rounds, 24 agents,
8.5 h) time or a round. The evidence is in brackets. Rules for the engine
(Blender API, Windows, puppeteer) are in `film-engine/references/gotchas.md`.

## Contract

1. The director writes `timeline.py` before any owner starts. It holds the
   format, the frame math, the layout in UI px, every event in seconds, and
   pure functions of time. Every reader imports it or reads `build/timeline.json`.
   Nobody copies a number out of it.
2. Write every hit time as a whole frame on the beat grid (`n*BEAT` or
   `f/FPS`). `frame(t) = floor(t*fps + 0.5) + 1`. [Python `round()` put six
   sound events half a frame off the picture.]
3. Pick a BPM whose sixteenth note is a whole number of frames. At 30 fps:
   BPM = 450/k, so 150, 112.5 or 90. [At 120 BPM an eighth is 7.5 frames.]
4. Fix the side names (`_px`, `_nx` by local axis) and one Euler order before
   the parallel build. [The rig and the motion named sides oppositely; the
   scene owner had to add a mapping.]
5. After any `timeline.py` change, run one rebuild: timeline.json, the UI, the
   result and clock sequences, the sound, the .blend. [A v1 render used clock
   PNGs from an older timeline.]

## Ownership

6. Every output file has exactly one owner (the table in `DESIGN.md`). Scratch
   caches get the owner's name. [Two owners overwrote one bbox file.]
7. Nobody writes `build/` while a Blender render reads it. [The result
   sequence was rewritten mid-render: frame 356 rendered with a black screen.]
8. The director owns every threshold. An owner never lowers one. [The motion
   owner set a 5.5 % width against a 10 % ruling and reported 0 violations.]
9. After every round, route every OPEN item to a named owner, or grant one
   owner a file for one round. [An unrouted rig problem came back as a major
   two rounds later.]

## Measurement

10. Measure the hero by its silhouette: surface points or the render mask,
    never a padded box. [A padded box read 12-15 % width; the mask read 9-11 %.]
11. Use per-element rules: each text box 100 % inside the frame with a 2 %
    margin at every press. Never a union rule. [A "95 % of the content" rule
    let the first letter of the title fall off the frame.]
12. Put every unit in frame fractions: margins and sizes as a fraction of the
    frame, speed in frame widths per second, blur in output pixels.
13. Turn every accepted critic note into a failing rule with a named constant
    in the checker. The checker is the memory of the rounds.
14. Measure the brand colour in the render, never trust the base colour.
    [AgX needed a deeper base than the hex: (0.526, 0.075, 0.024) linear for
    #D97757.]

## Camera

15. Split motion and camera into two owners, or start the camera earlier.
    [The combined owner took 42-78 min a round; the others took 3-22 min.]
16. Give every hit a still hold from 2 frames before to 2 frames after. Move
    the camera only between hits (ease, orbit whip, truck).
17. Keep the result in frame with the hero at every press: cause and effect
    in one shot. Solve hold positions; do not hand-place them.
18. Before a camera or geometry note goes out, run a what-if and put the
    predicted number in the note. [A "lift it 1.5 cm" note changed nothing;
    a "pan 4 %" note left the title 0.5 % outside.]
19. When a new heading appears, check the background edges. The world is
    near-black to camera rays only. [A new angle saw the studio's open side.]

## Render and GPU

20. One GPU job at a time. Time a render only when the GPU is idle.
    [Estimates under load were 5x too high: 55-71 min against 11 min.]
21. Stills: persistent data off, `frame_set` on the context scene. Never save
    the .blend after a stills run. [Out-of-order stills lost the shards.]
22. Render a 1080p v1 as insurance once the film holds together, and run the
    next round at the same time: the v1 script writes `renders/v1/DONE` at the
    end, and every owner and the integrator write nothing into `build/` until
    that file exists (a render reads the result sequences frame by frame).

## Critic loop

23. The critic did not build the film and judges only rendered frames.
24. Every critic prompt starts with a freshness check: renders newer than the
    .blend, the .blend newer than every input. [Critic 3 reviewed stale renders.]
25. Paste three lists into each critic prompt: the prior issues, the
    integrator's OPEN list, the director's rulings. [The critic missed an
    item the integrator had reported.]
26. Gate the final render on "no blocker". Majors go to the director as fix or
    a written accept. [Both automatic final gates waited for zero majors and
    never opened; the director rendered by hand.]
27. Expect four critic rounds. The issue count in the reference fell
    14 -> 11 -> 9 -> 5 -> 1.
28. An integrator that ends its turn while a render runs hands the critic
    stale frames. It waits for every render it started, then reports. [The
    TAP TO SUBMIT polish pass lost its final render this way.]
29. Never message an owner while its round runs. A message to a running
    workflow agent resumes a second copy of it; the two copies write the same
    files, and stopping by agent id can stop the wrong copy. New notes go into
    the next round's brief. [Round 2 of TAP TO SUBMIT ran two hero and two
    engine copies until the director stopped one of each.]

## The user

30. Ask one install question that names the sizes (Blender is about 350 MB
    and needs an admin prompt). Then install in the background.
31. Send the first animatic and the v1 as soon as they exist. ETAs were about
    2x low; say the round count.
32. The project folder and the outbox are git-ignored, so a film inside a
    worktree dies with the worktree. `new-video` refuses there; make the film
    in the main checkout. [TAP TO SUBMIT was made in a worktree and had to be
    moved, 5.2 GB.]
33. Watch long commands in the foreground. A `tail -f` left running holds the
    log open, and on Windows the project folder cannot move. Before moving or
    archiving a project, run `npm run unlock -- <id>`. [Eight orphan tails
    locked TAP TO SUBMIT.]
34. Every output path is absolute and inside the project; the engine refuses
    any other. [A relative stills path wrote to the drive root.]
