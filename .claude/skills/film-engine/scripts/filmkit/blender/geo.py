"""geo: exact meshes and rect-driven objects. Owner: blender-build. Imports bpy, bmesh, mathutils.

Rounded boxes carry exact custom split normals and no modifiers. Rect
objects take a layout.Layout for ui_to_world and uv_of, so a UI rect becomes
a box whose top face samples that rect of the atlas (u = x/ui_w, v = 1 - y/ui_h);
sides reuse the top corner UVs (edge pixels, never a smear). Every builder
returns an unlinked or collection-linked Object and sets no material values.

Units: metres. Angles in degrees where the name says _deg, else radians.
Every size, radius and count is an argument; the defaults are neutral placeholders.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector


# ---------------------------------------------------------------- mesh helpers
def _mesh_object(name, verts, faces, smooth=False, recalc=True):
    """Mesh + unlinked Object from vertex and face lists. recalc: outward normals via bmesh."""
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    if recalc:
        fix_normals(me)
    if smooth:
        me.shade_smooth()
    return bpy.data.objects.new(name, me)


def fix_normals(mesh):
    """Recalculate outward normals of a closed hand-built mesh."""
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def _axis_positions(h, r, k, step=None):
    """Grid positions on one axis of a box with half size h and edge radius r: k rounding steps
    following r * tan(theta) (even arc division) and, with step, a flat-face grid of that pitch."""
    inner = max(h - r, 0.0)
    band = [inner + r * math.tan(math.radians(45.0 * i / k)) for i in range(k + 1)]
    n = max(1, int(round(2 * inner / step))) if (step and inner > 1e-9) else 1
    flat = [-inner + 2 * inner * i / n for i in range(1, n)]
    neg = [-p for p in reversed(band)]
    if inner <= 1e-9:
        return neg + band[1:]
    return neg + flat + band


# ---------------------------------------------------------------- primitives
def rounded_box(name, size, r, k=6, centre=(0.0, 0.0, 0.0), flat_step=None):
    """Exact rounded-edge box: size (sx, sy, sz), edge radius r, k arc steps per quarter.
    flat_step: optional grid step on flat faces (None = none). -> Object (unlinked).

    Vertices of a box grid are clamped to the inner box (half - r) and pushed out by r along the
    clamp direction, so edges and corners are exact arcs; the push direction is the exact normal,
    set as custom split normals. r is limited to the smallest half size."""
    half = [s / 2 for s in size]
    r = min(r, *half)
    inner = [h - r for h in half]
    pos = [_axis_positions(half[a], r, k, flat_step) for a in range(3)]
    verts, index, faces = [], {}, []

    def vid(p):
        key = tuple(round(c, 7) for c in p)
        if key not in index:
            index[key] = len(verts)
            verts.append(p)
        return index[key]

    for a in range(3):
        b, c = [x for x in range(3) if x != a]
        for s in (-1, 1):
            for i in range(len(pos[b]) - 1):
                for j in range(len(pos[c]) - 1):
                    quad = []
                    for di, dj in ((0, 0), (1, 0), (1, 1), (0, 1)):
                        p = [0.0, 0.0, 0.0]
                        p[a] = s * half[a]
                        p[b] = pos[b][i + di]
                        p[c] = pos[c][j + dj]
                        quad.append(vid(tuple(p)))
                    cyclic = (b - a) % 3 == 1          # (b, c, a) right-handed for a cyclic triple
                    faces.append(quad if (s > 0) == cyclic else quad[::-1])

    out, normals = [], []
    for p in verts:
        q = [min(max(p[i], -inner[i]), inner[i]) for i in range(3)]
        n = Vector([p[i] - q[i] for i in range(3)]).normalized()
        out.append(tuple(q[i] + n[i] * r + centre[i] for i in range(3)))
        normals.append(n)

    me = bpy.data.meshes.new(name)
    me.from_pydata(out, [], faces)
    me.update()
    me.shade_smooth()
    me.normals_split_custom_set_from_vertices(normals)
    return bpy.data.objects.new(name, me)


def capsule(name, a, b, r, seg=24, ring=12):
    """Capsule from local point a to b, radius r. -> Object (unlinked).

    seg vertices around the axis; ring latitude rows per hemisphere cap. a == b gives a sphere.
    Smooth shaded, outward normals recalculated."""
    a, b = Vector(a), Vector(b)
    d = b - a
    length = d.length
    axis = d / length if length > 1e-9 else Vector((0.0, 0.0, 1.0))
    helper = Vector((1.0, 0.0, 0.0)) if abs(axis.x) < 0.9 else Vector((0.0, 1.0, 0.0))
    u = helper.cross(axis).normalized()
    v = axis.cross(u)
    centre = (a + b) / 2
    rows = []                                             # (z along the axis from centre, ring radius)
    for i in range(ring + 1):                             # cap a: pole -> equator
        phi = -math.pi / 2 + (math.pi / 2) * i / ring
        rows.append((-length / 2 + r * math.sin(phi), r * math.cos(phi)))
    for j in range(ring + 1):                             # cap b: equator -> pole
        phi = (math.pi / 2) * j / ring
        rows.append((length / 2 + r * math.sin(phi), r * math.cos(phi)))
    if length <= 1e-9:
        del rows[ring + 1]                                # the two equators coincide: keep one
    verts, starts, poles = [], [], []
    for z, rr in rows:
        starts.append(len(verts))
        poles.append(rr < 1e-12)
        if rr < 1e-12:
            verts.append(tuple(centre + axis * z))
        else:
            for s in range(seg):
                th = 2 * math.pi * s / seg
                verts.append(tuple(centre + u * (rr * math.cos(th)) + v * (rr * math.sin(th)) + axis * z))
    faces = []
    for i in range(len(rows) - 1):
        s0, s1 = starts[i], starts[i + 1]
        for s in range(seg):
            sn = (s + 1) % seg
            if poles[i]:
                faces.append((s0, s1 + s, s1 + sn))
            elif poles[i + 1]:
                faces.append((s0 + s, s0 + sn, s1))
            else:
                faces.append((s0 + s, s0 + sn, s1 + sn, s1 + s))
    return _mesh_object(name, verts, faces, smooth=True)


def sphere(name, r, seg=24, ring=12):
    """UV sphere of radius r at the local origin. -> Object (unlinked)."""
    return capsule(name, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), r, seg, ring)


_PLANES = {"XZ": lambda p: p, "XY": lambda p: (p[0], p[2], p[1]), "YZ": lambda p: (p[1], p[0], p[2])}


def arc_tube(name, radius, tube, a0_deg, a1_deg, flat_y=1.0, seg=24, ring=12, cap=4, plane="XZ"):
    """Thick arc with round caps in the given plane; cross-section squashed by flat_y. -> Object.

    Arc centre at the origin, angles in degrees from the plane's first axis toward its second.
    plane 'XZ' | 'XY' | 'YZ'; flat_y scales the cross-section along the plane normal (1 = round).
    seg points along the arc, ring vertices around the tube, cap rings per end cap."""
    if plane not in _PLANES:
        raise ValueError(f"arc_tube: plane must be one of {sorted(_PLANES)}, got {plane!r}")
    pts, tangents = [], []
    for i in range(seg + 1):
        ang = math.radians(a0_deg + (a1_deg - a0_deg) * i / seg)
        pts.append(Vector((radius * math.cos(ang), 0.0, radius * math.sin(ang))))
        tangents.append(Vector((-math.sin(ang), 0.0, math.cos(ang))) * (1 if a1_deg > a0_deg else -1))
    rings = []                                            # (centre, radial direction in the plane, radius)
    t0, t1 = tangents[0], tangents[-1]
    n0, n1 = pts[0].normalized(), pts[-1].normalized()
    for c in range(cap, 0, -1):
        phi = math.radians(90.0 * c / cap)
        rings.append((pts[0] - t0 * tube * math.sin(phi), n0, tube * math.cos(phi)))
    rings += [(p, p.normalized(), tube) for p in pts]
    for c in range(1, cap + 1):
        phi = math.radians(90.0 * c / cap)
        rings.append((pts[-1] + t1 * tube * math.sin(phi), n1, tube * math.cos(phi)))

    verts, faces = [], []
    bvec = Vector((0.0, 1.0, 0.0))
    for centre, n, rr in rings:
        for j in range(ring):
            u = 2 * math.pi * j / ring
            off = n * (rr * math.cos(u)) + bvec * (rr * math.sin(u) * flat_y)
            verts.append(tuple(centre + off))
    nr = len(rings)
    for i in range(nr - 1):
        for j in range(ring):
            a, b = i * ring + j, i * ring + (j + 1) % ring
            faces.append((a, b, b + ring, a + ring))
    start = len(verts)
    verts.append(tuple(pts[0] - t0 * tube))
    verts.append(tuple(pts[-1] + t1 * tube))
    last = (nr - 1) * ring
    for j in range(ring):
        faces.append((start, (j + 1) % ring, j))
        faces.append((start + 1, last + j, last + (j + 1) % ring))
    swap = _PLANES[plane]
    return _mesh_object(name, [swap(p) for p in verts], faces, smooth=True)


# ---------------------------------------------------------------- rect-driven objects
def box_from_rect(name, rect, z0, z1, top_mat, side_mat, collection, layout, uv_rect=None,
                  origin=(0.0, 0.0, 0.0), bevel=0.0, unit_uv=False):
    """Box over UI rect from z0 to z1 (world). Top face UV = uv_rect (default rect) of the atlas, or
    0..1 when unit_uv. Material slot 0 top, 1 sides. origin: world pivot the mesh is built around
    (the object sits at origin). bevel > 0 adds a 2-segment bevel modifier with hardened normals.

    rect = (x, y, w, h) UI px. layout supplies ui_to_world(x, y) -> (X, Y) and uv_of(x, y) -> (u, v).
    Sides and bottom reuse the top corner UVs (vertex index % 4). A None material leaves an empty
    slot. collection None leaves the object unlinked."""
    x, y, w, h = rect
    ux, uy, uw, uh = uv_rect or rect
    corners = [(x, y + h), (x + w, y + h), (x + w, y), (x, y)]            # SW, SE, NE, NW
    uvc = [(ux, uy + uh), (ux + uw, uy + uh), (ux + uw, uy), (ux, uy)]
    ox, oy, oz = origin
    top = [layout.ui_to_world(cx, cy) for cx, cy in corners]
    verts = [(vx - ox, vy - oy, z1 - oz) for vx, vy in top] + [(vx - ox, vy - oy, z0 - oz) for vx, vy in top]
    faces = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    uvl = me.uv_layers.new(name="UVMap")
    unit = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index % 4
            uvl.data[li].uv = unit[vi] if unit_uv else layout.uv_of(*uvc[vi])
        poly.material_index = 0 if poly.index == 0 else 1
    me.materials.append(top_mat)
    me.materials.append(side_mat)
    me.update()
    ob = bpy.data.objects.new(name, me)
    if bevel > 0:
        bv = ob.modifiers.new("bevel", "BEVEL")
        bv.width, bv.segments, bv.harden_normals = bevel, 2, True
        bv.limit_method = "ANGLE"
    if collection is not None:
        collection.objects.link(ob)
    ob.location = origin
    return ob


def plane_from_rect(name, rect, z, mat, collection, layout, origin=(0.0, 0.0, 0.0), thickness=0.0002):
    """Flat quad on a UI rect at height z, UV 0..1 over its own image (image-sequence screens).
    Built as a box of the given thickness under z, both slots mat, no bevel."""
    return box_from_rect(name, rect, z - thickness, z, mat, mat, collection, layout,
                         origin=origin, bevel=0.0, unit_uv=True)


# ---------------------------------------------------------------- outlines and flat parts
def _prism_lists(outline_xy, z_top, z_bot):
    """-> (verts, faces) of a closed prism over a counter-clockwise outline."""
    n = len(outline_xy)
    verts = [(x, y, z_top) for x, y in outline_xy] + [(x, y, z_bot) for x, y in outline_xy]
    faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    faces += [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)]
    return verts, faces


def prism(name, outline_xy, z_top, z_bot=0.0):
    """Extrude a 2D outline [(x, y)] into a closed prism. -> Object (unlinked)."""
    verts, faces = _prism_lists(outline_xy, z_top, z_bot)
    return _mesh_object(name, verts, faces)


def stadium(w, h, n_cap=12, inset=0.0):
    """-> outline [(x, y)] of a pill shape w x h centred on 0 (sprite meshes), counter-clockwise.
    inset shrinks the pill by that much on every side."""
    w, h = w - 2 * inset, h - 2 * inset
    r = h / 2
    pts = []
    for i in range(n_cap + 1):                            # right cap, bottom to top
        a = -math.pi / 2 + math.pi * i / n_cap
        pts.append((w / 2 - r + r * math.cos(a), r * math.sin(a)))
    for i in range(n_cap + 1):                            # left cap, top to bottom
        a = math.pi / 2 + math.pi * i / n_cap
        pts.append((-w / 2 + r + r * math.cos(a), r * math.sin(a)))
    return pts


def annulus(r, width, n=96):
    """-> (verts, faces) of a flat ring of radius r and stroke width, normals up, in the XY plane."""
    verts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        for rr in (r - width / 2, r + width / 2):
            verts.append((rr * math.cos(a), rr * math.sin(a), 0.0))
    faces = [(2 * i, 2 * ((i + 1) % n), 2 * ((i + 1) % n) + 1, 2 * i + 1) for i in range(n)]
    return verts, faces


def ring_growing(name, r0, r1, width, n=96):
    """Flat ring whose radius grows r0 -> r1 by a shape key 'grow' at constant stroke width. -> Object.
    Key 'grow' value u gives radius r0 + u * (r1 - r0). Unlinked."""
    verts, faces = annulus(r0, width, n)
    ob = _mesh_object(name, verts, faces, recalc=False)
    ob.shape_key_add(name="basis", from_mix=False)
    shape_key_from_points(ob, "grow", annulus(r1, width, n)[0])
    return ob


def shard_meshes(n_shapes, size, thick, rnd):
    """-> [Mesh] random star-shaped shards about `size` across and `thick` thick; rnd is a seeded
    callable -> [0, 1). Shape v has 4 + v % 3 corners; corner angles jitter by up to 0.6 of a step and
    radii span 0.55..1.15 of size / 2 (placeholder distribution)."""
    meshes = []
    for v in range(n_shapes):
        k = 4 + v % 3
        pts = []
        for i in range(k):
            a = 2 * math.pi * (i + 0.6 * rnd()) / k
            rr = size / 2 * (0.55 + 0.6 * rnd())
            pts.append((rr * math.cos(a), rr * math.sin(a)))
        verts, faces = _prism_lists(pts, thick / 2, -thick / 2)
        me = bpy.data.meshes.new(f"shard_{v}")
        me.from_pydata(verts, [], faces)
        fix_normals(me)
        meshes.append(me)
    return meshes


# ---------------------------------------------------------------- objects, parenting, shape keys
def empty(name, collection, location=(0.0, 0.0, 0.0), parent=None):
    """Empty object linked to collection (None = unlinked). -> Object."""
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_type = "PLAIN_AXES"
    ob.empty_display_size = 0.05
    if collection is not None:
        collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    ob.location = location
    return ob


def _as_matrix(m):
    """Matrix from a Matrix, a 3-tuple translation, a 4x4 nested list or a flat list of 16."""
    if hasattr(m, "inverted"):
        return m
    seq = list(m)
    if len(seq) == 3:
        return Matrix.Translation(seq)
    if len(seq) == 16:
        return Matrix([seq[0:4], seq[4:8], seq[8:12], seq[12:16]])
    if len(seq) == 4:
        return Matrix([list(row) for row in seq])
    raise ValueError(f"parent_keep_world: cannot read a matrix from {m!r}")


def parent_keep_world(child, parent, parent_rest_world):
    """Parent with matrix_parent_inverse = parent_rest_world.inverted(): the child's keyed location
    stays in rest-world coordinates while it inherits the parent's later motion.
    parent_rest_world: Matrix, or a translation (x, y, z), or 16 floats / 4 rows."""
    child.parent = parent
    child.matrix_parent_inverse = _as_matrix(parent_rest_world).inverted()


def shape_key_from_points(ob, name, points):
    """Add a shape key with the given vertex positions (same count as the mesh). -> ShapeKey.
    Adds the basis key first when the mesh has none."""
    me = ob.data
    if len(points) != len(me.vertices):
        raise ValueError(f"shape_key_from_points: {ob.name} has {len(me.vertices)} vertices, got {len(points)} points")
    if me.shape_keys is None:
        ob.shape_key_add(name="basis", from_mix=False)
    kb = ob.shape_key_add(name=name, from_mix=False)
    for i, co in enumerate(points):
        kb.data[i].co = co
    return kb


def curl_card(name, image_w, image_h, nx, ny, curl_fn):
    """Flat card (hinge at its bottom edge) with one shape key per entry of curl_fn: {key_name: angle_fn}.
    angle_fn(v) -> bend angle (rad) of the card tangent at height share v (0 hinge, 1 top edge).
    -> (Object, {key_name: ShapeKey}), unlinked.

    The card is image_w x image_h metres, origin at the middle of its bottom edge, lying toward +Y in
    the XY plane, UV (0..1, 0..1) over its own image, nx x ny quads, smooth. Each key integrates
    (cos a, sin a) along the rest height from the hinge, so a row at height y lands at the arc point;
    the hinge rotation itself is the object's rotation."""
    w, h = image_w, image_h
    xs = [-w / 2 + w * i / nx for i in range(nx + 1)]
    ys = [h * j / ny for j in range(ny + 1)]
    verts = [(x, y, 0.0) for y in ys for x in xs]
    faces = [(j * (nx + 1) + i, j * (nx + 1) + i + 1, (j + 1) * (nx + 1) + i + 1, (j + 1) * (nx + 1) + i)
             for j in range(ny) for i in range(nx)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    uvl = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            vx, vy, _ = verts[me.loops[li].vertex_index]
            uvl.data[li].uv = ((vx + w / 2) / w, vy / h)
    me.update()
    me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    ob.shape_key_add(name="flat", from_mix=False)
    keys = {}
    sub = 32                                              # midpoint samples per row
    for key_name, angle_fn in curl_fn.items():
        prof, py, pz = [(0.0, 0.0)], 0.0, 0.0
        for j in range(1, ny + 1):
            y0, y1 = ys[j - 1], ys[j]
            ds = (y1 - y0) / sub
            for s in range(sub):
                a = angle_fn((y0 + (s + 0.5) * ds) / h)
                py += math.cos(a) * ds
                pz += math.sin(a) * ds
            prof.append((py, pz))
        pts = [(xs[i], py, pz) for (py, pz) in prof for i in range(nx + 1)]
        keys[key_name] = shape_key_from_points(ob, key_name, pts)
    return ob, keys


def collection(name, scene=None):
    """-> the collection, created and linked to the scene when missing."""
    scene = scene or bpy.context.scene
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in scene.collection.children:
        scene.collection.children.link(c)
    return c
