"""hero_points: surface point cloud of a hero spec, posed. Owner: motion. Standard library only.

The hero spec is bpy-free data (API.md, 'Hero spec'). The Blender builder
(blender/hero.py) and this module read the same dict, so the silhouette the
checker measures is the mesh the render shows. Points lie on the real outer
surface (rounded-box corners pushed out along the 7 octant directions), never
on a padding box. Sides are named by local axis: _px (+X), _nx (-X).

A pose dict: {'root': {'pos': (x,y,z), 'euler': (rx,ry,rz)}, 'squash': (sx,sy,sz),
'joints': {part: angle | (rx,ry,rz)}, 'slides': {slide: 0..1}, 'expression': name,
'visible': bool}.

Transform chain (the one blender/hero.py builds): root Empty (pos, euler XYZ)
-> squash Empty (scale) -> parts at their pivots (parent-local), joint rotation
about the part's axis, mesh offset from the pivot. A part's local point p lands at
  world = root_T + root_R . (S * (T_part + R_part . p))
where (R_part, T_part) = part_transforms()[name] live in the squash frame.
"""
import math

from . import vec as V

_AXES = ((1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, 0, 1), (0, 1, 1), (1, 1, 1))
_OCT = {}
for _sx in (-1, 1):
    for _sy in (-1, 1):
        for _sz in (-1, 1):
            _OCT[(_sx, _sy, _sz)] = [V.norm((_sx * a, _sy * b, _sz * c)) for a, b, c in _AXES]
_SPHERE26 = [V.norm((x, y, z)) for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1) if (x, y, z) != (0, 0, 0)]
_IDENT = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
_REST = {"root": {"pos": (0.0, 0.0, 0.0), "euler": (0.0, 0.0, 0.0)}, "squash": (1.0, 1.0, 1.0),
         "joints": {}, "slides": {}, "expression": None, "visible": True}


def rbox_points(centre, half, r):
    """Rounded box: corners of the inner box (half - r) pushed out by r along the 7 octant directions.
    -> 56 points (local)."""
    r = min(r, half[0], half[1], half[2])
    out = []
    for s, ds in _OCT.items():
        q = (centre[0] + s[0] * (half[0] - r), centre[1] + s[1] * (half[1] - r), centre[2] + s[2] * (half[2] - r))
        out += [(q[0] + r * d[0], q[1] + r * d[1], q[2] + r * d[2]) for d in ds]
    return out


def _perp_basis(axis):
    """Unit axis -> two unit vectors perpendicular to it."""
    helper = (0.0, 0.0, 1.0) if abs(axis[2]) < 0.9 else (1.0, 0.0, 0.0)
    e1 = V.norm(V.cross(axis, helper))
    return e1, V.cross(axis, e1)


def capsule_points(a, b, r, n_ring=8, n_cap=3):
    """Capsule from a to b with radius r -> ring points around the axis plus cap points.
    Rings of n_ring at a and b; each cap: the tip plus n_cap - 1 rings between the tip and the end ring."""
    axis = V.norm(V.sub(b, a))
    if axis == (0.0, 0.0, 0.0):
        return sphere_points(a, r)
    e1, e2 = _perp_basis(axis)
    out = []
    for end, sign in ((a, -1.0), (b, 1.0)):
        for j in range(n_cap):
            phi = (math.pi / 2) * j / n_cap               # 0 = the end ring, -> the tip
            rr, h = r * math.cos(phi), r * math.sin(phi)
            c = V.add(end, V.mul(axis, sign * h))
            for i in range(n_ring):
                th = 2 * math.pi * i / n_ring
                out.append(V.add(c, V.add(V.mul(e1, rr * math.cos(th)), V.mul(e2, rr * math.sin(th)))))
        out.append(V.add(end, V.mul(axis, sign * r)))
    return out


def sphere_points(c, r, n=26):
    """Sphere -> n points spread over the surface (octants plus axes for n = 26; a Fibonacci spiral otherwise)."""
    if n == 26:
        dirs = _SPHERE26
    else:
        ga = math.pi * (3.0 - math.sqrt(5.0))
        dirs = []
        for i in range(n):
            z = 1.0 - 2.0 * (i + 0.5) / n
            rr = math.sqrt(max(0.0, 1.0 - z * z))
            dirs.append((rr * math.cos(ga * i), rr * math.sin(ga * i), z))
    return [V.add(c, V.mul(d, r)) for d in dirs]


