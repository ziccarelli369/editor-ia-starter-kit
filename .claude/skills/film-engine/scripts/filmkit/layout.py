"""layout: UI pixels <-> world metres, rects, stacks. Owner: core. Standard library only.

Rect = (x, y, w, h) in UI CSS px, y down. World: metres, X east, Y north, Z up.
UI centre = world origin; UI +y (down) = world -Y; slab tops at z 0.
One Layout per film; every reader calls its ui_to_world / world_to_ui.
No number here is taste: every rect, size and time is data the project supplies.
"""
from .ease import smoothstep
from .timebase import jsonable


def _rect(r):
    """-> (x, y, w, h) checked: four numbers, w and h >= 0."""
    if len(r) != 4:
        raise ValueError(f"rect needs 4 numbers, got {r!r}")
    x, y, w, h = r
    if w < 0 or h < 0:
        raise ValueError(f"rect has a negative size: {r!r}")
    return (x, y, w, h)


class Layout:
    """The app layout a film supplies. Every value is data; no colours here.

    ui: (w, h) CSS px. px_to_m: metres per UI px.
    panels: {name: rect}            one slab each
    buttons: {id: rect}             one raised tile each (the hero lands on these)
    screens: {name: (rect, flat_hex)}  per-frame image planes; the UI texture must
                                    leave the rect one flat colour flat_hex
    stacks: {name: {'rect': rect, 'y0': int, 'row_h': int, 'slide_s': float,
                    'items': [(id, rows, created_t)]}}   list blocks that insert
    sprites: {name: (w, h)}         transparent sprites screenshotted alone
    points: {name: (x, y)}          named UI points (spawn, targets)
    nested: {name: (rect, scale)}   a canvas shown inside a rect at a scale
    owners: {child: panel} optional explicit parent overrides.
    """

    def __init__(self, ui, px_to_m, panels=None, buttons=None, screens=None, stacks=None,
                 sprites=None, points=None, nested=None, owners=None):
        self.ui = (ui[0], ui[1])
        self.px_to_m = float(px_to_m)
        self.panels = {k: _rect(v) for k, v in (panels or {}).items()}
        self.buttons = {k: _rect(v) for k, v in (buttons or {}).items()}
        self.screens = {k: (_rect(v[0]), v[1]) for k, v in (screens or {}).items()}
        self.stacks = {}
        for k, v in (stacks or {}).items():
            s = dict(v)
            s["rect"] = _rect(s["rect"])
            s["items"] = [(i[0], i[1], i[2]) for i in s["items"]]
            self.stacks[k] = s
        self.sprites = {k: (v[0], v[1]) for k, v in (sprites or {}).items()}
        self.points = {k: (v[0], v[1]) for k, v in (points or {}).items()}
        self.nested = {k: (_rect(v[0]), v[1]) for k, v in (nested or {}).items()}
        self.owners = dict(owners or {})

    def ui_to_world(self, x, y):
        """UI px -> (X, Y) metres on the slab plane."""
        return ((x - self.ui[0] / 2) * self.px_to_m, (self.ui[1] / 2 - y) * self.px_to_m)

    def world_to_ui(self, X, Y):
        """(X, Y) metres -> UI px."""
        return (X / self.px_to_m + self.ui[0] / 2, self.ui[1] / 2 - Y / self.px_to_m)

    def uv_of(self, x, y):
        """UI px -> texture UV: (x/ui_w, 1 - y/ui_h)."""
        return (x / self.ui[0], 1 - y / self.ui[1])

    def rect_world(self, rect, z=0.0):
        """Rect -> 4 world corners [(X, Y, z)] in order SW, SE, NE, NW."""
        x, y, w, h = rect
        return [self.ui_to_world(px, py) + (z,) for px, py in ((x, y + h), (x + w, y + h), (x + w, y), (x, y))]

    def rect_of(self, name):
        """-> the rect registered under name in panels, buttons, screens, stacks or nested."""
        if name in self.panels:
            return self.panels[name]
        if name in self.buttons:
            return self.buttons[name]
        if name in self.screens:
            return self.screens[name][0]
        if name in self.stacks:
            return self.stacks[name]["rect"]
        if name in self.nested:
            return self.nested[name][0]
        raise KeyError(f"layout has no rect named {name!r}")

    def owner_of_point(self, pt, fallback=None):
        """-> the panel whose rect contains UI point pt (centre test), else fallback.

        Panels are tested in table order; the fallback panel itself is skipped so
        a panel laid over it wins.
        """
        for name, rect in self.panels.items():
            if name != fallback and rect_contains(rect, pt):
                return name
        return fallback

    def owner_of(self, name):
        """-> owners[name] if set, else owner_of_point(rect_center(rect_of(name)))."""
        if name in self.owners:
            return self.owners[name]
        return self.owner_of_point(rect_center(self.rect_of(name)))

    def nested_to_ui(self, name, cx, cy):
        """Nested canvas px -> UI px for nested[name] = (rect, scale)."""
        rect, scale = self.nested[name]
        return (rect[0] + cx * scale, rect[1] + cy * scale)

    def ui_to_nested(self, name, x, y):
        """UI px -> nested canvas px."""
        rect, scale = self.nested[name]
        return ((x - rect[0]) / scale, (y - rect[1]) / scale)

    def nested_to_world(self, name, cx, cy):
        """Nested canvas px -> (X, Y) metres."""
        return self.ui_to_world(*self.nested_to_ui(name, cx, cy))

    def to_json(self):
        """-> dict of every table, JSON-safe (tuples become lists)."""
        return jsonable({
            "ui": self.ui, "px_to_m": self.px_to_m, "panels": self.panels, "buttons": self.buttons,
            "screens": self.screens, "stacks": self.stacks, "sprites": self.sprites, "points": self.points,
            "nested": self.nested, "owners": self.owners,
        })


