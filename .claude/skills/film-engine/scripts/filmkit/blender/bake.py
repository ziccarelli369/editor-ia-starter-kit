"""bake: one key per frame per channel, written in bulk to Blender 5 layered actions.
Owner: blender-build. Imports bpy.

Transforms, custom properties ('["prop"]'), nested paths ('dof.focus_distance',
'key_blocks["grow"].value') are LINEAR; hide_render is CONSTANT; a channel
whose values never change is assigned once and gets no keys. Scales are
clamped to >= 1e-3 by the caller (hide with hide_render, never scale 0).
Angles should arrive continuous (unwrapped): LINEAR keys interpolate them. write() unwraps every
rotation_euler channel once more (ease.unwrap_series), so a look_at rotation that wraps at +-pi when
the view crosses due south never spins the camera the long way inside one frame (motion blur).

Frames are 1-based: put(..., f=1, ...) is t = 0. Keys land on frames 1..n.
"""
from bpy_extras import anim_utils

from .. import ease

LINEAR = 1
CONSTANT = 0


class Bake:
    """Collect values, then write F-curves in bulk through anim_utils.action_get_channelbag_for_slot.

    One record per (ID block, data path, array index): a list of n floats, one per frame, plus the
    interpolation. write() assigns the first value, skips constant channels, and keys the rest with
    keyframe_points.add + foreach_set('co' / 'interpolation').
    """

    def __init__(self, n_frames):
        if n_frames < 1:
            raise ValueError(f"bake: n_frames must be >= 1, got {n_frames}")
        self.n = int(n_frames)
        self.ch = {}

    def put(self, idb, path, f, value, index=-1, interp=LINEAR):
        """Record value for data path (and array index) of ID block idb at frame f (1-based)."""
        if not 1 <= f <= self.n:
            raise ValueError(f"bake: frame {f} outside 1..{self.n} for {idb.name} {path}")
        key = (idb.as_pointer(), path, index)
        rec = self.ch.get(key)
        if rec is None:
            rec = self.ch[key] = [idb, [None] * self.n, interp]
        rec[1][f - 1] = float(value)

    def vec(self, idb, path, f, values, interp=LINEAR):
        """put() each component of values at index 0..n-1."""
        for i, c in enumerate(values):
            self.put(idb, path, f, c, i, interp)

    def hide(self, ob, f, hidden):
        """put('hide_render', CONSTANT)."""
        self.put(ob, "hide_render", f, 1.0 if hidden else 0.0, interp=CONSTANT)

    def prop(self, idb, name, f, value):
        """put('["name"]') for a custom property (creates the property on first use)."""
        ensure_prop(idb, name, value)
        self.put(idb, f'["{name}"]', f, value)

    @staticmethod
    def _assign(idb, path, index, v):
        """Set one value on idb without keying it (first value of every channel)."""
        if path.startswith('["'):
            idb[path[2:-2]] = v
            return
        owner, attr = idb, path
        if "." in path:
            head, attr = path.rsplit(".", 1)
            owner = idb.path_resolve(head)
        if index >= 0:
            getattr(owner, attr)[index] = v
        elif attr.startswith("hide"):
            setattr(owner, attr, bool(v > 0.5))
        else:
            setattr(owner, attr, v)

    def write(self):
        """Assign constants, key the rest (keyframe_points.add + foreach_set co/interpolation).
        Raises RuntimeError when a channel misses a frame. -> (keyed_channels, constant_channels)."""
        keyed = constant = 0
        for (_, path, index), (idb, vals, interp) in self.ch.items():
            if any(v is None for v in vals):
                missing = [i + 1 for i, v in enumerate(vals) if v is None]
                raise RuntimeError(f"bake: {idb.name} {path}[{index}] misses frames {missing[:8]}"
                                   f"{'...' if len(missing) > 8 else ''}")
            if path.endswith("rotation_euler"):
                vals = ease.unwrap_series(vals)
            self._assign(idb, path, index, vals[0])
            if max(vals) - min(vals) < 1e-9:
                constant += 1
                continue
            idb.keyframe_insert(path, index=index, frame=1)
            fc = fcurve(idb, path, max(index, 0))
            if fc is None:
                raise RuntimeError(f"bake: no F-curve for {idb.name} {path}[{index}] after keyframe_insert")
            kp = fc.keyframe_points
            kp.add(self.n - len(kp))
            co = [0.0] * (2 * self.n)
            co[0::2] = [float(i + 1) for i in range(self.n)]
            co[1::2] = vals
            kp.foreach_set("co", co)
            kp.foreach_set("interpolation", [interp] * self.n)
            fc.update()
            keyed += 1
        return keyed, constant


def fcurve(idb, path, index=0):
    """-> the FCurve for path on idb's action slot, or None (Blender 5 layered actions)."""
    ad = getattr(idb, "animation_data", None)
    if ad is None or ad.action is None:
        return None
    bag = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    if bag is None:
        return None
    return bag.fcurves.find(path, index=index)


def ensure_prop(idb, name, default=1.0):
    """Create custom property name on idb with default when missing (needed before keying it)."""
    if idb.get(name) is None:
        idb[name] = float(default)
    return idb[name]
