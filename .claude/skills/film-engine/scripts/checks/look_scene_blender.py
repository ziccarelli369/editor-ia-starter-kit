"""look_scene_blender.py: the Blender side of check_blender_look (run by it, not by run_checks).

  blender -b --factory-startup -P ../filmkit/blender/gpu.py -P look_scene_blender.py -- --out <dir>

1. lookdev selfcheck through its CLI (8x8 numbered sequence, keyed props, no-props plane).
2. A tiny scene (160x90, 8 samples): a screen plane playing the numbered sequence through
   make_screen_material (+ grade, + glow highlights), a toy-material hero box on a root Empty, an arm
   box (pass_index 2), a tinted tile, a card, a flat emissive, a cyc, the camera-ray world, a 3-light
   rig with glossy flags, bloom, an occluder box in front of the arm with ob['mask_skip'] = 1;
   apply_look twice (idempotence), save_blend, then stills.main with --mask on frames 1 and 12
   (stills.json), the mask of frame 1 again with the skip turned off (the arm's class shrinks), the
   mask of frame 1 with the scene's view gamma at 1.2 (the class counts must not move: the mask
   render pins gamma 1, then restores the look's), the stills CLI with --points module:function
   from a module written next to the outputs (model_w filled), and render_stills with points_fn
   (model_w vs mask_w).
Every fixture number here is a check value, not a look. Writes <dir>/report.json.
"""
import sys
sys.dont_write_bytecode = True
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..")))

import bpy
from mathutils import Vector

from filmkit.blender import lookdev, materials, render, scene_kit, stills

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[argv.index("--out") + 1]) if "--out" in argv else os.path.join(HERE, "look_check_out")
os.makedirs(OUT, exist_ok=True)
report = {}

# ---------------------------------------------------------------- 1. selfcheck via the CLI
lookdev.main(["selfcheck", "--out", os.path.join(OUT, "selfcheck")])
with open(os.path.join(OUT, "selfcheck", "lookdev.json"), encoding="utf-8") as fh:
    report["selfcheck"] = json.load(fh)["selfcheck"]

# ---------------------------------------------------------------- 2. tiny scene
sc = bpy.context.scene
scene_kit.clear_scene(sc)
N_SEQ = 24
render.setup_render(sc, "chk", {"chk": (100, 8, 0.0, False)}, film=(160, 90), fps=30, frames=N_SEQ, view="AgX",
                    look="None", exposure=0.0, shutter=0.5, persistent=True)


def box(name, size, centre, mat, pass_index=0, parent=None):
    sx, sy, sz = (s / 2 for s in size)
    cx, cy, cz = centre
    v = [(cx + x, cy + y, cz + z) for z in (-sz, sz) for y in (-sy, sy) for x in (-sx, sx)]
    faces = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(v, [], faces)
    uvl = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li, uv in zip(poly.loop_indices, ((0, 0), (1, 0), (1, 1), (0, 1))):
            uvl.data[li].uv = uv
    me.update()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.pass_index = pass_index
    sc.collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


seq_first = lookdev.numbered_sequence(os.path.join(OUT, "seq"), N_SEQ)
screen_mat = materials.make_screen_material("screen:chk", seq_first, 1.0, sequence=True, frames=N_SEQ, spec=0.1,
                                            rough=0.32, interpolation="Closest")
