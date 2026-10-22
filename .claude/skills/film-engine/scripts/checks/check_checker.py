"""check_checker.py: quick check of filmkit.check, filmkit.fresh and the previs SVG. Standard library only.

A fake model (a cube of 8 hero points, two camera holds with a crossing, a title box, landings,
events) runs through check.run three times: clean (0 violations), with planted hero faults and
with planted camera faults. Each planted fault must produce exactly the expected violations per
rule. Then fresh.py stamps and detects staleness in a temp project, and write_previs_svg writes
a well-formed SVG with one tile per moment.

When camera.py or vec.py still raise NotImplementedError (another builder's stubs), this check
installs reference doubles of the same contract (pinhole: sensor 36 mm horizontal, no roll) and
says so, so the rule logic is checked on its own.
"""
import sys
sys.dont_write_bytecode = True
import math
import os
import tempfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from filmkit import camera, check, fresh, vec  # noqa: E402

FPS, DUR, N = 30, 3.0, 90
FILM = (1920, 1080)
FAILS = []


def expect(cond, msg):
    if not cond:
        FAILS.append(msg)
        print("  FAIL " + msg)


# ---- reference doubles (installed only over NotImplementedError stubs)

def _install_doubles():
    def add(a, b):
        return (a[0] + b[0], a[1] + b[1], a[2] + b[2])

    def sub(a, b):
        return (a[0] - b[0], a[1] - b[1], a[2] - b[2])

    def mul(a, s):
        return (a[0] * s, a[1] * s, a[2] * s)

    def dot(a, b):
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    def cross(a, b):
        return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])

    def length(a):
        return math.sqrt(dot(a, a))

    def norm(a):
        n = length(a)
        return (0.0, 0.0, 0.0) if n < 1e-12 else (a[0] / n, a[1] / n, a[2] / n)

    def mat_vec(m, v):
        return tuple(m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] for i in range(3))

    def mat_t(m):
        return tuple(tuple(m[j][i] for j in range(3)) for i in range(3))

    def hull2d(pts):
        pts = sorted(set(pts))
        if len(pts) < 3:
            return pts

        def cr(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
        lo, up = [], []
        for p in pts:
            while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0:
                lo.pop()
            lo.append(p)
        for p in reversed(pts):
            while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0:
                up.pop()
            up.append(p)
        return lo[:-1] + up[:-1]

    def basis_from_dir(f):
        f = norm(f)
        r = norm((f[1], -f[0], 0.0))
        return r, cross(r, f), f

    def tan_half(lens, sensor_w=36.0):
        return sensor_w / 2 / lens

    def project(pos, target, lens, X, film=(1920, 1080), sensor_w=36.0):
        r, u, f = basis_from_dir(sub(target, pos))
        d = sub(X, pos)
        zc = dot(d, f)
        tx = tan_half(lens, sensor_w)
        ty = tx * film[1] / film[0]
        if zc <= 1e-6:
            return (99.0, 99.0, zc)
        return (dot(d, r) / (zc * tx), dot(d, u) / (zc * ty), zc)

    o, z = (0.1, 0.2, 0.3), (0.0, 0.0, 0.0)
    m = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    table = [
        (vec, "add", add, lambda: vec.add(o, z)), (vec, "sub", sub, lambda: vec.sub(o, z)),
        (vec, "mul", mul, lambda: vec.mul(o, 2.0)), (vec, "dot", dot, lambda: vec.dot(o, o)),
        (vec, "cross", cross, lambda: vec.cross(o, z)), (vec, "length", length, lambda: vec.length(o)),
        (vec, "norm", norm, lambda: vec.norm(o)), (vec, "mat_vec", mat_vec, lambda: vec.mat_vec(m, o)),
        (vec, "mat_t", mat_t, lambda: vec.mat_t(m)), (vec, "hull2d", hull2d, lambda: vec.hull2d([(0, 0), (1, 0), (0, 1)])),
        (camera, "basis_from_dir", basis_from_dir, lambda: camera.basis_from_dir((0, 1, -1))),
        (camera, "tan_half", tan_half, lambda: camera.tan_half(35.0)),
        (camera, "project", project, lambda: camera.project((0, -1, 1), (0, 0, 0), 35.0, (0, 0, 0))),
    ]
    used = []
    for mod, name, fn, probe in table:
        try:
            probe()
        except NotImplementedError:
            setattr(mod, name, fn)
            used.append(f"{mod.__name__.split('.')[-1]}.{name}")
    return used


# ---- the fake model

def smoothstep(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def lerp3(a, b, u):
    return tuple(a[i] + (b[i] - a[i]) * u for i in range(3))


def frame(t):
    return int(math.floor(t * FPS + 0.5)) + 1


def time(f):
    return (f - 1) / FPS


class Fmt:
    fps, duration, frames, film, bpm = FPS, DUR, N, FILM, 120


class Events:
    def __init__(self, evs):
        self.evs = evs

    def of_kind(self, kind):
        return [e for e in self.evs if e["kind"] == kind]


class Fake:
    """Hold A (0-1.0 s) -> crossing (1.0-1.3 s) -> hold B (1.3-3.0 s). A cube hero slides 0 -> 0.4 m in x
    over 1.0-1.5 s. faults: teleport, dip, fstop, focus, landings, box_out, cam_dip, linear, hit_at_dip."""
    name = "fake model"
    A = ((0.0, -1.5, 1.0), (0.0, 0.0, 0.0))
    B = ((0.4, -1.2, 0.8), (0.4, 0.0, 0.0))

    def __init__(self, faults=()):
        self.faults = set(faults)
        self.fmt = Fmt()
        evs = [{"id": "land#1", "t": 1.5, "kind": "land", "frame": frame(1.5)},
               {"id": "press#1", "t": 2.5, "kind": "press", "frame": frame(2.5), "effect_end": 2.7},
               {"id": "press#2", "t": 2.9, "kind": "press", "frame": frame(2.9), "effect_end": 3.0}]
        if "hit_at_dip" in self.faults:
            evs.append({"id": "press#0", "t": 0.3, "kind": "press", "frame": frame(0.3)})
        self.events = Events(evs)
        self.ground_poly = [(-1.6, -0.9, 0.0), (1.6, -0.9, 0.0), (1.6, 0.9, 0.0), (-1.6, 0.9, 0.0)]

    def _pose(self, t):
        if t < 1.0:
            u = 0.0
        elif t < 1.3:
            u = (t - 1.0) / 0.3
            u = u if "linear" in self.faults else smoothstep(u)
        else:
            u = 1.0
        pos, target = lerp3(self.A[0], self.B[0], u), lerp3(self.A[1], self.B[1], u)
        if "cam_dip" in self.faults and frame(t) == 10:
            pos = (pos[0], pos[1], 0.05)
        return pos, target

    def camera_raw(self, t):
        pos, target = self._pose(t)
        if "raw_heading" in self.faults:              # the 4-tuple form: (pos, target, lens, heading)
            return pos, target, 35.0, 0.3
        return pos, target, 35.0

    def camera(self, t):
        pos, target, lens = self.camera_raw(t)
        f = frame(t)
        fstop = 4.0
        if "fstop" in self.faults:
            if f in (20, 22):
                fstop = 4.1
            if f >= 60:
                fstop = 4.0 + 0.003 * min(f - 60, 10)
        focus = math.dist(pos, target)
        if "focus" in self.faults and 76 <= f <= 78:
            focus = 0.3
        return {"pos": pos, "target": target, "lens": lens, "fstop": fstop, "focus_distance": focus}

    def hero_centre(self, t):
        x = 0.0 if t < 1.0 else 0.4 * smoothstep((t - 1.0) / 0.5)
        if "teleport" in self.faults and t >= 2.8 - 1e-9:
            x = 2.0
        z = 0.05
        if "dip" in self.faults and time(30) - 1e-9 <= t <= time(31) + 1e-9:
            z -= 0.003
        return (x, 0.0, z)

    def hero_points(self, t):
        c = self.hero_centre(t)
        return [(c[0] + sx * 0.05, c[1] + sy * 0.05, c[2] + sz * 0.05)
                for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]

    def hero_blocks(self, t):
        """The cube as one block; with 'hide_box' a wide slab stands between hold B's camera and the west
        half of the title box from f 85 on."""
        c = self.hero_centre(t)
        blocks = [(c, (0.05, 0.05, 0.05), None)]
        if "hide_box" in self.faults and frame(t) >= 85:
            blocks.append(((0.35, -0.6, 0.4), (0.05, 0.02, 0.6), None))
        return blocks

    def content_boxes(self, f):
        cx = 3.0 if "box_out" in self.faults and f >= 88 else 0.4
        return {"title": [(cx - 0.1, -0.05, 0.001), (cx + 0.1, -0.05, 0.001), (cx + 0.1, 0.05, 0.001), (cx - 0.1, 0.05, 0.001)]}

    def holds(self):
        return [("A", 0.0, 1.0), ("B", 1.3, 3.0)]

    def whip_windows(self):
        return []

    def landings(self):
        rows = [dict(id="land#1", t=1.5, target=(0.4, 0.0), sole_xyz=(0.4, 0.0, 0.0), surface_z=0.0, pitch=0.0)]
        if "landings" in self.faults:
            rows += [dict(id="land#2", t=2.0 + 1 / 60, target=(0.4, 0.0), sole_xyz=(0.4, 0.0, 0.0), surface_z=0.0, pitch=0.0),
                     dict(id="land#3", t=2.5, target=(0.4, 0.0), sole_xyz=(0.402, 0.0, 0.0), surface_z=0.0, pitch=0.0),
                     dict(id="step#1", t=2.8, target=(2.0, 0.0), sole_xyz=(2.0, 0.0, 0.0), surface_z=0.0, pitch=0.0)]
        return rows

    def channels(self, t):
        c = self.hero_centre(t)
        p, _, lens = self.camera_raw(t)
        ch = {f"hero.pos{i}": (c[i], "pos") for i in range(3)}
        ch.update({f"cam.pos{i}": (p[i], "pos") for i in range(3)})
        ch["cam.lens"] = (lens, "lens")
        return ch

    def probes(self):
        return [(x * 0.4, y * 0.3, 0.0) for x in range(-4, 5) for y in range(-3, 4)]


RULES_CLEAN = {
    "hero_margin": {"min": 0.05, "visible_only": True},
    "hero_width": {"default": 0.03, "zones": [], "exempt": []},
    "content_boxes": {"at_kinds": ["press"], "effect_end_field": "effect_end", "margin": 0.02, "boxes": ["title"],
                      "min_in_frame": 0.95, "max_tilt_deg": 11.0},
    "still_at_hits": {"kinds": ["land", "press"], "window_frames": 2, "max_fw_per_s": 0.30},
    "camera_smooth": {"max_accel": 0.2, "max_turn_deg": {"default": 4.0}},
    "ease_into_holds": {"frames": 4, "ratio": 0.3},
    "fstop_discipline": {"jitter": 0.02, "hold_tol": 0.01, "flat_holds": ["B"]},
    "void": {"max": 0.20, "at_kinds": ["press"]},
    "blur_budget": {"windows": [(2.5, 2.6, "title", 10.0)]},
    "continuity": {"rate": 480, "ratio": 4.0, "floors": {"pos": 5e-4, "lens": 0.05}},
    "landings": {"on_beat": True, "exceptions": ["step#1"], "xy_mm": 1.0, "z_mm": 1.0},
    "camera_floor": {"min_z": 0.1},
    "feet_above_ground": {"min_mm": -1.0},
}


def counts(rep):
    out = {}
    for v in rep.violations:
        key = v[1:v.index("]")] if v.startswith("[") else "?"
        out[key] = out.get(key, 0) + 1
    return out


def run_model(title, faults, cfg, expected):
    rep = check.run(Fake(faults), cfg)
    got = counts(rep)
    print(f"{title}: VIOLATIONS {len(rep.violations)}  per rule {got}")
    for v in rep.violations:
        print("    " + v)
    for rule, n in expected.items():
        expect(got.get(rule, 0) == n, f"{title}: {rule} gave {got.get(rule, 0)} violations, expected {n}")
    for rule in got:
        expect(rule in expected, f"{title}: unexpected violations from {rule}")
    expect(len(rep.violations) == sum(expected.values()), f"{title}: total {len(rep.violations)} != {sum(expected.values())}")
    expect(rep.exit_code == (1 if expected else 0), f"{title}: exit code {rep.exit_code}")
    txt = rep.text()
    first = txt.splitlines()[0]
    expect(first.startswith("fake model: rules ") and all(r in first for r in cfg), f"{title}: line 1 must name the rules: {first}")
    expect(f"VIOLATIONS: {len(rep.violations)}" in txt.splitlines(), f"{title}: no VIOLATIONS line")
    expect("PER FRAME" in txt and txt.count("\n") > N, f"{title}: per-frame table missing")
    return rep


def check_models():
    run_model("clean", (), RULES_CLEAN, {})
    cfg_b = dict(RULES_CLEAN)
    cfg_b["hero_width"] = {"default": 0.03, "zones": [(2.0, 2.5, 0.15, None, "zone")], "exempt": [(2.2, 2.3)]}
    cfg_b["void"] = {"max": 0.05, "at_kinds": ["press"]}
    for k in ("still_at_hits", "camera_smooth", "ease_into_holds", "camera_floor"):
        cfg_b.pop(k)
    run_model("hero faults", ("teleport", "dip", "fstop", "focus", "landings", "box_out"), cfg_b,
              {"hero_margin": 6, "hero_width": 12, "feet_above_ground": 2, "fstop_discipline": 3, "continuity": 3,
               "landings": 2, "content_boxes": 2, "blur_budget": 1, "void": 2})
    # max_hidden: the cube stands on the title box and hides 43 % of it at every press; the slab adds up at
    # press#2 (f 88-90) to 71 %. Limit 0.5: press#2 fails, press#1 passes; the share is reported per frame.
    cfg_h = {"content_boxes": dict(RULES_CLEAN["content_boxes"], max_hidden=0.5)}
    rep = run_model("hidden box", ("hide_box",), cfg_h, {"content_boxes": 1})
    hid = [v for v in rep.violations if "hidden by the hero" in v]
    expect(hid and "press#2" in hid[0] and "f 88" in hid[0], f"max_hidden names press#2 at f 88: {hid}")
    per_frame = [ln.strip() for ln in rep.text().splitlines() if "box hidden" in ln]
    expect(len(per_frame) == 6 + 3, f"hidden share reported per frame of each press window: {len(per_frame)} lines")

    def share(line):
        return float(line.split("hidden")[1].split("%")[0])
    s90 = [share(ln) for ln in per_frame if ln.startswith("f 90")]
    expect(s90 and 60.0 < s90[0] < 80.0, f"f 90: the slab and the cube hide about 70 % of the box, got {s90}")
    expect(all(35.0 < share(ln) < 50.0 for ln in per_frame if "press#1" in ln), "press#1: the cube alone hides about 43 %")
    run_model("hidden box clean", (), cfg_h, {})
    rep = check.run(Fake(("hide_box",)), {"content_boxes": dict(cfg_h["content_boxes"], max_hidden=0.05)}, scan=False)
    expect(len(rep.violations) == 2, f"max_hidden 0.05 fails both presses: {rep.violations}")

    rep = check.run(Fake(("hide_box",)), {"content_boxes": dict(cfg_h["content_boxes"], max_hidden={"title": 0.05})}, scan=False)
    expect(len(rep.violations) == 2, f"max_hidden as a per-box dict: {rep.violations}")
    rep = check.run(Fake(("hide_box",)), {"content_boxes": dict(cfg_h["content_boxes"], max_hidden={"tagline": 0.0})}, scan=False)
    expect(not rep.violations, "a per-box dict without this box (and no default) does not limit it")

    class NoBlocks(Fake):
        hero_blocks = property(lambda self: (_ for _ in ()).throw(AttributeError("hero_blocks")))
    rep = check.run(NoBlocks(), cfg_h, scan=False)
    expect(any("max_hidden needs" in v for v in rep.violations), "max_hidden without hero_blocks is a violation, never silent")
    cfg_c = {k: RULES_CLEAN[k] for k in ("camera_floor", "camera_smooth", "ease_into_holds", "still_at_hits")}
    rep = run_model("camera faults", ("cam_dip", "linear", "hit_at_dip"), cfg_c,
                    {"camera_floor": 1, "camera_smooth": 5, "ease_into_holds": 2, "still_at_hits": 1})
    turns = [v for v in rep.violations if "turn" in v]
    accs = [v for v in rep.violations if "acceleration" in v]
    expect(len(turns) == 2 and len(accs) == 3, f"camera faults: {len(accs)} accel + {len(turns)} turn violations, expected 3 + 2")
    # unknown rule and a missing model attribute are violations, never silent
    rep = check.run(Fake(), {"no_such_rule": {}, "landings": {"xy_mm": 1.0}}, scan=False)
    expect(any("unknown rule" in v for v in rep.violations), "unknown rule not reported")

    class NoLandings(Fake):
        landings = property(lambda self: (_ for _ in ()).throw(AttributeError("landings")))
    rep = check.run(NoLandings(), {"landings": {"xy_mm": 1.0}}, scan=False)
    expect(any("lacks landings" in v for v in rep.violations), "missing model attribute not reported")
    # metrics on their own
    cam = {"pos": (0.0, -2.0, 1.0), "target": (0.0, 0.0, 0.0), "lens": 36.0}
    expect(check.margin_of([(0.0, 0.0, 0.0)], cam) > 0.49, "centre point margin should be ~0.5")
    expect(check.margin_of([(0.0, -3.0, 1.0)], cam) == -1.0, "a point behind the camera gives margin -1")
    expect(abs(check.area([(0, 0), (2, 0), (2, 1), (0, 1)]) - 2.0) < 1e-12, "shoelace area")
    half = check.clip_rect([(-2, -0.5), (2, -0.5), (2, 0.5), (-2, 0.5)], -1, -1, 1, 1)
    expect(abs(check.area(half) - 2.0) < 1e-9, "clip_rect keeps the inside")
    expect(check.ray_box((0, 0, 0), (1, 0, 0), (2, 0, 0), (0.5, 0.5, 0.5)) == 1.5, "ray_box entry distance")
    expect(check.ray_box((0, 0, 0), (0, 1, 0), (2, 0, 0), (0.5, 0.5, 0.5)) is None, "ray_box miss")
    expect(check.occluded((0, -2, 0.5), (0, 2, 0.5), [((0, 0, 0.5), (0.1, 0.1, 0.1), None)]), "occluded by a box")
    jumps = check.continuity_scan(lambda t: {"a": (0.0 if t < 0.5 else 1.0, 0.01), "ang": (math.pi * 0.999 if t < 0.5 else -math.pi * 0.999, 0.01, "angle")}, 1.0)
    expect([j[1] for j in jumps] == ["a"], f"continuity: a step jumps, an angle wrap does not: {jumps}")
    rows = check.landing_audit([{"id": "x", "t": 0.5, "target": (0, 0), "sole_xyz": (0, 0, 0), "surface_z": 0, "pitch": 0}], 30, 120)
    expect(rows[0]["ok"] and rows[0]["beat_ok"] and rows[0]["frame_ok"], "landing_audit clean row")


def check_fresh():
    with tempfile.TemporaryDirectory() as tmp:
        build = os.path.join(tmp, "build")
        os.makedirs(build)
        tl = os.path.join(build, "timeline.json")
        src = os.path.join(tmp, "timeline.py")
        for p, body in ((src, "FORMAT = 1\n"), (tl, '{"hash": "aaa"}\n')):
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(body)
        fresh.stamp(build, "build/timeline.json", ["timeline.py"], "aaa", step="timeline")
        ui = os.path.join(build, "ui.png")
        with open(ui, "wb") as fh:
            fh.write(b"png")
        fresh.stamp(build, "build/ui.png", ["build/timeline.json"], "aaa", step="ui")
        expect(fresh.status(build, "build/ui.png", "aaa") == ("fresh", []), "fresh after stamping")
        expect(fresh.status(build, "build/comp", "aaa")[1] == ["build/comp: no stamp"], "unstamped artifact is stale")
        fresh.require_fresh(build, ["build/ui.png", "build/timeline.json"], "aaa")
        expect(fresh.main([tmp, "--require", "build/ui.png"]) == 0, "CLI fresh exit 0")
        later = os.path.getmtime(tl) + 10
        os.utime(tl, (later, later))
        st, why = fresh.status(build, "build/ui.png", "aaa")
        expect(st == "stale" and any("changed since the stamp" in w for w in why), f"stale after the input changed: {why}")
        code = None
        try:
            fresh.require_fresh(build, ["build/ui.png"], "aaa")
        except SystemExit as e:
            code = e.code
        expect(code == 2, f"require_fresh must exit 2, got {code}")
        expect(fresh.main([tmp, "--require", "build/ui.png"]) == 2, "CLI stale exit 2")
        fresh.stamp(build, "build/ui.png", ["build/timeline.json"], "bbb", step="ui")
        st, why = fresh.status(build, "build/ui.png", "aaa")
        expect(st == "stale" and any("stamped for timeline bbb" in w for w in why), f"stale on another hash: {why}")
        expect(fresh.current_hash(build) == "aaa", "current_hash reads timeline.json")
        expect(len(fresh.file_hash(tl)) == 12, "file_hash is 12 hex")


def check_previs():
    model = Fake()
    layers = [("ground", lambda t: [model.ground_poly], "fill:#333;stroke:#666"),
              ("title", lambda t: [q for q in model.content_boxes(frame(t)).values()], "fill:#cc3;fill-opacity:0.4")]
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "previs.svg")
        check.write_previs_svg(model, [0.0, 1.0, 1.5, 2.5], layers, out)
        root = ET.parse(out).getroot()
        labels = [e.text for e in root.iter() if e.get("class") == "lbl2" and e.text and " mm " in e.text]
        expect(len(labels) == 4 and all("f/4.0" in s for s in labels), f"previs labels carry the f-stop: {labels[:1]}")
        no_fstop = Fake()
        no_fstop.camera = lambda t: {k: v for k, v in Fake.camera(no_fstop, t).items() if k != "fstop"}
        check.write_previs_svg(no_fstop, [0.0, 2.5], layers, out)
        labels = [e.text for e in ET.parse(out).getroot().iter() if e.get("class") == "lbl2" and e.text and " mm " in e.text]
        expect(len(labels) == 2 and all("f/-" in s for s in labels), f"previs with fstop None prints f/-: {labels[:1]}")
        tiles = [e for e in root.iter() if e.get("class") == "tile"]
        expect(root.tag.endswith("svg") and len(tiles) == 4, f"previs: {len(tiles)} tiles, expected 4")
        with open(out, encoding="utf-8") as fh:
            n_lines = sum(1 for _ in fh)
        expect(n_lines > 100, "previs SVG is one element per line")


def check_heading():
    """A top-down camera with a heading: the checker's projections roll with it, as camera.py and Blender do."""
    cam = {"pos": (0.0, 0.0, 3.0), "target": (0.0, 0.0, 0.0), "lens": 35.0, "heading": math.radians(30)}
    X = (0.4, 0.1, 0.0)
    want = camera.project(cam["pos"], cam["target"], cam["lens"], X, FILM, 36.0, heading=cam["heading"])
    north = camera.project(cam["pos"], cam["target"], cam["lens"], X, FILM, 36.0)
    got = check._proj(cam, X, FILM)
    expect(max(abs(a - b) for a, b in zip(got[:2], want[:2])) < 1e-9 and abs(got[0] - north[0]) > 0.05,
           f"top-down _proj follows cam['heading']: {got[:2]} vs {want[:2]} (north-up {north[:2]})")
    poly = check.project_poly(cam, [X, (0.4, 0.2, 0.0), (0.5, 0.1, 0.0)], film=FILM)
    expect(poly and max(abs(a - b) for a, b in zip(poly[0], want[:2])) < 1e-9,
           f"top-down project_poly follows cam['heading']: {poly[:1]} vs {want[:2]}")
    # the unshaken path carries the heading when camera_raw returns one (4-tuple), None for the 3-tuple form
    m3, m4 = check.Memo(Fake()), check.Memo(Fake(("raw_heading",)))
    expect(m3.raw(5)["heading"] is None and m4.raw(5)["heading"] == 0.3 and m4.raw(5)["lens"] == 35.0,
           f"Memo.raw carries camera_raw's heading: {m3.raw(5)['heading']} / {m4.raw(5)['heading']}")


def main():
    used = _install_doubles()
    if used:
        print("doubles installed over stubs: " + ", ".join(used))
    check_models()
    check_fresh()
    check_previs()
    check_heading()
    if FAILS:
        print(f"check_checker: {len(FAILS)} failures")
        return 1
    print("check_checker: ok (3 model runs, fresh stamps, previs svg)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
