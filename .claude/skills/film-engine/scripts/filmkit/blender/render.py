"""render: render presets, world, studio, lights, bloom, apply_look. Owner: blender-look. Imports bpy.

Blender 5.2: the compositor is a CompositorNodeTree node group assigned to
scene.compositing_node_group with an interface output socket 'Image'; Glare
settings are input sockets (inputs['Type'].default_value = 'Bloom'); light
ray visibility lives on the light Object (visible_glossy); the OptiX device
is a preference (gpu.py), not saved. Every value (exposure, look, spp,
colours, watts) is an argument or a LOOK dict key (API.md, 'Look constants').
Engine defaults are neutral placeholders.

apply_look stores the LOOK and registry dicts as JSON in scene['film_look']
and scene['film_registry'], so stills.py and lookdev.py re-read them from a
saved .blend (presets, mask classes, target colour) without the project module.
"""
import json
import math
import os

import bpy
from mathutils import Vector

from filmkit.blender import bake as bake_mod, materials

PRESETS = {
    # name: (resolution_percent, samples, adaptive_threshold, denoise)  neutral placeholders
    "preview": (50, 16, 0.05, True),
    "stills": (50, 40, 0.03, True),
    "animatic": (50, 16, 0.05, True),
    "final": (100, 64, 0.01, True),
}
BOUNCES = {"max": 6, "diffuse": 3, "glossy": 3, "transmission": 4, "transparent": 8, "volume": 0}  # placeholders
LOOK_KEY, REGISTRY_KEY = "film_look", "film_registry"


def _collection(scene, name):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in scene.collection.children:
        scene.collection.children.link(c)
    return c


_fcurve = bake_mod.fcurve      # the FCurve animating idb.path, or None (Blender 5 layered actions)


# ---------------------------------------------------------------- render settings
def setup_render(scene, preset="final", presets=None, film=(1920, 1080), fps=30, frames=1, view="AgX",
                 look="None", exposure=0.0, shutter=0.5, persistent=True, bounces=None, clamp_indirect=6.0,
                 out_path=None, denoiser="OPENIMAGEDENOISE", blur_glossy=1.0):
    """Cycles setup from a preset tuple (pct, spp, adaptive, denoise): resolution, fps, range 1..frames,
    motion blur (centred shutter in frames; 0 = off), persistent data, PNG RGB 8-bit, GPU, OIDN on the
    GPU, bounces (dict like BOUNCES), clamps (direct 0, indirect clamp_indirect), caustics off, light
    tree, Filter Glossy blur_glossy (0 = sharp reflections; a look value, placeholder 1.0), view
    transform/look/exposure. out_path sets render.filepath (relative //). -> scene."""
    pct, samples, adaptive, denoise = (presets or PRESETS)[preset]
    r = scene.render
    r.engine = "CYCLES"
    r.resolution_x, r.resolution_y = int(film[0]), int(film[1])
    r.resolution_percentage = int(pct)
    r.fps, r.fps_base = int(fps), 1.0
    scene.frame_start, scene.frame_end = 1, int(frames)
    r.use_motion_blur = shutter > 0
    r.motion_blur_shutter = float(shutter) if shutter > 0 else 0.5
    r.motion_blur_position = "CENTER"
    r.use_persistent_data = bool(persistent)
    r.film_transparent = False
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    r.image_settings.color_depth = "8"
    if out_path:
        r.filepath = out_path

    cy = scene.cycles
    cy.device = "GPU"
    cy.samples = int(samples)
    cy.use_adaptive_sampling = adaptive is not None and adaptive > 0
    cy.adaptive_threshold = float(adaptive or 0.0)
    cy.use_denoising = bool(denoise)
    cy.denoiser = denoiser
    cy.denoising_use_gpu = True
    cy.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    cy.denoising_prefilter = "ACCURATE"
    b = dict(BOUNCES, **(bounces or {}))
    cy.max_bounces = b["max"]
    cy.diffuse_bounces = b["diffuse"]
    cy.glossy_bounces = b["glossy"]
    cy.transmission_bounces = b["transmission"]
    cy.transparent_max_bounces = b["transparent"]
    cy.volume_bounces = b["volume"]
    cy.caustics_reflective = False
    cy.caustics_refractive = False
    cy.blur_glossy = float(blur_glossy)
    cy.sample_clamp_direct = 0.0
    cy.sample_clamp_indirect = float(clamp_indirect)
    cy.use_light_tree = True

    scene.display_settings.display_device = "sRGB"
    vs = scene.view_settings
    vs.view_transform = view
    vs.look = look
    vs.exposure = float(exposure)
    return scene


