"""check: the model critic. Owner: checker. Standard library only.

Measures the planned film through the same pinhole model the camera solver
uses (camera.project), on every frame, with no renderer. Every unit is a
frame fraction (margins, sizes, void), frame widths per second (speed), frame
widths per frame^2 (acceleration), degrees per frame (turn) or px at film
width (blur), so thresholds carry between films and lenses. The engine holds
no threshold: every number comes from the project's RULES config (API.md,
'Check thresholds'). The report's line 'VIOLATIONS: N' and the exit code are
the gate.

The model a project passes is any object with:
  fmt: object with fps (int), duration (s), frames (int), film (w, h), bpm (or None)
  layout: layout.Layout (previs map only; optional)
  events: object with of_kind(kind) -> [event dicts {id, t, kind, frame, **fields}]
  camera(t) -> camera dict {pos, target, lens, fstop, focus_distance} (shaken)
  camera_raw(t) -> (pos, target, lens) unshaken
  hero_points(t) -> [world pts] or [] when hidden
  hero_blocks(t) -> [(centre, half, R)] oriented boxes (occlusion tests; optional)
  content_boxes(f) -> {name: [4 world pts] | None} boxes that must read, corners SW SE NE NW
  points_of(name, t) -> [world pts] named point sets (blur windows; optional)
  ground_poly -> [world pts] of the workspace outline (void measure)
  holds() -> [(name, t0, t1)];  whip_windows() -> [(t0, t1)]
  landings() -> [{'id', 't', 'target': (X, Y), 'sole_xyz', 'surface_z', 'pitch', 'rect_ok'?}]
  channels(t) -> {name: (value, floor | floor_class[, 'angle'])} every animated channel (continuity scan)
  probes() -> [world pts] still world points for the hit-stillness measure

Rules read RULES[name] (API.md section 4) and write violations as '[rule] f### t=.. ...'.
Optional keys beyond API.md: content_boxes 'min_in_frame' (area share), 'max_tilt_deg', 'max_hidden'
(share of the in-frame box the hero blocks hide, 1 - visible_share / area_in_frame, per frame through
that frame's camera; a number or {box: limit, 'default': limit}; needs hero_blocks);
camera_smooth 'max_turn_deg' is a number or {hold_name: deg, 'default': deg} where a named
limit covers the crossing into that hold and the hold itself; void 'cols'; continuity 'floors'
maps a channel's floor class to metres / radians / mm / f-stops; feet_above_ground 'ground_z'
(m, default 0, the slab tops); landings 'pitch_rad'; fstop_discipline 'flat_holds' names or
(t0, t1) windows.
"""
import math

from . import camera, timebase, vec

FILM = (1920, 1080)


# ---- report

class Report:
    """Collects violations, summary lines, sections and per-frame rows."""

    def __init__(self, title="model check"):
        self.title = title
        self.rules = []
        self.violations = []
        self.lines = []
        self.sections = []
        self.rows = []

    def violation(self, text):
        """Add one violation string (one rule, one frame or window, numbers in the text)."""
        self.violations.append(text)

    def line(self, text):
        """Add a summary line (printed after the VIOLATIONS line)."""
        self.lines.append(text)

    def section(self, title, lines):
        """Add a named section of text lines."""
        self.sections.append((title, list(lines)))

    def row(self, f, **cols):
        """Add a per-frame table row."""
        self.rows.append((f, cols))

    def text(self):
        """-> full report text; line 1 names the rules run, a line reads 'VIOLATIONS: N'."""
        out = [f"{self.title}: rules {', '.join(self.rules) if self.rules else '-'}",
               f"VIOLATIONS: {len(self.violations)}"]
        out += ["  " + v for v in self.violations]
        if self.lines:
            out += [""] + self.lines
        for title, lines in self.sections:
            out += ["", title] + ["  " + s for s in lines]
        if self.rows:
            cols = []
            for _, c in self.rows:
                for k in c:
                    if k not in cols:
                        cols.append(k)
            cells = [["f"] + cols]
            for f, c in self.rows:
                cells.append([str(f)] + [_cell(c.get(k)) for k in cols])
            widths = [max(len(r[i]) for r in cells) for i in range(len(cols) + 1)]
            out += ["", "PER FRAME"]
            out += ["  " + "  ".join(s.rjust(w) for s, w in zip(r, widths)) for r in cells]
        return "\n".join(out) + "\n"

    def write(self, path):
        """Write text() to path (utf-8). -> exit code (0 clean, 1 any violation)."""
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.text())
        return self.exit_code

    @property
    def exit_code(self):
        return 1 if self.violations else 0


def _cell(v):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


class Rule:
    """A named rule: fn(model, cfg, report) adds violations. cfg is RULES[name] from the project.
    needs: model attributes the rule reads; run() reports a missing one as a violation."""

    def __init__(self, name, fn, needs=()):
        self.name = name
        self.fn = fn
        self.needs = tuple(needs)


class Memo:
    """The model as rules see it: the project's model plus cached per-frame data.

    n frames, fps, film, t(f) seconds, cam(f) shaken camera dict, raw(f) unshaken
    {pos, target, lens}, pts(f) hero points, flow() = camera_flow of the unshaken path.
    Every other attribute reads through to the model.
    """

    def __init__(self, model):
        self._m = model
        self.fmt = model.fmt
        self.fps = model.fmt.fps
        self.n = int(model.fmt.frames)
        self.film = tuple(getattr(model.fmt, "film", FILM))
        self._cam, self._raw, self._pts, self._flow = {}, {}, {}, None

    def __getattr__(self, name):
        return getattr(self._m, name)

    def t(self, f):
        return timebase.time(f, self.fps)

    def cam(self, f):
        if f not in self._cam:
            self._cam[f] = self._m.camera(self.t(f))
        return self._cam[f]

    def raw(self, f):
        if f not in self._raw:
            raw = self._m.camera_raw(self.t(f))              # (pos, target, lens[, heading]): a 3-tuple still works
            pos, target, lens = raw[:3]
            self._raw[f] = {"pos": pos, "target": target, "lens": lens, "heading": raw[3] if len(raw) > 3 else None}
        return self._raw[f]

    def pts(self, f):
        if f not in self._pts:
            self._pts[f] = list(self._m.hero_points(self.t(f)))
        return self._pts[f]

    def flow(self):
        if self._flow is None:
            self._flow = camera_flow([self.raw(f) for f in range(1, self.n + 1)], self.film)
        return self._flow


def run(model, rules_cfg, rules=None, scan=True):
    """Run every rule named in rules_cfg (default: the STANDARD library). -> Report.
    scan=False skips the 480 Hz continuity scan (slowest rule). A rule whose cfg is None does not run."""
    rules = rules or standard_rules()
    m = model if isinstance(model, Memo) else Memo(model)
    rep = Report(getattr(model, "name", "model check"))
    for name, cfg in rules_cfg.items():
        if cfg is None:
            continue
        if name not in rules:
            rep.violation(f"[{name}] unknown rule (not in the library)")
            continue
        if name == "continuity" and not scan:
            rep.line("continuity: skipped (scan=False)")
            continue
        rule = rules[name]
        missing = [a for a in rule.needs if not hasattr(m, a)]
        if missing:
            rep.violation(f"[{name}] the model lacks {', '.join(missing)}")
            continue
        rep.rules.append(name)
        rule.fn(m, cfg, rep)
    _summary(m, rep)
    return rep


