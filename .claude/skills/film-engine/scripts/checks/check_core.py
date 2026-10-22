"""check_core.py: quick checks for filmkit timebase, layout, ease, vec and scripts/ease.mjs. Standard library only.

Needs node on PATH (or env NODE) for the Python/JS parity part. Exit 0 on pass,
1 on the first failure (the message says which assertion). Run with -B.
"""
import sys
sys.dont_write_bytecode = True
import json
import math
import os
import pathlib
import subprocess
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
sys.path.insert(0, SCRIPTS)
from filmkit import timebase as tb, layout as lo, ease, vec  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print("FAIL", msg)


def near(a, b, tol=1e-9):
    if isinstance(a, (tuple, list)):
        return len(a) == len(b) and all(near(x, y, tol) for x, y in zip(a, b))
    return abs(a - b) <= tol


# ---------------------------------------------------------------- frame math
def check_frames():
    check(tb.frame(4.95, 30) == 150, "frame(4.95, 30) must be 150 (Python round gives 149)")
    check(tb.frame(0.0, 30) == 1 and tb.time(1, 30) == 0.0, "frame(0) = 1, time(1) = 0")
    check(tb.frame(12.0, 30) - 1 == 360, "12 s at 30 fps = 360 frames")
    for fps in (24, 25, 30, 50, 60):
        check(all(tb.frame(tb.time(f, fps), fps) == f for f in range(1, 7201)), f"frame(time(f)) == f at {fps} fps")
        check(all(tb.first_frame_at_or_after(tb.time(f, fps), fps) == f for f in range(1, 7201)),
              f"first_frame_at_or_after(time(f)) == f at {fps} fps")
    # exact half-frame products round up, never to even
    halves = [t for t in (k / 20 for k in range(0, 2400)) if (t * 30) % 1 == 0.5]
    check(len(halves) > 50, "the sweep holds exact half-frame times")
    check(all(tb.frame(t, 30) == int(t * 30 + 0.5) + 1 for t in halves), "half-frame times round up")
    check(any(tb.frame(t, 30) != round(t * 30) + 1 for t in halves), "frame() differs from Python round() on x.5")
    # near-half-frame sweep t = 0.0167 k: monotone and within half a frame of its snap
    prev = 0
    for k in range(0, 720):
        t = 0.0167 * k
        f = tb.frame(t, 30)
        check(f >= prev, f"frame monotone at t={t}")
        check(abs(t - tb.snap(t, 30)) <= 0.5 / 30 + 1e-9, f"snap within half a frame at t={t}")
        prev = f
    check(tb.is_whole_frame(tb.time(149, 30), 30) and not tb.is_whole_frame(2.17, 30), "is_whole_frame")
    check(tb.first_frame_at_or_after(2.17, 30) == 67 and tb.frame(2.17, 30) == 66, "2.17 s: stamp 66, flip 67")
    # decimal half-frames are float-ambiguous: the detector must catch them
    check(tb.first_frame_at_or_after(2.05, 30) == 63 and not tb.is_whole_frame(2.05, 30), "2.05 s is not a frame time")


