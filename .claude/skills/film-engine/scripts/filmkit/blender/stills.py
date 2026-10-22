"""stills: render chosen frames and measure them; animatic mode. Owner: blender-look. Imports bpy, numpy.

Rules: persistent data OFF, render the context scene after frame_set(f),
never save the .blend afterwards. Render paths go through render.safe_out
before they reach scene.render.filepath (absolute, inside the project folder,
else a ValueError): Blender resolves a plain relative path against the drive
root, not the cwd. The class mask is one material_override
(materials.make_mask_material) rendered with the Standard view, exposure 0,
gamma 1 (the look's view gamma stays out of the mask: the bands are gamma-1 codes),
world strength 0, no denoise, no compositor, no adaptive sampling, motion
blur as the beauty. PNGs are read back as Non-Color and flipped. Renders go
to a temp name and are renamed once read back. Measurements are frame
fractions and sRGB 8-bit medians (filmkit.measure.measure_arrays holds the
maths); the engine holds no threshold. An object with ob['mask_skip'] set
(any true value) is hidden from camera rays for the mask render only (a haze
cone or any camera-only effect that must not occlude the classes).

numpy is Blender's own (this module runs inside Blender only).

CLI (the project passes the blend; mask classes and the target come from the
LOOK stored by render.apply_look: look['mask'] = {'classes': {...}, 'target':
'RRGGBB' sRGB hex, 'orange': [[r, g, b] linear, ...] optional}):
  blender -b --python-exit-code 1 film.blend -P gpu.py -P stills.py -- --frames 1,31,62 --out renders/stills
      [--percent 50 --samples 40 --adaptive 0.03] [--mask] [--target D97757] [--classes file.json]
      [--json stills.json] [--prefix f] [--points motion:hero_points] [--project <dir>]
  --json: a bare file name lands in --out; a path with a folder is used as given.
  --points module:function: a project function f(t) -> world points, imported from the project folder
  (--project; default the parent of the .blend's folder, i.e. <project>/build/film.blend), gives
  stills.json its silhouette.model_w (the model-vs-mask width cross-check). Without it model_w is null.
  blender -b --python-exit-code 1 film.blend -P gpu.py -P stills.py -- --animatic --out renders/animatic [--samples 16]
  blender -b --python-exit-code 1 film.blend -P gpu.py -P stills.py -- --final --out renders/frames_9x16
      [--camera camera_9x16 --film 1080x1920] [--preset final]
  --final: every frame at the look's final preset (or --preset), persistent data on, like `-a` on the saved
  scene but through another camera and film size (the vertical final); --percent / --samples / --adaptive
  override the preset. The .blend is never saved.
"""
import sys
sys.dont_write_bytecode = True
import importlib
import json
import os
import time

if __name__ == "__main__":   # run with -P: make filmkit importable
    sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

from filmkit import measure
from filmkit.blender import materials, render as render_mod

LUMA = measure.LUMA


def _tmp(path):
    d, n = os.path.split(path)
    return os.path.join(d, f".tmp_{n}")


def _finish(tmp, path):
    if not os.path.exists(tmp):
        raise RuntimeError(f"stills: render wrote nothing at {tmp}")
    os.replace(tmp, path)
    return path