def standard_rules():
    """-> {name: Rule} of the built-in library:
    hero_margin, hero_width, content_boxes, still_at_hits, camera_smooth, ease_into_holds,
    fstop_discipline, void, continuity, landings, camera_floor, feet_above_ground, blur_budget."""
    table = [
        ("hero_margin", _r_hero_margin, ("hero_points", "camera")),
        ("hero_width", _r_hero_width, ("hero_points", "camera")),
        ("content_boxes", _r_content_boxes, ("events", "content_boxes", "camera")),
        ("still_at_hits", _r_still_at_hits, ("events", "camera", "probes")),
        ("camera_smooth", _r_camera_smooth, ("camera_raw", "holds", "whip_windows")),
        ("ease_into_holds", _r_ease_into_holds, ("camera_raw", "holds")),
        ("fstop_discipline", _r_fstop_discipline, ("camera", "holds")),
        ("void", _r_void, ("camera", "ground_poly")),
        ("continuity", _r_continuity, ("channels",)),
        ("landings", _r_landings, ("landings",)),
        ("camera_floor", _r_camera_floor, ("camera",)),
        ("feet_above_ground", _r_feet_above_ground, ("hero_points",)),
        ("blur_budget", _r_blur_budget, ("camera", "content_boxes")),
    ]
    return {name: Rule(name, fn, needs) for name, fn, needs in table}


# ---- rule helpers

def _frames_in(t0, t1, fps, n):
    """-> [f] with t0 <= time(f) < t1, clipped to 1..n."""
    return [f for f in range(1, n + 1) if t0 - 1e-9 <= timebase.time(f, fps) < t1 - 1e-9]


def _events_of(m, kinds):
    out = []
    for k in kinds or ():
        out += list(m.events.of_kind(k))
    return sorted(out, key=lambda e: (e["t"], e["kind"], str(e["id"])))


def _frame_text(m, f):
    return f"f{f:>3} t={m.t(f):5.2f}"


def _r_hero_margin(m, cfg, rep):
    need = cfg["min"]
    visible_only = cfg.get("visible_only", True)
    for f in range(1, m.n + 1):
        pts = m.pts(f)
        if not pts:
            if not visible_only:
                rep.violation(f"[hero_margin] {_frame_text(m, f)} hero hidden")
            continue
        mg = margin_of(pts, m.cam(f), m.film)
        if mg < need - 1e-9:
            rep.violation(f"[hero_margin] {_frame_text(m, f)} margin {mg * 100:5.1f} % < {need * 100:.1f} %")


def _r_hero_width(m, cfg, rep):
    default = cfg.get("default")
    zones = cfg.get("zones", ())
    exempt = cfg.get("exempt", ())
    for f in range(1, m.n + 1):
        t = m.t(f)
        if any(a - 1e-9 <= t < b - 1e-9 for a, b in exempt):
            continue
        lo, hi, why = default, None, ""
        for z in zones:
            if z[0] - 1e-9 <= t < z[1] - 1e-9:
                lo, hi = z[2], z[3]
                why = z[4] if len(z) > 4 else f"zone {z[0]}-{z[1]} s"
                break
        if lo is None and hi is None:
            continue
        pts = m.pts(f)
        if not pts:
            continue
        w = screen_size(pts, m.cam(f), m.film)[0]
        tag = f" ({why})" if why else ""
        if lo is not None and w < lo - 1e-9:
            rep.violation(f"[hero_width] {_frame_text(m, f)} width {w * 100:4.1f} % < {lo * 100:.1f} %{tag}")
        if hi is not None and w > hi + 1e-9:
            rep.violation(f"[hero_width] {_frame_text(m, f)} width {w * 100:4.1f} % > {hi * 100:.1f} %{tag}")


def _r_content_boxes(m, cfg, rep):
    end_field = cfg.get("effect_end_field", "effect_end")
    margin = cfg.get("margin")
    names = cfg.get("boxes")
    min_in = cfg.get("min_in_frame")
    max_tilt = cfg.get("max_tilt_deg")
    max_hidden = cfg.get("max_hidden")
    blocks_fn = getattr(m, "hero_blocks", None) if max_hidden is not None else None
    if max_hidden is not None and blocks_fn is None:
        rep.violation("[content_boxes] max_hidden needs the model's hero_blocks(t)")
    lines = []
    for ev in _events_of(m, cfg.get("at_kinds", ())):
        f0 = timebase.frame(ev["t"], m.fps)
        t1 = ev.get(end_field)
        f1 = f0 if t1 is None else max(f0, timebase.frame(t1, m.fps) - 1)
        f1 = min(f1, m.n)
        if f0 > m.n:
            continue
        cam = m.cam(f0)
        who = f"{ev['kind']} {ev['id']}"
        quads = {}
        for f in range(f0, f1 + 1):
            bx = m.content_boxes(f) or {}
            for name in (names if names else list(bx.keys())):
                q = bx.get(name)
                if q:
                    quads.setdefault(name, []).append(q)
        for name in (names if names else list(quads.keys())):
            qs = quads.get(name)
            if not qs:
                lines.append(f"f{f0:>3} {who}: {name} box not drawn in f{f0}-f{f1}")
                continue
            pts = [p for q in qs for p in q]
            mg = margin_of(pts, cam, m.film)
            share = min(area_in_frame(q, cam, m.film) for q in qs)
            tilt = max((baseline_tilt(q, cam, m.film) for q in qs), key=abs)
            lines.append(f"f{f0:>3} {who}: {name} box margin {mg * 100:5.1f} %  in frame {share * 100:5.1f} %"
                         f"  tilt {tilt:+5.1f} deg  (f{f0}-f{f1})")
            if margin is not None and mg < margin - 1e-9:
                rep.violation(f"[content_boxes] f{f0:>3} {who}: {name} box margin {mg * 100:.1f} % < {margin * 100:.1f} %"
                              f" (union f{f0}-f{f1})")
            if min_in is not None and share < min_in - 1e-9:
                rep.violation(f"[content_boxes] f{f0:>3} {who}: {name} box {share * 100:.1f} % in frame < {min_in * 100:.0f} %")
            if max_tilt is not None and abs(tilt) > max_tilt + 1e-9:
                rep.violation(f"[content_boxes] f{f0:>3} {who}: {name} box tilts {tilt:+.1f} deg on screen (> {max_tilt})")
            lim = max_hidden.get(name, max_hidden.get("default")) if isinstance(max_hidden, dict) else max_hidden
            if blocks_fn is None or lim is None:
                continue
            # hidden share per frame: 1 - visible_share(box, hero blocks) / area_in_frame, each through that
            # frame's camera (the hero moves while the camera holds), reported per frame, the worst flagged
            worst = (0.0, f0)
            for f in range(f0, f1 + 1):
                q = (m.content_boxes(f) or {}).get(name)
                if not q:
                    continue
                c = m.cam(f)
                inside = area_in_frame(q, c, m.film)
                hidden = 0.0 if inside <= 1e-9 else max(0.0, 1.0 - visible_share([q], c, list(blocks_fn(m.t(f))), film=m.film) / inside)
                lines.append(f"f{f:>3} {who}: {name} box hidden {hidden * 100:5.1f} % by the hero")
                if hidden > worst[0]:
                    worst = (hidden, f)
            if worst[0] > lim + 1e-9:
                rep.violation(f"[content_boxes] f{worst[1]:>3} {who}: {name} box {worst[0] * 100:.1f} % hidden by the hero"
                              f" > {lim * 100:.0f} % (f{f0}-f{f1})")
    rep.section("CONTENT BOXES (margin, in-frame share, baseline tilt at each event; hidden share per frame)", lines)