def check_beats_and_format():
    fmt = tb.Format(30, 12.0, bpm=120)
    check(fmt.frames == 360 and fmt.beat == 0.5 and fmt.beat_frames == 15.0, "Format 30 fps 12 s 120 bpm")
    j = fmt.to_json()
    check(j["film"] == [1920, 1080] and j["comp"] is None and j["frames"] == 360, "Format.to_json")
    check(tb.beat(5, 120) == 2.5 and tb.beats_of(2.5, 120) == 5.0, "beat / beats_of")
    check(tb.on_beat(2.5, 120, 30) and not tb.on_beat(2.17, 120, 30), "on_beat")
    check(tb.on_beat(tb.beat(3, 150), 150, 30), "150 bpm beats are whole frames at 30 fps (12 each)")
    check(tb.sixteenth_frames(120, 30) == 3.75 and not tb.bpm_grid_ok(120, 30), "120 bpm at 30 fps is off grid")
    check(tb.bpm_grid_ok(150, 30) and tb.bpm_grid_ok(90, 30), "150 and 90 bpm are on grid at 30 fps")
    check(tb.bpm_candidates(30, 80, 180) == [90, 112.5, 150], "bpm_candidates(30, 80, 180)")
    check(tb.bpm_candidates(24, 80, 180) == [90, 120, 180], "bpm_candidates(24, 80, 180)")
    check(tb.timecode(0.0, 30) == "0:00:00:00" and tb.timecode(61.0, 30) == "0:01:01:00", "timecode")
    check(tb.timecode(3600.0, 30) == "1:00:00:00" and tb.timecode(0.1, 30) == "0:00:00:03", "timecode hours / fraction")
    try:
        tb.Format(29.97, 1.0)
        check(False, "Format rejects a fractional fps")
    except ValueError:
        pass


# ---------------------------------------------------------------- events + export
def check_events_and_export():
    fmt = tb.Format(30, 12.0, bpm=120)
    ev = tb.Events(fmt)
    land = ev.add(tb.beat(5, 120), "land", target="tool:type", to=(353, 44))
    check(land["id"] == "land#1" and land["frame"] == 76, "event id and frame stamp")
    ev.add(2.17, "takeoff", style="leap")
    ev.add(tb.time(149, 30), "land", id="step_land", target="effects:glow_item")
    ev.add(1.5, "peel", end=1.9)
    check(ev.get("step_land")["frame"] == 149 and len(ev) == 4, "get by id")
    try:
        ev.get("nope")
        check(False, "get of a missing id raises")
    except KeyError:
        pass
    try:
        ev.add(3.0, "land", id="land#1")
        check(False, "duplicate id raises")
    except ValueError:
        pass
    check(ev.kinds() == ["land", "peel", "takeoff"] and [e["id"] for e in ev.of_kind("land")] == ["land#1", "step_land"],
          "kinds / of_kind order")
    p = ev.validate(whole_frame_kinds=("land", "takeoff"))
    check(len(p) == 1 and p[0].startswith("takeoff#1"), f"off-frame takeoff caught: {p}")
    check(ev.validate(whole_frame_kinds=("land", "takeoff"), exceptions=("takeoff#1",)) == [], "named exception excuses it")
    p = ev.validate(on_beat_kinds=("land",))
    check(len(p) == 1 and p[0].startswith("step_land"), f"off-beat landing caught: {p}")
    ev2 = tb.Events(fmt)
    ev2.add(2.0, "takeoff"); ev2.add(2.5, "land"); ev2.add(2.4, "takeoff"); ev2.add(3.0, "land")
    check(len(ev2.validate(no_overlap=[("takeoff", "land")])) == 1, "overlapping jumps caught")
    ev2.add(13.0, "late")
    check(any("outside" in s for s in ev2.validate()), "event after the end caught")
    check("f  76" in ev.hit_table(("land",)) and "takeoff" not in ev.hit_table(("land",)), "hit_table filters")

    L = lo.Layout((1280, 720), 0.0025, panels={"p": (0, 0, 1280, 720)})

    def state(t):
        return {"age": None if t < 1.5 else t - 1.5, "pos": (t * 0.1, 1 / 3), "on": t >= 2.5}

    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "build", "timeline.json")
        doc = tb.export_timeline(fmt, L, ev, state, extra={"theme": {"bg": "#000"}, "pt": (1, 2)}, out=out)
        check(len(doc["frames"]) == 360 and doc["frames"][0] == {"f": 1, "t": 0.0, "age": None, "pos": [0.0, 0.3333], "on": False},
              f"frames baked: {doc['frames'][0]}")
        check(doc["frames"][75]["on"] is True and doc["frames"][74]["on"] is False, "state flips on frame 76")
        check(len(doc["hash"]) == 12 and all(c in "0123456789abcdef" for c in doc["hash"]), "hash is 12 hex")
        check(doc["extra"]["pt"] == [1, 2], "extra tuples become lists")
        check(not os.path.exists(out + ".tmp") and os.path.exists(out), "temp name renamed")
        raw = open(out, "rb").read()
        check(b"\r\n" not in raw and raw.endswith(b"\n"), "LF line ends")
        back = tb.load_timeline(out)
        check(back["hash"] == doc["hash"] and back["events"][0]["id"] == "peel#1", "load verifies the hash")
        tampered = json.loads(raw)
        tampered["frames"][3]["age"] = 9
        open(out, "w", encoding="utf-8").write(json.dumps(tampered))
        try:
            tb.load_timeline(out)
            check(False, "tampered timeline raises")
        except ValueError:
            pass
        try:
            tb.export_timeline(fmt, L, ev, lambda t: {"x": float("nan")}, out=out)
            check(False, "NaN in a state raises")
        except ValueError:
            pass


