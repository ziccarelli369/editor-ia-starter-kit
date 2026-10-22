/* comp.js: the result the app's viewer plays, drawn per film frame on a canvas (frames-render.mjs).
 * A classic script (no import): frames-render injects window.FilmKit and window.FilmEase before it runs.
 * Page contract (frames-render.mjs header): loadFonts(), init(timeline), render(f), bboxes().
 * The greybox result is a counter that increments on each press (timeline.frames[f-1].count) with a
 * short pop after the press. Every colour, size, font and motion value below is TASTE.
 */
(function () {
  const K = window.FilmKit, E = window.FilmEase;
  if (!K || !E) throw new Error('engine not injected before comp.js');

  // TASTE: palette falls back to the timeline theme; type sizes; the pop after a press.
  const FONT = (px) => `700 ${px}px CompFont`;
  const COUNT_PX = 96, TC_PX = 14;
  const POP = { scale: 0.25, s: 0.25 };          // extra scale at the press, decay time (s)

  let TL, W, H, ctx, theme, presses;

  function pressAge(t) {
    let best = null;
    for (const p of presses) if (p <= t + 1e-9 && (best === null || t - p < best)) best = t - p;
    return best;
  }
  function scaleAt(t) {
    const age = pressAge(t);
    return age === null ? 1 : 1 + POP.scale * Math.exp(-age / POP.s);
  }
  function countBox(st) {
    // The analytic box of the counter: measured text at the frame's scale, centred on the canvas.
    const s = scaleAt(st.t);
    ctx.font = FONT(COUNT_PX);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const m = ctx.measureText(String(st.count));
    return K.box(W / 2 - m.actualBoundingBoxLeft * s, H / 2 - m.actualBoundingBoxAscent * s,
                 W / 2 + m.actualBoundingBoxRight * s, H / 2 + m.actualBoundingBoxDescent * s);
  }

  window.FilmPage = {
    loadFonts: () => K.loadFonts([FONT(COUNT_PX), FONT(TC_PX)], '0123'),
    init(tl) {
      TL = tl;
      [W, H] = tl.format.comp;
      theme = (tl.extra && tl.extra.theme) || { bg: '#000000', ink: '#c8c8c8', dim: '#555555' };
      presses = tl.events.filter((e) => e.kind === 'press').map((e) => e.t);
      const c = document.getElementById('c');
      c.width = W; c.height = H;
      ctx = c.getContext('2d');
    },
    render(f) {
      const st = TL.frames[f - 1];
      if (!st || st.f !== f) throw new Error('no state for frame ' + f);
      ctx.fillStyle = theme.bg;
      ctx.fillRect(0, 0, W, H);
      const s = scaleAt(st.t);
      ctx.save();
      ctx.translate(W / 2, H / 2);
      ctx.scale(s, s);
      ctx.font = FONT(COUNT_PX);
      ctx.fillStyle = theme.ink;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(st.count), 0, 0);
      ctx.restore();
      ctx.font = FONT(TC_PX);
      ctx.fillStyle = theme.dim;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'alphabetic';
      ctx.fillText(K.timecode(st.t, TL.format.fps), 8, H - 10);
      const box = countBox(st);
      const checks = [];
      if (!K.inFrame(box, W, H)) checks.push('counter leaves the canvas');
      return { seq: { comp: ctx.canvas.toDataURL('image/png') }, bounds: { count: box },
               luma: K.lumaStats(ctx, 2), checks };
    },
    bboxes() {
      return TL.frames.map((st) => ({ f: st.f, count: countBox(st) }));
    },
  };
})();
