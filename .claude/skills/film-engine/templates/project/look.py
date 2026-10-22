"""look.py: the look constants (API.md section 4, 'Look constants'), read by scene.py through
render.apply_look and re-read from the saved .blend by stills.py and lookdev.py.

LOOK: view transform, render presets, shutter, bloom, world, studio cyc, lights, material values by
role, grades, glow highlights and the mask classes the stills measure. REGISTRY maps each role to the
material or object names scene.py creates. Greys everywhere: a fixture, not a design. Every value is TASTE.
"""

STUDIO_INDEX = 14      # pass_index of the cyc (mask class 'studio'); the hero parts use 1 (body) and 2 (eyes)
GREY = (0.35, 0.35, 0.35)

LOOK = {
    # TASTE: view transform, look, exposure, gamma.
    "view": {"transform": "AgX", "look": "None", "exposure": 0.0, "gamma": 1.0},
    # TASTE: render presets (percent, samples, adaptive threshold, denoise). The greybox keeps every
    # preset tiny (320x180 of a 1280x720 film, 4-8 samples); a real film uses about
    # stills (50, 40, 0.03, True), animatic (50, 16, 0.05, True), final (100, 64, 0.01, True).
    "preset": "final",
    "presets": {"stills": (25, 8, 0.0, True), "animatic": (25, 4, 0.0, True), "final": (25, 4, 0.0, True)},
    # TASTE: motion blur shutter in frames (0 = off).
    "shutter": 0.5,
    # TASTE: bloom of the Emission pass only.
    "bloom": {"threshold": 0.3, "smoothness": 0.5, "strength": 0.3, "size": 0.5, "quality": "Low"},
    # TASTE: the world lights with 'light' and shows 'camera' to camera rays.
    "world": {"light": (0.04, 0.04, 0.04), "strength": 1.0, "camera": (0.0, 0.0, 0.0)},
    # TASTE: the studio cyc (floor depth, material, wall, cove, top, half width).
    "cyc": {"floor_z": -2.0, "material": {"base": (0.02, 0.02, 0.02), "roughness": 0.8}, "wall_y": 4.0,
            "cove_r": 1.5, "top": 4.0, "half_x": 8.0},
    # TASTE: the light rig (locations relative to the rig that follows the hero; watts; glossy-visible).
    "lights": {
        "key": {"loc": (-0.6, -0.9, 1.2), "aim": (0.0, 0.0, 0.0), "size": 1.0, "watts": 120.0, "color": (1.0, 0.97, 0.92), "glossy": True},
        "fill": {"loc": (0.8, -1.2, 0.6), "aim": (0.0, 0.0, 0.05), "size": 1.5, "watts": 40.0, "color": (1.0, 1.0, 1.0), "glossy": False},
        "rim": {"loc": (0.3, 1.2, 0.8), "aim": (0.0, 0.0, 0.05), "size": 0.8, "watts": 60.0, "color": (1.0, 1.0, 1.0), "glossy": False},
    },
    # TASTE: material values by role (Principled keys for solids; spec/rough/strength for screens).
    "materials": {
        "body": {"base": GREY, "roughness": 0.35, "specular": 0.4, "coat": 0.1, "coat_roughness": 0.15},
        "eye": {"base": (0.02, 0.02, 0.02), "roughness": 0.3, "specular": 0.5},
        "screen": {"spec": 0.1, "rough": 0.32, "strength": 1.0},
        "side": {"base": (0.012, 0.011, 0.010), "specular": 0.3, "roughness": 0.45},
    },
    # TASTE: HSV grades on camera rays only, by object name; glow highlights lo/hi.
    "grades": {},
    "glow_highlights": {"lo": 0.1, "hi": 0.6},
    # The measurement mask (stills --mask): classes by pass_index; 'target' is the hero's sRGB hex.
    "mask": {"classes": {"body": {"index": 1, "channel": "B", "level": 1.0},
                         "eyes": {"index": 2, "channel": "B", "level": 0.5},
                         "studio": {"index": STUDIO_INDEX, "channel": "G", "level": 0.5}},
             "target": "9A9A9A"},   # TASTE: the hero colour the stills compare the body median against
}

# Names scene.py creates, by role. A role of LOOK['materials'] lists materials; the others name objects.
REGISTRY = {
    "screen": ["ui", "screen:viewer"], "side": ["side"], "body": ["hero_body"], "eye": ["hero_eye"],
    "glow_highlights": ["screen:viewer"], "cyc": ["studio_cyc"], "light_rig": ["light_rig"],
    "light_follow": ["hero"], "hero_root": ["hero"],
}