# ---------------------------------------------------------------- layout
def check_layout():
    items = [("opus", 1, 10.0), ("swoosh", 1, 3.5), ("spark", 1, 3.0), ("title", 4, 2.5), ("clawd", 1, -1.0)]
    L = lo.Layout((1280, 720), 0.0025,
                  panels={"menubar": (0, 0, 1280, 22), "toolbar": (0, 22, 1280, 44), "comp": (258, 70, 700, 378),
                          "timeline": (4, 452, 1272, 264)},
                  buttons={"tool:type": (336, 27, 34, 34)},
                  screens={"comp": ((320, 97, 576, 324), "#000000")},
                  stacks={"layers": {"rect": (4, 506, 1272, 210), "y0": 506, "row_h": 22, "slide_s": 0.12, "items": items}},
                  sprites={"chip": (74, 26)}, points={"start": (640, 400)},
                  nested={"comp": ((320, 97, 576, 324), 0.3)}, owners={"chip": None})
    check(L.ui_to_world(0, 0) == (-1.6, 0.9) and L.ui_to_world(1280, 720) == (1.6, -0.9), "ui_to_world corners")
    check(L.ui_to_world(640, 360) == (0.0, 0.0), "UI centre is the origin")
    for x in range(0, 1281, 37):
        for y in range(0, 721, 41):
            check(near(L.world_to_ui(*L.ui_to_world(x, y)), (x, y)), f"ui<->world round trip at {x},{y}")
    check(L.uv_of(1280, 720) == (1.0, 0.0) and L.uv_of(0, 0) == (0.0, 1.0), "uv_of")
    c = L.rect_world((320, 97, 576, 324), z=0.0005)
    check(c[0][0] < c[1][0] and c[0][1] < c[3][1] and c[0][2] == 0.0005 and len(c) == 4, "rect_world SW,SE,NE,NW")
    check(L.rect_of("comp") == (258, 70, 700, 378) and L.rect_of("tool:type") == (336, 27, 34, 34), "rect_of panels/buttons")
    check(L.rect_of("layers") == (4, 506, 1272, 210), "rect_of stacks")
    check(L.owner_of("tool:type") == "toolbar" and L.owner_of("layers") == "timeline", "owner_of by containment")
    check(L.owner_of_point((5, 5), fallback="menubar") == "menubar" and L.owner_of_point((2000, 5)) is None, "owner fallback")
    check(L.owner_of("chip") is None, "explicit owner override")
    check(near(L.nested_to_ui("comp", 960, 540), (608, 259)) and near(L.ui_to_nested("comp", 608, 259), (960, 540)), "nested round trip")
    check(near(L.nested_to_world("comp", 960, 540), L.ui_to_world(608, 259)), "nested_to_world")
    j = L.to_json()
    check(j["stacks"]["layers"]["items"][0] == ["opus", 1, 10.0] and j["screens"]["comp"] == [[320, 97, 576, 324], "#000000"],
          "Layout.to_json lists")
    json.dumps(j)
    check(lo.rect_center((10, 20, 30, 40)) == (25, 40), "rect_center")
    check(lo.rect_contains((0, 0, 10, 10), (10, 10)) and not lo.rect_contains((0, 0, 10, 10), (10.5, 5)), "rect_contains")
    check(lo.rect_contains((0, 0, 10, 10), (10.5, 5), eps=1), "rect_contains eps")
    check(lo.rect_inside((1, 1, 8, 8), (0, 0, 10, 10)) and not lo.rect_inside((1, 1, 10, 8), (0, 0, 10, 10)), "rect_inside")
    check(lo.rect_inset((0, 0, 10, 10), 2) == (2, 2, 6, 6) and lo.rect_union((0, 0, 2, 2), (5, 5, 1, 1)) == (0, 0, 6, 6),
          "rect_inset / rect_union")
    check(lo.rect_scale((1, 2, 3, 4), 3) == (3, 6, 9, 12), "rect_scale")
    tops = lo.stack_tops(12.0, items, 506, 22, 0.12)
    final = lo.stack_final_tops(items, 506, 22)
    check(tops == final == {"opus": 506, "swoosh": 528, "spark": 550, "title": 572, "clawd": 660}, f"stack tops at the end {tops}")
    t0 = lo.stack_tops(0.0, items, 506, 22, 0.12)
    check(t0["title"] is None and t0["clawd"] == 506, "before creation: None; the first block sits at y0")
    t1 = lo.stack_tops(2.5, items, 506, 22, 0.12)
    check(t1["title"] == 506 and t1["clawd"] == 506, "a new block appears at y0; the one below has not moved yet")
    t2 = lo.stack_tops(2.56, items, 506, 22, 0.12)
    check(506 < t2["clawd"] < 594 and near(t2["clawd"], 506 + 88 * 0.5), "mid slide is eased (smoothstep 0.5)")
    check(lo.stack_tops(2.62, items, 506, 22, 0.12)["clawd"] == 594, "slide done after slide_s")
    check(lo.stack_tops(2.5, items, 506, 22, 0.0)["clawd"] == 594, "slide_s 0 is a step")
    check(lo.ruler_x(2.0, 548, 170) == 888, "ruler_x")


