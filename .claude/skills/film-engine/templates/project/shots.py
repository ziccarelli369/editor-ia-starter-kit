"""shots.py: the camera as a shot list (filmkit.camera). No bpy.

Holds are solved once from point groups with margins (camera.frame_solve); the crossings between
holds are named here. camera_state(t) is what scene.py bakes and the checker measures; camera_raw(t)
is the unshaken path. Every heading, elevation, lens, margin and crossing is TASTE.
"""
import sys
sys.dont_write_bytecode = True
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.environ.get("FILM_ENGINE") or os.path.normpath(
    os.path.join(HERE, "..", "..", ".claude", "skills", "film-engine", "scripts"))
sys.path[:0] = [p for p in (HERE, ENGINE) if p not in sys.path]

from filmkit import camera  # noqa: E402
import motion as M  # noqa: E402
import timeline as T  # noqa: E402

# The set the camera keeps in frame besides the hero: both tiles and the result screen (top corners).
SET = [p for rect in list(T.LAYOUT.buttons.values()) + [T.LAYOUT.screens["viewer"][0]]
       for p in T.LAYOUT.rect_world(rect, T.Z["tile"][1])]
# TASTE: frame fraction kept free at each edge around the hero and around the set.
MARGIN = {"hero": 0.12, "set": 0.04}


def groups(t):
    """-> [(points, margin)] the hold solver keeps inside the frame; the first group is the subject."""
    return [(M.hero_points(t), MARGIN["hero"]), (SET, MARGIN["set"])]


def samples(a, b, step=0.05):
    """-> solve times every `step` s over [a, b] clipped to the film."""
    a, b = max(0.0, a), min(T.DURATION, b)
    n = max(1, int(round((b - a) / step)))
    return [a + (b - a) * i / n for i in range(n + 1)]


# TASTE: the shot list. Hold(name, t0, t1, heading deg (0 = looking north), elevation deg (down), lens mm,
# groups_fn, bias, solve_at). The solve windows reach into the crossings so the hero stays framed there.
SHOTS = [
    camera.Hold("open", 0.0, 0.7, 0.0, 50.0, 35.0, groups, bias=(0.5, 0.0), solve_at=samples(-0.2, 1.0)),
    camera.Hold("close", 0.9, T.DURATION, 20.0, 40.0, 45.0, groups, bias=(0.5, 0.0), solve_at=samples(0.6, T.DURATION)),
]
# TASTE: crossing kinds and params per pair of consecutive holds (camera.py module docstring).
CROSSINGS = {("open", "close"): ("ease", {"ease": "smooth"})}
# TASTE: camera shakes [(t_hit, amp_deg, decay_s, f_heading_hz, f_elev_hz)].
SHAKES = []
# TASTE: the aperture; a film with blur budgets builds a camera.fstop_track instead of a constant.
FSTOP = 5.6

SHOTLIST = camera.ShotList(SHOTS, CROSSINGS, subject_fn=M.hero_centre, film=T.FORMAT.film).solve()


def camera_state(t):
    """-> camera dict at t: pos, target, lens, fstop, focus_distance, rot (Euler XYZ), raw."""
    return camera.camera_state(SHOTLIST, t, M.hero_centre, lambda _t: FSTOP, SHAKES, T.FORMAT.film)


def camera_raw(t):
    """-> (pos, target, lens, heading) of the unshaken camera at t (the heading rolls a vertical view;
    the checker reads it, a 3-tuple without it still works)."""
    raw = camera_state(t)["raw"]
    return raw["pos"], raw["target"], raw["lens"], raw["heading"]


def holds():
    return SHOTLIST.holds()


def whip_windows():
    return SHOTLIST.whip_windows()


def channels(t):
    """-> {name: (value, floor_class)} of every camera channel for the continuity scan."""
    pos, target, lens = camera_raw(t)[:3]
    out = {f"cam.pos{i}": (v, "pos") for i, v in enumerate(pos)}
    out.update({f"cam.target{i}": (v, "pos") for i, v in enumerate(target)})
    out["cam.lens"] = (lens, "lens")
    return out