screen = box("screen:chk", (0.40, 0.30, 0.0004), (0.0, 0.0, -0.0002), screen_mat, pass_index=11)
materials.set_props(screen, ui_glow=1.0, ui_power=1.0)
hero_lin = materials.srgb_to_linear("D97757")
body_mat = materials.make_toy_material("hero_body", hero_lin, 0.3, 0.4, 0.15, 0.15)
root = bpy.data.objects.new("hero", None)
sc.collection.objects.link(root)
body = box("hero_body", (0.12, 0.08, 0.06), (0.0, 0.0, 0.05), body_mat, pass_index=1, parent=root)
arm = box("arm_px", (0.04, 0.03, 0.05), (0.08, 0.0, 0.045), body_mat, pass_index=2, parent=root)
# a camera-side occluder on the ray from the camera (0, -0.5, 0.26) to the arm: the mask must skip it
occluder = box("occluder:chk", (0.02, 0.002, 0.06), (0.061, -0.12, 0.097), body_mat)
occluder["mask_skip"] = 1
tile_mat = materials.make_tinted_screen_material("tile:chk", seq_first, (0.3, 0.7, 1.6), 0.8, sequence=True, frames=N_SEQ)
tile = box("tile:chk", (0.04, 0.04, 0.006), (-0.14, 0.08, 0.003), tile_mat)
materials.set_props(tile, ui_glow=2.0, ui_power=1.0)
card_mat = materials.make_card_material("card:chk", seq_first, 1.0, grade=(0.5, 1.0, 1.0))
box("card:chk", (0.03, 0.0002, 0.03), (0.15, 0.06, 0.02), card_mat)
flat_mat = materials.make_flat_emissive("flat:chk", (0.2, 0.5, 1.0), 2.0, 0.3, 0.3)
box("flat:chk", (0.02, 0.01, 0.01), (0.12, -0.1, 0.005), flat_mat)
side_mat = materials.make_side_material("side:chk", (0.012, 0.011, 0.010), 0.3, 0.45)
cam = render.camera_object(sc, "camera", 36.0, 50.0)
cam.location = (0.0, -0.5, 0.26)
cam.rotation_euler = (Vector((0.0, 0.0, 0.04)) - cam.location).to_track_quat("-Z", "Y").to_euler("XYZ")
cam.data.dof.focus_distance = 0.5
cam.data.dof.aperture_fstop = 8.0

CLASSES = {
    "front": {"index": 1, "level": 1.0, "normal": "-Y"},
    "top": {"index": 1, "level": 0.8, "normal": "+Z"},
    "side_px": {"index": 1, "level": 0.6, "normal": "+X"},
    "bevel": {"index": 1, "level": 0.3},
    "parts": {"index": 2, "level": 0.15},
    "body": {"channel": "B", "band": (0.14, 1.0)},
    "studio": {"index": 14, "channel": "G", "level": 0.5},
    "seq_f12": {"index": 11, "channel": "R", "material": "screen:chk", "near": [materials.srgb_to_linear((144, 0, 0))], "dist": 0.02},
    "seq_f1": {"index": 11, "channel": "G", "material": "screen:chk", "near": [materials.srgb_to_linear((12, 0, 0))], "dist": 0.02},
}
LOOK = {
    "view": {"transform": "AgX", "look": "None", "exposure": 0.0, "gamma": 1.0},
    "preset": "chk", "presets": {"chk": (100, 8, 0.0, False), "stills": (100, 8, 0.0, False)},
    "shutter": 0.5,
    "bloom": {"threshold": 0.5, "smoothness": 0.5, "strength": 0.3, "size": 0.5, "quality": "Low"},
    "world": {"light": (0.05, 0.05, 0.05), "strength": 1.0, "camera": (0.0, 0.0, 0.0)},
    "cyc": {"floor_z": -0.5, "material": {"base": (0.02, 0.02, 0.02), "roughness": 0.8}, "wall_y": 2.0,
            "cove_r": 0.5, "top": 2.0, "half_x": 3.0},
    "lights": {
        "key": {"loc": (-0.6, -0.9, 1.2), "aim": (0.0, 0.0, 0.0), "size": 1.0, "watts": 60.0, "color": (1.0, 0.95, 0.9), "glossy": True},
        "rim": {"loc": (0.5, 1.0, 0.5), "aim": (0.0, 0.0, 0.05), "size": 0.6, "watts": 40.0, "color": (1.0, 0.9, 0.8), "glossy": False},
        "fill": {"loc": (0.0, -1.2, 0.3), "aim": (0.0, 0.0, 0.05), "size": 1.0, "watts": 25.0, "color": (1.0, 1.0, 1.0), "glossy": False},
    },
    "materials": {"body": {"base": hero_lin, "roughness": 0.3, "specular": 0.4, "coat": 0.15, "coat_roughness": 0.15},
                  "screen": {"spec": 0.1, "rough": 0.32, "strength": 1.0}, "side": {"base": (0.012, 0.011, 0.010), "specular": 0.3, "roughness": 0.45}},
    "grades": {"screen:chk": (0.5, 1.0, 1.0)},
    "glow_highlights": {"lo": 0.1, "hi": 0.6},
    "mask": {"classes": CLASSES, "target": "D97757"},
}
REGISTRY = {"screen": ["screen:chk", "tile:chk"], "side": ["side:chk"], "body": ["hero_body"],
            "glow_highlights": ["screen:chk"], "cyc": ["studio_cyc"], "light_rig": ["light_rig"],
            "light_follow": ["hero"], "hero_root": ["hero"]}
