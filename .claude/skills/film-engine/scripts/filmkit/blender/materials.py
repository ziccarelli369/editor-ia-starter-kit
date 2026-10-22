"""materials: node-tree builders driven by arguments and object properties. Owner: blender-look. Imports bpy.

Blender 5.2 facts baked in: no Material.use_nodes; a new material already has
'Principled BSDF' + 'Material Output'; Principled sockets 'Specular IOR Level',
'Coat Weight', 'Emission Color'; Attribute(OBJECT) outputs 'Color', 'Vector',
'Factor', 'Alpha' (Alpha 0 when the property is missing); ShaderNodeMix FLOAT
inputs [0] factor, [2] A, [3] B; RGBA sockets chosen by .type; Hue/Saturation
factor socket is 'Factor'. Every builder is idempotent: a second call with the
same name updates the values. No colour or level is hard-coded here; the
defaults below are neutral placeholders a project overrides.

Object properties `ui_glow` (1 rest) and `ui_power` (1 on, 0 black) drive
emission; a missing property reads as 1.0. Node names starting `ui_` and
`look_` are the handles the set_* updaters find; keep them.
"""
import math
import os

import bpy

PRINCIPLED = "Principled BSDF"
PRINCIPLED_KEYS = {    # LOOK material dict key -> Principled socket
    "base": "Base Color", "roughness": "Roughness", "specular": "Specular IOR Level",
    "coat": "Coat Weight", "coat_roughness": "Coat Roughness", "metallic": "Metallic", "ior": "IOR",
    "emission": "Emission Color", "emission_strength": "Emission Strength",
}
AXES = {"+X": (1, 0, 0), "-X": (-1, 0, 0), "+Y": (0, 1, 0), "-Y": (0, -1, 0), "+Z": (0, 0, 1), "-Z": (0, 0, -1)}


# ---------------------------------------------------------------- helpers
def _material(name):
    """-> (Material, created) by name; a new one keeps Blender's default Principled tree."""
    m = bpy.data.materials.get(name)
    if m is None:
        return bpy.data.materials.new(name), True
    return m, False


def _rgba(c):
    c = tuple(float(v) for v in c)
    return c if len(c) == 4 else (*c, 1.0)


def _rgba_sockets(node, direction="inputs"):
    return [s for s in getattr(node, direction) if s.type == "RGBA"]


def srgb8(v):
    """Linear 0..1 -> sRGB 8-bit int (round half up), the Standard view at exposure 0."""
    v = max(0.0, min(1.0, float(v)))
    s = v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
    return int(math.floor(s * 255.0 + 0.5))


def srgb_to_linear(c):
    """sRGB (r, g, b) 0..255 or a hex string -> linear (r, g, b) 0..1."""
    if isinstance(c, str):
        h = c.lstrip("#")
        c = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    out = []
    for v in c:
        v = float(v) / 255.0
        out.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    return tuple(out)


def load_image(path, sequence=False, frames=None, start=1, offset=0):
    """-> Image (reused by path; a bpy Image passes through). '//' paths resolve against the open
    .blend, others against the cwd; a missing file raises. sequence=True sets source SEQUENCE; the
    node that shows it gets its image_user from set_sequence(node, frames, start, offset)."""
    if isinstance(path, bpy.types.Image):
        img = path
    else:
        p = bpy.path.abspath(path) if str(path).startswith("//") else os.path.abspath(path)
        if not os.path.exists(p):
            raise FileNotFoundError(f"materials.load_image: {p}")
        img = bpy.data.images.load(p, check_existing=True)
    if sequence:
        img.source = "SEQUENCE"
    return img


def set_sequence(node, frames, start=1, offset=0):
    """Image node shows frame N + offset of its sequence at scene frame N: frame_duration=frames,
    frame_start=start, frame_offset=offset, auto refresh, no cycling."""
    if not frames:
        raise ValueError("materials.set_sequence: frames (the sequence length) is required")
    iu = node.image_user
    iu.frame_duration = int(frames)
    iu.frame_start = int(start)
    iu.frame_offset = int(offset)
    iu.use_auto_refresh = True
    iu.use_cyclic = False
    return node