def add_emission_bloom(scene, threshold=0.15, smoothness=0.5, strength=0.4, size=0.6, quality="High",
                       name="film_bloom"):
    """Compositor group: Emission pass -> Glare(Bloom) -> ADD over the beauty -> group output 'Image'.
    Turns on use_pass_emit (the beauty and the hero never bloom). Idempotent. -> NodeTree."""
    for vl in scene.view_layers:
        vl.use_pass_emit = True
    ng = bpy.data.node_groups.get(name)
    if ng is None:
        ng = bpy.data.node_groups.new(name, "CompositorNodeTree")
        ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        rl = ng.nodes.new("CompositorNodeRLayers")
        rl.location = (-500, 0)
        rl.scene = scene
        g = ng.nodes.new("CompositorNodeGlare")
        g.name = "bloom"
        g.location = (-250, -150)
        g.inputs["Type"].default_value = "Bloom"
        add = ng.nodes.new("ShaderNodeMix")
        add.name = "bloom_add"
        add.data_type = "RGBA"
        add.blend_type = "ADD"
        add.location = (0, 0)
        add.inputs[0].default_value = 1.0
        out = ng.nodes.new("NodeGroupOutput")
        out.location = (250, 0)
        rgba_in = [i for i in add.inputs if i.type == "RGBA"]
        emit = rl.outputs.get("Emission") or rl.outputs.get("Emit")
        if emit is None:
            raise RuntimeError("add_emission_bloom: the Render Layers node has no Emission output")
        ng.links.new(rl.outputs["Image"], rgba_in[0])
        ng.links.new(emit, g.inputs["Image"])
        ng.links.new(g.outputs["Glare"], rgba_in[1])
        ng.links.new([o for o in add.outputs if o.type == "RGBA"][0], out.inputs["Image"])
    g = ng.nodes["bloom"]
    g.inputs["Quality"].default_value = quality
    for k, v in (("Threshold", threshold), ("Smoothness", smoothness), ("Strength", strength), ("Size", size)):
        g.inputs[k].default_value = float(v)
    scene.compositing_node_group = ng
    scene.render.use_compositing = True
    return ng


