"""hero: build a hero rig from the bpy-free hero spec. Owner: blender-build. Imports bpy.

The spec (API.md, 'Hero spec') lists parts (rounded boxes, capsules,
spheres) with parent, pivot, offset, material role and pass_index, named
expression sets swapped by hide_render, and slides (keyed pivot
translations). Tree: root Empty (location, rotation 'XYZ') -> squash Empty
(scale) -> body mesh -> child parts at their pivots. hero_points.py reads
the same spec, so the checker's silhouette is this mesh.

Part transform: object location = pivot (parent part's local space; world for
the root part); mesh vertices = shape at the origin + offset. A joint rotates
the part object about its pivot: axis 'X' | 'Y' | 'Z' takes a scalar angle
(rad), axis None takes an (rx, ry, rz) Euler in the spec's euler_order. A
slide moves the pivot: location = pivot + sum(delta_s * u_s). Every part is
keyed every frame (rotation; location when it has a slide; hide_render), so
a pose may omit a joint (0), a slide (0) or the expression (the default).
Scales are clamped >= 1e-3; hidden parts use hide_render.
"""
import bpy

from . import geo
from .. import hero_points

MIN_SCALE = 1e-3


def _shape(part):
    """Part spec -> unlinked mesh Object, built at the origin + offset."""
    name, shape = part["name"], part["shape"]
    off = tuple(part.get("offset", (0.0, 0.0, 0.0)))
    if shape == "rbox":
        return geo.rounded_box(name, part["size"], part["r"], part.get("k", 6), centre=off,
                               flat_step=part.get("flat_step"))
    if shape == "capsule":
        a = tuple(x + o for x, o in zip(part["a"], off))
        b = tuple(x + o for x, o in zip(part["b"], off))
        return geo.capsule(name, a, b, part["r"], part.get("seg", 24), part.get("ring", 12))
    if shape == "sphere":
        return geo.capsule(name, off, off, part["r"], part.get("seg", 24), part.get("ring", 12))
    raise ValueError(f"hero: part {name!r} has unknown shape {shape!r} (rbox | capsule | sphere)")


def build_hero(spec, collection, materials, name=None):
    """Build the rig. materials: {role: Material}. -> {'root', 'squash', 'body', 'parts': {name: Object},
    'expressions': {name: [Object]}, 'slides': {name: (Object, delta)}, 'spec': spec}.

    Also returns 'axes' {part: axis}, 'pivots' {part: pivot}, 'part_slides' {part: [(delta, slide)]},
    'default_expression', 'expression_parts' (set of names), for pose_channels / set_pose.
    name: object name of the root Empty (default spec['name'] or 'hero'); the squash Empty is
    '<name>:squash'; parts keep their spec names. Expression parts outside the default set start
    hidden. Raises on an unknown parent, shape or side-name violation (assert_sides)."""
    name = name or spec.get("name", "hero")
    order = spec.get("euler_order", "XYZ")
    materials = materials or {}
    root = geo.empty(name, collection)
    root.rotation_mode = order
    squash = geo.empty(f"{name}:squash", collection, parent=root)
    parts, pivots, axes = {}, {}, {}
    for part in spec["parts"]:
        ob = _shape(part)
        ob.rotation_mode = order
        ob.pass_index = int(part.get("pass_index", 0))
        mat = materials.get(part.get("material"))
        if mat is not None:
            ob.data.materials.append(mat)
        if collection is not None:
            collection.objects.link(ob)
        parts[part["name"]] = ob
        pivots[part["name"]] = tuple(part.get("pivot", (0.0, 0.0, 0.0)))
        axes[part["name"]] = part.get("axis")
    body = None
    for part in spec["parts"]:
        ob = parts[part["name"]]
        parent = part.get("parent")
        if parent is None:
            if body is not None:
                raise ValueError(f"hero: two root parts ({body.name}, {ob.name}); exactly one part has parent None")
            body = ob
            ob.parent = squash
        elif parent in parts:
            ob.parent = parts[parent]
        else:
            raise ValueError(f"hero: part {ob.name!r} names unknown parent {parent!r}")
        ob.location = pivots[part["name"]]
    if body is None:
        raise ValueError("hero: no root part (one part must have parent None)")

    sets = hero_points.expression_sets(spec)
    default = hero_points.default_expression(spec)
    expression_parts = {p for names in sets.values() for p in names}
    for ex, names in sets.items():
        for pname in names:
            if pname not in parts:
                raise ValueError(f"hero: expression {ex!r} names unknown part {pname!r}")
            parts[pname].hide_render = ex != default
    slides, part_slides = {}, {}
    for sname, s in spec.get("slides", {}).items():
        if s["part"] not in parts:
            raise ValueError(f"hero: slide {sname!r} names unknown part {s['part']!r}")
        delta = tuple(s["delta"])
        slides[sname] = (parts[s["part"]], delta)
        part_slides.setdefault(s["part"], []).append((delta, sname))

    rig = {"root": root, "squash": squash, "body": body, "parts": parts,
           "expressions": {ex: [parts[p] for p in names] for ex, names in sets.items()},
           "slides": slides, "spec": spec, "axes": axes, "pivots": pivots, "part_slides": part_slides,
           "default_expression": default, "expression_parts": expression_parts}
    assert_sides(rig)
    return rig