# ---------------------------------------------------------------- vec
def check_vec():
    R = vec.rot_xyz(0.3, -0.7, 2.1)
    check(near(vec.euler_xyz(R), (0.3, -0.7, 2.1)), "euler_xyz inverts rot_xyz")
    check(near(vec.mat_mul(vec.mat_t(R), R), vec.IDENTITY, 1e-12), "transpose is the inverse")
    check(near(vec.mat_vec(vec.rot_z(math.pi / 2), (1, 0, 0)), (0, 1, 0), 1e-12), "rot_z turns +X to +Y")
    check(near(vec.mat_vec(vec.rot_x(math.pi / 2), (0, 1, 0)), (0, 0, 1), 1e-12), "rot_x turns +Y to +Z")
    Rc, Tc = vec.compose(R, (1, 2, 3), vec.rot_y(0.2), (0.5, 0, 0))
    p = vec.transform(Rc, Tc, (0.1, 0.2, 0.3))
    check(near(p, vec.transform(R, (1, 2, 3), vec.transform(vec.rot_y(0.2), (0.5, 0, 0), (0.1, 0.2, 0.3)))), "compose")
    check(near(vec.norm((3, 0, 4)), (0.6, 0, 0.8)) and vec.norm((0, 0, 0)) == (0.0, 0.0, 0.0), "norm")
    check(vec.cross((1, 0, 0), (0, 1, 0)) == (0, 0, 1) and vec.length((2, 3, 6)) == 7.0, "cross / length")
    hull = vec.hull2d([(0, 0), (2, 0), (2, 2), (0, 2), (1, 1), (1, 0), (0.5, 0.5)])
    check(hull == [(0, 0), (2, 0), (2, 2), (0, 2)], f"hull2d of a square is its ccw corners: {hull}")
    check(vec.in_hull2d((1, 1), hull) and not vec.in_hull2d((3, 1), hull) and vec.in_hull2d((1, 1), hull[::-1]), "in_hull2d")