def _r_still_at_hits(m, cfg, rep):
    wf = cfg.get("window_frames", 2)
    vmax = cfg["max_fw_per_s"]
    hits = [(f"{ev['kind']} {ev['id']}", ev["t"]) for ev in _events_of(m, cfg["kinds"])]
    static = list(m.probes())
    has_boxes = hasattr(m, "content_boxes")

    def probes_at(t):
        if not has_boxes:
            return static
        bx = m.content_boxes(timebase.frame(t, m.fps)) or {}
        return static + [p for q in bx.values() if q for p in q]

    rows = hit_stillness(m.camera, hits, probes_at, wf, 1.0 / (8 * m.fps), m.fps, m.film)
    for name, t, sp in rows:
        if sp >= vmax:
            rep.violation(f"[still_at_hits] f{timebase.frame(t, m.fps):>3} t={t:5.2f} {name}: camera speed {sp:.3f} fw/s"
                          f" within {wf} frames (>= {vmax})")
    rep.section(f"STILL CAMERA AT HITS (max image speed of the still world within {wf} frames, frame widths / s)",
                [f"f{timebase.frame(t, m.fps):>3} {t:5.2f}s  {name:<28} {sp:.3f}" for name, t, sp in rows])


def _whip_frames(m):
    out = set()
    for t0, t1 in m.whip_windows():
        out |= set(range(timebase.frame(t0, m.fps) - 1, timebase.frame(t1, m.fps) + 2))
    return out


def _r_camera_smooth(m, cfg, rep):
    v, a, turn = m.flow()
    whips = _whip_frames(m)
    amax = cfg.get("max_accel")
    if amax is not None:
        bad = sorted(((a[f], f) for f in range(2, m.n) if f not in whips and a[f] > amax), reverse=True)
        for a_, f in bad[:12]:
            rep.violation(f"[camera_smooth] {_frame_text(m, f)} image acceleration {a_:.3f} fw/frame^2 > {amax} (not a whip)")
        if len(bad) > 12:
            rep.violation(f"[camera_smooth] ... and {len(bad) - 12} more frames over the image acceleration limit")
    tcfg = cfg.get("max_turn_deg")
    if tcfg is not None:
        if not isinstance(tcfg, dict):
            tcfg = {"default": tcfg}
        limit = [tcfg.get("default")] * (m.n + 1)
        named = [False] * (m.n + 1)
        prev_end = 0.0
        for name, t0, t1 in sorted(m.holds(), key=lambda h: h[1]):
            if name in tcfg:
                for f in range(max(1, timebase.frame(prev_end, m.fps)), min(timebase.frame(t1, m.fps), m.n) + 1):
                    limit[f], named[f] = tcfg[name], True
            prev_end = t1
        bad = sorted(((turn[f], f) for f in range(1, m.n) if limit[f] is not None and (named[f] or f not in whips)
                      and turn[f] > limit[f]), reverse=True)
        for tn, f in bad[:12]:
            rep.violation(f"[camera_smooth] {_frame_text(m, f)} turn {tn:.2f} deg/frame > {limit[f]}")
        if len(bad) > 12:
            rep.violation(f"[camera_smooth] ... and {len(bad) - 12} more frames over the turn limit")
    top_turn = sorted(((turn[f], f) for f in range(1, m.n)), reverse=True)[:6]
    top_acc = sorted(((a[f], f) for f in range(2, m.n) if f not in whips), reverse=True)[:6]
    rep.section("CAMERA FLOW (unshaken path)", [
        "fastest turns (deg/frame @frame): " + ", ".join(f"{x:.2f} @f{f}" for x, f in top_turn),
        "largest image accelerations outside whips (fw/frame^2 @frame): " + ", ".join(f"{x:.3f} @f{f}" for x, f in top_acc),
        f"whip frames: {len(whips)}"])


def _r_ease_into_holds(m, cfg, rep):
    v = m.flow()[0]
    for p in ease_ok(v, m.holds(), m.fps, cfg.get("frames", 4), cfg.get("ratio", 0.3)):
        rep.violation(f"[ease_into_holds] {p}")


def _r_fstop_discipline(m, cfg, rep):
    fst = [m.cam(f)["fstop"] for f in range(1, m.n + 1)]
    holds = list(m.holds())
    by_name = {h[0]: (h[1], h[2]) for h in holds}
    flat = []
    for x in cfg.get("flat_holds", ()):
        if isinstance(x, str):
            if x not in by_name:
                rep.violation(f"[fstop_discipline] flat hold {x!r} is not a hold name")
                continue
            flat.append(by_name[x])
        else:
            flat.append((x[0], x[1]))
    for p in aperture_audit(fst, holds, flat, m.fps, cfg.get("jitter", 0.02), cfg.get("hold_tol", 0.01),
                            cfg.get("eps", 1e-4)):
        rep.violation(f"[fstop_discipline] {p}")
    dd = [abs(b - a) for a, b in zip(fst, fst[1:])]
    k = dd.index(max(dd)) if dd else 0
    rep.line(f"f-stop: f/{min(fst):.2f}..f/{max(fst):.2f}, steepest change {max(dd) if dd else 0:.3f}/frame at f{k + 2}")


def _r_void(m, cfg, rep):
    vmax = cfg["max"]
    cols = cfg.get("cols", 33)
    kinds = cfg.get("at_kinds")
    if kinds:
        where = [(timebase.frame(ev["t"], m.fps), f"{ev['kind']} {ev['id']}") for ev in _events_of(m, kinds)]
    else:
        where = [(f, "") for f in range(1, m.n + 1)]
    lines = []
    for f, who in where:
        if f > m.n:
            continue
        mean, worst = void_above(m.cam(f), m.ground_poly, cols, m.film)
        lines.append(f"f{f:>3} {who:<20} void {mean * 100:5.1f} % (worst column {worst * 100:5.1f})")
        if mean > vmax + 1e-9:
            rep.violation(f"[void] {_frame_text(m, f)} {who}: void above the ground {mean * 100:.1f} % of the frame height"
                          f" > {vmax * 100:.0f} %")
    if kinds:
        rep.section("VOID (frame height above the ground polygon, mean over columns)", lines)


def _points_named(m, name, f):
    bx = m.content_boxes(f) or {}
    if bx.get(name):
        return bx[name]
    if hasattr(m, "points_of"):
        return m.points_of(name, m.t(f))
    return None


def _r_blur_budget(m, cfg, rep):
    for t0, t1, name, budget in cfg["windows"]:
        worst, wf = 0.0, None
        for f in _frames_in(t0, t1, m.fps, m.n):
            pts = _points_named(m, name, f)
            if pts is None:
                rep.violation(f"[blur_budget] {_frame_text(m, f)} no points named {name!r}")
                break
            cam = m.cam(f)
            b = defocus_px(cam, pts, m.film, cam.get("sensor_w", 36.0))
            if b > worst:
                worst, wf = b, f
        rep.line(f"blur {t0}-{t1} s {name}: max {worst:.1f} px" + (f" at f{wf}" if wf else ""))
        if worst > budget + 1e-9:
            rep.violation(f"[blur_budget] window {t0}-{t1} s {name}: blur {worst:.1f} px at f{wf} > {budget} px")


