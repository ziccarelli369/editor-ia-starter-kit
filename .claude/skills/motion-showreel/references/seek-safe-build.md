# Seek-safe build rules

Read this before you write the showreel's HTML (step 6). Every rule keeps a frame identical whether the timeline plays forward or seeks to it.

- Every time comes from the beat sheet: `const B = (n) => n * PERIOD`.
- Put a **per-frame driver** on the timeline and make it a pure function of time:
  `tl.fromTo(drv, {t:0}, {t:END, duration:END, ease:'none', onUpdate:() => frame(drv.t)}, 0)`.
  Draw canvas effects (particles, noise, big grids) there from seeded values computed before draw time. Drive the HUD from the same function.
- Tween only transforms and opacity. To morph a dot into a tile, draw the final tile and scale it down into a circle (`border-radius: 128px / 72px` on a 256x144 tile), then tween back to scale 1.
- A property that several tweens animate across the reel (a shared flash layer) can stick on a backward seek. Compute it in the per-frame driver instead, and do the same for class swaps like an invert.
- Measure layout (`getBoundingClientRect`) once, at the top of the build, before any `immediateRender` tween applies a transform. Read measurements from that cache inside `onUpdate`.
- Put each `<video data-start>` in an untimed wrapper, outside any timed `.clip`. You can still scale the wrapper for push-ins.
- Staggered phases finish before their cut: latest completion = start + max delay + duration. Check it on paper, then in a render strip.
- Use solid fills and `text-shadow` for bloom on text; `background-clip: text` renders invisible in capture.
- Fonts: download them into the project's `assets/fonts/` and load them with `@font-face`, so the render never falls back to a system font.
