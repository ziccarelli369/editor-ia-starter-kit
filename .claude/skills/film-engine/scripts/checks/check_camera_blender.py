"""check_camera_blender.py: the Python pinhole (filmkit.camera.project) against Blender's own projection.

Runs Blender in the background with --factory-startup, builds a camera from camera.py parameters
(sensor 36 mm HORIZONTAL, lens, position, rotation_euler XYZ from look_at_euler) and 20 empties, and
reads Blender's world_to_camera_view for each. The check compares those with camera.project: max error
< 1e-4 in ndc and depth, for a 16:9 and a 9:16 film. The probe also imports filmkit under Blender's
Python (standard library only) and compares there. Blender's camera axes (matrix_world columns) must
match camera.basis_from_dir within 1e-6, and the rz Blender stores must match look_at_euler's and the
rz the Python basis implies within 1e-6. Vertical views (E = +-90 deg) are cases too: two top-down holds
solved through camera_state (their roll comes from 'heading') and one view looking straight up.
Exit 1 on any mismatch, or when Blender is missing. Env BLENDER overrides the Blender path.
"""
import sys
sys.dont_write_bytecode = True
import json
import math
import os
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, SCRIPTS)
from filmkit import camera, ease, vec  # noqa: E402

BLENDER = os.environ.get("BLENDER") or "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
TOL = 1e-4
AXIS_TOL = 1e-6

PROBE = r'''
import sys
sys.dont_write_bytecode = True
import json
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index("--") + 1:]
with open(argv[0], encoding="utf-8") as fh:
    job = json.load(fh)
sys.path.insert(0, job["scripts"])
from filmkit import camera as fk_camera

scene = bpy.context.scene
scene.render.resolution_percentage = 100
scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1.0
out = []
for case in job["cases"]:
    scene.render.resolution_x, scene.render.resolution_y = case["film"]
    data = bpy.data.cameras.new("probe_cam")
    data.sensor_width = case["sensor_w"]
    data.sensor_fit = "HORIZONTAL"
    data.lens = case["lens"]
    data.shift_x = data.shift_y = 0.0
    cam = bpy.data.objects.new("probe_cam", data)
    scene.collection.objects.link(cam)
    cam.rotation_mode = "XYZ"
    cam.location = case["pos"]
    cam.rotation_euler = case["rot"]
    scene.camera = cam
    empties = []
    for i, X in enumerate(case["points"]):
        e = bpy.data.objects.new(f"probe_pt_{i}", None)
        e.location = X
        scene.collection.objects.link(e)
        empties.append(e)
    bpy.context.view_layer.update()
    rows = []
    worst = 0.0
    hd = case.get("heading")
    # a vertical view compares from the float64 pos: Blender's float32 location adds ~1e-8 of horizontal
    # noise to target - pos, above camera.VERTICAL_EPS (the chain itself projects from the float64 camera dict)
    pos = tuple(case["pos"]) if hd is not None else tuple(cam.location)
    for e in empties:
        X = e.matrix_world.translation
        v = world_to_camera_view(scene, cam, X)
        b = (v.x * 2.0 - 1.0, v.y * 2.0 - 1.0, v.z)
        p = fk_camera.project(pos, case["target"], case["lens"], tuple(X), tuple(case["film"]), case["sensor_w"], hd)
        worst = max(worst, abs(b[0] - p[0]), abs(b[1] - p[1]), abs(b[2] - p[2]))
        rows.append(b)
    mw = cam.matrix_world
    out.append({"name": case["name"], "blender": rows, "inside_err": worst, "python": sys.version.split()[0],
                "rot": list(cam.rotation_euler), "axes": [[mw[i][j] for i in range(3)] for j in range(3)]})
    for e in empties:
        bpy.data.objects.remove(e)
    bpy.data.objects.remove(cam)
    bpy.data.cameras.remove(data)
with open(argv[1], "w", encoding="utf-8") as fh:
    json.dump(out, fh)
print("PROBE_DONE")
'''


