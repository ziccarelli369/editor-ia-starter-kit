"""motion.py: the hero's choreography as pure functions of t (seconds). No bpy.

Reads timeline.JUMPS (the beat sheet) and hero_spec.HERO; resolves the jump arcs with filmkit.arc;
exposes hero_pose(t) (the pose dict blender/hero.py bakes and hero_points.py measures), hero_points(t),
hero_blocks(t), hero_centre(t), tile_state(button, t) (press depth and glow) and landings() (the
checker's landing audit rows). The camera lives in shots.py. Every number marked TASTE is the director's.
"""
import sys
sys.dont_write_bytecode = True
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.environ.get("FILM_ENGINE") or os.path.normpath(
    os.path.join(HERE, "..", "..", ".claude", "skills", "film-engine", "scripts"))
sys.path[:0] = [p for p in (HERE, ENGINE) if p not in sys.path]

from filmkit import arc, ease, hero_points as HP, layout as layout_mod  # noqa: E402
import timeline as T  # noqa: E402
from hero_spec import BODY_PIVOT_Z, HERO  # noqa: E402

# TASTE: jump styles (arc.py docstring explains every key; crouch s, squash c_a, stretch st, landing c_l, lean rad,
# then the envelope shape: an omitted key takes the engine placeholder, which is the reference film's value).
STYLES = {"hop": {"crouch": 0.12, "c_a": 0.14, "st": 0.09, "c_l": 0.15, "lean": 0.06,
                  "crouch_min": 0.0, "ground_speed": None, "tuck": 0.0, "crouch_share": 0.75, "air_fade": 0.45,
                  "pre_land": (0.6, 0.35), "land": (0.04, 0.06, 0.32), "land_fade": 0.08, "unload": 0.03}}
# TASTE: squash floor (s_z never under this) and pin (0 keeps volume, 1 spreads less).
SQUASH = {"floor": 0.45, "pin": 0.0}
# TASTE: the tile press: depth m, time to full depth s, release time constant s, glow added at full depth.
PRESS = {"depth": 0.003, "hit_s": 0.06, "release_tau": 0.08, "glow": 0.6}
# TASTE: the expression after the last landing.
FINAL_EXPRESSION = "happy"

TILE_TOP = T.Z["tile"][1]
START = (*T.LAYOUT.ui_to_world(*T.LAYOUT.points["spawn"]), 0.0)
PRESS_INTERVALS = arc.press_intervals([(t1, target) for _, _, t1, target, _, _ in T.JUMPS], None)


def _hit(tau, dur):
    return PRESS["depth"] * ease.smoothstep(tau / PRESS["hit_s"])


def _release(x):
    return math.exp(-x / PRESS["release_tau"])


def tile_depth(bid, t):
    """-> how far tile `bid` is pressed at t (m, 0 at rest)."""
    return arc.press_depth(t, PRESS_INTERVALS.get(bid, []), _hit, _release)


def tile_state(bid, t):
    """-> {'depth': m, 'glow': ui_glow} of a tile at t."""
    d = tile_depth(bid, t)
    return {"depth": d, "glow": 1.0 + PRESS["glow"] * d / PRESS["depth"]}


def surface_z(target, t):
    """-> z of the landing surface of `target` at t (a pressed tile sits lower)."""
    return TILE_TOP - tile_depth(target, t)


def _rows():
    rows = []
    for jid, t0, t1, target, apex, style in T.JUMPS:
        cx, cy = layout_mod.rect_center(T.LAYOUT.buttons[target])
        rows.append((jid, t0, t1, T.LAYOUT.ui_to_world(cx, cy), apex, style, target, TILE_TOP))
    return rows


JUMPS = arc.resolve_jumps(_rows(), START, surface_z, STYLES, T.FPS)


def _yaw_keys():
    # TASTE: the hero faces -Y at t 0 and turns toward each hop's travel during its crouch.
    keys = [(0.0, 0.0)]
    for J in JUMPS:
        travel = J["arc"].travel                 # None for a hop in place: keep the running yaw
        keys += [(J["crouch_t0"], keys[-1][1]), (J["t0"], keys[-1][1] if travel is None else travel)]
    return keys


YAW = arc.yaw_track(_yaw_keys())


def hero_root(t):
    """-> world position of the hero's soles at t."""
    ph, J = arc.phase(JUMPS, t)
    if ph == "air":
        return J["arc"](t)[0]
    if ph == "crouch":
        if J["k"] == 0:
            return J["from"]
        prev = JUMPS[J["k"] - 1]
        return (prev["to"][0], prev["to"][1], surface_z(prev["target"], t))
    if J is None:
        return START
    return (J["to"][0], J["to"][1], surface_z(J["target"], t))


def hero_pose(t):
    """-> the pose dict (API.md 'Hero spec') at t."""
    c = arc.compression(t, JUMPS, STYLES)
    return {"root": {"pos": hero_root(t), "euler": (0.0, 0.0, YAW(t))},
            "squash": arc.squash_scale(c, SQUASH["floor"], SQUASH["pin"]),
            "joints": {}, "slides": {},
            "expression": FINAL_EXPRESSION if t >= JUMPS[-1]["t1"] else HERO["default_expression"],
            "visible": True}


def hero_points(t):
    """-> world surface points of the posed hero at t."""
    return HP.hero_points(HERO, hero_pose(t))


def hero_blocks(t):
    """-> oriented boxes of the posed hero at t (occlusion tests)."""
    return HP.hero_blocks(HERO, hero_pose(t))


def hero_centre(t):
    """-> world point the camera frames and focuses on: the body centre."""
    p = hero_root(t)
    return (p[0], p[1], p[2] + BODY_PIVOT_Z)


def landings():
    """-> the checker's landing rows: sole position at each landing against the target button centre."""
    rows = []
    for J in JUMPS:
        ev = next(e for e in T.EVENTS.of_kind("land") if e.get("jump") == J["id"])
        pos = hero_root(J["t1"])
        low = min(p[2] for p in hero_points(J["t1"]))
        rows.append({"id": ev["id"], "t": J["t1"], "target": (J["to"][0], J["to"][1]),
                     "sole_xyz": (pos[0], pos[1], low), "surface_z": J["to"][2], "pitch": 0.0})
    return rows


def channels(t):
    """-> {name: (value, floor_class)} of every hero channel for the continuity scan."""
    pose = hero_pose(t)
    px, py, pz = pose["root"]["pos"]
    out = {"hero.x": (px, "pos"), "hero.y": (py, "pos"), "hero.z": (pz, "pos"),
           "hero.yaw": (pose["root"]["euler"][2], "angle"), "hero.squash_z": (pose["squash"][2], "scale")}
    for bid in T.LAYOUT.buttons:
        out[f"tile.{bid}.depth"] = (tile_depth(bid, t), "pos")
    return out
