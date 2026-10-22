"""check_blender_build.py: quick check of filmkit.blender gpu, bake, geo and hero. Standard library only.

Run by run_checks.py (plain python). It launches Blender headless with gpu.py first and this file
second, then reads the Blender stdout:
  blender -b --python-exit-code 1 --factory-startup -P <engine>/filmkit/blender/gpu.py -P <this file> -- <out_dir>
Inside Blender it builds the example hero (a grey placeholder toy: body, head, two arms, two legs,
two eye sets; a second hero from the same spec, its objects renamed by Blender, must still swap its
eye sets through show_expression), slabs from rects, a screen plane, a growing ring, a curl card, a prism, shards, an
arc tube, a capsule and a sphere; bakes 12 frames of a simple state(t) (move, rotate, squash,
joint, slide, expression swap, hide, slab drop and tilt, custom prop, shape key, lens); saves
<out_dir>/build.blend; reloads it; asserts F-curve values at frames 1, 6 and 12 (hide curves at
1, 8, 12), CONSTANT vs LINEAR interpolation, a constant channel without keys, parent_keep_world
world positions; then renders frame 6 at 160x90 with 4 samples to <out_dir>/frame_0006.png; last,
with the cwd at <out_dir>, runs lookdev.main(['selfcheck', '--out', 'lookdev_rel']) (a RELATIVE out:
bpy resolves a plain relative path against the drive root) and asserts <out_dir>/lookdev_rel holds a
fresh lookdev.json with selfcheck ok and the 24 sequence PNGs.
Env: BLENDER (default Program Files Blender 5.2), FILM_SCRATCH (default <temp>/film-engine-checks).
Blender exits 0 on a script exception unless --python-exit-code is given, so this passes it and
also requires the line 'BLENDER_BUILD_CHECK: PASS'. Exit 1 on any failure, including bytecode left
under the skill folder (removed, then reported).
"""
import sys
sys.dont_write_bytecode = True
import json
import math
import os
import shutil
import subprocess
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.dirname(HERE)
SKILL = os.path.dirname(ENGINE)
DEFAULT_BLENDER = "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
N = 12
EPS = 1e-5
MAX_PATH = 240          # Windows refuses file writes near 260 chars; Blender adds '@' while saving

# The example hero: a grey placeholder toy used only by this check. Not a design.
HERO = {
    "name": "toy", "euler_order": "XYZ", "facing": "-Y",
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
         "pivot": (0.02, -0.03, 0.02), "offset": (0.0, 0.0, 0.0), "axis": None, "material": "eye", "pass_index": 2, "expression": "open"},
        {"name": "eye_nx_open", "parent": "body", "shape": "rbox", "size": (0.008, 0.004, 0.012), "r": 0.002, "k": 3,
         "pivot": (-0.02, -0.03, 0.02), "offset": (0.0, 0.0, 0.0), "axis": None, "material": "eye", "pass_index": 2, "expression": "open"},
        {"name": "eye_px_happy", "parent": "body", "shape": "sphere", "r": 0.004,
         "pivot": (0.02, -0.03, 0.02), "offset": (0.0, 0.0, 0.0), "axis": None, "material": "eye", "pass_index": 2, "expression": "happy"},
        {"name": "eye_nx_happy", "parent": "body", "shape": "sphere", "r": 0.004,
         "pivot": (-0.02, -0.03, 0.02), "offset": (0.0, 0.0, 0.0), "axis": None, "material": "eye", "pass_index": 2, "expression": "happy"},
    ],
    "expressions": {"open": ["eye_px_open", "eye_nx_open"], "happy": ["eye_px_happy", "eye_nx_happy"]},
    "slides": {"lift_px": {"part": "arm_px", "delta": (0.0, 0.0, 0.03)}},
    "materials": {"body": "toy", "eye": "flat"},
}
ARM_PIVOT_Z, LIFT_DZ = 0.02, 0.03


def wrap_rz(f):
    """A yaw that crosses +pi (a look_at crossing due south): 2.9 + 0.1 (f - 1) wrapped to (-pi, pi]."""
    a = 2.9 + 0.1 * (f - 1)
    return math.atan2(math.sin(a), math.cos(a))