def make_cases():
    rnd = ease.mulberry32(2026)
    cases = []
    for film in ((1920, 1080), (1080, 1920)):
        for name, pos, target, lens in (("wide", (0.4, -1.9, 1.6), (0.0, 0.1, 0.0), 30.0),
                                        ("long", (-1.1, -0.5, 0.35), (0.2, 0.3, 0.05), 85.0)):
            pts = []
            for _ in range(20):
                pts.append((target[0] + rnd() * 1.2 - 0.6, target[1] + rnd() * 1.2 - 0.6, rnd() * 0.4 - 0.05))
            cases.append({"name": f"{name}_{film[0]}x{film[1]}", "film": list(film), "sensor_w": 36.0, "lens": lens,
                          "pos": list(pos), "target": list(target), "rot": list(camera.look_at_euler(pos, target)),
                          "points": [list(p) for p in pts]})
    # vertical views: two solved top-down holds (camera_state carries the heading) and one looking up
    frame = [(0.7 + x, 0.4 + y, 0.0) for x in (-0.3, 0.3) for y in (-0.2, 0.2)]
    for A in (30.0, -135.0):
        sl = camera.ShotList([camera.Hold("top", 0.0, 1.0, A, 90.0, 35.0, lambda t: [(frame, 0.05)])]).solve()
        st = camera.camera_state(sl, 0.5, lambda t: (0.7, 0.4, 0.0), None)
        pts = [(0.7 + rnd() * 0.6 - 0.3, 0.4 + rnd() * 0.4 - 0.2, rnd() * 0.05) for _ in range(20)]
        cases.append({"name": f"top_A{A:g}_1920x1080", "film": [1920, 1080], "sensor_w": 36.0, "lens": 35.0,
                      "pos": list(st["pos"]), "target": list(st["target"]), "rot": list(st["rot"]),
                      "heading": st["heading"], "points": [list(p) for p in pts]})
    pos, target, hd = (0.75, 0.5, -1.5), (0.75, 0.5, 0.0), 1.0
    pts = [(0.75 + rnd() * 1.0 - 0.5, 0.5 + rnd() * 0.6 - 0.3, rnd() * 0.3) for _ in range(20)]
    cases.append({"name": "up_A57_1920x1080", "film": [1920, 1080], "sensor_w": 36.0, "lens": 35.0,
                  "pos": list(pos), "target": list(target), "rot": list(camera.look_at_euler(pos, target, hd)),
                  "heading": hd, "points": [list(p) for p in pts]})
    return cases


def main():
    if not os.path.exists(BLENDER):
        print(f"FAIL blender not found at {BLENDER} (set env BLENDER)")
        return 1
    cases = make_cases()
    tmp = tempfile.mkdtemp(prefix="film-engine-cam-")
    probe, job, result = (os.path.join(tmp, n) for n in ("probe.py", "job.json", "result.json"))
    with open(probe, "w", encoding="utf-8") as fh:
        fh.write(PROBE)
    with open(job, "w", encoding="utf-8") as fh:
        json.dump({"scripts": SCRIPTS, "cases": cases}, fh)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([BLENDER, "-b", "--factory-startup", "--python", probe, "--", job, result],
                          capture_output=True, text=True, env=env, timeout=180)
    if proc.returncode != 0 or "PROBE_DONE" not in proc.stdout or not os.path.exists(result):
        print("FAIL blender probe did not finish")
        print(proc.stdout[-3000:])
        print(proc.stderr[-3000:])
        return 1
    with open(result, encoding="utf-8") as fh:
        rows = json.load(fh)
    fails = 0
    for case, got in zip(cases, rows):
        worst = 0.0
        hd = case.get("heading")
        for X, b in zip(case["points"], got["blender"]):
            p = camera.project(tuple(case["pos"]), tuple(case["target"]), case["lens"], tuple(X), tuple(case["film"]), 36.0, hd)
            worst = max(worst, abs(b[0] - p[0]), abs(b[1] - p[1]), abs(b[2] - p[2]))
        behind = sum(1 for b in got["blender"] if b[2] <= 0)
        r, u, f = camera.basis_from_dir(vec.sub(case["target"], case["pos"]), hd)
        axes = max(abs(a - b) for col, want in zip(got["axes"], (r, u, vec.mul(f, -1.0))) for a, b in zip(col, want))
        rz = max(abs(ease.wrap(got["rot"][2] - case["rot"][2])), abs(ease.wrap(case["rot"][2] - math.atan2(r[1], r[0]))))
        ok = worst < TOL and got["inside_err"] < TOL and behind == 0 and axes < AXIS_TOL and rz < AXIS_TOL
        fails += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {case['name']:<20} max |blender - python| {worst:.2e} ndc (in-Blender {got['inside_err']:.2e}),"
              f" axes {axes:.1e}, rz {rz:.1e}, 20 points, blender python {got['python']}")
    for p in (probe, job, result):
        os.remove(p)
    os.rmdir(tmp)
    print(f"check_camera_blender: {fails} failures (tolerance {TOL})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
