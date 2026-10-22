"""lookdev: try look values on real frames before writing them down; self-checks. Owner: blender-look.
Imports bpy and Blender's numpy (runs inside Blender only).

CLI:
  blender -b --python-exit-code 1 film.blend -P gpu.py -P lookdev.py -- frames 1 31 [--prop obj.prop=v[;...]]
      [--mat name.socket=v[;...]] [--light name=watts[;...]] [--grade mat:h,s,v|mat:none[;...]] [--world r,g,b]
      [--percent 50 --samples 32] [--adaptive 0.03] [--tag t] [--out renders/lookdev] [--mask [--target D97757]]
  blender -b --python-exit-code 1 --factory-startup -P gpu.py -P lookdev.py -- selfcheck [--out renders/lookdev]
  blender -b --python-exit-code 1 film.blend -P gpu.py -P lookdev.py -- tune <material> --target D97757 --frames 31,124
      [--rounds 4 --tol 2 --band body --percent 50 --samples 16] [--out dir]
  blender -b --python-exit-code 1 film.blend -P gpu.py -P lookdev.py -- turnaround [--out renders/lookdev] [--root hero]
      [--dist 0.5 --lens 50]
--python-exit-code 1 makes Blender stop with exit 1 on the first exception in a -P script (gpu.py's
'no device' included); without it Blender exits 0 and runs the next script. --out may be relative to
the cwd: every path handed to bpy goes through render.safe_out first (absolute, inside the project).
Every number printed goes to stdout prefixed LOOKDEV / CHECK / TUNE / TURN and to <out>/lookdev.json
(keys: 'frames' {tag: entries}, 'selfcheck', 'tune', 'turnaround'). The frames/tune/turnaround steps
re-apply the LOOK stored in the .blend by render.apply_look first, then the CLI overrides, in memory.
"""
import sys
sys.dont_write_bytecode = True
import json
import math
import os
import subprocess

if __name__ == "__main__":   # run with -P: make filmkit importable
    sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))

import bpy
from mathutils import Vector

from filmkit.blender import materials, render as render_mod, stills

DEFAULT_VIEWS = [("front", 0.0, 0.0), ("three_quarter", 35.0, 0.0), ("side_px", 90.0, 0.0),   # placeholders
                 ("back", 180.0, 0.0), ("top", 25.0, 42.0)]