def render_still(scene, f, path, percent, samples, adaptive, denoise=True):
    """Render frame f of the context scene to path (PNG) with the given quality; adaptive None or 0
    turns adaptive sampling off. Persistent data off. Restores nothing; the .blend is not saved.
    -> seconds."""
    r, cy = scene.render, scene.cycles
    r.resolution_percentage = int(percent)
    cy.samples = int(samples)
    cy.use_adaptive_sampling = bool(adaptive)
    cy.adaptive_threshold = float(adaptive or 0.0)
    cy.use_denoising = bool(denoise)
    r.use_persistent_data = False
    path = render_mod.safe_out(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    scene.frame_set(int(f))
    tmp = _tmp(path)
    r.filepath = tmp
    t0 = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    secs = time.perf_counter() - t0
    _finish(tmp, path)
    return secs


def mask_skipped(scene):
    """-> [Object] of the scene with ob['mask_skip'] set to a true value (hidden from the mask render)."""
    return [ob for ob in scene.objects if ob.get("mask_skip")]


def render_mask(scene, f, path, mask_material, samples=32):
    """Render the class mask for frame f to path with the measurement settings (Standard view, look
    None, exposure 0, gamma 1 (the look's view gamma would move every band: materials.mask_bands is
    computed for gamma 1 and the PNG applies the view gamma), world 'Background' strength 0, no denoise,
    no adaptive, no compositor, motion blur as set; objects with ob['mask_skip'] turned camera-invisible),
    then restore view, exposure, gamma, world strength, compositor, denoise, override, filepath and the
    skipped objects' camera visibility."""
    vl = bpy.context.view_layer
    vs, cy, r = scene.view_settings, scene.cycles, scene.render
    bg = scene.world.node_tree.nodes.get("Background") if scene.world else None
    keep = (vs.view_transform, vs.look, vs.exposure, vs.gamma, cy.samples, cy.use_adaptive_sampling, cy.use_denoising,
            r.use_compositing, bg.inputs["Strength"].default_value if bg else None, r.filepath,
            vl.material_override, r.use_persistent_data)
    skipped = [(ob, ob.visible_camera) for ob in mask_skipped(scene)]
    try:
        for ob, _ in skipped:
            ob.visible_camera = False       # a ray-visibility flag: not keyed, so frame_set cannot undo it
        vl.material_override = mask_material
        vs.view_transform, vs.look, vs.exposure, vs.gamma = "Standard", "None", 0.0, 1.0
        cy.samples, cy.use_adaptive_sampling, cy.use_denoising = int(samples), False, False
        r.use_compositing = False
        r.use_persistent_data = False
        if bg:
            bg.inputs["Strength"].default_value = 0.0
        path = render_mod.safe_out(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        scene.frame_set(int(f))
        tmp = _tmp(path)
        r.filepath = tmp
        bpy.ops.render.render(write_still=True)
        _finish(tmp, path)
    finally:
        (vs.view_transform, vs.look, vs.exposure, vs.gamma, cy.samples, cy.use_adaptive_sampling, cy.use_denoising,
         r.use_compositing, bg_strength, r.filepath, vl.material_override, r.use_persistent_data) = keep
        if bg:
            bg.inputs["Strength"].default_value = bg_strength
        for ob, vis in skipped:
            ob.visible_camera = vis
    return path


def read_png(path):
    """-> (h, w, 4) float array (0..1) read through bpy as Non-Color, top-down. Needs numpy."""
    import numpy as np
    im = bpy.data.images.load(os.path.abspath(path))     # a relative path would resolve against the .blend
    im.colorspace_settings.name = "Non-Color"
    w, h = im.size
    a = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return np.flipud(a.reshape(h, w, 4))


def measure_regions(beauty_png, mask_png, bands, target_srgb=None, erode=2, hot=245, grow=3,
                    hero="body", studio="studio", min_px=30, studio_guard=8):
    """Read both PNGs (bpy, Non-Color) and measure them: filmkit.measure.measure_arrays (per class band
    count and sRGB median with 'err' vs target_srgb, hero silhouette, hot pixels, void, studio_luma).
    The studio class is eroded by max(erode, studio_guard) px so a motion-blurred edge of a bright class
    on the same channel cannot pass for studio. -> {'colour', 'silhouette', 'hot', 'void', 'studio_luma',
    'max'}."""
    img = read_png(beauty_png)[..., :3] * 255.0
    msk = read_png(mask_png)[..., :3] * 255.0
    return measure.measure_arrays(img, msk, bands, target_srgb, erode=erode, hot=hot, grow=grow, hero=hero,
                                  studio=studio, min_px=min_px, studio_guard=studio_guard)


def model_width(scene, points):
    """Silhouette width share of world points through the scene camera (Blender's own projection), for
    the model-vs-render cross-check. -> float (frame fraction), None without points."""
    if not points:
        return None
    bpy.context.view_layer.update()
    xs = [world_to_camera_view(scene, scene.camera, Vector(p)).x for p in points]
    return round(float(max(xs) - min(xs)), 4)


def _merge_json(path, entries):
    try:
        with open(path, encoding="utf-8") as fh:
            keep = [e for e in json.load(fh) if e["frame"] not in {x["frame"] for x in entries}]
    except (OSError, ValueError):
        keep = []
    merged = sorted(keep + entries, key=lambda e: e["frame"])
    tmp = _tmp(path)
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=1)
    os.replace(tmp, path)
    return merged


def render_stills(scene, frames, out_dir, percent=50, samples=40, adaptive=0.03, mask_material=None,
                  bands=None, target_srgb=None, points_fn=None, json_out=None, prefix="f", extra_fn=None,
                  mask_samples=32, measure_kw=None, denoise=True):
    """Render each frame to out_dir/<prefix>####.png (and its mask mask_####.png when mask_material is
    given), measure, merge into json_out (entries of other frames kept). points_fn(t) -> world points
    for model_width; extra_fn(scene, f) -> dict merged into the entry (e.g. content_in_frame).
    Entry: {frame, t, seconds_render, path, colour, silhouette: {mask_w, mask_h, model_w}, hot, void,
    studio_luma, max, content_in_frame}. Prints one STILL line per frame. -> [per-frame dicts]."""
    fps = scene.render.fps / scene.render.fps_base
    out_dir = render_mod.safe_out(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    entries = []
    for f in frames:
        f = int(f)
        t = (f - 1) / fps
        path = os.path.join(out_dir, f"{prefix}{f:04d}.png")
        secs = render_still(scene, f, path, percent, samples, adaptive, denoise)
        entry = {"frame": f, "t": round(t, 6), "seconds_render": round(secs, 2), "path": path,
                 "colour": {}, "silhouette": None, "hot": None, "void": None, "studio_luma": None, "max": None,
                 "content_in_frame": None}
        if mask_material is not None:
            mask_path = os.path.join(out_dir, f"mask_{f:04d}.png")
            render_mask(scene, f, mask_path, mask_material, mask_samples)
            entry.update(measure_regions(path, mask_path, bands or {}, target_srgb, **(measure_kw or {})))
            entry["mask_path"] = mask_path
        model_w = model_width(scene, points_fn(t)) if points_fn else None
        sil = entry["silhouette"] or {}
        entry["silhouette"] = {"mask_w": sil.get("mask_w"), "mask_h": sil.get("mask_h"), "model_w": model_w}
        if extra_fn:
            entry.update(extra_fn(scene, f) or {})
        entries.append(entry)
        cols = "  ".join(f"{k} {tuple(int(round(c)) for c in v['median'])}" for k, v in entry["colour"].items())
        hot = entry["hot"] or {}
        print(f"STILL f{f:04d} {secs:5.1f} s  {cols}  width {sil.get('mask_w')} (model {model_w})  "
              f"void {(entry['void'] or {}).get('top')}  hot {hot.get('n')} max {entry['max']}")
    if json_out:
        _merge_json(json_out, entries)
    if entries:
        s = [e["seconds_render"] for e in entries]
        print(f"STILLS {len(s)} frames, mean {sum(s) / len(s):.1f} s, max {max(s):.1f} s per frame")
    return entries


def render_animatic(scene, out_dir, percent=50, samples=16, adaptive=0.05, frames=None, denoise=True):
    """Render every frame (persistent data ON, one animation render into out_dir/####.png) or the
    given frames (out of order: persistent data OFF, one still each) at low quality. denoise: the
    preset's flag. -> seconds."""
    r, cy = scene.render, scene.cycles
    out_dir = render_mod.safe_out(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.perf_counter()
    if frames:
        for f in frames:
            render_still(scene, f, os.path.join(out_dir, f"{int(f):04d}.png"), percent, samples, adaptive, denoise)
        n = len(frames)
    else:
        r.resolution_percentage = int(percent)
        cy.samples = int(samples)
        cy.use_adaptive_sampling = bool(adaptive)
        cy.adaptive_threshold = float(adaptive or 0.0)
        cy.use_denoising = bool(denoise)
        r.use_persistent_data = True
        r.filepath = os.path.join(out_dir, "")
        bpy.ops.render.render(animation=True)
        n = scene.frame_end - scene.frame_start + 1
    secs = time.perf_counter() - t0
    print(f"ANIMATIC {n} frames at {percent} %, {samples} samples in {secs:.0f} s ({secs / max(n, 1):.2f} s per frame)")
    return secs


def mask_from_look(look, target=None, classes=None):
    """-> (mask_material, bands, target_srgb) from look['mask'] (see the module doc); target: hex
    override; classes: dict override. (None, {}, None) when the look has no mask."""
    spec = dict(look.get("mask", {}))
    if classes is not None:
        spec["classes"] = classes
    if target is not None:
        spec["target"] = target
    if not spec.get("classes"):
        return None, {}, None
    target_srgb = None
    if spec.get("target"):
        h = spec["target"].lstrip("#")
        target_srgb = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    orange = spec.get("orange") or ([materials.srgb_to_linear(spec["target"])] if spec.get("target") else [])
    mat = materials.make_mask_material(spec.get("name", "film_mask"), spec["classes"], orange)
    return mat, materials.mask_bands(spec["classes"]), target_srgb


def load_points_fn(spec, project_dir=None):
    """'module:function' -> callable(t) -> world points, imported from the project folder (put first on
    sys.path; project modules bootstrap the engine themselves, env FILM_ENGINE names it outside the
    kit). project_dir None: the parent of the open .blend's folder (<project>/build/film.blend).
    -> None for an empty spec; raises SystemExit on a bad spec or a missing module/function."""
    if not spec:
        return None
    mod_name, sep, fn_name = str(spec).partition(":")
    if not sep or not mod_name or not fn_name:
        raise SystemExit(f"stills: --points wants module:function, got {spec!r}")
    if project_dir is None:
        if not bpy.data.filepath:
            raise SystemExit("stills: --points needs --project when no .blend is open")
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(bpy.data.filepath)))
    project_dir = os.path.abspath(project_dir)
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)
    try:
        fn = getattr(importlib.import_module(mod_name), fn_name)
    except (ImportError, AttributeError) as e:
        raise SystemExit(f"stills: --points {spec}: {e} (project folder {project_dir})")
    return lambda t: fn(t)