render.apply_look(sc, LOOK, REGISTRY)
sc.objects["studio_cyc"].pass_index = 14
n_nodes = {m.name: len(m.node_tree.nodes) for m in bpy.data.materials}
n_objects = len(bpy.data.objects)
render.apply_look(sc, LOOK, REGISTRY)
report["idempotent"] = {"materials_same_nodes": n_nodes == {m.name: len(m.node_tree.nodes) for m in bpy.data.materials},
                        "objects_same": n_objects == len(bpy.data.objects)}
report["lights"] = {n: {"glossy": sc.objects[n].visible_glossy, "camera": sc.objects[n].visible_camera,
                        "watts": sc.objects[n].data.energy, "parent": sc.objects[n].parent.name}
                    for n in ("key", "rim", "fill")}
report["rig_follow"] = sc.objects["light_rig"].constraints["follow"].target.name
report["bloom"] = {"group": sc.compositing_node_group.name if sc.compositing_node_group else None,
                   "use_compositing": sc.render.use_compositing, "use_pass_emit": sc.view_layers[0].use_pass_emit,
                   "type": sc.compositing_node_group.nodes["bloom"].inputs["Type"].default_value}
wn = sc.world.node_tree.nodes
report["world"] = {"nodes": sorted(n.name for n in wn), "camera_color": list(wn["camera_bg"].inputs["Color"].default_value)[:3]}
report["grade"] = {"screen_has_grade": "look_grade" in screen_mat.node_tree.nodes,
                   "card_has_grade": "look_grade" in card_mat.node_tree.nodes,
                   "screen_glow_hi": "look_glow_hi_w" in screen_mat.node_tree.nodes}
materials.set_grade(card_mat, None)
report["grade"]["card_grade_removed"] = "look_grade" not in card_mat.node_tree.nodes
report["stored_look"] = render.stored_look(sc)[0].get("mask", {}).get("target")
report["cyc_min_z"] = min(v.co.z for v in sc.objects["studio_cyc"].data.vertices)
rz, gain = render.light_rig_track([0.0, math.pi / 2, 0.1], [0.0, 0.0, 0.0], render.key_yaw_of((-0.6, -0.9, 1.2)))
report["rig_track"] = {"n": len(rz), "rz": [round(v, 4) for v in rz], "gain": [round(v, 4) for v in gain]}
report["bands"] = materials.mask_bands(CLASSES)
fake = []


class FakeBake:
    def put(self, idb, path, f, value, index=-1, interp=1):
        fake.append((idb.name, path, f, value, index, interp))


scene_kit.bake_states(FakeBake(), 2, 30, lambda t: scene_kit.camera_channels(cam, {"pos": (0, -0.5, 0.26), "rot": (1.2, 0, 0), "lens": 50, "focus_distance": 0.5, "fstop": 8})
                      + scene_kit.object_channels(body, {"pos": (0, 0, 0), "scale": (1, 1, 0), "visible": t < 0.02, "props": {"ui_glow": 1.0}}))