def part_points(part):
    """Part spec dict -> local surface points of its shape ('rbox' | 'capsule' | 'sphere'), offset applied."""
    off = tuple(part.get("offset") or (0.0, 0.0, 0.0))
    shape = part["shape"]
    if shape == "rbox":
        sx, sy, sz = part["size"]
        return rbox_points(off, (sx / 2.0, sy / 2.0, sz / 2.0), part.get("r", 0.0))
    if shape == "capsule":
        return capsule_points(V.add(part["a"], off), V.add(part["b"], off), part["r"])
    if shape == "sphere":
        return sphere_points(off, part["r"])
    raise ValueError(f"part {part.get('name')!r}: unknown shape {shape!r}")


def _joint_rot(part, value):
    if value is None:
        return _IDENT
    if isinstance(value, (int, float)):
        axis = part.get("axis")
        if axis == "X":
            return V.rot_x(value)
        if axis == "Y":
            return V.rot_y(value)
        if axis == "Z":
            return V.rot_z(value)
        raise ValueError(f"part {part['name']!r} has no axis: give (rx, ry, rz)")
    return V.rot_xyz(*value)


def root_frame(pose):
    """-> (R_root, T_root, S): the root rotation (Euler XYZ), position and squash scale of a pose."""
    root = pose.get("root") or {}
    pos = tuple(root.get("pos") or (0.0, 0.0, 0.0))
    eul = tuple(root.get("euler") or (0.0, 0.0, 0.0))
    S = tuple(pose.get("squash") or (1.0, 1.0, 1.0))
    return V.rot_xyz(*eul), pos, S


def part_transforms(spec, pose):
    """Walk the transform tree. -> {part_name: (R, T)} rotation and translation of each part's
    mesh origin in the squash frame, applying joints and slides parent-first (root and squash are
    applied by root_frame; see the module docstring)."""
    parts = {p["name"]: p for p in spec["parts"]}
    joints = pose.get("joints") or {}
    slides = pose.get("slides") or {}
    shift = {}
    for name, sl in (spec.get("slides") or {}).items():
        v = slides.get(name, 0.0)
        if v:
            shift[sl["part"]] = V.add(shift.get(sl["part"], (0.0, 0.0, 0.0)), V.mul(sl["delta"], v))
    out = {}

    def solve(name):
        if name in out:
            return out[name]
        part = parts[name]
        parent = part.get("parent")
        Rp, Tp = solve(parent) if parent else (_IDENT, (0.0, 0.0, 0.0))
        pivot = V.add(tuple(part.get("pivot") or (0.0, 0.0, 0.0)), shift.get(name, (0.0, 0.0, 0.0)))
        R = V.mat_mul(Rp, _joint_rot(part, joints.get(name)))
        T = V.add(V.mat_vec(Rp, pivot), Tp)
        out[name] = (R, T)
        return out[name]

    for name in parts:
        solve(name)
    return out


def expression_sets(spec):
    """-> {expression: [part names]}: spec['expressions'] in order, plus every part's 'expression' tag
    appended to its set. blender/hero.py builds its rig from this, so both readers agree."""
    sets = {k: list(v) for k, v in (spec.get("expressions") or {}).items()}
    for part in spec["parts"]:
        tag = part.get("expression")
        if tag is not None and part["name"] not in sets.setdefault(tag, []):
            sets[tag].append(part["name"])
    return sets


def default_expression(spec):
    """-> spec['default_expression'], else the first expression set, else None."""
    sets = expression_sets(spec)
    return spec.get("default_expression") or (next(iter(sets)) if sets else None)


def active_expression(spec, pose):
    """-> the expression a pose shows: pose['expression'] when the key is present (None or '' = no set
    shown), else default_expression(spec). Raises ValueError on a name that is not an expression set."""
    if "expression" not in pose:
        return default_expression(spec)
    name = pose["expression"]
    if name and name not in expression_sets(spec):
        raise ValueError(f"hero: pose expression {name!r} is not in the spec")
    return name


def _active_parts(spec, pose, parts=None):
    sets = expression_sets(spec)
    expr = active_expression(spec, pose)
    shown = set(sets.get(expr, [])) if expr else set()
    swapped = {p for names in sets.values() for p in names}
    for part in spec["parts"]:
        if parts is not None and part["name"] not in parts:
            continue
        if part["name"] in swapped and part["name"] not in shown:
            continue
        yield part


def _to_world(R_root, T_root, S, q):
    return V.add(T_root, V.mat_vec(R_root, (q[0] * S[0], q[1] * S[1], q[2] * S[2])))