def set_props(ob, **props):
    """Create or set custom properties on ob (before any key on them)."""
    for k, v in props.items():
        ob[k] = float(v)
    return ob


def prop_or_default(node_tree, prop, default=1.0, location=(0, 0)):
    """Attribute(OBJECT) node for prop mixed with default by Alpha. -> the output socket
    (= obj[prop] when the object has it, else default)."""
    nodes, links = node_tree.nodes, node_tree.links
    a = nodes.new("ShaderNodeAttribute")
    a.attribute_type = "OBJECT"
    a.attribute_name = prop
    a.location = location
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "FLOAT"
    mix.location = (location[0] + 200, location[1])
    mix.inputs[2].default_value = float(default)
    links.new(a.outputs["Alpha"], mix.inputs[0])
    links.new(a.outputs["Factor"], mix.inputs[3])
    return mix.outputs[0]


def _emission_chain(m, strength, glow_prop, power_prop):
    """Emission Strength = glow x power x strength (node 'ui_strength' holds strength in inputs[1]).
    Records m['ui_strength_node']. Idempotent."""
    nt = m.node_tree
    p = nt.nodes[PRINCIPLED]
    node = nt.nodes.get("ui_strength")
    if node is None:
        glow = prop_or_default(nt, glow_prop, 1.0, (-900, -200))
        power = prop_or_default(nt, power_prop, 1.0, (-900, -400))
        m1 = nt.nodes.new("ShaderNodeMath")
        m1.name = "ui_glow_power"
        m1.operation = "MULTIPLY"
        m1.location = (-450, -250)
        nt.links.new(glow, m1.inputs[0])
        nt.links.new(power, m1.inputs[1])
        node = nt.nodes.new("ShaderNodeMath")
        node.name = "ui_strength"
        node.operation = "MULTIPLY"
        node.location = (-250, -250)
        nt.links.new(m1.outputs[0], node.inputs[0])
        nt.links.new(node.outputs[0], p.inputs["Emission Strength"])
        m["ui_strength_node"] = node.name
    node.inputs[1].default_value = float(strength)
    return node


def _tex_node(m, image, interpolation, extension, name="ui_tex"):
    """The material's image node (created once, linked Color -> Emission Color). -> node."""
    nt = m.node_tree
    tex = nt.nodes.get(name)
    if tex is None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.name = name
        tex.location = (-700, 200)
        nt.links.new(tex.outputs["Color"], nt.nodes[PRINCIPLED].inputs["Emission Color"])
    tex.image = image
    tex.interpolation = interpolation
    tex.extension = extension
    return tex


