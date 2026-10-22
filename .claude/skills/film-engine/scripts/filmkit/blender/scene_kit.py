"""scene_kit: what a project scene.py calls to assemble the .blend. Owner: blender-look. Imports bpy.

A project scene.py: bootstraps sys.path, imports its timeline/motion/look
modules, then: load_timeline -> build_slabs/tiles/stacks/screens/sprites ->
build the hero (blender/hero) -> render.camera_object -> bake_states over
every frame -> render.apply_look -> render.save_blend. Object names are
stable and prefixed: panel:<name>, tile:<id>, stack:<stack>:<id>,
screen:<name>, sprite:<name>, camera, light_rig. Z offsets and thicknesses
are arguments (project values). Children are parented with
geo.parent_keep_world, so state functions speak rest-world coordinates
while a slab falls; every built object carries ob['rest_world'] (16 floats,
row-major) and the ui_glow / ui_power properties at 1.
"""
import sys
sys.dont_write_bytecode = True
import os

import bpy
from mathutils import Matrix

from filmkit import timebase
from filmkit import layout as layout_mod
from filmkit.blender import bake as bake_mod
from filmkit.blender import geo, materials

LAYOUT_KEYS = ("panels", "buttons", "screens", "stacks", "sprites", "points", "nested", "owners")


def bootstrap(project_dir, engine_dir=None):
    """Insert project_dir and the engine scripts folder into sys.path; set dont_write_bytecode.
    engine_dir defaults to env FILM_ENGINE or <project>/../../.claude/skills/film-engine/scripts.
    -> (project_dir, engine_dir) absolute."""
    sys.dont_write_bytecode = True
    project_dir = os.path.abspath(project_dir)
    engine_dir = os.path.abspath(engine_dir or os.environ.get("FILM_ENGINE") or os.path.normpath(
        os.path.join(project_dir, "..", "..", ".claude", "skills", "film-engine", "scripts")))
    for p in (engine_dir, project_dir):
        if p not in sys.path:
            sys.path.insert(0, p)
    return project_dir, engine_dir


def _tup(v):
    """Lists from JSON -> tuples, recursively (dict values too)."""
    if isinstance(v, list):
        return tuple(_tup(x) for x in v)
    if isinstance(v, dict):
        return {k: _tup(x) for k, x in v.items()}
    return v


def load_timeline(project_dir):
    """-> (doc, layout): build/timeline.json (timebase.load_timeline, hash verified) and a
    layout.Layout rebuilt from doc['layout'] (ui, px_to_m and every table it carries)."""
    doc = timebase.load_timeline(os.path.join(project_dir, "build", "timeline.json"))
    L = doc["layout"]
    tables = {k: _tup(L[k]) for k in LAYOUT_KEYS if k in L}
    return doc, layout_mod.Layout(tuple(L["ui"]), float(L["px_to_m"]), **tables)


def clear_scene(scene):
    """Remove every object, then every orphan mesh, light, camera, material, image, node group and
    collection (factory start made safe). The scene, its world and its view layer stay."""
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for block in (bpy.data.meshes, bpy.data.lights, bpy.data.cameras, bpy.data.materials, bpy.data.images,
                  bpy.data.node_groups):
        for x in list(block):
            if block is bpy.data.images and x.type != "IMAGE":
                continue                      # Render Result, Viewer Node
            if x.users == 0 or block is bpy.data.materials or block is bpy.data.node_groups:
                block.remove(x)
    return scene


def _finish(ob, origin, with_props=True):
    ob.rotation_mode = "XYZ"
    ob["rest_world"] = [float(v) for row in Matrix.Translation(origin) for v in row]
    if with_props:
        materials.set_props(ob, ui_glow=1.0, ui_power=1.0)
    return ob


def rest_world(ob):
    """-> the rest matrix stored by the builders on ob (Matrix)."""
    vals = list(ob["rest_world"])
    return Matrix([vals[i:i + 4] for i in range(0, 16, 4)])


def _centre(layout, rect):
    x, y, w, h = rect
    return layout.ui_to_world(x + w / 2.0, y + h / 2.0)