def hero_points(spec, pose, parts=None):
    """-> [world points] of every visible part (or only `parts`), posed. Empty when pose['visible'] is False."""
    if not pose.get("visible", True):
        return []
    R_root, T_root, S = root_frame(pose)
    tr = part_transforms(spec, pose)
    out = []
    for part in _active_parts(spec, pose, parts):
        R, T = tr[part["name"]]
        for p in part_points(part):
            out.append(_to_world(R_root, T_root, S, V.transform(R, T, p)))
    return out


def _local_block(part):
    """-> (centre, half, R) of a part's shape in its own frame (offset applied)."""
    off = tuple(part.get("offset") or (0.0, 0.0, 0.0))
    if part["shape"] == "rbox":
        sx, sy, sz = part["size"]
        return off, (sx / 2.0, sy / 2.0, sz / 2.0), _IDENT
    if part["shape"] == "sphere":
        return off, (part["r"],) * 3, _IDENT
    a, b = V.add(part["a"], off), V.add(part["b"], off)
    axis = V.sub(b, a)
    L = V.length(axis)
    if L < 1e-12:
        return a, (part["r"],) * 3, _IDENT
    ax = V.mul(axis, 1.0 / L)
    e1, e2 = _perp_basis(ax)
    R = ((ax[0], e1[0], e2[0]), (ax[1], e1[1], e2[1]), (ax[2], e1[2], e2[2]))
    return V.lerp3(a, b, 0.5), (L / 2.0 + part["r"], part["r"], part["r"]), R


def hero_blocks(spec, pose):
    """-> [(centre, half, R)] oriented boxes of every visible part for ray occlusion tests.
    Under a non-uniform squash the half sizes are scaled along each box axis and the frame re-normalised
    (an approximation; exact at squash (1, 1, 1))."""
    if not pose.get("visible", True):
        return []
    R_root, T_root, S = root_frame(pose)
    tr = part_transforms(spec, pose)
    out = []
    for part in _active_parts(spec, pose):
        R, T = tr[part["name"]]
        c, half, Rl = _local_block(part)
        Rq = V.mat_mul(R, Rl)
        centre = _to_world(R_root, T_root, S, V.transform(R, T, c))
        cols, hw = [], []
        for i in range(3):
            col = (Rq[0][i] * S[0], Rq[1][i] * S[1], Rq[2][i] * S[2])
            n = V.length(col)
            cols.append(V.mat_vec(R_root, V.mul(col, 1.0 / n)))
            hw.append(half[i] * n)
        Rw = tuple(tuple(cols[j][i] for j in range(3)) for i in range(3))
        out.append((centre, tuple(hw), Rw))
    return out


def cylinder_points(centre, r, h, n=12):
    """Yaw-free bound: a vertical cylinder of radius r and height h around centre (for shots that set the yaw).
    -> 2n points, rings at z = centre.z and centre.z + h."""
    return [(centre[0] + r * math.cos(2 * math.pi * k / n), centre[1] + r * math.sin(2 * math.pi * k / n), centre[2] + z)
            for k in range(n) for z in (0.0, h)]


def silhouette(points, cam, film=(1920, 1080), sensor_w=36.0):
    """Project points through cam (pos, target, lens, optional heading). -> {'width', 'height' (frame
    fractions), 'margin' (min edge distance as a frame fraction; -1 if any point is behind the camera),
    'cx', 'cy' (ndc)}."""
    from . import camera as C
    if not points:
        return {"width": 0.0, "height": 0.0, "margin": -1.0, "cx": 0.0, "cy": 0.0}
    xs, ys, margin = [], [], 1e9
    hd = cam.get("heading")
    for X in points:
        nx, ny, z = C.project(cam["pos"], cam["target"], cam["lens"], X, film, sensor_w, hd)
        if z <= 0:
            margin = -1.0
            continue
        xs.append(nx)
        ys.append(ny)
        margin = min(margin, (1 - abs(nx)) / 2, (1 - abs(ny)) / 2)
    if not xs:
        return {"width": 0.0, "height": 0.0, "margin": -1.0, "cx": 0.0, "cy": 0.0}
    return {"width": (max(xs) - min(xs)) / 2, "height": (max(ys) - min(ys)) / 2, "margin": margin,
            "cx": (max(xs) + min(xs)) / 2, "cy": (max(ys) + min(ys)) / 2}


def extent_width(spec):
    """-> rest width (m) of the hero across local X (every part, rest pose), for scale sanity checks."""
    tr = part_transforms(spec, _REST)
    xs = [V.transform(tr[p["name"]][0], tr[p["name"]][1], q)[0] for p in spec["parts"] for q in part_points(p)]
    return max(xs) - min(xs)
