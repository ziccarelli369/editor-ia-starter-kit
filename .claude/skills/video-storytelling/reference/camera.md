# Camera grammar

Read this before you write any camera move, framing, or wipe. The camera is the
edit: moving through a space that stays put costs the viewer nothing, while a cut
to a new graphic costs their bearings. A push-in reads as "look closer at what you
already understand"; the pull-back is where the work pays off.

## Altitudes

| Altitude | Shows | Used for |
| --- | --- | --- |
| World | the whole space | orienting, payoffs, "here is where we are" |
| Region | the subgraph under discussion | most of the runtime |
| Detail | one element | a number, a state change, a decision |

Move between adjacent altitudes. Jump detail to world only as a deliberate
payoff beat, where it is the best move available.

## Rules that each cost a rebuild

- **Name framings as exact world windows**, with window boundaries *between*
  labels. A framing written as "scale 0.6" slices words at the frame edge.
- **Reuse the same window for the same purpose.** If the orient shot is a given
  window, always use that exact window; near-identical framings read as drift.
- **Vary duration with distance travelled**, not one global preset.
- **Sequence camera and full-frame wipes: camera first, then wipe.** Concurrent,
  they guillotine content.
- **Make a cover layer opaque before the camera moves under it.** Reversed, part
  of the move shows and reads as a jump cut.
- **Keep every label at least 60px from the frame edge** (see the layout rules in
  [design-system.md](design-system.md)). Solve it by placement.
- **Merge two moves on one subject into one gesture.** A reframe that finishes
  and THEN a wipe that starts reads as a zoom, a dead stop, and a second motion:
  "a glitch and a pause". Give both a shared symmetric ease (`power2.inOut`)
  landing on the same frame, so the panel reads as pushing the footage aside.
- **Reserve front-loaded eases (`power3/4.out`) for element entrances.** On a
  visible footage move they spend ~90% of the travel early and crawl to a stop;
  on an entrance the crawl reads as settling. (This cost a client-flagged
  revision on the worked example's intro.)