# ---------------------------------------------------------------- world, studio, lights
def setup_world(scene, light_color, strength=1.0, camera_color=(0.0, 0.0, 0.0), name="film_world"):
    """World that lights with light_color (linear rgb) at strength but shows camera_color to camera
    rays (Is Camera Ray mix). Keeps a node named 'Background' so masks can zero its Strength.
    Idempotent. -> World."""
    w = scene.world or bpy.data.worlds.get(name) or bpy.data.worlds.new(name)
    scene.world = w
    nt = w.node_tree
    bg = nt.nodes.get("Background")
    if bg is None:
        bg = nt.nodes.new("ShaderNodeBackground")
        bg.name = "Background"
    out = next(n for n in nt.nodes if n.type == "OUTPUT_WORLD")
    bg.inputs["Color"].default_value = materials._rgba(light_color)
    bg.inputs["Strength"].default_value = float(strength)
    cam = nt.nodes.get("camera_bg") or nt.nodes.new("ShaderNodeBackground")
    cam.name = "camera_bg"
    cam.inputs["Color"].default_value = materials._rgba(camera_color)
    cam.inputs["Strength"].default_value = 1.0
    lp = nt.nodes.get("camera_ray") or nt.nodes.new("ShaderNodeLightPath")
    lp.name = "camera_ray"
    mix = nt.nodes.get("camera_mix") or nt.nodes.new("ShaderNodeMixShader")
    mix.name = "camera_mix"
    bg.location, cam.location, lp.location, mix.location, out.location = (-300, 0), (-300, -150), (-300, 250), (-80, 0), (140, 0)
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(bg.outputs["Background"], mix.inputs[1])
    nt.links.new(cam.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return w


def _cyc_mesh(name, floor_z, wall_y, cove_r, top, half_x, mat):
    prof = [(-half_x, floor_z), (wall_y - cove_r, floor_z)]
    for i in range(1, 16):
        a = math.radians(90.0 * i / 16)
        prof.append((wall_y - cove_r + cove_r * math.sin(a), floor_z + cove_r - cove_r * math.cos(a)))
    prof += [(wall_y, floor_z + cove_r), (wall_y, top)]
    verts = [(x, y, z) for x in (-half_x, half_x) for y, z in prof]
    n = len(prof)
    faces = [(i, n + i, n + i + 1, i + 1) for i in range(n - 1)]   # normals up / south
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    me.shade_smooth()
    me.materials.append(mat)
    return me


def make_cyc(scene, floor_z, material, wall_y=9.0, cove_r=4.0, top=10.0, half_x=25.0, name="studio_cyc"):
    """Floor at floor_z + quarter-circle cove + back wall at wall_y up to top, extruded along X over
    +-half_x. material: a Material, or a dict {'base', 'roughness', 'specular'} for '<name>_mat'.
    Rebuilds the mesh when any size changed. Idempotent. -> Object."""
    if not isinstance(material, bpy.types.Material):
        mat, _ = materials._material(f"{name}_mat")
        materials.set_principled(mat, material)
        material = mat
    params = [float(v) for v in (floor_z, wall_y, cove_r, top, half_x)]
    ob = scene.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, _cyc_mesh(name, *params, material))
        _collection(scene, "Studio").objects.link(ob)
    elif list(ob.get("cyc_params", [])) != params:
        old = ob.data
        ob.data = _cyc_mesh(name, *params, material)
        if old.users == 0:
            bpy.data.meshes.remove(old)
    if ob.data.materials[0] is not material:
        ob.data.materials[0] = material
    ob["cyc_params"] = params
    return ob


def _set_light(ob, spec):
    loc, aim = Vector(spec["loc"]), Vector(spec["aim"])
    ld = ob.data
    ld.shape = "SQUARE"
    ld.size = float(spec["size"])
    ld.color = tuple(float(c) for c in spec["color"][:3])
    ob.location = loc
    ob.rotation_mode = "XYZ"
    ob.rotation_euler = (aim - loc).to_track_quat("-Z", "Y").to_euler("XYZ")
    ob.visible_glossy = bool(spec.get("glossy", False))
    ob.visible_camera = False
    ob.hide_render = False
    set_light_power(ob, spec["watts"])


def setup_lights(scene, lights, follow=None, rig_name="light_rig"):
    """lights: {name: {'loc': (x,y,z) relative to the rig, 'aim': (x,y,z), 'size': m, 'watts': W,
    'color': (r,g,b), 'glossy': bool}}. AREA lights parented to an Empty; visible_camera False;
    follow: Object to COPY_LOCATION (no Z). Stores base power on the light data. A rig light not in
    `lights` is hidden; a missing one is added. Idempotent. -> {'rig': obj, name: obj}."""
    coll = _collection(scene, "Lights")
    rig = scene.objects.get(rig_name)
    if rig is None:
        rig = bpy.data.objects.new(rig_name, None)
        rig.empty_display_size = 0.3
        rig.rotation_mode = "XYZ"
        coll.objects.link(rig)
    out = {"rig": rig}
    for ob in rig.children:
        if ob.type == "LIGHT" and ob.name not in lights:
            ob.hide_render = True
    for name, spec in lights.items():
        ob = scene.objects.get(name)
        if ob is None:
            ld = bpy.data.lights.new(name, "AREA")
            ob = bpy.data.objects.new(name, ld)
            coll.objects.link(ob)
            ob.parent = rig
        _set_light(ob, spec)
        out[name] = ob
    if follow is not None:
        con = rig.constraints.get("follow") or rig.constraints.new("COPY_LOCATION")
        con.name = "follow"
        con.target = follow
        con.use_z = False
    return out


