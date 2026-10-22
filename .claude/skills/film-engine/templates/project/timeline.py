"""timeline.py: the one contract every reader shares. The director writes every number here.

Exports FORMAT (timebase.Format), LAYOUT (layout.Layout), EVENTS (timebase.Events), JUMPS (the beat
sheet), Z (the z stack in metres), state(t) (the per-frame state the JS readers bake) and EXTRA
(JSON-safe project data: the hero spec, the theme). `python -B timeline.py` validates the events
and writes build/timeline.json; every other reader imports this module (Python) or reads the JSON (JS).

Every hit time is written as beat(n) or time(f), never as a decimal (API.md section 1).
The values below are the greybox placeholders: a 2.0 s, 30 fps, 120 BPM fixture with two panels,
two buttons, one result screen and two hops. Lines marked TASTE are the director's decisions.
"""
import sys
sys.dont_write_bytecode = True
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.environ.get("FILM_ENGINE") or os.path.normpath(
    os.path.join(HERE, "..", "..", ".claude", "skills", "film-engine", "scripts"))
sys.path[:0] = [p for p in (HERE, ENGINE) if p not in sys.path]

from filmkit import layout, timebase  # noqa: E402
import hero_spec  # noqa: E402

# TASTE: the format. fps and bpm must agree (timebase.bpm_grid_ok) or the project names the override.
FPS, DURATION, BPM = 30, 2.0, 120
# TASTE: film size. film.json next to this file (written by `new-video --kind film --size WxH --fps N`;
# build-only, so a deliver that rewrites project.json never marks the film stale) overrides the film
# size and the fps when it carries them; the scaffold values stand without it. Whole numbers only:
# a fractional fps (29.97) raises here instead of being truncated.
FILM = (1280, 720)
_FILM_JSON = os.path.join(HERE, "film.json")
if os.path.exists(_FILM_JSON):
    with open(_FILM_JSON, encoding="utf-8") as _fh:
        _FILM = json.load(_fh)
    for _k in ("fps", "width", "height"):
        if _FILM.get(_k) is not None and _FILM[_k] != int(_FILM[_k]):
            raise ValueError(f"film.json {_k} must be a whole number, got {_FILM[_k]!r}")
    FPS = int(_FILM.get("fps") or FPS)
    FILM = (int(_FILM.get("width") or FILM[0]), int(_FILM.get("height") or FILM[1]))
# TASTE: UI page size (CSS px), texture scale, metres per UI px, result canvas size.
FORMAT = timebase.Format(FPS, DURATION, bpm=BPM, film=FILM, ui=(640, 360), ui_scale=2,
                         px_to_m=0.0025, comp=(480, 270))
UI = FORMAT.ui


def beat(n):
    """Beat n -> seconds (the only way to write a musical time)."""
    return timebase.beat(n, BPM)


def time(f):
    """1-based frame -> seconds (the only way to write a picture time)."""
    return timebase.time(f, FPS)


# TASTE: the app layout in UI px. Panels become slabs, buttons become tiles the hero lands on,
# screens are per-frame image planes (the texture leaves them one flat colour), points are named spots.
PANELS = {"left": (0, 0, 320, 360), "right": (320, 0, 320, 360)}
BUTTONS = {"btn:a": (80, 150, 60, 40), "btn:b": (180, 150, 60, 40)}
SCREENS = {"viewer": ((360, 60, 240, 135), "#000000")}
POINTS = {"spawn": (60, 290)}
LAYOUT = layout.Layout(UI, FORMAT.px_to_m, panels=PANELS, buttons=BUTTONS, screens=SCREENS, points=POINTS)

# TASTE: the z stack in metres (slab bottom, slab bevel, tile bottom and top, screen plane lift).
Z = {"slab": -0.03, "bevel": 0.002, "tile": (-0.006, 0.004), "screen": 0.0005}

# TASTE: the beat sheet. One row per hop: (id, takeoff s, landing s, target button, apex m, style).
# Landings sit on beats; takeoffs may float. motion.py turns these into arcs; the events below follow.
JUMPS = [
    ("hop#1", 0.2, beat(1), "btn:a", 0.08, "hop"),
    ("hop#2", 0.75, beat(2), "btn:b", 0.08, "hop"),
]

EVENTS = timebase.Events(FORMAT)
for _jid, _t0, _t1, _target, _apex, _style in JUMPS:
    EVENTS.add(_t0, "takeoff", jump=_jid)
    EVENTS.add(_t1, "land", jump=_jid, target=_target)
    EVENTS.add(_t1, "press", jump=_jid, button=_target)   # TASTE: every landing is a press here

# TASTE: the theme the JS readers draw with (the UI page owns its own palette in ui_build.py).
THEME = {"bg": "#000000", "ink": "#c8c8c8", "dim": "#555555"}


def state(t):
    """Per-frame state baked into timeline.json for the comp page: the press count so far and the
    last pressed button (None before the first press)."""
    presses = [e for e in EVENTS.of_kind("press") if e["t"] <= t + 1e-9]
    return {"count": len(presses), "button": presses[-1]["button"] if presses else None}


EXTRA = {"hero": hero_spec.HERO, "jumps": JUMPS, "z": Z, "theme": THEME}


def main():
    problems = EVENTS.validate(whole_frame_kinds=("land", "press"), on_beat_kinds=("land", "press"))
    if problems:
        for p in problems:
            print("EVENT PROBLEM " + p)
        return 1
    out = os.path.join(HERE, "build", "timeline.json")
    doc = timebase.export_timeline(FORMAT, LAYOUT, EVENTS, state, EXTRA, out=out)
    timebase.print_hits(doc)
    print(f"timeline: {FORMAT.frames} frames at {FPS} fps, film {FILM[0]}x{FILM[1]}, {len(EVENTS)} events, "
          f"hash {doc['hash']} -> build/timeline.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