def _r_continuity(m, cfg, rep):
    rate = cfg.get("rate", 480)
    ratio = cfg.get("ratio", 4.0)
    floors = cfg.get("floors", {})

    def channels(t):
        out = {}
        for k, v in m.channels(t).items():
            val, fl = v[0], v[1]
            kind = v[2] if len(v) > 2 else None
            if isinstance(fl, str):
                kind = kind or ("angle" if fl == "angle" else None)
                fl = floors[fl]
            out[k] = (val, fl, kind)
        return out

    jumps = continuity_scan(channels, m.fmt.duration, rate, ratio)
    for t, k, d in jumps[:20]:
        rep.violation(f"[continuity] {k} jumps {d:.4f} at t={t:.4f} s (f{timebase.frame(t, m.fps)})")
    if len(jumps) > 20:
        rep.violation(f"[continuity] ... and {len(jumps) - 20} more jumps")
    rep.line(f"continuity scan at {rate} Hz: {len(jumps)} jumps")


def _r_landings(m, cfg, rep):
    bpm = m.fmt.bpm if cfg.get("on_beat", True) else None
    rows = landing_audit(m.landings(), m.fps, bpm, cfg.get("exceptions", ()), cfg.get("xy_mm", 1.0),
                         cfg.get("z_mm", 1.0), cfg.get("pitch_rad"))
    for r in rows:
        if not (r["ok"] and r["beat_ok"] and r["frame_ok"]):
            why = []
            if not r["ok"]:
                why.append(f"xy {r['dxy_mm']:.2f} mm, z {r['dz_mm']:+.2f} mm, pitch {r['pitch']:.4f}, rect {r['rect_ok']}")
            if not r["frame_ok"]:
                why.append("between frames")
            if not r["beat_ok"]:
                why.append("off the beat")
            rep.violation(f"[landings] {r['id']} at {r['t']:.4f} s (f{r['frame']}): " + "; ".join(why))
    rep.section("LANDINGS", [r["text"] for r in rows])


def _r_camera_floor(m, cfg, rep):
    z_min = cfg["min_z"]
    for f in range(1, m.n + 1):
        z = m.cam(f)["pos"][2]
        if z < z_min - 1e-9:
            rep.violation(f"[camera_floor] {_frame_text(m, f)} camera z {z:.3f} m < {z_min} m")


def _r_feet_above_ground(m, cfg, rep):
    lim = cfg["min_mm"] / 1000.0
    ground = cfg.get("ground_z", 0.0)
    for f in range(1, m.n + 1):
        pts = m.pts(f)
        if not pts:
            continue
        low = min(p[2] for p in pts) - ground
        if low < lim - 1e-9:
            rep.violation(f"[feet_above_ground] {_frame_text(m, f)} lowest hero point {low * 1000:.1f} mm"
                          f" (< {cfg['min_mm']} mm above z {ground})")


def _summary(m, rep):
    has_hero = hasattr(m, "hero_points")
    v, a, turn = m.flow() if hasattr(m, "camera_raw") else ([0.0] * (m.n + 1),) * 3
    margins, widths = [], []
    for f in range(1, m.n + 1):
        c = m.cam(f)
        pts = m.pts(f) if has_hero else []
        mg = margin_of(pts, c, m.film) if pts else None
        w = screen_size(pts, c, m.film)[0] if pts else None
        if mg is not None:
            margins.append((mg, f))
            widths.append((w, f))
        rep.row(f, t=m.t(f), margin_pct=None if mg is None else mg * 100, width_pct=None if w is None else w * 100,
                lens=c["lens"], fstop=c.get("fstop"), focus_m=c.get("focus_distance"),
                speed=v[f], accel=a[f], turn=turn[f], cam_x=c["pos"][0], cam_y=c["pos"][1], cam_z=c["pos"][2])
    if margins:
        mn = min(margins)
        rep.line(f"hero margin over {len(margins)} visible frames: min {mn[0] * 100:.1f} % (f{mn[1]}),"
                 f" mean {sum(x for x, _ in margins) / len(margins) * 100:.1f} %")
        wn = min(widths)
        rep.line(f"hero width: min {wn[0] * 100:.1f} % (f{wn[1]}), max {max(widths)[0] * 100:.1f} %")
    zs = [(m.cam(f)["pos"][2], f) for f in range(1, m.n + 1)]
    rep.line(f"camera z: min {min(zs)[0]:.3f} m (f{min(zs)[1]}), max {max(zs)[0]:.3f} m")


# ---- metrics (pure functions; the rules compose these)

def _proj(cam, X, film):
    return camera.project(cam["pos"], cam["target"], cam["lens"], X, film, cam.get("sensor_w", 36.0),
                          heading=cam.get("heading"))


def _tx(cam):
    return camera.tan_half(cam["lens"], cam.get("sensor_w", 36.0))


def margin_of(points, cam, film=FILM):
    """-> min over points of (1 - |ndc|) / 2 on both axes; -1 when any point is behind the camera."""
    m = 1e9
    for X in points:
        nx, ny, z = _proj(cam, X, film)
        if z <= 0:
            return -1.0
        m = min(m, (1 - abs(nx)) / 2, (1 - abs(ny)) / 2)
    return m


def screen_size(points, cam, film=FILM):
    """-> (width, height) of the projected points as frame fractions."""
    ndc = [p for p in (_proj(cam, X, film) for X in points) if p[2] > 0]
    if not ndc:
        return 0.0, 0.0
    return ((max(p[0] for p in ndc) - min(p[0] for p in ndc)) / 2,
            (max(p[1] for p in ndc) - min(p[1] for p in ndc)) / 2)


def project_poly(cam, pts, near=0.03, film=FILM):
    """World polygon -> screen polygon in ndc with near-plane clipping."""
    pos = cam["pos"]
    r, u, f = camera.basis_from_dir(vec.sub(cam["target"], pos), cam.get("heading"))
    cs = []
    for p in pts:
        d = vec.sub(p, pos)
        cs.append((vec.dot(d, r), vec.dot(d, u), vec.dot(d, f)))
    out = []
    n = len(cs)
    for i in range(n):
        a, b = cs[i], cs[(i + 1) % n]
        ain, bin_ = a[2] >= near, b[2] >= near
        if ain:
            out.append(a)
        if ain != bin_:
            s = (near - a[2]) / (b[2] - a[2])
            out.append(tuple(a[k] + (b[k] - a[k]) * s for k in range(3)))
    tx = _tx(cam)
    ty = tx * film[1] / film[0]
    return [(c[0] / (c[2] * tx), c[1] / (c[2] * ty)) for c in out]


def clip_rect(poly, x0, y0, x1, y1):
    """Sutherland-Hodgman clip of a 2D polygon to a rect."""
    def clip(poly, inside, inter):
        out = []
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            if inside(a):
                out.append(a)
            if inside(a) != inside(b):
                out.append(inter(a, b))
        return out

    def ix(xv):
        return lambda a, b: (xv, a[1] + (b[1] - a[1]) * (xv - a[0]) / (b[0] - a[0]))

    def iy(yv):
        return lambda a, b: (a[0] + (b[0] - a[0]) * (yv - a[1]) / (b[1] - a[1]), yv)

    for inside, inter in ((lambda p: p[0] >= x0, ix(x0)), (lambda p: p[0] <= x1, ix(x1)),
                          (lambda p: p[1] >= y0, iy(y0)), (lambda p: p[1] <= y1, iy(y1))):
        if not poly:
            return []
        poly = clip(poly, inside, inter)
    return poly