# ---------------------------------------------------------------- ease (Python) and JS parity
US = [k / 97.0 for k in range(-5, 106)]
TAUS = [k * 0.0125 for k in range(-2, 60)]
KEYS = [(0.0, 1.0), (0.5, 3.0), (0.5, 2.0), (1.2, -1.0), (2.0, 4.0)]
VKEYS = [(0.0, (0.0, 1.0)), (1.0, (2.0, -1.0)), (3.0, (1.0, 5.0)), (3.5, (0.0, 0.0))]
SEEDS = [0, 1, 7, 12345, 0xFFFFFFFF, 2 ** 31, -1]
KINDS = ["land", "press", "key_tap", "pöwer_down"]
ANGLES = [k * 0.37 - 9.0 for k in range(0, 60)]

JS_PROBE = r"""
import * as E from %s;
const US = %s, TAUS = %s, KEYS = %s, VKEYS = %s, SEEDS = %s, KINDS = %s, ANGLES = %s;
const out = { rng: {}, f: {} };
for (const s of SEEDS) { const r = E.rng(s); out.rng[String(s)] = Array.from({ length: 1000 }, r); }
for (const n of ['smoothstep', 'smootherstep', 'outCubic', 'inOutCos', 'trap']) out.f[n] = US.map((u) => E[n](u));
out.f.trap2 = US.map((u) => E.trap(u, 0.4));
out.f.win = TAUS.map((t) => E.win(t, 0.1, 0.4)); out.f.winstep = TAUS.map((t) => E.win(t, 0.3, 0.3));
out.f.bell = TAUS.map((t) => E.bell(t, 0.1, 0.5));
out.f.impulse = TAUS.map((t) => E.impulse(t)); out.f.impulse2 = TAUS.map((t) => E.impulse(t, 0.03, 0.05, 0.32));
out.f.spring = TAUS.map((t) => E.spring(t, 0.0, 0.08, 1.15)); out.f.spring2 = TAUS.map((t) => E.spring(t, 2.2, 0.12, 0.8));
out.f.springStep = TAUS.map((t) => E.springStep(t, 0.42, 24)); out.f.springStep1 = TAUS.map((t) => E.springStep(t, 1, 20));
out.f.springStep2 = TAUS.map((t) => E.springStep(t, 1.5, 20));
out.f.keyed = TAUS.map((t) => E.keyed(KEYS, t * 3)); out.f.keyedv = TAUS.map((t) => E.keyed(VKEYS, t * 5));
out.f.catmull = TAUS.map((t) => E.catmull(KEYS, t * 3)); out.f.catmullv = TAUS.map((t) => E.catmull(VKEYS, t * 5));
out.f.wrap = ANGLES.map(E.wrap); out.f.unwrap = ANGLES.map((a) => E.unwrapTo(a, 1.3));
out.f.hash01 = []; for (let i = -3; i < 40; i++) for (let j = -2; j < 30; j++) out.f.hash01.push(E.hash01(i * 7919, j * 104729));
out.f.seedOf = KINDS.map((k) => E.seedOf(k, 3)); out.f.seedOf0 = KINDS.map((k) => E.seedOf(k));
console.log(JSON.stringify(out));
"""