def state(f):
    """The baked test state at frame f (1..N): a pose plus slab, tile, ring, lens and card values."""
    k = f - 1
    u = k / (N - 1)
    pose = {"root": {"pos": (0.02 * k, 0.0, 0.001 * k), "euler": (0.0, 0.0, 0.1 * k)},
            "squash": (1.0, 1.0, 1.0 - 0.01 * k),
            "joints": {"arm_px": 0.05 * k, "leg_nx": -0.02 * k},
            "slides": {"lift_px": u}, "expression": "open" if f < 7 else "happy", "visible": f <= 9}
    return {"pose": pose, "drop": 0.01 * k, "tilt": 0.02 * k, "power": 1.0 - u, "slab_visible": f < 12,
            "depth": 0.001 * k, "grow": u, "lens": 35.0 + k, "card_key": "k1" if f % 2 else "k2"}


class _Layout:
    """Stand-in for layout.Layout: ui_to_world and uv_of only (UI centre = origin, +y down = -Y)."""

    def __init__(self, ui, px_to_m):
        self.ui, self.px_to_m = ui, px_to_m

    def ui_to_world(self, x, y):
        return ((x - self.ui[0] / 2) * self.px_to_m, (self.ui[1] / 2 - y) * self.px_to_m)

    def uv_of(self, x, y):
        return (x / self.ui[0], 1.0 - y / self.ui[1])


try:
    import bpy
except ImportError:
    bpy = None