def clip_convex(poly, clip):
    """Clip a 2D polygon to a convex polygon of either winding."""
    if len(clip) < 3:
        return []
    sgn = 1.0 if sum(clip[i][0] * clip[(i + 1) % len(clip)][1] - clip[(i + 1) % len(clip)][0] * clip[i][1]
                     for i in range(len(clip))) > 0 else -1.0
    out = list(poly)
    for i in range(len(clip)):
        a, b = clip[i], clip[(i + 1) % len(clip)]
        if not out:
            return []

        def side(p):
            return sgn * ((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]))
        inp, out = out, []
        for j in range(len(inp)):
            p, q = inp[j], inp[(j + 1) % len(inp)]
            sp, sq = side(p), side(q)
            if sp >= 0:
                out.append(p)
            if (sp >= 0) != (sq >= 0):
                s = sp / (sp - sq)
                out.append((p[0] + (q[0] - p[0]) * s, p[1] + (q[1] - p[1]) * s))
    return out


def area(poly):
    """Shoelace area (absolute)."""
    if len(poly) < 3:
        return 0.0
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                   for i in range(len(poly)))) / 2


def area_in_frame(quad_world, cam, film=FILM):
    """-> share 0..1 of the projected quad's area inside the frame."""
    poly = project_poly(cam, quad_world, film=film)
    a = area(poly)
    return area(clip_rect(poly, -1, -1, 1, 1)) / a if a > 0 else 0.0


def box_margin(quad_world, cam, film=FILM):
    """-> min edge margin of the projected quad (frame fraction); negative when it spills."""
    return margin_of(quad_world, cam, film)


def baseline_tilt(quad_world, cam, film=FILM):
    """-> on-screen angle (deg) of the quad's bottom edge (corners SW, SE first). 0 = level."""
    a = _proj(cam, quad_world[0], film)
    b = _proj(cam, quad_world[1], film)
    if a[2] <= 0 or b[2] <= 0:
        return 0.0
    return math.degrees(math.atan2((b[1] - a[1]) * film[1], (b[0] - a[0]) * film[0]))


def grid_coverage(rect_world, cam, nx=24, ny=14, film=FILM):
    """-> share of an nx x ny grid over the world rect (corners SW, SE, NE, NW) that lands in frame."""
    c = rect_world
    inside = 0
    for i in range(nx):
        for j in range(ny):
            u, v = (i + 0.5) / nx, (j + 0.5) / ny
            p = tuple((1 - v) * ((1 - u) * c[0][k] + u * c[1][k]) + v * ((1 - u) * c[3][k] + u * c[2][k]) for k in range(3))
            a, b, z = _proj(cam, p, film)
            if z > 0 and abs(a) <= 1 and abs(b) <= 1:
                inside += 1
    return inside / (nx * ny)


def void_above(cam, ground_poly, cols=33, film=FILM):
    """Per screen column, the height above the ground polygon's top edge (a column that misses it counts
    whole). -> (mean, worst) frame fractions."""
    poly = project_poly(cam, ground_poly, film=film)
    vs = []
    for i in range(cols):
        x = -1 + 2 * i / (cols - 1)
        ys = []
        for j in range(len(poly)):
            a, b = poly[j], poly[(j + 1) % len(poly)]
            if (a[0] - x) * (b[0] - x) <= 0 and a[0] != b[0]:
                ys.append(a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0]))
        top = max(ys) if ys else -1.0
        vs.append(min(1.0, max(0.0, (1.0 - top) / 2.0)))
    return sum(vs) / len(vs), max(vs)


def hit_stillness(camera_fn, hits, probes, window_frames=2, h=1.0 / 240, fps=30, film=FILM):
    """For each (name, t) hit: fastest on-screen speed (frame widths/s) of in-frame probes within
    +-window_frames (4 samples per frame), central difference h. probes: [pts] or callable(t) -> [pts].
    -> [(name, t, fw_per_s)]."""
    out = []
    sub = 4
    ratio = film[1] / film[0]
    for name, t in hits:
        best = 0.0
        for i in range(-sub * window_frames, sub * window_frames + 1):
            tt = t + i / (sub * fps)
            if tt - h < 0:
                continue
            pts = probes(tt) if callable(probes) else probes
            ca, cb = camera_fn(tt - h), camera_fn(tt + h)
            for X in pts:
                a = _proj(ca, X, film)
                b = _proj(cb, X, film)
                if a[2] <= 0 or b[2] <= 0 or max(abs(a[0]), abs(a[1]), abs(b[0]), abs(b[1])) > 1.0:
                    continue
                vx = (b[0] - a[0]) / 2 / (2 * h)
                vy = (b[1] - a[1]) / 2 * ratio / (2 * h)
                best = max(best, math.hypot(vx, vy))
        out.append((name, t, best))
    return out


_FLOW_GRID = [(sx, sy) for sx in (-0.8, -0.4, 0.0, 0.4, 0.8) for sy in (-0.7, 0.0, 0.7)]


def _unproject(cam, sx, sy, film, depth):
    r, u, fw = camera.basis_from_dir(vec.sub(cam["target"], cam["pos"]), cam.get("heading"))
    tx = _tx(cam)
    ty = tx * film[1] / film[0]
    d = vec.norm(vec.add(vec.add(fw, vec.mul(r, sx * tx)), vec.mul(u, sy * ty)))
    s = -cam["pos"][2] / d[2] if d[2] < -1e-6 else depth
    return vec.add(cam["pos"], vec.mul(d, min(s, depth)))


def camera_flow(cams, film=FILM, depth=8.0):
    """cams: [camera dict per frame]. Unproject a fixed 5x3 screen grid to the ground z 0 (or `depth` m away),
    reproject in the next frame. -> (speed, accel, turn) lists indexed by frame 1..n (index 0 unused):
    speed[f] fw/frame from f to f+1, accel[f] fw/frame^2 (second difference over f-1, f, f+1),
    turn[f] deg of view-direction change from f to f+1."""
    n = len(cams)
    v, a, turn = [0.0] * (n + 1), [0.0] * (n + 1), [0.0] * (n + 1)
    ratio = film[1] / film[0]

    def fw(p):
        return (p[0] / 2, p[1] / 2 * ratio)

    for f in range(1, n + 1):
        c = cams[f - 1]
        W = [_unproject(c, sx, sy, film, depth) for sx, sy in _FLOW_GRID]
        if f < n:
            cn = cams[f]
            best = 0.0
            for X, (sx, sy) in zip(W, _FLOW_GRID):
                q = _proj(cn, X, film)
                best = max(best, math.hypot(*fw((q[0] - sx, q[1] - sy))))
            v[f] = best
            da = vec.norm(vec.sub(c["target"], c["pos"]))
            db = vec.norm(vec.sub(cn["target"], cn["pos"]))
            turn[f] = math.degrees(math.acos(max(-1.0, min(1.0, vec.dot(da, db)))))
        if 1 < f < n:
            cp, cn = cams[f - 2], cams[f]
            best = 0.0
            for X, (sx, sy) in zip(W, _FLOW_GRID):
                p = _proj(cp, X, film)
                q = _proj(cn, X, film)
                best = max(best, math.hypot(*fw((p[0] - 2 * sx + q[0], p[1] - 2 * sy + q[1]))))
            a[f] = best
    return v, a, turn