def build_slabs(layout, z0, z1, top_mats, side_mat, collection, bevel=0.002, pivot="top_centre"):
    """One box per layout.panels rect, z0..z1 (world). top_mats: {panel: Material} or one Material (a
    'base' atlas for panels that host moving blocks). pivot 'top_centre' puts the origin at the rect
    centre at z1 ('origin' leaves it at the world origin). -> {name: Object} with ob['rest_world']."""
    out = {}
    for name, rect in layout.panels.items():
        mat = top_mats[name] if isinstance(top_mats, dict) else top_mats
        cx, cy = _centre(layout, rect)
        origin = (cx, cy, z1) if pivot == "top_centre" else (0.0, 0.0, 0.0)
        ob = geo.box_from_rect(f"panel:{name}", rect, z0, z1, mat, side_mat, collection, layout, origin=origin,
                               bevel=bevel)
        out[name] = _finish(ob, origin)
    return out


def _parent(ob, slabs, owner):
    if owner not in slabs:
        raise KeyError(f"scene_kit: owner panel {owner!r} of {ob.name} has no slab")
    geo.parent_keep_world(ob, slabs[owner], rest_world(slabs[owner]))


def build_tiles(layout, z0, z1, mat, side_mat, collection, slabs, bevel=0.0008):
    """One raised box per layout.buttons rect (origin at its rect centre, z 0), parented (keep world)
    to its owner slab. -> {id: Object}."""
    out = {}
    for bid, rect in layout.buttons.items():
        cx, cy = _centre(layout, rect)
        ob = geo.box_from_rect(f"tile:{bid}", rect, z0, z1, mat, side_mat, collection, layout,
                               origin=(cx, cy, 0.0), bevel=bevel)
        _finish(ob, (cx, cy, 0.0))
        _parent(ob, slabs, layout.owner_of(bid))
        out[bid] = ob
    return out


def build_stacks(layout, z0, z1, mat, side_mat, collection, slabs, bevel=0.0):
    """One block per stack item at its final top (the texture source rect), origin at the block's NW
    corner (z 0), parented to the owner slab. -> {(stack, id): Object}."""
    out = {}
    for name, s in layout.stacks.items():
        x, _, w, _ = s["rect"]
        tops = layout_mod.stack_final_tops(s["items"], s["y0"], s["row_h"])
        owner = layout.owner_of(name)
        for item in s["items"]:
            iid, rows = item[0], item[1]
            rect = (x, tops[iid], w, rows * s["row_h"])
            ox, oy = layout.ui_to_world(rect[0], rect[1])
            ob = geo.box_from_rect(f"stack:{name}:{iid}", rect, z0, z1, mat, side_mat, collection, layout,
                                   origin=(ox, oy, 0.0), bevel=bevel)
            _finish(ob, (ox, oy, 0.0))
            _parent(ob, slabs, owner)
            out[(name, iid)] = ob
    return out


def build_screens(layout, z, sequences, collection, slabs, strength=1.0, spec=0.1, rough=0.32, grades=None):
    """One image-sequence plane per layout.screens rect at height z, material 'screen:<name>'.
    sequences: {name: (first_png_path, n_frames)} (every screen needs one). grades: {name: (h, s, v)}
    camera-ray grades. -> {name: Object}."""
    out = {}
    for name, (rect, _flat) in layout.screens.items():
        if name not in sequences:
            raise KeyError(f"scene_kit.build_screens: no sequence for screen {name!r}")
        first, n = sequences[name]
        mat = materials.make_screen_material(f"screen:{name}", first, strength, sequence=True, frames=n, spec=spec,
                                             rough=rough, grade=(grades or {}).get(name))
        cx, cy = _centre(layout, rect)
        ob = geo.plane_from_rect(f"screen:{name}", rect, z, mat, collection, layout, origin=(cx, cy, 0.0))
        _finish(ob, (cx, cy, 0.0))
        _parent(ob, slabs, layout.owner_of(name))
        out[name] = ob
    return out


