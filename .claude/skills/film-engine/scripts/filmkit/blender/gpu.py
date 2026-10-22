"""gpu.py: render on the GPU with OptiX. Owner: blender-build.

Pass it on every headless Blender call, before the render flag or the next -P,
with --python-exit-code 1 right after -b:
  blender -b --python-exit-code 1 film.blend -P gpu.py -a
  blender -b --python-exit-code 1 --factory-startup -P gpu.py -P scene.py

The compute device is a user preference, not part of the .blend, so a
background Blender starts on the CPU unless this runs. It sets the Cycles
preference to KIND, enables only devices of that type, sets every scene to
GPU and repeats the scene part in a persistent load_post handler. It raises
when no device of that type exists: never a silent CPU fallback. The raise
stops Blender only with --python-exit-code 1 (exit 1, nothing after it runs);
without the flag Blender exits 0 and runs the next -P and -a on the CPU.
Env CYCLES_DEVICE=CUDA|HIP|METAL picks another type (fallback only).
"""
import sys
sys.dont_write_bytecode = True
import os

import bpy
from bpy.app.handlers import persistent

KIND = os.environ.get("CYCLES_DEVICE", "OPTIX")


def enable_gpu(kind=KIND):
    """Set the Cycles compute device preference to kind and enable its devices. -> [device names]."""
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = kind
    prefs.get_devices()
    used = []
    for d in prefs.devices:
        d.use = d.type == kind
        if d.use:
            used.append(d.name)
    if not used:
        raise RuntimeError(f"gpu.py: no {kind} device found")
    return used


@persistent
def _scenes_to_gpu(*_):
    for s in bpy.data.scenes:
        s.cycles.device = "GPU"


_used = enable_gpu()
_scenes_to_gpu()
if _scenes_to_gpu not in bpy.app.handlers.load_post:
    bpy.app.handlers.load_post.append(_scenes_to_gpu)
print(f"gpu.py: {KIND} on {', '.join(_used)}; {len(bpy.data.scenes)} scene(s) set to GPU")