# ---------------------------------------------------------------- inside Blender
def blender_main(out_dir):
    from mathutils import Matrix, Vector
    if ENGINE not in sys.path:
        sys.path.insert(0, ENGINE)
    from filmkit import ease
    from filmkit.blender import bake, geo, hero

    def near(a, b, what):
        if abs(a - b) > EPS:
            raise AssertionError(f"{what}: {a!r} != {b!r}")

    sc = bpy.context.scene
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    coll = geo.collection("Check")
    lay = _Layout((1280, 720), 0.0025)

    # slabs, tile, screen, flats
    pivot = (*lay.ui_to_world(300, 200), 0.0)
    slab = geo.box_from_rect("panel:a", (100, 100, 400, 200), -0.03, 0.0, None, None, coll, lay, origin=pivot, bevel=0.002)
    slab.rotation_mode = "XYZ"
    tile_c = (*lay.ui_to_world(180, 170), 0.0)
    tile = geo.box_from_rect("tile:b", (150, 150, 60, 40), -0.006, 0.004, None, None, coll, lay, origin=tile_c, bevel=0.0008)
    geo.parent_keep_world(tile, slab, pivot)                                  # translation form
    screen_c = (*lay.ui_to_world(360, 190), 0.0)
    screen = geo.plane_from_rect("screen:c", (300, 150, 120, 80), 0.0005, None, coll, lay, origin=screen_c)
    geo.parent_keep_world(screen, slab, Matrix.Translation(pivot))             # Matrix form
    pivot2 = (*lay.ui_to_world(750, 250), 0.0)
    geo.box_from_rect("panel:d", (600, 100, 300, 300), -0.03, 0.0, None, None, coll, lay, origin=pivot2, bevel=0.002)
    ring = geo.ring_growing("ring:0", 0.02, 0.04, 0.003)
    coll.objects.link(ring)
    ring.location = (pivot2[0], pivot2[1], 0.0004)
    card, card_keys = geo.curl_card("card", 0.16, 0.10, 4, 10,
                                    {"k1": lambda v: 0.5 * v * v, "k2": lambda v: 1.5 * max(0.0, v - 0.4) ** 2})
    coll.objects.link(card)
    card.location = (pivot2[0], pivot2[1] - 0.2, 0.001)
    pr = geo.prism("prism", geo.stadium(0.05, 0.02, 6, inset=0.001), 0.002)
    coll.objects.link(pr)
    pr.location = (pivot[0] + 0.3, pivot[1], 0.0)
    rnd = ease.mulberry32(7)
    shards = geo.shard_meshes(3, 0.02, 0.0015, rnd)
    arc = geo.arc_tube("arc", 0.01, 0.003, 12.0, 168.0, flat_y=0.6, plane="XY")
    coll.objects.link(arc)
    arc.location = (pivot[0] - 0.3, pivot[1], 0.003)
    cap = geo.capsule("cap", (0.0, 0.0, 0.0), (0.0, 0.0, 0.05), 0.01)
    coll.objects.link(cap)
    cap.location = (pivot[0] - 0.4, pivot[1], 0.01)
    sph = geo.sphere("sph", 0.01)
    coll.objects.link(sph)
    sph.location = (pivot[0] - 0.5, pivot[1], 0.01)
    for ob in (slab, tile, screen, ring, card, pr, arc, cap, sph):
        if ob.data.validate(verbose=False, clean_customdata=False):
            raise AssertionError(f"mesh {ob.name} needed fixing by validate()")
    for me in shards:
        if me.validate(verbose=False, clean_customdata=False):
            raise AssertionError(f"shard mesh {me.name} needed fixing by validate()")
    top_uv = [tuple(round(c, 5) for c in slab.data.uv_layers[0].data[li].uv) for li in slab.data.polygons[0].loop_indices]
    want_uv = [tuple(round(c, 5) for c in lay.uv_of(x, y)) for x, y in ((100, 300), (500, 300), (500, 100), (100, 100))]
    if sorted(top_uv) != sorted(want_uv):
        raise AssertionError(f"slab top UVs {top_uv} do not match its rect")
    print(f"CHECK geo: slab {len(slab.data.vertices)} v, card {len(card.data.vertices)} v / {len(card_keys)} keys, "
          f"capsule {len(cap.data.vertices)} v, arc {len(arc.data.vertices)} v, shards {len(shards)}")

    # hero, camera, light
    rig = hero.build_hero(HERO, coll, {})
    if not (rig["parts"]["arm_px"].location.x > 0 and rig["parts"]["arm_nx"].location.x < 0):
        raise AssertionError("side naming: arm_px / arm_nx pivots have the wrong sign")
    if not rig["parts"]["eye_px_happy"].hide_render or rig["parts"]["eye_px_open"].hide_render:
        raise AssertionError("default expression 'open' must show open eyes and hide happy eyes")
    hero.show_expression(rig, "happy")
    if rig["parts"]["eye_px_happy"].hide_render or not rig["parts"]["eye_px_open"].hide_render:
        raise AssertionError("show_expression('happy') did not swap the eye sets")
    hero.set_pose(rig, state(3)["pose"])
    near(rig["parts"]["arm_px"].rotation_euler.y, state(3)["pose"]["joints"]["arm_px"], "set_pose arm_px")
    # a second hero from the same spec: Blender renames its objects (eye_px_happy.001); show_expression must still
    # swap the sets by spec part names, as the baked poses do
    rig2 = hero.build_hero(HERO, coll, {}, name="toy2")
    happy2, open2 = rig2["parts"]["eye_px_happy"], rig2["parts"]["eye_px_open"]
    if happy2.name == "eye_px_happy" or open2.name == "eye_px_open":
        raise AssertionError(f"the second hero kept the first hero's object names ({happy2.name}, {open2.name}): the case is not exercised")
    hero.show_expression(rig2, "happy")
    if happy2.hide_render or not open2.hide_render:
        raise AssertionError(f"show_expression('happy') on a second hero ({happy2.name}): happy hidden {happy2.hide_render}, "
                             f"open hidden {open2.hide_render}; want False, True")
    print(f"CHECK hero 2: show_expression swaps the sets of a renamed hero ({happy2.name} shown, {open2.name} hidden)")
    for ob in [rig2["root"], rig2["squash"]] + list(rig2["parts"].values()):
        bpy.data.objects.remove(ob, do_unlink=True)
    print(f"CHECK hero: {len(rig['parts'])} parts, expressions {sorted(rig['expressions'])}, slides {sorted(rig['slides'])}")
    bad = {"name": "bad", "parts": [
        {"name": "core", "parent": None, "shape": "sphere", "r": 0.01, "pivot": (0.0, 0.0, 0.0)},
        {"name": "fin_px", "parent": "core", "shape": "sphere", "r": 0.005, "pivot": (-0.02, 0.0, 0.0)}]}
    try:
        hero.build_hero(bad, None, {})
    except AssertionError:
        pass
    else:
        raise AssertionError("build_hero accepted a _px part at negative x")
    for ob in list(bpy.data.objects):
        if ob.name in ("bad", "bad:squash", "core", "fin_px"):
            bpy.data.objects.remove(ob, do_unlink=True)
    partial = bake.Bake(3)
    partial.put(sph, "location", 1, 0.0, index=2)
    partial.put(sph, "location", 3, 0.1, index=2)
    try:
        partial.write()
    except RuntimeError:
        pass
    else:
        raise AssertionError("Bake.write accepted a channel that misses frame 2")
    print("CHECK refusals: _px at negative x and a missing bake frame both raise")
    cd = bpy.data.cameras.new("camera")
    cd.sensor_width, cd.sensor_fit, cd.lens = 36.0, "HORIZONTAL", 35.0
    cam = bpy.data.objects.new("camera", cd)
    coll.objects.link(cam)
    cam.rotation_mode = "XYZ"
    cam.location = (0.0, -0.9, 0.6)
    cam.rotation_euler = Vector((0.0, 0.9, -0.6)).to_track_quat("-Z", "Y").to_euler("XYZ")
    sc.camera = cam
    ld = bpy.data.lights.new("sun", "SUN")
    ld.energy = 3.0
    sun = bpy.data.objects.new("sun", ld)
    coll.objects.link(sun)
    sun.rotation_euler = (0.6, 0.3, 0.0)

    # bake 12 frames
    B = bake.Bake(N)
    for f in range(1, N + 1):
        s = state(f)
        hero.pose_channels(rig, s["pose"], f, B)
        B.vec(slab, "location", f, (pivot[0], pivot[1], pivot[2] - s["drop"]))
        B.vec(slab, "rotation_euler", f, (s["tilt"], 0.0, 0.0))
        B.prop(slab, "ui_power", f, s["power"])
        B.hide(slab, f, not s["slab_visible"])
        B.vec(tile, "location", f, (tile_c[0], tile_c[1], -s["depth"]))
        B.prop(tile, "ui_glow", f, 1.0)
        B.put(ring.data.shape_keys, 'key_blocks["grow"].value', f, s["grow"])
        B.put(cd, "lens", f, s["lens"])
        B.vec(cam, "rotation_euler", f, (0.0, 0.0, wrap_rz(f)))          # wraps past +pi between f 3 and f 4
        for key_name, kb in card_keys.items():
            B.put(card.data.shape_keys, f'key_blocks["{kb.name}"].value', f, 1.0 if s["card_key"] == key_name else 0.0)
    keyed, const = B.write()
    print(f"CHECK bake: {N} frames, {keyed} keyed channels, {const} constant channels")
    sc.frame_set(1)
    blend = os.path.join(out_dir, "build.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)

    # reload and read back
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    O = bpy.data.objects
    if sc.cycles.device != "GPU":
        raise AssertionError(f"after reload the scene device is {sc.cycles.device}, not GPU (gpu.py load_post)")

    def fc(idb, path, index=0):
        c = bake.fcurve(idb, path, index)
        if c is None:
            raise AssertionError(f"no F-curve {idb.name} {path}[{index}]")
        return c

    for f in (1, 6, 12):
        s = state(f)
        p = s["pose"]
        near(fc(O["toy"], "location", 0).evaluate(f), p["root"]["pos"][0], f"root x f{f}")
        near(fc(O["toy"], "rotation_euler", 2).evaluate(f), p["root"]["euler"][2], f"root yaw f{f}")
        near(fc(O["toy:squash"], "scale", 2).evaluate(f), p["squash"][2], f"squash z f{f}")
        near(fc(O["arm_px"], "rotation_euler", 1).evaluate(f), p["joints"]["arm_px"], f"arm_px joint f{f}")
        near(fc(O["leg_nx"], "rotation_euler", 0).evaluate(f), p["joints"]["leg_nx"], f"leg_nx joint f{f}")
        near(fc(O["arm_px"], "location", 2).evaluate(f), ARM_PIVOT_Z + LIFT_DZ * p["slides"]["lift_px"], f"lift_px f{f}")
        near(fc(O["panel:a"], '["ui_power"]').evaluate(f), s["power"], f"ui_power f{f}")
        near(fc(O["panel:a"], "location", 2).evaluate(f), -s["drop"], f"slab drop f{f}")
        near(fc(O["ring:0"].data.shape_keys, 'key_blocks["grow"].value').evaluate(f), s["grow"], f"ring grow f{f}")
        near(fc(bpy.data.cameras["camera"], "lens").evaluate(f), s["lens"], f"lens f{f}")
        near(fc(O["card"].data.shape_keys, 'key_blocks["k1"].value').evaluate(f), 1.0 if s["card_key"] == "k1" else 0.0, f"card k1 f{f}")
    rz = [kp.co[1] for kp in fc(O["camera"], "rotation_euler", 2).keyframe_points]
    if len(rz) != N or any(abs(b - a) > 1.0 for a, b in zip(rz, rz[1:])):
        raise AssertionError(f"camera rz keys are not continuous (bake unwrap): {[round(v, 3) for v in rz]}")
    for f in (1, 4, N):
        near(math.atan2(math.sin(rz[f - 1]), math.cos(rz[f - 1])), math.atan2(math.sin(wrap_rz(f)), math.cos(wrap_rz(f))), f"camera rz mod 2 pi f{f}")
    print(f"CHECK bake unwrap: camera rz keys {rz[0]:.2f} .. {rz[-1]:.2f} rad continuous across the +-pi wrap")
    for f in (1, 8, 12):
        p = state(f)["pose"]
        vis, ex = p["visible"], p["expression"]
        near(fc(O["eye_px_open"], "hide_render").evaluate(f), 0.0 if (vis and ex == "open") else 1.0, f"eye_px_open hide f{f}")
        near(fc(O["eye_px_happy"], "hide_render").evaluate(f), 0.0 if (vis and ex == "happy") else 1.0, f"eye_px_happy hide f{f}")
        near(fc(O["body"], "hide_render").evaluate(f), 0.0 if vis else 1.0, f"body hide f{f}")
    near(fc(O["panel:a"], "hide_render").evaluate(12), 1.0, "slab hidden f12")
    near(fc(O["eye_px_happy"], "hide_render").evaluate(6.5), 1.0, "CONSTANT hide holds at f6.5")
    near(fc(O["toy"], "location", 0).evaluate(6.5),
         (state(6)["pose"]["root"]["pos"][0] + state(7)["pose"]["root"]["pos"][0]) / 2, "LINEAR x at f6.5")
    if bake.fcurve(O["tile:b"], '["ui_glow"]') is not None:
        raise AssertionError("constant channel tile ui_glow got keys")
    near(O["tile:b"]["ui_glow"], 1.0, "constant ui_glow value")
    if O["tile:b"].parent.name != "panel:a" or O["screen:c"].parent.name != "panel:a":
        raise AssertionError("tile / screen are not parented to panel:a")
    for f in (1, 12):
        s = state(f)
        sc.frame_set(f)
        bpy.context.view_layer.update()
        local = Vector((tile_c[0], tile_c[1], -s["depth"]))
        expect = (Matrix.Translation((pivot[0], pivot[1], -s["drop"])) @ Matrix.Rotation(s["tilt"], 4, "X")
                  @ Matrix.Translation((-pivot[0], -pivot[1], 0.0))) @ local
        got = O["tile:b"].matrix_world.translation
        for i, ax in enumerate("xyz"):
            near(got[i], expect[i], f"parent_keep_world tile world {ax} f{f}")
    print("CHECK reload: F-curves at f1/f6/f12, hide at f1/f8/f12, CONSTANT vs LINEAR, constant channel, parent_keep_world ok")

    # one tiny render
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 4
    sc.cycles.use_adaptive_sampling = False
    sc.cycles.use_denoising = False
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 160, 90, 100
    sc.render.use_persistent_data = False
    sc.render.image_settings.file_format = "PNG"
    sc.frame_set(6)
    png = os.path.join(out_dir, "frame_0006.png")
    if os.path.exists(png):
        os.remove(png)
    sc.render.filepath = png
    t0 = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    dt = time.perf_counter() - t0
    if not os.path.isfile(png) or os.path.getsize(png) == 0:
        raise AssertionError(f"render wrote no file at {png}")
    print(f"CHECK render: 160x90 4 samples on {sc.cycles.device}, {os.path.getsize(png)} bytes, {dt:.1f} s -> {png}")

    # lookdev selfcheck with a relative --out (160x80, 4 samples, 3 frames + 2 stills)
    from filmkit.blender import lookdev
    rel = "lookdev_rel"
    shutil.rmtree(os.path.join(out_dir, rel), ignore_errors=True)       # no stale PNG or JSON can pass
    os.chdir(out_dir)
    lookdev.main(["selfcheck", "--out", rel])
    doc_path = os.path.join(out_dir, rel, "lookdev.json")
    if not os.path.isfile(doc_path):
        raise AssertionError(f"lookdev selfcheck --out {rel} wrote no {doc_path}")
    with open(doc_path, encoding="utf-8") as fh:
        sc_doc = json.load(fh)["selfcheck"]
    if sc_doc.get("ok") is not True:
        raise AssertionError(f"lookdev selfcheck --out {rel}: {sc_doc.get('problems')}")
    n_seq = len([n for n in os.listdir(os.path.join(out_dir, rel, "seq")) if n.endswith(".png")])
    if n_seq != 24:
        raise AssertionError(f"lookdev selfcheck --out {rel}: {n_seq} sequence PNGs under {rel}/seq, want 24")
    print(f"CHECK lookdev relative out: selfcheck ok, lookdev.json and {n_seq} sequence PNGs under {rel}/")
    print("BLENDER_BUILD_CHECK: PASS")


# ---------------------------------------------------------------- plain python launcher
def sweep_bytecode(root):
    """Remove __pycache__ folders and .pyc files under root. -> [removed paths]."""
    removed = []
    for dirpath, dirnames, filenames in os.walk(root):
        for d in list(dirnames):
            if d == "__pycache__":
                full = os.path.join(dirpath, d)
                for fn in os.listdir(full):
                    os.remove(os.path.join(full, fn))
                os.rmdir(full)
                removed.append(full)
                dirnames.remove(d)
        for fn in filenames:
            if fn.endswith(".pyc"):
                full = os.path.join(dirpath, fn)
                os.remove(full)
                removed.append(full)
    return removed


def main():
    blender = os.environ.get("BLENDER") or DEFAULT_BLENDER
    if not os.path.isfile(blender):
        print(f"FAIL: Blender not found at {blender} (set env BLENDER)")
        return 1
    default_root = os.path.join(tempfile.gettempdir(), "film-engine-checks")
    root = os.environ.get("FILM_SCRATCH") or default_root
    out = os.path.join(root, "blender_build")
    if len(os.path.join(out, "frame_0006.png")) > MAX_PATH:
        print(f"NOTE: FILM_SCRATCH gives a {len(out)}-char path; Windows file writes fail past {MAX_PATH}. "
              f"Using {default_root} instead.")
        out = os.path.join(default_root, "blender_build")
    os.makedirs(out, exist_ok=True)
    gpu = os.path.join(ENGINE, "filmkit", "blender", "gpu.py")
    cmd = [blender, "-b", "--python-exit-code", "1", "--factory-startup",
           "-P", gpu, "-P", os.path.abspath(__file__), "--", out]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=600, cwd=out,
                          encoding="utf-8", errors="replace")
    dt = time.perf_counter() - t0
    lines = (proc.stdout + "\n" + proc.stderr).splitlines()
    gpu_line = next((ln for ln in lines if ln.startswith("gpu.py: ")), None)
    passed = any(ln.startswith("BLENDER_BUILD_CHECK: PASS") for ln in lines)
    ok = proc.returncode == 0 and passed and gpu_line is not None
    for ln in lines:
        if ln.startswith(("gpu.py: ", "CHECK ")):
            print(ln)
    if not ok:
        print(f"FAIL: blender exit {proc.returncode}, gpu line {'present' if gpu_line else 'missing'}, "
              f"PASS line {'present' if passed else 'missing'}; last output lines:")
        for ln in lines[-40:]:
            print("  " + ln)
    removed = sweep_bytecode(SKILL)
    if removed:
        ok = False
        print("FAIL: bytecode was written under the skill folder (removed): " + ", ".join(removed))
    print(f"{'PASS' if ok else 'FAIL'} check_blender_build in {dt:.1f} s; outputs in {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    if bpy is not None:
        blender_main(sys.argv[sys.argv.index("--") + 1])
    else:
        sys.exit(main())