def build_sprite(name, png_path, size_ui, layout, z, collection, mat=None, outline="stadium", inset_px=0.6,
                 thick=0.0025, n_cap=10):
    """Sprite mesh cut to its outline ('stadium' | 'rect') of size_ui (w, h) UI px, inset by inset_px,
    `thick` m thick, textured with the RGBA sprite (a screen material 'sprite:<name>' clipped to the
    image unless mat is given); the back face reads mirrored so it is the right way round. Origin at
    the sprite centre at height z. -> Object (linked to collection)."""
    px = layout.px_to_m
    W, H = size_ui[0] * px, size_ui[1] * px
    inset = inset_px * px
    if outline == "stadium":
        ring = geo.stadium(W - 2 * inset, H - 2 * inset, n_cap)
    else:
        hw, hh = W / 2 - inset, H / 2 - inset
        ring = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    ob = geo.prism(f"sprite:{name}", ring, thick / 2, -thick / 2)
    me = ob.data
    uvl = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        side = poly.normal.z
        for li in poly.loop_indices:
            x, y, _ = me.vertices[me.loops[li].vertex_index].co
            u, v = (x + W / 2) / W, (y + H / 2) / H
            uvl.data[li].uv = (u, v) if side > 0.5 else ((1.0 - u, v) if side < -0.5 else (0.0, 0.0))
    me.materials.clear()
    me.materials.append(mat or materials.make_screen_material(f"sprite:{name}", png_path, extension="CLIP"))
    if ob.name not in collection.objects:
        collection.objects.link(ob)
    ob.location = (0.0, 0.0, z)
    return _finish(ob, (0.0, 0.0, z))


def bake_states(bake, n_frames, fps, channels_fn):
    """For f in 1..n: channels_fn(time(f)) -> [(idb, path, value, index, interp)]; bake.put each.
    -> bake (call bake.write() after)."""
    for f in range(1, int(n_frames) + 1):
        t = timebase.time(f, fps)
        for idb, path, value, index, interp in channels_fn(t):
            bake.put(idb, path, f, value, index, interp)
    return bake


def camera_channels(cam_ob, state):
    """Camera dict {pos, rot (rad XYZ), lens, focus_distance, fstop} -> [(idb, path, value, index,
    interp)]: location, rotation_euler, lens, dof.focus_distance, dof.aperture_fstop (skipped when None),
    all LINEAR."""
    L = bake_mod.LINEAR
    out = [(cam_ob, "location", float(v), i, L) for i, v in enumerate(state["pos"])]
    out += [(cam_ob, "rotation_euler", float(v), i, L) for i, v in enumerate(state["rot"])]
    cd = cam_ob.data
    out.append((cd, "lens", float(state["lens"]), -1, L))
    if "focus_distance" in state:
        out.append((cd, "dof.focus_distance", float(state["focus_distance"]), -1, L))
    if state.get("fstop") is not None:          # None = no aperture track: the camera data keeps its own
        out.append((cd, "dof.aperture_fstop", float(state["fstop"]), -1, L))
    return out


def object_channels(ob, state):
    """Generic object state {'pos', 'euler', 'scale', 'visible', 'props': {name: v}} -> channel tuples
    (scale clamped >= 1e-3, visibility CONSTANT on hide_render, props as '["name"]'). Absent keys
    produce no channel."""
    L, C = bake_mod.LINEAR, bake_mod.CONSTANT
    out = []
    if "pos" in state:
        out += [(ob, "location", float(v), i, L) for i, v in enumerate(state["pos"])]
    if "euler" in state:
        out += [(ob, "rotation_euler", float(v), i, L) for i, v in enumerate(state["euler"])]
    if "scale" in state:
        out += [(ob, "scale", max(float(v), 1e-3), i, L) for i, v in enumerate(state["scale"])]
    if "visible" in state:
        out.append((ob, "hide_render", 0.0 if state["visible"] else 1.0, -1, C))
    for name, v in (state.get("props") or {}).items():
        out.append((ob, f'["{name}"]', float(v), -1, L))
    return out


def summary(scene, bake_result):
    """Print the build summary: frames, keyed/constant channels (bake.write() result), objects,
    non-relative image paths. -> dict."""
    keyed, constant = bake_result
    bad = [im.filepath for im in bpy.data.images if im.filepath and not im.filepath.startswith("//")]
    info = {"frames": scene.frame_end, "keyed": int(keyed), "constant": int(constant),
            "objects": len(bpy.data.objects), "non_relative": bad}
    print(f"scene: {info['frames']} frames, {keyed} keyed channels, {constant} constant channels, "
          f"{info['objects']} objects; non-relative image paths: {bad or 'none'}")
    return info