def rect_center(rect):
    """-> (cx, cy)."""
    return (rect[0] + rect[2] / 2, rect[1] + rect[3] / 2)


def rect_contains(rect, pt, eps=0.0):
    """True when pt lies inside rect grown by eps on each side."""
    x, y, w, h = rect
    return x - eps <= pt[0] <= x + w + eps and y - eps <= pt[1] <= y + h + eps


def rect_inside(inner, outer, eps=0.0):
    """True when inner lies wholly inside outer grown by eps."""
    x, y, w, h = inner
    return rect_contains(outer, (x, y), eps) and rect_contains(outer, (x + w, y + h), eps)


def rect_inset(rect, d):
    """-> rect shrunk by d on every side."""
    x, y, w, h = rect
    return (x + d, y + d, w - 2 * d, h - 2 * d)


def rect_union(a, b):
    """-> smallest rect holding a and b."""
    x0, y0 = min(a[0], b[0]), min(a[1], b[1])
    x1, y1 = max(a[0] + a[2], b[0] + b[2]), max(a[1] + a[3], b[1] + b[3])
    return (x0, y0, x1 - x0, y1 - y0)


def rect_scale(rect, s):
    """-> rect with every value times s (UI px -> texture px with s = ui_scale)."""
    return (rect[0] * s, rect[1] * s, rect[2] * s, rect[3] * s)


def stack_tops(t, items, y0, row_h, slide_s, ease=None):
    """Eased list insert. items: [(id, rows, created_t)] in stack order (top first).

    A block appears at created_t at y0; blocks below it slide down by its height
    over slide_s with ease (default smoothstep). -> {id: top_y | None before created_t}.
    slide_s <= 0 makes the push a step.
    """
    ease = smoothstep if ease is None else ease
    out = {}
    for lid, _, created in items:
        if t < created:
            out[lid] = None
            continue
        y = y0
        for lid2, rows2, created2 in items:
            if lid2 == lid:
                break
            if t >= created2:
                y += rows2 * row_h * (1.0 if slide_s <= 0 else ease((t - created2) / slide_s))
        out[lid] = y
    return out


def stack_final_tops(items, y0, row_h):
    """-> {id: top_y} once every block exists (the texture source rect of each block)."""
    tops, y = {}, y0
    for lid, rows, _ in items:
        tops[lid] = y
        y += rows * row_h
    return tops


def ruler_x(value, x0, px_per_unit):
    """Linear ruler: value -> UI x."""
    return x0 + value * px_per_unit
