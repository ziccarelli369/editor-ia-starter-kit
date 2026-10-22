"""filmkit: the taste-free engine for a 3D character film over a software UI.

Read API.md (one folder up from scripts/) for the contract. Modules at this
level and in blender/ are standard-library only, so Blender's Python and the
plain-Python checker import the same code. sound/ and measure.py need the kit
venv (numpy, scipy, pedalboard, Pillow).

Every entry script starts with `import sys; sys.dont_write_bytecode = True`
before it imports filmkit, and runs under `python -B`.
"""

__all__ = [
    "timebase", "layout", "ease", "vec", "arc", "camera", "hero_points",
    "check", "fresh", "measure", "ui_html",
]