report["channels"] = {"n": len(fake), "scale_clamped": min(v for _, p, _, v, _, _ in fake if p == "scale") >= 1e-3,
                      "hide_const": [(f, v, i) for _, p, f, v, _, i in fake if p == "hide_render"]}
report["save"] = render.save_blend(os.path.join(OUT, "chk.blend"))

# ---------------------------------------------------------------- 3. stills through the CLI, then with points
stills_dir = os.path.join(OUT, "stills")
stills.main(["--frames", "1,12", "--out", stills_dir, "--mask", "--json", "stills.json"])
with open(os.path.join(stills_dir, "stills.json"), encoding="utf-8") as fh:
    parts_skip = next(e for e in json.load(fh) if e["frame"] == 1)["colour"].get("parts", {"n": 0})["n"]
occluder["mask_skip"] = 0
mask_mat, mask_bands, mask_target = stills.mask_from_look(LOOK)
noskip = os.path.join(stills_dir, "mask_noskip_0001.png")
stills.render_mask(sc, 1, noskip, mask_mat)
parts_noskip = stills.measure_regions(os.path.join(stills_dir, "f0001.png"), noskip, mask_bands, mask_target)["colour"].get("parts", {"n": 0})["n"]
occluder["mask_skip"] = 1
report["mask_skip"] = {"with_skip": parts_skip, "without_skip": parts_noskip, "camera_visible_restored": occluder.visible_camera}
# the look's view gamma (taste, apply_look) must not reach the mask PNG: the bands are computed for gamma 1, and a
# PNG saved at gamma 1.2 lifts the 'parts' level 0.15 (code 108) to about 125, out of its band
sc.view_settings.gamma = 1.2
gamma_png = os.path.join(stills_dir, "mask_gamma_0001.png")
stills.render_mask(sc, 1, gamma_png, mask_mat)
col_gamma = stills.measure_regions(os.path.join(stills_dir, "f0001.png"), gamma_png, mask_bands, mask_target)["colour"]
report["mask_gamma"] = {"parts": col_gamma.get("parts", {"n": 0})["n"], "front": col_gamma.get("front", {"n": 0})["n"],
                        "gamma_restored": sc.view_settings.gamma}
sc.view_settings.gamma = 1.0
with open(os.path.join(OUT, "chkpoints.py"), "w", encoding="utf-8") as fh:
    fh.write("import bpy\nfrom mathutils import Vector\n\n\ndef corners(t):\n    sc = bpy.context.scene\n"
             "    return [tuple(ob.matrix_world @ Vector(v.co)) for ob in (sc.objects['hero_body'], sc.objects['arm_px'])"
             " for v in ob.data.vertices]\n")
stills.main(["--frames", "1", "--out", stills_dir, "--mask", "--json", "pts_cli.json", "--prefix", "cli_f",
             "--points", "chkpoints:corners", "--project", OUT])
with open(os.path.join(stills_dir, "pts_cli.json"), encoding="utf-8") as fh:
    report["points_cli"] = json.load(fh)[0]["silhouette"]
corners = [ob.matrix_world @ Vector(v.co) for ob in (body, arm) for v in ob.data.vertices]
entries = stills.render_stills(sc, [1], stills_dir, 100, 8, 0.0, *stills.mask_from_look(LOOK),
                               points_fn=lambda t: corners, prefix="pts_f", denoise=False)
report["points"] = entries[0]["silhouette"]
report["blend_mtime_after"] = os.path.getmtime(os.path.join(OUT, "chk.blend"))
tmp = os.path.join(OUT, ".tmp_report.json")
with open(tmp, "w", encoding="utf-8") as fh:
    json.dump(report, fh, indent=1, default=str)
os.replace(tmp, os.path.join(OUT, "report.json"))
print("LOOK SCENE OK")
