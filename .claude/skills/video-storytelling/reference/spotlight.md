# Spotlight implementation

Read this when you write the opacity logic. The rule (one element lit, the rest
quiet but legible) is in the skill; the target luma per state is in
[design-system.md](design-system.md).

The implementation is one function, called at every narration beat with the ids
being talked about (`build_s01.py`, `lit()`):

```python
def lit(t, active, warm=(), dur=0.5, floor=FLOOR):
    active = list(active) + [g + "-l" for g in active if g + "-l" in order]
    for gid in order:
        if gid not in opac:      # never drawn: nothing to light
            continue
        tgt = 1.0 if gid in active else (WARM if gid in warm else floor)
        if gid not in active:
            tgt = min(tgt, MUTED.get(gid, 1.0))
        ...
```

The load-bearing details:

- **A label inherits its element's state** (the `-l` suffix fold-in). A lit
  element over an unreadable label is the exact defect being fixed.
- **A finished prop retires to opacity 0** through a `MUTED` cap. Emit the
  `mute()` **before** any later-starting `lit()`, or the mute is overwritten when
  its tween completes.
- **Emit opacity events in timeline order.** Out of order, the tracker sees stale
  state and computes the wrong target. Keep a `seq()` guard that raises on
  out-of-order emission.
- **One opacity authority per element per window.** Two concurrent tweens that
  drive one element's opacity to different values render smoothly in a section
  but strobe at ~10Hz in the assembled master. The reference build shipped this
  at every dock. When a sweep like `lit()` overlaps an explicit brighten or mute,
  the later-starting tween is the sole driver and the sweep skips those ids
  (`lit(..., skip=(...))`). Gate it: scan assembled renders for one-frame
  out-and-back luminance pops in every transition window
  (`qa/v4/flicker/qa-flicker.mjs` in the reference build).