def ease_ok(speed, holds, fps, n=4, ratio=0.3, floor=0.004):
    """Into and out of every hold: speed over the n frames must fall monotonically from its peak and the
    last frame must be <= ratio * peak. speed[f] indexed by frame (camera_flow); holds [(name, t0, t1)].
    floor: fw/frame under which the camera counts as still (numerical tolerance). -> [problem strings]."""
    probs = []
    last = len(speed) - 1
    for name, t0, t1 in holds:
        fa, fb = timebase.frame(t0, fps), timebase.frame(t1, fps)
        for side, fs in (("arrives", [fa - k for k in range(n, 0, -1)]), ("leaves", [fb + k for k in range(n)])):
            if fs[0] < 1 or fs[-1] >= last:
                continue
            sp = [speed[f] for f in fs]
            if side == "leaves":
                sp = sp[::-1]
            peak = max(sp)
            kp = sp.index(peak)
            mono = all(sp[k + 1] <= sp[k] + floor / 2 for k in range(kp, len(sp) - 1))
            ok = peak < floor or (mono and sp[-1] <= max(floor, ratio * peak))
            if not ok:
                probs.append(f"{name}: the camera {side} un-eased f{fs[0]}-f{fs[-1]} (speeds toward the hold "
                             + " ".join(f"{x:.3f}" for x in sp) + f", need the last <= {ratio} x peak)")
    return probs


def aperture_audit(fstops, camera_holds, flat_holds, fps, jitter=0.02, hold_tol=0.01, eps=1e-4):
    """fstops: per frame (index 0 = frame 1). Flags the worst zig-zag (> jitter), breathing inside flat
    holds (> hold_tol) and any direction change inside a camera hold (> eps). -> [problem strings]."""
    probs = []
    n = len(fstops)
    dd = [fstops[k + 1] - fstops[k] for k in range(n - 1)]
    zig = [(abs(dd[k]), k + 2) for k in range(1, len(dd) - 1) if dd[k - 1] * dd[k] < 0 and dd[k] * dd[k + 1] < 0]
    if zig:
        worst = max(zig)
        if worst[0] > jitter:
            probs.append(f"f-stop jitter: a zig-zag of {worst[0]:.3f} at f{worst[1]} (> {jitter}; {len(zig)} zig-zags)")
    for h in flat_holds:
        t0, t1 = h[-2], h[-1]
        fa, fb = timebase.frame(t0, fps), min(timebase.frame(t1, fps), n)
        vs = fstops[fa - 1:fb]
        if vs and max(vs) - min(vs) > hold_tol:
            probs.append(f"f-stop hold f{fa}-f{fb} breathes f/{min(vs):.2f}..f/{max(vs):.2f} (> {hold_tol})")
    for name, t0, t1 in camera_holds:
        fa, fb = timebase.frame(t0, fps), min(timebase.frame(t1, fps), n)
        vs = fstops[fa - 1:fb]
        steps = [(b - a, f) for f, (a, b) in enumerate(zip(vs, vs[1:]), start=fa + 1) if abs(b - a) > eps]
        turns = [f for (a, _), (b, f) in zip(steps, steps[1:]) if a * b < 0]
        if turns:
            probs.append(f"f-stop: the aperture changes direction inside the {name} hold f{fa}-f{fb} at f{turns}"
                         f" (f/{min(vs):.2f}..f/{max(vs):.2f})")
    return probs


def defocus_px(cam, points, film=FILM, sensor_w=36.0):
    """-> max thin-lens blur (px at film width) of the in-frame points for cam (lens, fstop, focus_distance).
    film: (w, h) px (the in-frame test uses the real aspect; a 9:16 film is not 16:9). A bare width is
    accepted as a 16:9 film (older callers)."""
    film = (film, int(film * 9 / 16 + 0.5)) if isinstance(film, (int, float)) else (film[0], film[1])
    film_w = film[0]
    lm, df, N = cam["lens"] / 1000.0, cam["focus_distance"], cam["fstop"]
    worst = 0.0
    for X in points:
        q = _proj(cam, X, film)
        if q[2] <= 0.05 or abs(q[0]) > 1 or abs(q[1]) > 1:
            continue
        b = lm * lm * abs(q[2] - df) / (N * q[2] * max(df - lm, 1e-3))
        worst = max(worst, b / (sensor_w / 1000.0) * film_w)
    return worst


def ray_box(o, d, c, half, R=None):
    """Ray o + s d against an oriented box (centre c, half sizes, rotation R; None = axis aligned).
    -> s of entry (>= 0) or None."""
    if R is not None:
        Rt = vec.mat_t(R)
        o = vec.mat_vec(Rt, vec.sub(o, c))
        d = vec.mat_vec(Rt, d)
        c = (0.0, 0.0, 0.0)
    lo, hi = 0.0, 1e9
    for i in range(3):
        if abs(d[i]) < 1e-12:
            if abs(o[i] - c[i]) > half[i]:
                return None
            continue
        a, b = (c[i] - half[i] - o[i]) / d[i], (c[i] + half[i] - o[i]) / d[i]
        lo, hi = max(lo, min(a, b)), min(hi, max(a, b))
        if lo > hi:
            return None
    return lo


def occluded(cam_pos, X, blocks):
    """True when the segment cam_pos -> X hits any oriented box in blocks [(centre, half, R)]."""
    d = vec.sub(X, cam_pos)
    for c, half, R in blocks:
        s = ray_box(cam_pos, d, c, half, R)
        if s is not None and s < 0.999:
            return True
    return False


def visible_share(faces, cam, blocks, n=6, film=FILM):
    """faces: [[3 or 4 world pts]]. Barycentric samples per triangle, weighted by projected area, counted when
    in frame and unoccluded. -> share 0..1."""
    seen = total = 0.0
    for face in faces:
        tris = [(face[0], face[1], face[2])] + ([(face[0], face[2], face[3])] if len(face) > 3 else [])
        for tri in tris:
            P = [_proj(cam, V, film) for V in tri]
            if any(p[2] <= 0 for p in P):
                continue
            ar = abs((P[1][0] - P[0][0]) * (P[2][1] - P[0][1]) - (P[2][0] - P[0][0]) * (P[1][1] - P[0][1])) / 2
            for i in range(n):
                for j in range(n - i):
                    u, v = i / n + 1 / (3 * n), j / n + 1 / (3 * n)
                    X = tuple(tri[0][k] + u * (tri[1][k] - tri[0][k]) + v * (tri[2][k] - tri[0][k]) for k in range(3))
                    q = _proj(cam, X, film)
                    ok = q[2] > 0 and abs(q[0]) <= 1 and abs(q[1]) <= 1 and not occluded(cam["pos"], X, blocks)
                    seen += ar * ok
                    total += ar
    return seen / total if total > 0 else 0.0


def landing_audit(landings, fps, bpm, on_beat_exceptions=(), xy_mm=1.0, z_mm=1.0, pitch_rad=None):
    """Per landing: sole xy error to the target point, z error to the surface, pitch, on-frame, on-beat.
    -> [row dicts] with 'ok' (geometry), 'frame_ok' and 'beat_ok' (enforced unless id in exceptions;
    beat_ok is True when bpm is None), 'text' (one review line)."""
    rows = []
    for L in landings:
        t = L["t"]
        f = timebase.frame(t, fps)
        on_frame = timebase.is_whole_frame(t, fps)
        on_beat = bpm is not None and abs(t - timebase.beat(math.floor(timebase.beats_of(t, bpm) + 0.5), bpm)) < 1e-6
        sole = L["sole_xyz"]
        tgt = L.get("target")
        dxy = math.hypot(sole[0] - tgt[0], sole[1] - tgt[1]) * 1000.0 if tgt is not None else 0.0
        dz = (sole[2] - L["surface_z"]) * 1000.0 if L.get("surface_z") is not None else 0.0
        pitch = abs(L.get("pitch", 0.0))
        rect_ok = L.get("rect_ok", True)
        exc = L["id"] in on_beat_exceptions
        ok = (dxy <= xy_mm + 1e-9 and abs(dz) <= z_mm + 1e-9 and (pitch_rad is None or pitch <= pitch_rad)
              and rect_ok is not False)
        beat_ok = bpm is None or on_beat or exc
        frame_ok = on_frame or exc
        text = (f"{'OK ' if ok and beat_ok and frame_ok else 'BAD'} {str(L['id']):<12} land {t:7.4f}s f{f:>3}"
                f"{'' if on_frame else ' (between frames)'}{' beat' if on_beat else ''}"
                f"  xy err {dxy:5.2f} mm  z err {dz:+5.2f} mm  pitch {pitch:.4f}  rect {rect_ok}")
        rows.append({"id": L["id"], "t": t, "frame": f, "on_frame": on_frame, "on_beat": on_beat, "frame_ok": frame_ok,
                     "beat_ok": beat_ok, "dxy_mm": dxy, "dz_mm": dz, "pitch": pitch, "rect_ok": rect_ok, "ok": ok,
                     "text": text})
    return rows