def py_probe():
    out = {"rng": {}, "f": {}}
    for s in SEEDS:
        r = ease.mulberry32(s)
        out["rng"][str(s)] = [r() for _ in range(1000)]
    f = out["f"]
    for n, fn in (("smoothstep", ease.smoothstep), ("smootherstep", ease.smootherstep), ("outCubic", ease.out_cubic),
                  ("inOutCos", ease.in_out_cos), ("trap", ease.trap)):
        f[n] = [fn(u) for u in US]
    f["trap2"] = [ease.trap(u, 0.4) for u in US]
    f["win"] = [ease.win(t, 0.1, 0.4) for t in TAUS]
    f["winstep"] = [ease.win(t, 0.3, 0.3) for t in TAUS]
    f["bell"] = [ease.bell(t, 0.1, 0.5) for t in TAUS]
    f["impulse"] = [ease.impulse(t) for t in TAUS]
    f["impulse2"] = [ease.impulse(t, 0.03, 0.05, 0.32) for t in TAUS]
    f["spring"] = [ease.spring(t, 0.0, 0.08, 1.15) for t in TAUS]
    f["spring2"] = [ease.spring(t, 2.2, 0.12, 0.8) for t in TAUS]
    f["springStep"] = [ease.spring_step(t, 0.42, 24) for t in TAUS]
    f["springStep1"] = [ease.spring_step(t, 1, 20) for t in TAUS]
    f["springStep2"] = [ease.spring_step(t, 1.5, 20) for t in TAUS]
    f["keyed"] = [ease.keyed(KEYS, t * 3) for t in TAUS]
    f["keyedv"] = [list(ease.keyed(VKEYS, t * 5)) for t in TAUS]
    f["catmull"] = [ease.catmull(KEYS, t * 3) for t in TAUS]
    f["catmullv"] = [list(ease.catmull(VKEYS, t * 5)) for t in TAUS]
    f["wrap"] = [ease.wrap(a) for a in ANGLES]
    f["unwrap"] = [ease.unwrap_to(a, 1.3) for a in ANGLES]
    f["hash01"] = [ease.hash01(i * 7919, j * 104729) for i in range(-3, 40) for j in range(-2, 30)]
    f["seedOf"] = [ease.seed_of(k, 3) for k in KINDS]
    f["seedOf0"] = [ease.seed_of(k) for k in KINDS]
    return out


def check_ease_python():
    check(ease.smoothstep(0.5) == 0.5 and ease.smoothstep(2) == 1.0 and ease.smootherstep(1) == 1.0, "smoothstep ends")
    check(abs(ease.trap(0.5) - 0.5) < 1e-12 and ease.trap(1) == 1.0 and ease.trap(0.3, 0) == 0.3, "trap symmetric, r 0 linear")
    check(ease.impulse(0) == 0 and abs(ease.impulse(0.04) - 1) < 1e-12 and ease.impulse(0.6) < 0.005, "impulse shape")
    check(abs(ease.spring(0.08, 0.0, 0.08, 1.15) - 1.15) < 1e-12 and ease.spring(0, 0.0, 0.08, 1.15) == 0.0, "spring peak")
    check(ease.spring(1, 1.0, 0.08, 1.15) == 1.0, "spring from 1 stays 1")
    check(max(ease.spring_step(t, 0.42, 24) for t in TAUS) > 1.1 and abs(ease.spring_step(5, 0.42, 24) - 1) < 1e-6, "springStep overshoots then settles")
    check(all(ease.spring_step(t, 1.0, 20) <= 1.0 + 1e-12 for t in TAUS), "critical damping never overshoots")
    check(ease.keyed(KEYS, 0.5) == 2.0 and ease.keyed(KEYS, -1) == 1.0 and ease.keyed(KEYS, 9) == 4.0, "keyed step + holds")
    check(ease.keyed(KEYS, 0.25) == 2.0 and ease.keyed(KEYS, 0.25, ease=lambda u: u) == 2.0, "keyed eased midpoint")
    check(near(ease.catmull(VKEYS, 1.0), (2.0, -1.0)) and near(ease.catmull(KEYS, 1.2), -1.0), "catmull passes through keys")
    check(ease.catmull([(0, 5.0)], 3) == 5.0, "catmull with one key")
    check(ease.wrap(math.pi) == math.pi and ease.wrap(-math.pi) == math.pi and abs(ease.wrap(3 * math.pi) - math.pi) < 1e-12, "wrap (-pi, pi]")
    check(near(ease.unwrap_to(0.1, 6.2), 2 * math.pi + 0.1), "unwrap_to picks the near turn")
    series = ease.unwrap_series([3.0, 3.1, -3.1, -3.0, 3.1, 0.2])
    check(all(abs(b - a) < math.pi for a, b in zip(series, series[1:])) and series[0] == 3.0
          and near(series[2], 2 * math.pi - 3.1) and near(series[5], 0.2), f"unwrap_series removes the 2 pi jumps: {series}")
    check(ease.unwrap_series([]) == [] and ease.unwrap_series([1.0]) == [1.0], "unwrap_series on 0 or 1 values")
    check(ease.seed_of("land", 3) == (zlib.crc32(b"land") + 3) & 0xFFFFFFFF, "seed_of is crc32 + n")
    check(0 <= ease.hash01(5, 9) < 1 and ease.hash01(5, 9) == ease.hash01(5 + 2 ** 32, 9), "hash01 uses the low 32 bits")
    r = ease.mulberry32(42)
    a = [r() for _ in range(3)]
    check(a == [r2() for r2 in [ease.mulberry32(42)] for _ in range(3)], "mulberry32 repeats per seed")