# ---------------------------------------------------------------- screens
def make_screen_material(name, image, strength=1.0, sequence=False, frames=None, spec=0.1, rough=0.32,
                         glow_prop="ui_glow", power_prop="ui_power", grade=None, start=1, offset=0,
                         interpolation="Linear", extension="EXTEND"):
    """Image (or sequence) emission under black glossy glass. Emission = image x strength x glow x power;
    Specular IOR Level = spec faded by power (set_power_specular). grade (h, s, v) or None applies to
    camera rays only. Records m['ui_strength_node']. Idempotent. -> Material."""
    m, _ = _material(name)
    p = m.node_tree.nodes[PRINCIPLED]
    p.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    p.inputs["Roughness"].default_value = float(rough)
    p.inputs["Emission Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    tex = _tex_node(m, load_image(image, sequence, frames), interpolation, extension)
    if sequence:
        set_sequence(tex, frames, start, offset)
    _emission_chain(m, strength, glow_prop, power_prop)
    set_power_specular(m, spec, prop=power_prop)
    set_grade(m, grade)
    return m


def make_tinted_screen_material(name, image, tint, gain, **kw):
    """Screen material whose tint colour (linear rgb) multiplies in by clamp((glow - 1) x gain, 0, 1)
    (a pressed tile lights up). kw as make_screen_material. Idempotent. -> Material."""
    grade = kw.pop("grade", None)
    m = make_screen_material(name, image, **kw)
    nt = m.node_tree
    p = nt.nodes[PRINCIPLED]
    mix = nt.nodes.get("ui_tint_mix")
    if mix is None:
        tex = nt.nodes["ui_tex"]
        glow = prop_or_default(nt, kw.get("glow_prop", "ui_glow"), 1.0, (-1300, 300))
        sub = nt.nodes.new("ShaderNodeMath")
        sub.operation = "SUBTRACT"
        sub.inputs[1].default_value = 1.0
        sub.use_clamp = True
        sub.location = (-1000, 300)
        nt.links.new(glow, sub.inputs[0])
        g = nt.nodes.new("ShaderNodeMath")
        g.name = "ui_tint_gain"
        g.operation = "MULTIPLY"
        g.use_clamp = True
        g.location = (-800, 300)
        nt.links.new(sub.outputs[0], g.inputs[0])
        mix = nt.nodes.new("ShaderNodeMix")
        mix.name = "ui_tint_mix"
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.location = (-500, 300)
        a, b = _rgba_sockets(mix)
        nt.links.new(g.outputs[0], mix.inputs[0])
        nt.links.new(tex.outputs["Color"], a)
        nt.links.new(_rgba_sockets(mix, "outputs")[0], p.inputs["Emission Color"])
    nt.nodes["ui_tint_gain"].inputs[1].default_value = float(gain)
    _rgba_sockets(mix)[1].default_value = _rgba(tint)
    set_grade(m, grade)
    return m


def set_power_specular(material, spec, ramp=(0.3, 0.9), prop="ui_power"):
    """Specular IOR Level = spec x smoothstep(obj[prop], ramp): a powered-down slab stops mirroring
    lights; an object without the property keeps the full spec. Idempotent. -> Material."""
    nt = material.node_tree
    p = nt.nodes[PRINCIPLED]
    w = nt.nodes.get("look_spec_power")
    if w is None:
        power = prop_or_default(nt, prop, 1.0, (-900, -800))
        w = nt.nodes.new("ShaderNodeMapRange")
        w.name = "look_spec_power"
        w.interpolation_type = "SMOOTHSTEP"
        w.location = (-500, -800)
        nt.links.new(power, w.inputs["Value"])
        nt.links.new(w.outputs["Result"], p.inputs["Specular IOR Level"])
    w.inputs["From Min"].default_value, w.inputs["From Max"].default_value = float(ramp[0]), float(ramp[1])
    w.inputs["To Min"].default_value, w.inputs["To Max"].default_value = 0.0, float(spec)
    return material


def set_grade(material, grade):
    """Insert or update a Hue/Sat/Value grade (h, s, v) on camera rays only between the emission
    source and the shader; None removes it. Spill light stays ungraded. Idempotent. -> Material."""
    nt = material.node_tree
    p = nt.nodes[PRINCIPLED]
    g = nt.nodes.get("look_grade")
    if g is None and grade is None:
        return material
    if g is None:
        if not p.inputs["Emission Color"].links:
            raise ValueError(f"set_grade: {material.name} has no emission source to grade")
        src = p.inputs["Emission Color"].links[0].from_socket
        x, y = src.node.location
        g = nt.nodes.new("ShaderNodeHueSaturation")
        g.name = g.label = "look_grade"
        g.location = (x + 250, y + 300)
        lp = nt.nodes.new("ShaderNodeLightPath")
        lp.name = "look_grade_path"
        lp.location = (x + 250, y + 600)
        mix = nt.nodes.new("ShaderNodeMix")
        mix.name = "look_grade_mix"
        mix.data_type = "RGBA"
        mix.location = (x + 500, y + 300)
        a, b = _rgba_sockets(mix)
        nt.links.new(src, g.inputs["Color"])
        nt.links.new(src, a)
        nt.links.new(g.outputs["Color"], b)
        nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
        nt.links.new(_rgba_sockets(mix, "outputs")[0], p.inputs["Emission Color"])
    if grade is None:
        mix = nt.nodes["look_grade_mix"]
        nt.links.new(g.inputs["Color"].links[0].from_socket, p.inputs["Emission Color"])
        for n in (g, mix, nt.nodes["look_grade_path"]):
            nt.nodes.remove(n)
        return material
    h, s, v = grade
    g.inputs["Hue"].default_value = float(h)
    g.inputs["Saturation"].default_value = float(s)
    g.inputs["Value"].default_value = float(v)
    g.inputs["Factor"].default_value = 1.0
    return material


def set_glow_highlights(material, lo=0.1, hi=0.6):
    """glow above 1 lifts only pixels whose linear max channel is above smoothstep(lo..hi):
    strength = ((glow - 1) x w + 1) x power x strength. Needs a make_screen_material. Idempotent."""
    nt = material.node_tree
    nodes, links = nt.nodes, nt.links
    w = nodes.get("look_glow_hi_w")
    if w is None:
        m2 = nodes[material["ui_strength_node"]]
        m1 = m2.inputs[0].links[0].from_node
        glow = m1.inputs[0].links[0].from_socket
        tex = nodes["ui_tex"]
        sep = nodes.new("ShaderNodeSeparateColor")
        sep.location = (-1100, -600)
        links.new(tex.outputs["Color"], sep.inputs[0])
        mx = []
        for i, (a, b) in enumerate(((sep.outputs[0], sep.outputs[1]), (None, sep.outputs[2]))):
            n = nodes.new("ShaderNodeMath")
            n.operation = "MAXIMUM"
            n.location = (-900 + 150 * i, -600)
            links.new(a if a is not None else mx[-1].outputs[0], n.inputs[0])
            links.new(b, n.inputs[1])
            mx.append(n)
        w = nodes.new("ShaderNodeMapRange")
        w.name = "look_glow_hi_w"
        w.interpolation_type = "SMOOTHSTEP"
        w.location = (-600, -600)
        links.new(mx[-1].outputs[0], w.inputs["Value"])
        sub = nodes.new("ShaderNodeMath")
        sub.operation = "SUBTRACT"
        sub.location = (-700, -450)
        sub.inputs[1].default_value = 1.0
        links.new(glow, sub.inputs[0])
        add = nodes.new("ShaderNodeMath")
        add.operation = "MULTIPLY_ADD"          # (glow - 1) * w + 1
        add.location = (-500, -450)
        add.inputs[2].default_value = 1.0
        links.new(sub.outputs[0], add.inputs[0])
        links.new(w.outputs["Result"], add.inputs[1])
        links.new(add.outputs[0], m1.inputs[0])
    w.inputs["From Min"].default_value, w.inputs["From Max"].default_value = float(lo), float(hi)
    return material


# ---------------------------------------------------------------- solids
def set_principled(material, values):
    """Set Principled sockets from a LOOK material dict (keys of PRINCIPLED_KEYS; 'base' also sets the
    viewport colour). Unknown keys are ignored. -> Material."""
    p = material.node_tree.nodes[PRINCIPLED]
    for k, v in values.items():
        sock = PRINCIPLED_KEYS.get(k)
        if sock is None:
            continue
        inp = p.inputs[sock]
        inp.default_value = _rgba(v) if inp.type == "RGBA" else float(v)
    if "base" in values:
        material.diffuse_color = _rgba(values["base"])
    return material


def make_toy_material(name, base_linear, roughness, specular, coat=0.0, coat_roughness=0.15):
    """Principled plastic/vinyl body (base colour linear rgb). Idempotent. -> Material."""
    m, _ = _material(name)
    return set_principled(m, {"base": base_linear, "roughness": roughness, "specular": specular,
                              "coat": coat, "coat_roughness": coat_roughness})


def make_flat_emissive(name, color_linear, strength=1.0, roughness=0.3, specular=0.3,
                       glow_prop="ui_glow", power_prop="ui_power", base_share=0.0):
    """Solid emissive colour obeying the glow and power properties. base_share x colour is the diffuse
    base (0 = black when powered down). Idempotent. -> Material."""
    m, _ = _material(name)
    col = tuple(float(c) for c in color_linear[:3])
    set_principled(m, {"base": tuple(c * base_share for c in col), "roughness": roughness,
                       "specular": specular, "emission": col})
    _emission_chain(m, strength, glow_prop, power_prop)
    m.diffuse_color = _rgba(col)
    return m


def make_side_material(name, base_linear, specular, roughness, power_prop="ui_power"):
    """Dark glossy slab side whose specular fades with power. Idempotent. -> Material."""
    m, _ = _material(name)
    set_principled(m, {"base": base_linear, "roughness": roughness})
    return set_power_specular(m, specular, prop=power_prop)


def make_card_material(name, image_rgba, strength=1.0, grade=None, roughness=0.32, specular=0.0,
                       glow_prop="ui_glow", power_prop="ui_power"):
    """Emissive sprite card: the RGBA image is the emission and its alpha cuts the card (Principled
    Alpha). Obeys glow and power. Idempotent. -> Material."""
    m, _ = _material(name)
    nt = m.node_tree
    p = nt.nodes[PRINCIPLED]
    set_principled(m, {"base": (0.0, 0.0, 0.0), "roughness": roughness, "specular": specular})
    tex = _tex_node(m, load_image(image_rgba), "Linear", "CLIP")
    if not p.inputs["Alpha"].links:
        nt.links.new(tex.outputs["Alpha"], p.inputs["Alpha"])
    _emission_chain(m, strength, glow_prop, power_prop)
    set_grade(m, grade)
    return m


# ---------------------------------------------------------------- masks
def make_mask_material(name, classes, orange_targets=()):
    """Emission material_override that encodes region classes in R, G, B for the measurement render
    (Standard view, exposure 0). classes = {name: spec}; spec keys:
      index    pass_index of the objects this class marks (required to write)
      channel  'R' | 'G' | 'B' (default 'B')
      level    emission level 0..1 written (default 1.0)
      normal   '+X' .. '-Z' (optional): only faces whose object-space normal has dot > 0.9 with that
               axis; the index's plain class (no normal) is the base level of its other faces
      material name of a screen material (optional): sample its image on objects of `index` and write
               `level` where it is within 'dist' (default 0.04 linear) of one of 'near' (default
               orange_targets, linear rgb), or, with 'white': (min_lo, chroma_max), where the image's
               min channel > min_lo and max - min < chroma_max
      band     (lo, hi) linear levels: reader-only class (mask_bands), nothing written
    Classes of one channel must not overlap (values add). Idempotent. -> Material."""
    m, _ = _material(name)
    nt = m.node_tree
    nt.nodes.clear()
    N, L = nt.nodes.new, nt.links.new

    def op(kind, a, b=None, c=None):
        n = N("ShaderNodeMath")
        n.operation = kind
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = float(v)
            else:
                L(v, n.inputs[i])
        return n.outputs[0]

    idx = N("ShaderNodeObjectInfo").outputs["Object Index"]
    is_index = {}

    def is_(i):
        if i not in is_index:
            is_index[i] = op("COMPARE", idx, float(i), 0.1)
        return is_index[i]

    normal_xyz = None

    def normal_dot(axis):
        nonlocal normal_xyz
        if normal_xyz is None:
            geo = N("ShaderNodeNewGeometry")
            vt = N("ShaderNodeVectorTransform")
            vt.vector_type, vt.convert_from, vt.convert_to = "NORMAL", "WORLD", "OBJECT"
            L(geo.outputs["Normal"], vt.inputs[0])
            normal_xyz = vt.outputs[0]
        d = N("ShaderNodeVectorMath")
        d.operation = "DOT_PRODUCT"
        L(normal_xyz, d.inputs[0])
        d.inputs[1].default_value = AXES[axis]
        return op("GREATER_THAN", d.outputs["Value"], 0.9)

    tex_cache = {}

    def tex_of(mat_name):
        if mat_name not in tex_cache:
            src_m = bpy.data.materials.get(mat_name)
            if src_m is None:
                raise KeyError(f"make_mask_material: screen material {mat_name!r} not found")
            src = src_m.node_tree.nodes.get("ui_tex") or next(n for n in src_m.node_tree.nodes if n.type == "TEX_IMAGE")
            t = N("ShaderNodeTexImage")
            t.image, t.interpolation, t.extension = src.image, src.interpolation, src.extension
            if src.image is not None and src.image.source == "SEQUENCE":
                for k in ("frame_duration", "frame_start", "frame_offset", "use_auto_refresh", "use_cyclic"):
                    setattr(t.image_user, k, getattr(src.image_user, k))
            tex_cache[mat_name] = t
        return tex_cache[mat_name]

    base_of = {}       # (channel, index) -> plain level
    for spec in classes.values():
        if "index" in spec and "normal" not in spec and "material" not in spec and "band" not in spec:
            base_of[(spec.get("channel", "B"), int(spec["index"]))] = float(spec.get("level", 1.0))
    sums = {"R": None, "G": None, "B": None}

    def add(ch, v):
        sums[ch] = v if sums[ch] is None else op("ADD", sums[ch], v)

    for (ch, i), level in base_of.items():
        add(ch, op("MULTIPLY", is_(i), level))
    for spec in classes.values():
        if "index" not in spec or "band" in spec:
            continue
        ch, i, level = spec.get("channel", "B"), int(spec["index"]), float(spec.get("level", 1.0))
        if "normal" in spec:
            add(ch, op("MULTIPLY", op("MULTIPLY", is_(i), normal_dot(spec["normal"])), level - base_of.get((ch, i), 0.0)))
        elif "material" in spec:
            t = tex_of(spec["material"])
            if "white" in spec:
                lo_v, chroma = spec["white"]
                sep = N("ShaderNodeSeparateColor")
                L(t.outputs["Color"], sep.inputs[0])
                lo = op("MINIMUM", op("MINIMUM", sep.outputs[0], sep.outputs[1]), sep.outputs[2])
                hi = op("MAXIMUM", op("MAXIMUM", sep.outputs[0], sep.outputs[1]), sep.outputs[2])
                cond = op("MULTIPLY", op("GREATER_THAN", lo, float(lo_v)), op("LESS_THAN", op("SUBTRACT", hi, lo), float(chroma)))
            else:
                targets = spec.get("near", orange_targets)
                if not targets:
                    raise ValueError(f"make_mask_material: class with material {spec['material']!r} needs 'near' or orange_targets")
                cond = None
                for tgt in targets:
                    d = N("ShaderNodeVectorMath")
                    d.operation = "DISTANCE"
                    L(t.outputs["Color"], d.inputs[0])
                    d.inputs[1].default_value = tuple(float(c) for c in tgt[:3])
                    near = op("LESS_THAN", d.outputs["Value"], float(spec.get("dist", 0.04)))
                    cond = near if cond is None else op("MAXIMUM", cond, near)
            if "alpha" in spec:
                cond = op("MULTIPLY", cond, op("GREATER_THAN", t.outputs["Alpha"], float(spec["alpha"])))
            add(ch, op("MULTIPLY", op("MULTIPLY", is_(i), cond), level))
    comb = N("ShaderNodeCombineColor")
    for k, ch in enumerate("RGB"):
        if sums[ch] is not None:
            L(sums[ch], comb.inputs[k])
        else:
            comb.inputs[k].default_value = 0.0
    em = N("ShaderNodeEmission")
    L(comb.outputs[0], em.inputs["Color"])
    L(em.outputs[0], N("ShaderNodeOutputMaterial").inputs["Surface"])
    return m


def mask_bands(classes, margin=10):
    """-> {name: (channel, lo, hi)} 8-bit read-back bands (lo inclusive, hi exclusive) matching
    make_mask_material levels under the Standard view at exposure 0. A level's band reaches at most
    `margin` below and `margin + 1` above its sRGB code, and never past the midpoint to the next level
    written on the same channel. A 'band' class spans srgb(lo) - margin .. srgb(hi) + margin + 1."""
    levels = {}
    for spec in classes.values():
        if "index" in spec and "band" not in spec:
            levels.setdefault(spec.get("channel", "B"), set()).add(srgb8(spec.get("level", 1.0)))
    out = {}
    for name, spec in classes.items():
        ch = spec.get("channel", "B")
        if "band" in spec:
            lo, hi = spec["band"]
            out[name] = (ch, max(0, srgb8(lo) - margin), min(256, srgb8(hi) + margin + 1))
            continue
        if "index" not in spec:
            continue
        s = srgb8(spec.get("level", 1.0))
        below = [v for v in levels[ch] if v < s]
        above = [v for v in levels[ch] if v > s]
        lo = max(s - margin, (s + max(below)) // 2 + 1 if below else 0, 0)
        hi = min(s + margin + 1, (s + min(above)) // 2 + 1 if above else 256, 256)
        out[name] = (ch, lo, hi)
    return out