def _wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def _is_angle(name, kind):
    return kind == "angle" or name.endswith(("yaw", "pitch", "roll", "rot", "angle"))


def continuity_scan(channels_fn, duration, rate=480, ratio=4.0):
    """Sample channels_fn(t) -> {name: (value, floor[, 'angle'])} at rate Hz. A jump is a step > floor and
    > ratio x both neighbours (angles wrap). -> [(t, name, step)]."""
    n = int(math.floor(duration * rate + 0.5))
    S = [channels_fn(i / rate) for i in range(n + 1)]
    jumps = []
    for i in range(2, n + 1):
        p2, p1, c = S[i - 2], S[i - 1], S[i]
        nx = S[i + 1] if i + 1 <= n else None
        for k, v1 in p1.items():
            if k not in p2 or k not in c:
                continue
            ang = _is_angle(k, v1[2] if len(v1) > 2 else None)

            def dif(a, b):
                return abs(_wrap(a - b)) if ang else abs(a - b)
            d0 = dif(v1[0], p2[k][0])
            d1 = dif(c[k][0], v1[0])
            if d1 > v1[1] and d1 > ratio * d0:
                d2 = dif(nx[k][0], c[k][0]) if nx is not None and k in nx else 0.0
                if d1 > ratio * d2:
                    jumps.append((i / rate, k, d1))
    return jumps


def tune(model, hold, heads, elevs, lenses, score_fn, filters, film=FILM):
    """Grid search over heading, elevation (deg) and lens for one camera.Hold using camera.frame_solve.
    filters(model, P, f, lens) -> bool; score_fn(model, P, f, lens) -> float (higher is better).
    -> [(score, A, E, lens, P)] best first."""
    times = getattr(hold, "solve_at", None) or [hold.t0 + (hold.t1 - hold.t0) * k / 4 for k in range(5)]
    groups = []
    for t in times:
        groups += list(hold.groups_fn(t))
    bias = getattr(hold, "bias", (0.5, 0.0))
    out = []
    for A in heads:
        for E in elevs:
            for L in lenses:
                P, f = camera.frame_solve(math.radians(A), math.radians(E), L, groups, film=film,
                                          bias_r=bias[0], bias_u=bias[1], cap=getattr(hold, "cap", None))
                if not filters(model, P, f, L):
                    continue
                out.append((score_fn(model, P, f, L), A, E, L, P))
    return sorted(out, key=lambda r: -r[0])


# ---- previs SVG

def _tcolor(t, duration):
    h = 240 - 240 * t / max(duration, 1e-9)
    return f"hsl({h:.0f},85%,55%)"


