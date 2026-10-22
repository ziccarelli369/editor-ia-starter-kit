"""checks_config.py: the thresholds the model check enforces (API.md section 4, 'Check thresholds').

A rule absent from RULES does not run; the engine never lowers a number. The greybox runs three
rules; the commented rows show the rest of the library with the reference film's values. Every number
is TASTE: the director owns every threshold (session-workflows: a builder never edits a threshold it
must pass).
"""

# TASTE: which rules run and their numbers.
RULES = {
    "hero_margin": {"min": 0.05, "visible_only": True},
    "hero_width": {"default": 0.04, "zones": [], "exempt": []},
    "landings": {"on_beat": True, "exceptions": [], "xy_mm": 1.0, "z_mm": 1.0},
    # "content_boxes": {"at_kinds": ["press"], "effect_end_field": "effect_end", "margin": 0.02, "boxes": ["title"]},
    # "still_at_hits": {"kinds": ["land", "press"], "window_frames": 2, "max_fw_per_s": 0.30},
    # "camera_smooth": {"max_accel": 0.04, "max_turn_deg": {"default": 4.0}},
    # "ease_into_holds": {"frames": 4, "ratio": 0.3},
    # "fstop_discipline": {"jitter": 0.02, "hold_tol": 0.01},
    # "void": {"max": 0.20, "at_kinds": ["press"]},
    # "blur_budget": {"windows": [(0.0, 2.0, "title", 10.0)]},
    # "continuity": {"rate": 480, "ratio": 4.0, "floors": {"pos": 5e-4, "angle": 5e-3, "lens": 0.05, "scale": 5e-3}},
    # "camera_floor": {"min_z": 0.1},
    # "feet_above_ground": {"min_mm": -1.0},
}

# TASTE: the sound step's gates (absent = reported, not enforced): contour_lu (max |K - REFERENCE| per 0.5 s
# block), tap_ms + tap_kinds (max |mix onset error| on those rows), audible_db + audible_kinds (the floor of
# the hit table's audibility column, the kind over the rest of the pre-master mix in the phone band, best 5 ms).
# SOUND = {"contour_lu": 1.0, "tap_ms": 5.0, "tap_kinds": ["tap"], "audible_db": -3.0, "audible_kinds": ["land"]}

# TASTE: the moments the previs storyboard draws (seconds).
PREVIS_MOMENTS = [0.0, 0.35, 0.5, 0.85, 1.0, 1.5, 1.9667]