def node_exe():
    return os.environ.get("NODE") or "node"


def check_js_parity():
    mjs = pathlib.Path(SCRIPTS, "ease.mjs")
    url = json.dumps(mjs.as_uri())
    code = JS_PROBE % (url, json.dumps(US), json.dumps(TAUS), json.dumps(KEYS), json.dumps(VKEYS),
                       json.dumps(SEEDS), json.dumps(KINDS, ensure_ascii=False), json.dumps(ANGLES))
    chk = subprocess.run([node_exe(), "--check", str(mjs)], capture_output=True, text=True)
    check(chk.returncode == 0, f"node --check ease.mjs: {chk.stderr.strip()}")
    proc = subprocess.run([node_exe(), "--input-type=module", "-e", code], capture_output=True, text=True, encoding="utf-8")
    check(proc.returncode == 0, f"node probe failed: {proc.stderr.strip()[:400]}")
    if proc.returncode != 0:
        return
    js = json.loads(proc.stdout)
    py = py_probe()
    n = 0
    for s in SEEDS:
        same = js["rng"][str(s)] == py["rng"][str(s)]
        n += len(py["rng"][str(s)])
        check(same, f"rng parity seed {s}")
    print(f"rng parity: {n} draws over {len(SEEDS)} seeds identical")
    exact = {"wrap", "unwrap", "hash01", "seedOf", "seedOf0", "win", "winstep", "keyed", "keyedv"}
    worst = 0.0
    for name, vals in py["f"].items():
        jv = js["f"][name]
        check(len(jv) == len(vals), f"{name}: length {len(jv)} vs {len(vals)}")
        for a, b in zip(vals, jv):
            if isinstance(a, list):
                d = max(abs(x - y) for x, y in zip(a, b))
            else:
                d = abs(a - b)
            worst = max(worst, d)
            if name in exact:
                check(a == b, f"{name}: {a!r} != {b!r} (must be bit-identical)")
            else:
                check(d <= 1e-12, f"{name}: {a!r} vs {b!r} differ by {d}")
    print(f"ease parity: {sum(len(v) for v in py['f'].values())} samples, worst |py - js| = {worst:.3g}")


def main():
    check_frames()
    check_beats_and_format()
    check_events_and_export()
    check_layout()
    check_vec()
    check_ease_python()
    check_js_parity()
    if FAILS:
        print(f"check_core: {len(FAILS)} failed")
        return 1
    print("check_core: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