def _write_json(out_dir, key, value):
    """Merge {key: value} into <out_dir>/lookdev.json (temp name, then rename). -> path."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "lookdev.json")
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        doc = {}
    if isinstance(value, dict) and isinstance(doc.get(key), dict):
        doc[key].update(value)
    else:
        doc[key] = value
    tmp = os.path.join(out_dir, ".tmp_lookdev.json")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    os.replace(tmp, path)
    return path


def _num(s):
    return tuple(float(v) for v in str(s).split(",")) if "," in str(s) else float(s)


def _mute_keys(idb, path):
    """Mute the F-curve of a keyed channel so a raw value override holds at every frame."""
    fc = render_mod._fcurve(idb, path)
    if fc is not None:
        fc.mute = True


# ---------------------------------------------------------------- overrides
def apply_overrides(scene, props=(), mats=(), lights=(), grades=(), world=None):
    """Apply CLI overrides in memory (never saved). props: ['obj.prop=v'] (a keyed property is muted,
    then set); mats: ['name.socket=v'] with socket a LOOK key (base, roughness, specular, coat, ...),
    'strength' (screen emission) or a Principled socket name, v a float or r,g,b; lights:
    ['name=watts']; grades: ['mat:h,s,v' | 'mat:none']; world: (r, g, b) light colour."""
    for kv in props:
        k, v = kv.split("=")
        on, pn = k.split(".", 1)
        ob = scene.objects[on]
        _mute_keys(ob, f'["{pn}"]')
        ob[pn] = float(v)
    for kv in mats:
        k, v = kv.split("=")
        mn, sock = k.rsplit(".", 1)
        m = bpy.data.materials[mn]
        val = _num(v)
        if sock == "strength" and "ui_strength_node" in m:
            m.node_tree.nodes[m["ui_strength_node"]].inputs[1].default_value = val
        elif sock in ("specular", "spec") and m.node_tree.nodes.get("look_spec_power") is not None:
            materials.set_power_specular(m, val)
        elif sock in materials.PRINCIPLED_KEYS:
            materials.set_principled(m, {sock: val})
        else:
            inp = m.node_tree.nodes[materials.PRINCIPLED].inputs[sock]
            inp.default_value = materials._rgba(val) if inp.type == "RGBA" else val
    for kv in lights:
        name, w = kv.split("=")
        render_mod.set_light_power(scene.objects[name], float(w))
    for kv in grades:                      # material names carry ':' (screen:comp): split on the last one
        mn, g = kv.rsplit(":", 1)
        materials.set_grade(bpy.data.materials[mn], None if g.strip().lower() == "none" else _num(g))
    if world is not None:
        bg = scene.world.node_tree.nodes["Background"]
        bg.inputs["Color"].default_value = materials._rgba(world)
    return scene


def render_frames(scene, frames, out_dir, tag, percent, samples, mask=False, bands=None, target_srgb=None,
                  adaptive=0.03, points_fn=None):
    """Render and measure the frames with the current overrides to <out_dir>/<tag>_f####.png. mask:
    False, True (material and bands from the stored look['mask']) or a mask Material (with bands).
    Entries go to lookdev.json under 'frames'[tag]. -> [dicts]."""
    mask_material = None
    if mask is True:
        look, _ = render_mod.stored_look(scene)
        mask_material, look_bands, look_target = stills.mask_from_look(look)
        if mask_material is None:
            raise SystemExit("lookdev: --mask needs look['mask']['classes'] stored in the .blend")
        bands, target_srgb = bands or look_bands, target_srgb or look_target
    elif mask:
        mask_material = mask
    entries = stills.render_stills(scene, frames, out_dir, percent, samples, adaptive, mask_material, bands,
                                   target_srgb, points_fn, None, prefix=f"{tag}_f")
    _write_json(out_dir, "frames", {tag: entries})
    print(f"LOOKDEV {tag}: {len(entries)} frames -> {out_dir}")
    return entries


# ---------------------------------------------------------------- self-check
def numbered_sequence(seq_dir, n, size=8):
    """Write <seq_dir>/0001..n PNGs (size x size) whose byte values encode the frame number:
    R = 12 (n mod 20), G = 12 (n div 20). -> path of 0001.png."""
    import numpy as np
    seq_dir = render_mod.safe_out(seq_dir)
    os.makedirs(seq_dir, exist_ok=True)
    im = bpy.data.images.new("seqgen", size, size, alpha=False)
    for k in range(1, n + 1):
        px = np.zeros((size, size, 4), np.float32)
        px[..., 0] = (k % 20) * 12 / 255
        px[..., 1] = (k // 20) * 12 / 255
        px[..., 3] = 1
        im.pixels.foreach_set(px.ravel())
        im.filepath_raw = os.path.join(seq_dir, f"{k:04d}.png")
        im.file_format = "PNG"
        im.save()
    bpy.data.images.remove(im)
    return os.path.join(seq_dir, "0001.png")


def _lin_to_srgb(v):
    v = max(float(v), 0.0)
    return v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


def decode_frame(rgb_linear):
    """Linear (r, g, b) of a numbered_sequence pixel as rendered -> the frame number it shows."""
    r, g = (int(math.floor(_lin_to_srgb(c) * 255 / 12 + 0.5)) for c in rgb_linear[:2])
    return r + 20 * g


def _sample_exr(path, x, span=3.0, half=3):
    """Mean linear rgb of a (2 half)^2 patch at horizontal position x (world units, ortho span) in an EXR."""
    import numpy as np
    img = bpy.data.images.load(os.path.abspath(path))    # a relative load resolves against the .blend
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    col = int((x + span / 2) / span * w)
    v = px[h // 2 - half:h // 2 + half, col - half:col + half, :3].reshape(-1, 3).mean(axis=0)
    bpy.data.images.remove(img)
    return [float(c) for c in v]


def selfcheck(out_dir, n_seq=24, size=(160, 80), samples=4):
    """Tiny ortho scene: a keyed-props plane (glow 1, 3, 3; power 1, 1, 0 on frames 1..3), a no-props
    plane (must read 1.0) and a plane playing a numbered PNG sequence. Renders frames 1..3 as an
    animation (persistent data on, the -a path) and stills at n_seq/2 and n_seq, as EXR, and decodes
    which frame each plane shows. out_dir may be relative to the cwd. -> dict; prints CHECK lines;
    raises on a failure."""
    import numpy as np
    out_dir = render_mod.safe_out(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    sc = bpy.context.scene
    render_mod.setup_render(sc, "chk", {"chk": (100, samples, 0.0, False)}, film=size, fps=30, frames=3,
                            view="Standard", look="None", exposure=0.0, shutter=0.0, persistent=True)
    sc.render.use_compositing = False
    render_mod.setup_world(sc, (0.0, 0.0, 0.0), 0.0, (0.0, 0.0, 0.0))
    white = bpy.data.images.new("chk_white", 8, 8, alpha=False)
    white.pixels.foreach_set(np.ones(8 * 8 * 4, np.float32))
    white.pack()
    first = numbered_sequence(os.path.join(out_dir, "seq"), n_seq)
    ui = materials.make_screen_material("chk_ui", white, spec=0.0, rough=0.5)
    seq = materials.make_screen_material("chk_seq", first, sequence=True, frames=n_seq, spec=0.0, rough=0.5,
                                         interpolation="Closest")

    def plane(name, x, mat):
        me = bpy.data.meshes.new(name)
        me.from_pydata([(x - 0.45, -0.45, 0), (x + 0.45, -0.45, 0), (x + 0.45, 0.45, 0), (x - 0.45, 0.45, 0)],
                       [], [(0, 1, 2, 3)])
        uvl = me.uv_layers.new(name="UVMap")
        for li, uv in zip(range(4), ((0, 0), (1, 0), (1, 1), (0, 1))):
            uvl.data[li].uv = uv
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        sc.collection.objects.link(ob)
        return ob

    keyed = plane("keyed", -1.0, ui)
    plane("noprops", 0.0, ui)
    plane("seq", 1.0, seq)
    materials.set_props(keyed, ui_glow=1.0, ui_power=1.0)
    expect = {1: (1.0, 1.0), 2: (3.0, 1.0), 3: (3.0, 0.0)}
    for f, (g, p) in expect.items():
        keyed["ui_glow"], keyed["ui_power"] = g, p
        keyed.keyframe_insert('["ui_glow"]', frame=f)
        keyed.keyframe_insert('["ui_power"]', frame=f)
    cd = bpy.data.cameras.new("chk_cam")
    cd.type, cd.ortho_scale = "ORTHO", 3.0
    cam = bpy.data.objects.new("chk_cam", cd)
    sc.collection.objects.link(cam)
    cam.location = (0, 0, 2)
    sc.camera = cam
    r = sc.render
    r.image_settings.file_format = "OPEN_EXR"
    r.image_settings.color_depth = "32"
    r.filepath = os.path.join(out_dir, "chk_")
    bpy.ops.render.render(animation=True)

    results, problems = {}, []
    for f in (1, 2, 3):
        p = os.path.join(out_dir, f"chk_{f:04d}.exr")
        k, n, s = _sample_exr(p, -1.0), _sample_exr(p, 0.0), _sample_exr(p, 1.0)
        want = expect[f][0] * expect[f][1]
        dec = decode_frame(s)
        results[f"frame_{f}"] = {"keyed": round(k[0], 3), "keyed_expected": want, "noprops": round(n[0], 3), "seq_shows": dec}
        print(f"CHECK frame {f}: keyed={k[0]:.3f} (want {want}) noprops={n[0]:.3f} (want 1) seq shows frame {dec} (want {f})")
        if abs(k[0] - want) > 0.05:
            problems.append(f"frame {f}: keyed props read {k[0]:.3f}, want {want}")
        if abs(n[0] - 1.0) > 0.05:
            problems.append(f"frame {f}: no-props plane read {n[0]:.3f}, want 1.0")
        if dec != f:
            problems.append(f"frame {f}: sequence shows frame {dec}")
    for f in (n_seq // 2, n_seq):
        sc.frame_set(f)
        p = os.path.join(out_dir, f"still_{f:04d}.exr")
        r.filepath = p
        bpy.ops.render.render(write_still=True)
        dec = decode_frame(_sample_exr(p, 1.0))
        results[f"still_{f}"] = {"seq_shows": dec}
        print(f"CHECK still {f}: seq shows frame {dec} (want {f})")
        if dec != f:
            problems.append(f"still {f}: sequence shows frame {dec}")
    results["ok"] = not problems
    results["problems"] = problems
    _write_json(out_dir, "selfcheck", results)
    print(f"CHECK selfcheck: {'ok' if not problems else 'FAIL ' + '; '.join(problems)}")
    if problems:
        raise RuntimeError("lookdev selfcheck failed: " + "; ".join(problems))
    return results


# ---------------------------------------------------------------- tune
def tune_base(scene, material, shots, target_srgb, bands, rounds=4, tol=2.0, damping=0.9, mask_material=None,
              band="body", out_dir="renders/lookdev", percent=50, samples=16, adaptive=0.03):
    """Closed-loop base colour solve: shots are callables shots[i](scene) that place the camera and hero
    (frame_set or direct moves). Each round renders every shot, reads the median of `band` (mask
    rendered once per shot with mask_material), takes the mean over shots and corrects the Principled
    base colour by (lin(target) / lin(mean)) ^ damping, stopping when the max abs error is under tol
    sRGB levels. -> (r, g, b) linear; prints TUNE lines; writes lookdev.json 'tune'."""
    import numpy as np
    os.makedirs(out_dir, exist_ok=True)
    p = material.node_tree.nodes[materials.PRINCIPLED]
    base = np.array(p.inputs["Base Color"].default_value[:3], float)
    target = np.array(target_srgb, float)
    masks = []
    for i, shot in enumerate(shots):
        shot(scene)
        masks.append(stills.render_mask(scene, scene.frame_current, os.path.join(out_dir, f"tune_mask_{i}.png"), mask_material))
    log = []
    for rnd in range(rounds):
        p.inputs["Base Color"].default_value = (*base, 1.0)
        meds = []
        for i, shot in enumerate(shots):
            shot(scene)
            beauty = os.path.join(out_dir, f"tune_{i}.png")
            stills.render_still(scene, scene.frame_current, beauty, percent, samples, adaptive)
            m = stills.measure_regions(beauty, masks[i], bands, tuple(target))
            if band not in m["colour"]:
                raise RuntimeError(f"tune_base: band {band!r} has no pixels in shot {i}")
            meds.append(m["colour"][band]["median"])
            print(f"TUNE {rnd} shot {i}: base={np.round(base, 4).tolist()} {band} {m['colour'][band]['median']}")
        mean = np.mean(meds, axis=0)
        err = mean - target
        log.append({"round": rnd, "base": np.round(base, 4).tolist(), "mean": np.round(mean, 1).tolist(), "err": np.round(err, 1).tolist()})
        print(f"TUNE {rnd} mean over shots: {np.round(mean, 1).tolist()} err {np.round(err, 1).tolist()}")
        if max(abs(err)) < tol:
            break
        ratio = np.array(materials.srgb_to_linear(target)) / np.maximum(np.array(materials.srgb_to_linear(mean)), 1e-4)
        base = np.clip(base * ratio ** damping, 0.0, 1.0)
    p.inputs["Base Color"].default_value = (*base, 1.0)
    out = tuple(round(float(v), 4) for v in base)
    _write_json(out_dir, "tune", {"material": material.name, "band": band, "target": list(target), "rounds": log, "base": list(out)})
    print(f"TUNE base {material.name} = {out}")
    return out


# ---------------------------------------------------------------- turnaround
def turnaround(scene, rig, views, pose_fn, out_path, percent=50, samples=32, dist=0.5, lens=50.0, fstop=4.0,
               height=0.05, adaptive=0.03):
    """Render views [(name, az_deg, elev_deg)] of rig['root'] (camera orbit: az 0 = in front of the
    hero's -Y face, elev up) with a temporary 'lookdev_cam' (lens mm, dist m, focus on the hero at
    `height`), after pose_fn(rig, name) when given, then tile them with contact.py (needs FILM_PYTHON
    with Pillow; without it the frames stay single). -> sheet path or None; writes 'turnaround'."""
    out_path = render_mod.safe_out(out_path)
    out_dir = os.path.dirname(out_path)
    os.makedirs(out_dir, exist_ok=True)
    keep_cam = scene.camera
    cam = render_mod.camera_object(scene, "lookdev_cam", 36.0, lens)
    cam.data.dof.aperture_fstop = float(fstop)
    paths, entries = [], []
    for name, az, elev in views:
        if pose_fn:
            pose_fn(rig, name)
        bpy.context.view_layer.update()
        centre = rig["root"].matrix_world.translation + Vector((0.0, 0.0, float(height)))
        a, e = math.radians(az), math.radians(elev)
        off = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * float(dist)
        cam.location = centre + off
        cam.rotation_euler = (-off).to_track_quat("-Z", "Y").to_euler("XYZ")
        cam.data.dof.focus_distance = off.length
        p = os.path.join(out_dir, f"turn_{name}.png")
        secs = stills.render_still(scene, scene.frame_current, p, percent, samples, adaptive)
        print(f"TURN {name}: {secs:.1f} s -> {p}")
        paths.append(p)
        entries.append({"view": name, "az": az, "elev": elev, "path": p, "seconds_render": round(secs, 2)})
    scene.camera = keep_cam
    sheet = None
    py = os.environ.get("FILM_PYTHON")
    contact = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "contact.py"))
    if py and os.path.exists(contact):
        args = [py, "-B", contact, "--out", out_path, "--cols", str(min(3, len(paths)))]
        args += [f"{p}:{e['view']}" for p, e in zip(paths, entries)]
        proc = subprocess.run(args, capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        if proc.returncode == 0 and os.path.exists(out_path):
            sheet = out_path
            print(f"TURN sheet: {sheet}")
        else:
            print(f"TURN sheet skipped: contact.py failed: {(proc.stderr or proc.stdout).strip()[-300:]}")
    else:
        print("TURN sheet skipped: set FILM_PYTHON (kit venv with Pillow) for contact.py")
    _write_json(out_dir, "turnaround", {"views": entries, "sheet": sheet})
    return sheet


# ---------------------------------------------------------------- CLI
def _split(opts, key):
    return [s for s in str(opts.get(key, "")).split(";") if s]


def _reapply_stored_look(scene):
    look, registry = render_mod.stored_look(scene)
    if look:
        render_mod.apply_look(scene, look, registry)
    return look


def main(argv):
    """Parse the CLI after '--' and dispatch: frames F... | selfcheck | tune <material> | turnaround."""
    if not argv:
        raise SystemExit(__doc__)
    sub, rest = argv[0], argv[1:]
    pos = []
    while rest and not rest[0].startswith("--"):
        pos.append(rest.pop(0))
    opts = stills.parse_cli(rest)
    out = opts.get("out", "renders/lookdev")
    scene = bpy.context.scene
    if sub == "selfcheck":
        selfcheck(out)
        return
    look = _reapply_stored_look(scene)
    presets = look.get("presets") or render_mod.PRESETS
    pct, spp, adaptive, _ = presets.get("stills", render_mod.PRESETS["stills"])
    pct, spp, adaptive = int(opts.get("percent", pct)), int(opts.get("samples", spp)), float(opts.get("adaptive", adaptive))
    if sub == "frames":
        frames = [int(v) for v in pos]
        if not frames:
            raise SystemExit("lookdev frames: give frame numbers")
        world = _num(opts["world"]) if "world" in opts else None
        apply_overrides(scene, _split(opts, "prop"), _split(opts, "mat"), _split(opts, "light"), _split(opts, "grade"), world)
        mask = "mask" in opts
        target = None
        if mask and "target" in opts:
            _, _, target = stills.mask_from_look(look, opts["target"])
        render_frames(scene, frames, out, opts.get("tag", "film"), pct, spp, mask=mask, target_srgb=target, adaptive=adaptive)
    elif sub == "tune":
        if not pos:
            raise SystemExit("lookdev tune: give the material name")
        mat = bpy.data.materials[pos[0]]
        mask_material, bands, target = stills.mask_from_look(look, opts.get("target"))
        if mask_material is None or target is None:
            raise SystemExit("lookdev tune: needs look['mask'] with classes and a target (or --target hex)")
        frames = [int(v) for v in str(opts.get("frames", scene.frame_current)).split(",")]
        shots = [(lambda sc, f=f: sc.frame_set(f)) for f in frames]
        tune_base(scene, mat, shots, target, bands, int(opts.get("rounds", 4)), float(opts.get("tol", 2.0)),
                  mask_material=mask_material, band=opts.get("band", "body"), out_dir=out, percent=pct, samples=spp,
                  adaptive=adaptive)
    elif sub == "turnaround":
        _, registry = render_mod.stored_look(scene)
        root = opts.get("root") or (registry.get("hero_root", ["hero"]))
        root = root if isinstance(root, str) else root[0]
        if root not in scene.objects:
            raise SystemExit(f"lookdev turnaround: root object {root!r} not in the scene (use --root)")
        views = [tuple(v) for v in look.get("turnaround", {}).get("views", DEFAULT_VIEWS)]
        turnaround(scene, {"root": scene.objects[root]}, views, None, os.path.join(out, "turnaround.png"), pct, spp,
                   dist=float(opts.get("dist", 0.5)), lens=float(opts.get("lens", 50.0)), adaptive=adaptive)
    else:
        raise SystemExit(f"lookdev: unknown step {sub!r}")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