def set_light_power(light_ob, watts):
    """Set power, rescaling keyed energy (values and handles) by new/old base power when keys exist."""
    ld = light_ob.data
    old = ld.get("look_power")
    fc = _fcurve(ld, "energy")
    if fc is not None and old:
        k = float(watts) / float(old)
        for kp in fc.keyframe_points:
            kp.co.y *= k
            kp.handle_left.y *= k
            kp.handle_right.y *= k
        fc.update()
    elif fc is None:
        ld.energy = float(watts)
    ld["look_power"] = float(watts)
    return light_ob


# ---------------------------------------------------------------- rig tracking (pure math)
def _wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def _gauss(vals, sigma):
    if sigma <= 0:
        return list(vals)
    h = int(3 * sigma)
    w = [math.exp(-0.5 * (i / sigma) ** 2) for i in range(-h, h + 1)]
    n = len(vals)
    return [sum(vals[min(max(i + j, 0), n - 1)] * w[j + h] for j in range(-h, h + 1)) / sum(w) for i in range(n)]


def key_yaw_of(loc):
    """Rig-relative key light location (x, y, z) -> its yaw in hero terms (rad): atan2(x, -y)."""
    return math.atan2(float(loc[0]), -float(loc[1]))


def light_rig_track(hero_yaws, cam_rz, key_yaw, full_deg=25.0, symmetry=4, sigma=4.0, gain_sigma=2.0,
                    gain_clamp=(0.6, 1.6)):
    """Per frame: the hero face nearest the camera (symmetry-fold of yaw - cam_rz), rig yaw following
    it within full_deg then easing to the camera axis at half a sector; unwrap; gaussian smoothing
    (sigma frames); key gain = cos(key_yaw) / cos(key angle to that face), clamped and smoothed.
    hero_yaws, cam_rz, key_yaw in radians. -> (rig_rz[], key_gain[]). Pure math (no bpy)."""
    sector = 2 * math.pi / symmetry
    full = math.radians(full_deg)
    raw, faces = [], []
    for yaw, cz in zip(hero_yaws, cam_rz):
        phi = _wrap(yaw - cz)
        phi = (phi + sector / 2) % sector - sector / 2
        u = min(max((abs(phi) - full) / max(sector / 2 - full, 1e-9), 0.0), 1.0)
        rz = cz + phi + (-key_yaw - phi) * u * u * (3 - 2 * u)
        if raw:
            rz = raw[-1] + _wrap(rz - raw[-1])
        raw.append(rz)
        faces.append(cz + phi)
    rz = _gauss(raw, sigma)
    gain = []
    for r, face in zip(rz, faces):
        delta = _wrap(key_yaw + r - face)
        g = math.cos(key_yaw) / max(math.cos(delta), 1e-3)
        gain.append(min(max(g, gain_clamp[0]), gain_clamp[1]))
    return rz, _gauss(gain, gain_sigma)


# ---------------------------------------------------------------- camera, look, save
def camera_object(scene, name="camera", sensor_w=36.0, lens=50.0):
    """Camera with sensor_fit HORIZONTAL, sensor_width, rotation_mode 'XYZ', dof on, clip 0.01..80.
    Reused by name. Sets scene.camera. -> Object."""
    cam = scene.objects.get(name)
    if cam is None:
        cd = bpy.data.cameras.new(name)
        cam = bpy.data.objects.new(name, cd)
        _collection(scene, "Camera").objects.link(cam)
    cd = cam.data
    cd.sensor_fit = "HORIZONTAL"
    cd.sensor_width = float(sensor_w)
    cd.lens = float(lens)
    cd.shift_x = cd.shift_y = 0.0
    cd.clip_start, cd.clip_end = 0.01, 80.0
    cd.dof.use_dof = True
    cam.rotation_mode = "XYZ"
    scene.camera = cam
    return cam


def _material_values(m, vals):
    """Apply a LOOK material dict to one material by its structure: screen materials ('ui_strength_node')
    take spec/rough/strength, power-faded materials take 'specular' through set_power_specular, the rest
    are Principled values."""
    nt = m.node_tree
    vals = dict(vals)
    if "ui_strength_node" in m:
        if "strength" in vals:
            nt.nodes[m["ui_strength_node"]].inputs[1].default_value = float(vals.pop("strength"))
        if "rough" in vals:
            vals["roughness"] = vals.pop("rough")
        if "spec" in vals:
            vals["specular"] = vals.pop("spec")
    if "specular" in vals and nt.nodes.get("look_spec_power") is not None:
        materials.set_power_specular(m, vals.pop("specular"), ramp=tuple(vals.pop("ramp", (0.3, 0.9))))
    materials.set_principled(m, vals)