def parse_cli(argv):
    """['--k', 'v', '--flag', ...] -> {k: v | True}."""
    opts, i = {}, 0
    while i < len(argv):
        a = argv[i]
        if not a.startswith("--"):
            raise SystemExit(f"stills: unexpected argument {a!r}")
        if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            opts[a[2:]] = argv[i + 1]
            i += 2
        else:
            opts[a[2:]] = True
            i += 1
    return opts


def main(argv):
    """Parse the CLI after '--' and dispatch on the context scene of the opened .blend."""
    opts = parse_cli(argv)
    scene = bpy.context.scene
    if "camera" in opts:                      # another camera the scene built (the 9:16 one), never saved
        cam = scene.objects.get(str(opts["camera"]))
        if cam is None or cam.type != "CAMERA":
            raise SystemExit(f"stills: --camera {opts['camera']!r} is not a camera object of the scene")
        scene.camera = cam
    if "film" in opts:                        # its film size WxH (resolution_percentage stays the preset's)
        w, h = (int(v) for v in str(opts["film"]).lower().split("x"))
        scene.render.resolution_x, scene.render.resolution_y = w, h
    look, _ = render_mod.stored_look(scene)
    presets = look.get("presets") or render_mod.PRESETS
    out = opts.get("out", "renders/animatic" if "animatic" in opts else "renders/stills")
    if "animatic" in opts or "final" in opts:
        name = "animatic" if "animatic" in opts else str(opts.get("preset", look.get("preset", "final")))
        if name not in presets:
            raise SystemExit(f"stills: preset {name!r} is not in the stored look's presets {sorted(presets)}")
        pct, spp, adaptive, denoise = presets[name]
        render_animatic(scene, out, int(opts.get("percent", pct)), int(opts.get("samples", spp)),
                        float(opts.get("adaptive", adaptive)), denoise=bool(denoise))
        return
    if "frames" not in opts:
        raise SystemExit("stills: --frames a,b,c or --animatic is required")
    frames = [int(v) for v in str(opts["frames"]).split(",") if v]
    pct, spp, adaptive, denoise = presets.get("stills", render_mod.PRESETS["stills"])
    mask_material, bands, target = None, {}, None
    if "mask" in opts:
        classes = None
        if "classes" in opts:
            with open(opts["classes"], encoding="utf-8") as fh:
                classes = json.load(fh)
        mask_material, bands, target = mask_from_look(look, opts.get("target"), classes)
        if mask_material is None:
            raise SystemExit("stills: --mask needs look['mask']['classes'] stored in the .blend or --classes file")
    json_out = opts.get("json")
    if json_out and not os.path.dirname(json_out):       # a bare file name lands in --out
        json_out = os.path.join(out, json_out)
    points_fn = load_points_fn(opts.get("points"), opts.get("project"))
    render_stills(scene, frames, out, int(opts.get("percent", pct)), int(opts.get("samples", spp)),
                  float(opts.get("adaptive", adaptive)), mask_material, bands, target, points_fn, json_out,
                  prefix=opts.get("prefix", "f"), denoise=bool(denoise))


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