def _joint_euler(rig, pname, value):
    """Joint value (scalar on the part's axis, or an Euler triple) -> (rx, ry, rz)."""
    axis = rig["axes"].get(pname)
    if isinstance(value, (int, float)):
        if axis not in ("X", "Y", "Z"):
            raise ValueError(f"hero: joint {pname!r} has axis {axis!r}; a scalar angle needs 'X', 'Y' or 'Z'")
        e = [0.0, 0.0, 0.0]
        e["XYZ".index(axis)] = float(value)
        return tuple(e)
    if len(value) != 3:
        raise ValueError(f"hero: joint {pname!r} needs an angle or (rx, ry, rz), got {value!r}")
    return tuple(float(v) for v in value)


def _channels(rig, pose):
    """Pose -> [(idb, path, value, interp)]; value is a tuple for vector paths, a bool for hide_render."""
    out = []
    root = pose.get("root", {})
    out.append((rig["root"], "location", tuple(root.get("pos", (0.0, 0.0, 0.0))), "LINEAR"))
    out.append((rig["root"], "rotation_euler", tuple(root.get("euler", (0.0, 0.0, 0.0))), "LINEAR"))
    sq = pose.get("squash", (1.0, 1.0, 1.0))
    out.append((rig["squash"], "scale", tuple(max(float(s), MIN_SCALE) for s in sq), "LINEAR"))
    joints = pose.get("joints", {})
    for pname in joints:
        if pname not in rig["parts"]:
            raise ValueError(f"hero: pose joint {pname!r} is not a part")
    slides = pose.get("slides", {})
    for sname in slides:
        if sname not in rig["slides"]:
            raise ValueError(f"hero: pose slide {sname!r} is not in the spec")
    visible = bool(pose.get("visible", True))
    expression = hero_points.active_expression(rig["spec"], pose)
    # spec part names, not object names: a second hero from the same spec gets renamed objects (body.001)
    shown = set(hero_points.expression_sets(rig["spec"]).get(expression, ())) if expression else set()
    for pname, ob in rig["parts"].items():
        out.append((ob, "rotation_euler", _joint_euler(rig, pname, joints.get(pname, (0.0, 0.0, 0.0))), "LINEAR"))
        if pname in rig["part_slides"]:
            loc = list(rig["pivots"][pname])
            for delta, sname in rig["part_slides"][pname]:
                u = float(slides.get(sname, 0.0))
                for i in range(3):
                    loc[i] += delta[i] * u
            out.append((ob, "location", tuple(loc), "LINEAR"))
        hidden = not visible or (pname in rig["expression_parts"] and pname not in shown)
        out.append((ob, "hide_render", hidden, "CONSTANT"))
    return out


def pose_channels(rig, pose, f, bake):
    """Record one pose into a Bake at frame f: root location/rotation, squash scale, joint rotations,
    slide locations, expression visibility (CONSTANT), visible. Scales clamped >= 1e-3."""
    for idb, path, value, interp in _channels(rig, pose):
        if path == "hide_render":
            bake.hide(idb, f, value)
        else:
            bake.vec(idb, path, f, value)


def set_pose(rig, pose):
    """Apply a pose directly (no keys), for lookdev stills and turnarounds."""
    for idb, path, value, interp in _channels(rig, pose):
        setattr(idb, path, value)


def show_expression(rig, name):
    """hide_render every expression part except the named set's. Spec part names, as _channels: a second
    hero from the same spec has renamed objects (eye_px_happy.001), so an object-name test would hide every
    part."""
    if name not in rig["expressions"]:
        raise ValueError(f"hero: expression {name!r} is not in the spec")
    shown = set(hero_points.expression_sets(rig["spec"]).get(name, ()))
    for pname in rig["expression_parts"]:
        rig["parts"][pname].hide_render = pname not in shown


def _rest_centre(spec, pname):
    """Rest-world centre of a part's mesh: the pivot chain plus the offset (and the capsule midpoint)."""
    parts = {p["name"]: p for p in spec["parts"]}
    c = [0.0, 0.0, 0.0]
    part = parts[pname]
    off = part.get("offset", (0.0, 0.0, 0.0))
    if part["shape"] == "capsule":
        off = tuple(o + (a + b) / 2 for o, a, b in zip(off, part["a"], part["b"]))
    for i in range(3):
        c[i] += off[i]
    while part is not None:
        piv = part.get("pivot", (0.0, 0.0, 0.0))
        for i in range(3):
            c[i] += piv[i]
        part = parts.get(part.get("parent")) if part.get("parent") is not None else None
    return tuple(c)


def assert_sides(rig):
    """Assert every part named *_px has local x > 0 and *_nx x < 0 (the one side convention).
    The test uses the rest-world centre of the part's mesh; 'px' / 'nx' are matched as name tokens
    split on '_' (eye_px_open counts)."""
    spec = rig["spec"]
    for part in spec["parts"]:
        tokens = part["name"].split("_")
        px, nx = "px" in tokens, "nx" in tokens
        if px and nx:
            raise AssertionError(f"hero: part {part['name']!r} is named both _px and _nx")
        if not (px or nx):
            continue
        x = _rest_centre(spec, part["name"])[0]
        if px and not x > 0:
            raise AssertionError(f"hero: part {part['name']!r} is _px but its rest x is {x:.4f}")
        if nx and not x < 0:
            raise AssertionError(f"hero: part {part['name']!r} is _nx but its rest x is {x:.4f}")
    return True
