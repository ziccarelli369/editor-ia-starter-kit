# Verification

Read this before the first render you gate. Run every gate, then look anyway:
gates that have never failed are not gates.

## Gate commands

```bash
node scripts/qa-tokens.mjs          # 0 off-system strokes / type sizes / radii
node scripts/qa-no-crossfade.mjs    # 0 full-bleed layers animating opacity
node scripts/qa-legibility.mjs <render>
node scripts/qa-exposure.mjs <render> assets/edit-master.mp4 plan/cover-seams.json
node scripts/qa-seamjump.mjs <render> plan/cover-seams.json --control <cut>
node scripts/qa-deadframe.mjs <render> --control <cut>
node scripts/qa-presence.mjs <render> --every 1      # speaker on-screen share
node scripts/integrate.mjs --check                   # 0 gaps, 0 stale mounts
npx hyperframes lint                                 # 0 errors, 0 warnings
ffmpeg -hide_banner -i <render> -vf blackdetect=d=0.03:pix_th=0.06 -f null -   # 0
```

The kit does not ship the `qa-*` and `integrate.mjs` scripts; they come from the
reference build. Write the equivalents for the project, each with a control.

## Look after the gates

- **Read a contiguous strip across every transition window** (camera move, wipe,
  reframe, dock, section seam). One frame per beat proves composition; every
  motion defect (a jump into a move, a crawl to a dead stop before a second move,
  a freeze, a one-frame pop) lives between beat frames.

  ```bash
  ffmpeg -i render.mp4 -vf "select='between(n,A,B)',scale=480:270,tile=layout=6x7" \
    -frames:v 1 tile-<window>.png
  ```

  Defect signatures: a large jump then several near-identical tiles (front-loaded
  ease, dead stop); a motion that halts and a different motion that then begins
  (two moves that should be one gesture); one tile unlike both neighbours (pop).
  The worked example's intro shipped a zoom-freeze that passed tokens,
  cross-fade, legibility, dead-gap, and per-beat frame reads; the client caught
  it in one viewing. This class recurs.
- **Read legibility by eye** on a 960x540 downscale of every major beat. Pixel-
  share thresholds measure text volume, so a wordy build scores higher.
- **Validate every gate against a control** known to trip it. A seam gate that
  reports zero on a broken build is worse than no gate.
- **Verify the assembled artifact**, not section prototypes. Most bugs that
  survived the reference build's gates existed only in the assembly.
- **Audit the audio acoustically**: see [audio-and-timeline.md](audio-and-timeline.md).

## Presence

Aim for ~40% speaker on screen across a graphics-led video. Long absences are
fine at payoff beats that need full width; audit them rather than capping them.
The reference build's measured presence is in [design-system.md](design-system.md).
