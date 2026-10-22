"""hero_spec.py: the hero as bpy-free data (API.md section 4, 'Hero spec').

blender/hero.py builds this rig and hero_points.py measures it, so the silhouette the checker sees is
the mesh the render shows. Metres. Sides are named by LOCAL axis: _px is +X, _nx is -X.
The spec below is the grey placeholder toy: a rounded-box body, a sphere head, two capsule arms, two
box legs and two eye sets (expressions 'open' and 'happy'). Every number is TASTE.
"""

# TASTE: the whole character: parts, sizes, pivots, expressions, slides, material roles.
HERO = {
    "name": "hero", "euler_order": "XYZ", "facing": "-Y",
    "parts": [
        {"name": "body", "parent": None, "shape": "rbox", "size": (0.10, 0.06, 0.08), "r": 0.01, "k": 5,
         "pivot": (0.0, 0.0, 0.07), "offset": (0.0, 0.0, 0.0), "axis": None, "material": "body", "pass_index": 1},
        {"name": "head", "parent": "body", "shape": "sphere", "r": 0.028,
         "pivot": (0.0, 0.0, 0.04), "offset": (0.0, 0.0, 0.02), "axis": "Z", "material": "body", "pass_index": 1},
        {"name": "arm_px", "parent": "body", "shape": "capsule", "a": (0.0, 0.0, 0.0), "b": (0.0, 0.0, -0.05), "r": 0.009,
         "pivot": (0.045, 0.0, 0.02), "offset": (0.012, 0.0, 0.0), "axis": "Y", "material": "body", "pass_index": 1},
        {"name": "arm_nx", "parent": "body", "shape": "capsule", "a": (0.0, 0.0, 0.0), "b": (0.0, 0.0, -0.05), "r": 0.009,
         "pivot": (-0.045, 0.0, 0.02), "offset": (-0.012, 0.0, 0.0), "axis": "Y", "material": "body", "pass_index": 1},
        {"name": "leg_px", "parent": "body", "shape": "rbox", "size": (0.02, 0.02, 0.035), "r": 0.005, "k": 4,
         "pivot": (0.02, 0.0, -0.035), "offset": (0.0, 0.0, -0.0175), "axis": "X", "material": "body", "pass_index": 1},
        {"name": "leg_nx", "parent": "body", "shape": "rbox", "size": (0.02, 0.02, 0.035), "r": 0.005, "k": 4,
         "pivot": (-0.02, 0.0, -0.035), "offset": (0.0, 0.0, -0.0175), "axis": "X", "material": "body", "pass_index": 1},
        {"name": "eye_px_open", "parent": "body", "shape": "rbox", "size": (0.008, 0.004, 0.012), "r": 0.002, "k": 3,
         "pivot": (0.02, -0.03, 0.02), "offset": (0.0, 0.0, 0.0), "axis": None, "material": "eye", "pass_index": 2,
         "expression": "open"},
        {"name": "eye_nx_open", "parent": "body", "shape": "rbox", "size": (0.008, 0.004, 0.012), "r": 0.002, "k": 3,
         "pivot": (-0.02, -0.03, 0.02), "offset": (0.0, 0.0, 0.0), "axis": None, "material": "eye", "pass_index": 2,
         "expression": "open"},
        {"name": "eye_px_happy", "parent": "body", "shape": "sphere", "r": 0.004,
         "pivot": (0.02, -0.03, 0.02), "offset": (0.0, 0.0, 0.0), "axis": None, "material": "eye", "pass_index": 2,
         "expression": "happy"},
        {"name": "eye_nx_happy", "parent": "body", "shape": "sphere", "r": 0.004,
         "pivot": (-0.02, -0.03, 0.02), "offset": (0.0, 0.0, 0.0), "axis": None, "material": "eye", "pass_index": 2,
         "expression": "happy"},
    ],
    "expressions": {"open": ["eye_px_open", "eye_nx_open"], "happy": ["eye_px_happy", "eye_nx_happy"]},
    "default_expression": "open",
    "slides": {"lift_px": {"part": "arm_px", "delta": (0.0, 0.0, 0.03)}},
    "materials": {"body": "toy", "eye": "toy"},
}

# Derived facts other project modules read (not taste).
BODY_PIVOT_Z = next(p["pivot"][2] for p in HERO["parts"] if p["parent"] is None)