def _fmt_pts(pts):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def write_previs_svg(model, moments, layers, out, safe=0.05, width=1800):
    """Storyboard with no renderer: top-down map (layer polygons at t 0, hero path, landings, camera wedges every
    0.25 s), a chart over time (hero sole z, camera z / 10, margins, beat grid) and one pinhole tile per moment
    in `moments` ([t]). layers: [(name, polys_fn(t) -> [[world pts]], css)] css = inline style of the polygons.
    Writes one SVG (one element per line); rasterise with headless Chrome."""
    m = model if isinstance(model, Memo) else Memo(model)
    dur = m.fmt.duration
    bpm = getattr(m.fmt, "bpm", None)
    has_hero = hasattr(m, "hero_points")
    body = []
    # ---- map
    cams = [(i * 0.25, m.camera(i * 0.25)) for i in range(int(dur / 0.25) + 1)]
    xy = [(c["pos"][0], c["pos"][1]) for _, c in cams]
    for _, polys_fn, _ in layers:
        for poly in polys_fn(0.0):
            xy += [(p[0], p[1]) for p in poly]
    if hasattr(m, "ground_poly"):
        xy += [(p[0], p[1]) for p in m.ground_poly]
    if not xy:
        xy = [(-1, -1), (1, 1)]
    x0, x1 = min(p[0] for p in xy) - 0.15, max(p[0] for p in xy) + 0.15
    y0, y1 = min(p[1] for p in xy) - 0.15, max(p[1] for p in xy) + 0.15
    map_w = width - 40
    sc = map_w / (x1 - x0)
    map_h = (y1 - y0) * sc

    def mp(X, Y):
        return ((X - x0) * sc + 20, (y1 - Y) * sc + 60)

    body.append('<text x="20" y="36" class="h">Top-down map: layers at t 0, hero path (colour = time, blue 0 s to red '
                f'{dur:.1f} s), landings, camera every 0.25 s (label: t, z)</text>')
    for name, polys_fn, css in layers:
        for poly in polys_fn(0.0):
            body.append(f'<polygon points="{_fmt_pts(mp(p[0], p[1]) for p in poly)}" style="{css}"/>')
    if has_hero:
        prev = None
        for f in range(1, m.n + 1):
            pts = m.pts(f)
            if not pts:
                prev = None
                continue
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            p = mp(cx, cy)
            if prev:
                body.append(f'<line x1="{prev[0]:.1f}" y1="{prev[1]:.1f}" x2="{p[0]:.1f}" y2="{p[1]:.1f}" '
                            f'stroke="{_tcolor(m.t(f), dur)}" stroke-width="3"/>')
            prev = p
    if hasattr(m, "landings"):
        for L in m.landings():
            s = L["sole_xyz"]
            p = mp(s[0], s[1])
            body.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="4" fill="{_tcolor(L["t"], dur)}" stroke="#fff"/>'
                        f'<text x="{p[0] + 6:.1f}" y="{p[1] - 6:.1f}" class="lbl2">{L["id"]} {L["t"]:.2f}</text>')
    for i, (t, c) in enumerate(cams):
        p = mp(c["pos"][0], c["pos"][1])
        d = vec.norm(vec.sub(c["target"], c["pos"]))
        hd = math.hypot(d[0], d[1]) or 1
        q = (p[0] + 30 * d[0] / hd, p[1] - 30 * d[1] / hd)
        half = math.atan(camera.tan_half(c["lens"], c.get("sensor_w", 36.0)))
        ang = math.atan2(d[1], d[0])
        fl = (p[0] + 22 * math.cos(ang + half), p[1] - 22 * math.sin(ang + half))
        fr = (p[0] + 22 * math.cos(ang - half), p[1] - 22 * math.sin(ang - half))
        col = _tcolor(t, dur)
        body.append(f'<path d="M{fl[0]:.1f},{fl[1]:.1f} L{p[0]:.1f},{p[1]:.1f} L{fr[0]:.1f},{fr[1]:.1f}" fill="none" '
                    f'stroke="{col}" stroke-width="1" opacity="0.6"/>'
                    f'<line x1="{p[0]:.1f}" y1="{p[1]:.1f}" x2="{q[0]:.1f}" y2="{q[1]:.1f}" stroke="{col}" stroke-width="2"/>'
                    f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="3.5" fill="{col}"/>')
        if i % 2 == 0:
            body.append(f'<text x="{p[0] + 5:.1f}" y="{p[1] + 12:.1f}" class="lbl2">{t:.1f} z{c["pos"][2]:.2f}</text>')
    # ---- chart
    cy0 = 60 + map_h + 40
    ch = 240
    cx0, cw = 60, width - 100
    soles, camz, margins = [], [], []
    for f in range(1, m.n + 1):
        c = m.cam(f)
        camz.append((m.t(f), c["pos"][2] / 10))
        pts = m.pts(f) if has_hero else []
        if pts:
            soles.append((m.t(f), min(p[2] for p in pts)))
            margins.append((m.t(f), margin_of(pts, c, m.film)))
    vmax = max([0.45] + [v * 1.1 for _, v in soles] + [v * 1.1 for _, v in camz])

    def cp(t, v_):
        return (cx0 + cw * t / dur, cy0 + ch - ch * v_ / vmax)

    body.append(f'<text x="20" y="{cy0 - 10:.0f}" class="h">Chart: hero sole z (m, white), camera z / 10 (grey), hero frame '
                f'margin (green, red under {safe * 100:.0f} %); dots = landings</text>')
    body.append(f'<rect x="{cx0}" y="{cy0:.1f}" width="{cw}" height="{ch}" class="chart"/>')
    step = 60.0 / bpm if bpm else 1.0
    k = 0
    while k * step <= dur + 1e-9:
        x = cx0 + cw * k * step / dur
        body.append(f'<line x1="{x:.1f}" y1="{cy0:.1f}" x2="{x:.1f}" y2="{cy0 + ch:.1f}" class="grid"/>'
                    f'<text x="{x - 8:.1f}" y="{cy0 + ch + 14:.1f}" class="lbl2">{k * step:.2f}</text>')
        k += 1
    for v_ in (0.1, 0.2, 0.3, 0.4):
        if v_ < vmax:
            y = cp(0, v_)[1]
            body.append(f'<line x1="{cx0}" y1="{y:.1f}" x2="{cx0 + cw}" y2="{y:.1f}" class="grid"/>'
                        f'<text x="20" y="{y + 4:.1f}" class="lbl2">{v_:.1f}</text>')
    ys = cp(0, safe)[1]
    body.append(f'<line x1="{cx0}" y1="{ys:.1f}" x2="{cx0 + cw}" y2="{ys:.1f}" stroke="#e44" stroke-dasharray="4 3"/>')
    body.append(f'<polyline points="{_fmt_pts(cp(t, v_) for t, v_ in camz)}" class="camz"/>')
    if soles:
        body.append(f'<polyline points="{_fmt_pts(cp(t, v_) for t, v_ in soles)}" class="zline"/>')
    for t, mg in margins:
        p = cp(t, max(0.0, mg))
        body.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="1.6" fill="{"#f33" if mg < safe else "#3c6"}"/>')
    if hasattr(m, "landings"):
        for L in m.landings():
            p = cp(L["t"], L["sole_xyz"][2])
            body.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="4" fill="#fff"/>')
    # ---- storyboard
    sy0 = cy0 + ch + 60
    cols = 6
    tw = (width - 20 - cols * 10) // cols
    th = int(tw * m.film[1] / m.film[0])
    body.append(f'<text x="20" y="{sy0 - 14:.0f}" class="h">Storyboard: the pinhole view of camera(t) (frame = '
                f'{m.film[0]}x{m.film[1]}, dashed = {safe * 100:.0f} % safe margin, hero = silhouette hull)</text>')
    for i, t in enumerate(moments):
        gx = 20 + (i % cols) * (tw + 10)
        gy = sy0 + (i // cols) * (th + 30)
        body.append(_tile_svg(m, t, layers, gx, gy, tw, th, safe))
    H = sy0 + ((len(moments) + cols - 1) // cols) * (th + 30) + 20
    style = ("<style>.h{font:600 15px sans-serif;fill:#eee}.lbl2{font:10px sans-serif;fill:#ccc}"
             ".chart{fill:#181818;stroke:#555}.grid{stroke:#333}.zline{fill:none;stroke:#fff;stroke-width:1.5}"
             ".camz{fill:none;stroke:#888;stroke-width:1}.vhero{fill:#d97757;stroke:#fff;stroke-width:0.8}"
             ".safe{fill:none;stroke:#888;stroke-dasharray:3 3;stroke-width:0.6}</style>")
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{H:.0f}" viewBox="0 0 {width} {H:.0f}">',
           style, '<rect width="100%" height="100%" fill="#111"/>'] + body + ["</svg>"]
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(svg) + "\n")
    return out


def _tile_svg(m, t, layers, gx, gy, tw, th, safe):
    cam = m.camera(t)
    f = timebase.frame(t, m.fps)

    def to_px(p):
        return (gx + (p[0] + 1) / 2 * tw, gy + (1 - p[1]) / 2 * th)

    parts = [f'<svg x="{gx}" y="{gy}" width="{tw}" height="{th}" viewBox="{gx} {gy} {tw} {th}" overflow="hidden" class="tile">',
             f'<rect x="{gx}" y="{gy}" width="{tw}" height="{th}" fill="#0b0b0b"/>']
    for name, polys_fn, css in layers:
        for poly in polys_fn(t):
            ndc = project_poly(cam, poly, film=m.film)
            if len(ndc) < 3:
                continue
            ndc = clip_rect(ndc, -1.02, -1.02, 1.02, 1.02)
            if len(ndc) >= 3:
                parts.append(f'<polygon points="{_fmt_pts(to_px(p) for p in ndc)}" style="{css}"/>')
    pts = m.hero_points(t) if hasattr(m, "hero_points") else []
    mg = margin_of(pts, cam, m.film) if pts else None
    w = screen_size(pts, cam, m.film)[0] if pts else 0.0
    if pts:
        ndc = [(p[0], p[1]) for p in (_proj(cam, X, m.film) for X in pts) if p[2] > 0]
        hl = vec.hull2d(ndc) if len(ndc) >= 3 else []
        if len(hl) >= 3:
            parts.append(f'<polygon points="{_fmt_pts(to_px(p) for p in hl)}" class="vhero"/>')
    mx, my = safe * tw, safe * th
    parts.append(f'<rect x="{gx + mx:.1f}" y="{gy + my:.1f}" width="{tw - 2 * mx:.1f}" height="{th - 2 * my:.1f}" class="safe"/>')
    parts.append("</svg>")
    bad = mg is not None and mg < safe
    void = void_above(cam, m.ground_poly, film=m.film)[0] if hasattr(m, "ground_poly") else None
    parts.append(f'<rect x="{gx}" y="{gy}" width="{tw}" height="{th}" fill="none" stroke="{"#f33" if bad else "#555"}" '
                 f'stroke-width="{2 if bad else 1}"/>')
    fstop = cam.get("fstop")
    label = (f"t {t:.2f}  f{f}  {cam['lens']:.0f} mm  f/{'-' if fstop is None else '%.1f' % fstop}  hero {w * 100:.1f}% w"
             f"  margin {'-' if mg is None else '%.0f%%' % (mg * 100)}" + (f"  void {void * 100:.0f}%" if void is not None else ""))
    parts.append(f'<text x="{gx}" y="{gy + th + 13}" class="lbl2">{label}</text>')
    return "\n".join(parts)