def apply_look(scene, look, registry):
    """Re-apply a LOOK dict in memory to a built scene: view/exposure/gamma, render preset
    (look['preset'], default 'final', with look['presets']) and shutter, world, cyc, lights (add new,
    hide retired, rescale keyed power), materials by role, screen grades, glow highlights, bloom.
    registry: {role: [object or material names]}: a role of look['materials'] lists its materials
    ('screen' and 'side' included); 'glow_highlights' lists materials that get look['glow_highlights'];
    'cyc', 'light_rig', 'camera', 'light_follow' name single objects. look['grades'] is {object name:
    (h, s, v)} on that object's active material. Stores both dicts as JSON on the scene. Call at the end
    of a scene build and after every .blend load. Idempotent. -> scene."""
    registry = registry or {}
    view = look.get("view", {})
    r = scene.render
    setup_render(scene, look.get("preset", "final"), look.get("presets"), film=(r.resolution_x, r.resolution_y),
                 fps=r.fps, frames=scene.frame_end, view=view.get("transform", "AgX"), look=view.get("look", "None"),
                 exposure=view.get("exposure", 0.0), shutter=look.get("shutter", 0.5), persistent=r.use_persistent_data,
                 bounces=look.get("bounces"), clamp_indirect=look.get("clamp_indirect", 6.0),
                 blur_glossy=look.get("blur_glossy", 1.0))
    scene.view_settings.gamma = float(view.get("gamma", 1.0))
    if "world" in look:
        w = look["world"]
        setup_world(scene, w["light"], w.get("strength", 1.0), w.get("camera", (0.0, 0.0, 0.0)))
    if "cyc" in look:
        c = dict(look["cyc"])
        name = registry.get("cyc", ["studio_cyc"])
        name = name if isinstance(name, str) else name[0]
        make_cyc(scene, c.pop("floor_z"), c.pop("material"), name=name, **c)
    if "lights" in look:
        follow = registry.get("light_follow")
        follow = scene.objects.get(follow if isinstance(follow, str) else follow[0]) if follow else None
        rig = registry.get("light_rig", ["light_rig"])
        setup_lights(scene, look["lights"], follow=follow, rig_name=rig if isinstance(rig, str) else rig[0])
    for role, vals in look.get("materials", {}).items():
        for name in registry.get(role, ()):
            m = bpy.data.materials.get(name)
            if m is not None:
                _material_values(m, vals)
    for ob_name, grade in look.get("grades", {}).items():
        ob = scene.objects.get(ob_name)
        if ob is not None and ob.active_material is not None:
            materials.set_grade(ob.active_material, grade)
    if "glow_highlights" in look:
        gh = look["glow_highlights"]
        for name in registry.get("glow_highlights", ()):
            m = bpy.data.materials.get(name)
            if m is not None:
                materials.set_glow_highlights(m, gh.get("lo", 0.1), gh.get("hi", 0.6))
    if "bloom" in look:
        add_emission_bloom(scene, **look["bloom"])
    scene[LOOK_KEY] = json.dumps(look, sort_keys=True)
    scene[REGISTRY_KEY] = json.dumps(registry, sort_keys=True)
    return scene


def stored_look(scene):
    """-> (look, registry) dicts stored by apply_look on this scene ({} when absent)."""
    return json.loads(scene.get(LOOK_KEY, "{}")), json.loads(scene.get(REGISTRY_KEY, "{}"))


def save_blend(path):
    """frame_set(1), save with relative paths (no .blend1 backup), verify no absolute image path remains.
    -> {'objects': n, 'non_relative': [paths]}."""
    bpy.context.scene.frame_set(1)
    bpy.context.preferences.filepaths.save_version = 0      # the second save below would leave a .blend1
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(path), relative_remap=True)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile()
    bad = [im.filepath for im in bpy.data.images if im.filepath and not im.filepath.startswith("//")]
    return {"objects": len(bpy.data.objects), "non_relative": bad}
