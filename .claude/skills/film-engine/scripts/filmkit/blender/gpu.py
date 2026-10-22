"""gpu.py: pick the GPU for Cycles and guard the render path. Owner: blender-build.

Pass it on every headless Blender call, before the render flag or the next -P,
with --python-exit-code 1 right after -b:
  blender -b --python-exit-code 1 film.blend -P gpu.py -a
  blender -b --python-exit-code 1 --factory-startup -P gpu.py -P scene.py

The compute device is a user preference, not part of the .blend, so a
background Blender starts on the CPU unless this runs. CYCLES_DEVICE unset:
the first kind with a device, in the order OPTIX, CUDA, HIP, METAL, ONEAPI;
only that kind's devices are enabled (an iGPU of another kind stays off).
CYCLES_DEVICE=<kind> forces that kind and raises when it has no device.
CYCLES_DEVICE=CPU is the one way to render on the CPU: every scene goes to
CPU and a loud warning prints. No GPU and no explicit CPU raises; the raise
stops Blender only with --python-exit-code 1 (without the flag Blender exits
0 and runs the next -P and -a on the CPU). The scene device is set again in
a persistent load_post handler.

The render guard: before any render (a render_init handler, which fires for
write_still, animation and -a), bpy.path.abspath(scene.render.filepath) must
be absolute, carry a drive on Windows and not sit at a filesystem or drive
root (filmkit.outpath.root_problem); otherwise Blender exits 1 before a
pixel is written. A raise inside a handler does not stop a render in
Blender 5.2; sys.exit does (proven on 5.2.2 for write_still and -a).
"""
import sys
sys.dont_write_bytecode = True
import os

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))

import bpy
from bpy.app.handlers import persistent

from filmkit import outpath

KINDS = ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI")
KIND = os.environ.get("CYCLES_DEVICE") or None
DEVICE = "CPU" if KIND == "CPU" else "GPU"


def devices_of(prefs, kind):
    """-> [device names] of one Cycles compute kind on this machine ([] when this build lacks it)."""
    try:
        prefs.compute_device_type = kind
    except TypeError:
        return []
    prefs.get_devices()
    return [d.name for d in prefs.devices if d.type == kind]


def enable_gpu(kind=None):
    """Set the Cycles compute device preference to kind (None: the first of KINDS with a device) and
    enable only its devices. -> (kind, [device names]); raises when none."""
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for k in ([kind] if kind else KINDS):
        names = devices_of(prefs, k)
        if names:
            for d in prefs.devices:
                d.use = d.type == k
            return k, names
    raise RuntimeError(f"gpu.py: no {kind or '/'.join(KINDS)} device found; CYCLES_DEVICE=CPU is the explicit, slow opt-in")


@persistent
def _scenes_to_device(*_):
    for s in bpy.data.scenes:
        s.cycles.device = DEVICE


@persistent
def _guard_render_path(scene, *_):
    why = outpath.root_problem(bpy.path.abspath(scene.render.filepath))
    if why:
        print(f"gpu.py: RENDER REFUSED: {why}; give an absolute path inside the project", file=sys.stderr, flush=True)
        sys.exit(1)


if KIND == "CPU":
    print("gpu.py: WARNING CYCLES_DEVICE=CPU: every scene renders on the CPU, many times slower than a GPU", flush=True)
    _kind, _used = "CPU", ["CPU"]
else:
    _kind, _used = enable_gpu(KIND)
_scenes_to_device()
for _handlers, _fn in ((bpy.app.handlers.load_post, _scenes_to_device), (bpy.app.handlers.render_init, _guard_render_path)):
    if _fn not in _handlers:
        _handlers.append(_fn)
print(f"gpu.py: {_kind} on {', '.join(_used)}; {len(bpy.data.scenes)} scene(s) set to {DEVICE}")
