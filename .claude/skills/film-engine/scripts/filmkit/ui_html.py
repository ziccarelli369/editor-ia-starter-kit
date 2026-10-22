"""ui_html: HTML primitives for the app page the UI texture is screenshotted from.
Owner: node. Standard library only.

Every element is absolutely positioned at a Layout rect and tagged
data-in="<rect name>" so ui-render.mjs can prove containment. The page shows
the FINAL state; time-varying blocks sit in div.layer (hidden in 'base'
mode); sprites sit in their own wrappers shown alone in '<sprite>' mode.
Colours, glyphs and labels are the project's; this module has no palette.

Rects are (x, y, w, h) in UI CSS px. The registry the page embeds
(window.UI_RECTS, UI_EMPTY, UI_SPRITES, UI_SIZE) is built from the Layout:
panels, buttons, screens and nested by name, stack blocks as
'<stack>:<id>' at their final tops, sprites as (0, 0, w, h). register()
adds any other rect a project element names.

Usage (a project's ui_page.py):
    page = Page(LAYOUT, css=PROJECT_CSS, font_css=FONT_FACES, title="app")
    page.box(LAYOUT.panels["top"], "top", bg="#222")
    with page.layer():                      # hidden in 'base' mode
        page.box(rect, "stack:layers:title", bg="#333")
    with page.sprite("chip"):               # shown alone in mode 'chip'
        page.box((0, 0, 74, 26), "chip", bg="#456")
    page.check_overlay()
    n = page.write("build/ui.html")
"""
import html as _html
import json
import os

from . import layout as _layout

_ENGINE_CSS = (
    "html,body{{margin:0;padding:0;}}"
    "body{{width:{w}px;height:{h}px;overflow:hidden;}}"
    "#ui{{position:absolute;left:0;top:0;width:{w}px;height:{h}px;overflow:hidden;}}"
    ".a{{position:absolute;box-sizing:border-box;white-space:nowrap;margin:0;}}"
    "#check,.sprite{{display:none;}}"
    "html.base .layer{{display:none;}}"
    "html.check #check{{display:block;}}"
    ".ck{{font:600 6px/7px sans-serif;background:rgba(0,0,0,0.65);padding:0 1px;}}"
)
_SPRITE_CSS = (
    "html.{s},html.{s} body{{background:transparent;}}"
    "html.{s} #ui{{display:none;}}"
    "html.{s} #sprite-{s}{{display:block;}}"
)
_RESERVED_MODES = ("base", "check")
# Review-overlay colours by rect kind (a review image, not a film colour).
_CHECK_COLORS = {"panel": "#ff00ff", "button": "#ff00ff", "screen": "#00ffff", "stack": "#ff8800",
                 "nested": "#ffff00", "sprite": "#00ffff", "extra": "#ffffff"}


def esc(s):
    """HTML-escape a string (quotes included)."""
    return _html.escape(str(s), quote=True)


def _n(v):
    """Number -> shortest CSS px string: 12 -> '12', 12.5 -> '12.5', 1/3 -> '0.333'."""
    f = float(v)
    if f.is_integer():
        return str(int(f))
    s = f"{f:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _table(layout, key):
    """Read table `key` from a Layout object or a Layout.to_json() dict. -> dict (never None)."""
    v = layout.get(key) if isinstance(layout, dict) else getattr(layout, key, None)
    return dict(v) if v else {}


def _rect(r):
    """-> [x, y, w, h] as floats from any 4-sequence."""
    x, y, w, h = r
    return [float(x), float(y), float(w), float(h)]


class _Group:
    """Context manager that redirects the page's appends into one wrapper element.
    On exit the wrapped html goes to sink(html), or to the page where the group was opened."""

    def __init__(self, page, open_tag, sink=None, close_tag="</div>"):
        self.page, self.open_tag, self.sink, self.close_tag = page, open_tag, sink, close_tag
        self.parts = []

    def __enter__(self):
        self._saved = self.page._target
        self.page._target = self.parts
        return self

    def __exit__(self, *exc):
        self.page._target = self._saved
        if exc[0] is None:
            (self.sink or self._saved.append)(self.open_tag + "".join(self.parts) + self.close_tag)
        return False


class Page:
    """Builds build/ui.html from a Layout.

    layout: layout.Layout (or its to_json() dict). css: project CSS (palette, fonts,
    background) appended after the engine's mode CSS. font_css: @font-face rules
    (local() or url()). title: page title.
    Every primitive appends to the page (or to the open layer/sprite group) and
    returns its html. Sizes are UI CSS px.
    """

    def __init__(self, layout, css="", font_css="", title="ui"):
        self.layout = layout
        ui = layout.get("ui") if isinstance(layout, dict) else getattr(layout, "ui")
        self.ui = (float(ui[0]), float(ui[1]))
        self.css, self.font_css, self.title = css, font_css, title
        self.rects = {}       # name -> [x, y, w, h]: the containment contract
        self.kinds = {}       # name -> panel | button | screen | stack | nested | sprite | extra
        self.empty = {}       # screen name -> [[x, y, w, h], flat_hex]
        self.sprites = {}     # name -> [w, h]
        self.points = {k: [float(v[0]), float(v[1])] for k, v in _table(layout, "points").items()}
        self._parts = []      # html inside #ui
        self._target = self._parts
        self._sprite_html = {}
        self._check = ""
        for name, r in _table(layout, "panels").items():
            self._add(name, r, "panel")
        for name, r in _table(layout, "buttons").items():
            self._add(name, r, "button")
        for name, (r, hexcol) in _table(layout, "screens").items():
            self._add(name, r, "screen")
            self.empty[name] = [_rect(r), str(hexcol)]
        for name, (r, _scale) in _table(layout, "nested").items():
            self._add(name, r, "nested")
        for name, st in _table(layout, "stacks").items():
            sx, _sy, sw, _sh = _rect(st["rect"])
            self._add(name, st["rect"], "stack")
            tops = _layout.stack_final_tops(st["items"], st["y0"], st["row_h"])
            for item_id, rows, _created in st["items"]:
                self._add(f"{name}:{item_id}", (sx, tops[item_id], sw, rows * st["row_h"]), "stack")
        for name, (w, h) in _table(layout, "sprites").items():
            if name in _RESERVED_MODES:
                raise ValueError(f"sprite name {name!r} is a reserved page mode")
            self.sprites[name] = [float(w), float(h)]
            self._add(name, (0, 0, w, h), "sprite")

    # ---------------------------------------------------------------- registry
    def _add(self, name, rect, kind):
        if name in self.rects:
            raise ValueError(f"rect name {name!r} registered twice ({self.kinds[name]} and {kind})")
        self.rects[name] = _rect(rect)
        self.kinds[name] = kind

    def register(self, name, rect, kind="extra"):
        """Add a containment rect under name (for elements no Layout table names)."""
        self._add(name, rect, kind)
        return self.rects[name]

    def _emit(self, s):
        self._target.append(s)
        return s

    # ---------------------------------------------------------------- primitives
    def box(self, rect, own, bg=None, style="", inner="", cls=""):
        """Absolutely positioned div at rect, data-in=own. bg: CSS background or None.
        style: extra CSS. inner: html inside. -> html (also appended to the page)."""
        x, y, w, h = _rect(rect)
        st = f"left:{_n(x)}px;top:{_n(y)}px;width:{_n(w)}px;height:{_n(h)}px;"
        if bg:
            st += f"background:{bg};"
        own_attr = f' data-in="{esc(own)}"' if own else ""
        cls_attr = f' class="a {cls}"' if cls else ' class="a"'
        return self._emit(f'<div{cls_attr} style="{st}{style}"{own_attr}>{inner}</div>')

    def text(self, x, cy, s, own, size=11, color=None, weight=400, align="left", font=None, style=""):
        """One line of text centred on line y = cy. x is the left edge (align 'left'), the centre
        ('center') or the right edge ('right'). size: px. color: CSS colour or None (inherit).
        font: font-family or None (inherit). The line box is round(size * 1.36) px tall."""
        h = round(size * 1.36)
        tr = {"left": "", "center": "transform:translateX(-50%);", "right": "transform:translateX(-100%);"}[align]
        st = (f"left:{_n(x)}px;top:{_n(cy - h / 2)}px;height:{_n(h)}px;line-height:{_n(h)}px;"
              f"font-size:{_n(size)}px;font-weight:{weight};{tr}")
        if color:
            st += f"color:{color};"
        if font:
            st += f"font-family:{font};"
        return self._emit(f'<div class="a t" style="{st}{style}" data-in="{esc(own)}">{esc(s)}</div>')

    def svg(self, rect, body, own, color=None, view_box=None, stroke=None, style=""):
        """Inline SVG at rect: body is the inner markup, view_box defaults to '0 0 w h'.
        color sets currentColor; stroke is the stroke width (None -> 1), fill none."""
        x, y, w, h = _rect(rect)
        vb = view_box or f"0 0 {_n(w)} {_n(h)}"
        col = f"color:{color};" if color else ""
        sw = 1 if stroke is None else stroke
        return self._emit(
            f'<svg class="a" data-in="{esc(own)}" style="left:{_n(x)}px;top:{_n(y)}px;width:{_n(w)}px;'
            f'height:{_n(h)}px;{col}{style}" viewBox="{vb}" fill="none" stroke="currentColor" '
            f'stroke-width="{_n(sw)}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')

    def hline(self, x, y, w, own, color, thickness=1):
        """Horizontal rule from (x, y), w wide, thickness tall."""
        return self.box((x, y, w, thickness), own, color)

    def vline(self, x, y, h, own, color, thickness=1):
        """Vertical rule from (x, y), h tall, thickness wide."""
        return self.box((x, y, thickness, h), own, color)

    def layer(self, inner="", cls="layer"):
        """Time-varying block hidden in 'base' mode. With inner: wrap that html, append, -> html.
        Without: -> a context manager; primitives called inside it land in the wrapper."""
        w, h = self.ui
        open_tag = f'<div class="a {cls}" style="left:0;top:0;width:{_n(w)}px;height:{_n(h)}px">'
        if inner:
            return self._emit(open_tag + inner + "</div>")
        return _Group(self, open_tag)

    def sprite(self, name, inner=""):
        """Sprite wrapper at (0, 0) of size layout.sprites[name], shown alone in mode name on a
        transparent background. Elements inside name own=name (rect (0, 0, w, h)). With inner:
        set that html, -> html. Without: -> a context manager collecting the primitives."""
        if name not in self.sprites:
            raise KeyError(f"sprite {name!r} is not in layout.sprites")
        w, h = self.sprites[name]
        open_tag = f'<div id="sprite-{esc(name)}" class="a sprite" style="left:0;top:0;width:{_n(w)}px;height:{_n(h)}px">'
        if inner:
            self._sprite_html[name] = open_tag + inner + "</div>"
            return self._sprite_html[name]
        return _Group(self, open_tag, sink=lambda h: self._sprite_html.__setitem__(name, h))

    def texture_px_svg(self, rect, scale, marks, own, color):
        """One SVG over rect whose viewBox is in texture px (rect * scale), shape-rendering
        crispEdges. marks: [(x_ui, y_ui, w_ui, h_ui[, color])], each drawn as a rect snapped to
        whole texture px, so a 3D object centred on the same UI x lines up (CSS boxes snap to
        whole CSS px). color: fill for marks without their own."""
        x, y, w, h = _rect(rect)
        body = []
        for m in marks:
            mx, my, mw, mh = m[:4]
            col = m[4] if len(m) > 4 else color
            tx = round((mx - x) * scale)
            ty = round((my - y) * scale)
            tw = max(1, round(mw * scale))
            th = max(1, round(mh * scale))
            body.append(f'<rect x="{tx}" y="{ty}" width="{tw}" height="{th}" fill="{col}"/>')
        return self.svg(rect, "".join(body), own, view_box=f"0 0 {_n(w * scale)} {_n(h * scale)}",
                        stroke=0, style="shape-rendering:crispEdges;")

    # ---------------------------------------------------------------- review overlay
    def check_overlay(self, rects=None, points=None):
        """Draw rects and points as labelled outlines and crosses in #check (mode 'check').
        rects: {name: rect} or {name: (rect, color)}; default every registered rect, coloured
        by kind. points: {name: (x, y)}; default layout.points. -> html (stored for html())."""
        out = []

        def draw_rect(name, r, color):
            x, y, w, h = _rect(r)
            out.append(f'<div class="a" style="left:{_n(x)}px;top:{_n(y)}px;width:{_n(w)}px;height:{_n(h)}px;'
                       f'border:1px solid {color};"></div>')
            out.append(f'<div class="a ck" style="left:{_n(x + 1)}px;top:{_n(y + 1)}px;color:{color}">{esc(name)}</div>')

        def draw_point(name, p, color="#00ffff"):
            x, y = float(p[0]), float(p[1])
            out.append(f'<div class="a" style="left:{_n(x - 4)}px;top:{_n(y)}px;width:9px;height:1px;background:{color}"></div>')
            out.append(f'<div class="a" style="left:{_n(x)}px;top:{_n(y - 4)}px;width:1px;height:9px;background:{color}"></div>')
            out.append(f'<div class="a ck" style="left:{_n(x + 3)}px;top:{_n(y + 2)}px;color:{color}">{esc(name)}</div>')

        if rects is None:
            for name, r in self.rects.items():
                if self.kinds[name] == "sprite":
                    continue
                draw_rect(name, r, _CHECK_COLORS[self.kinds[name]])
        else:
            for name, v in rects.items():
                r, color = (v[0], v[1]) if (len(v) == 2 and not isinstance(v[1], (int, float))) else (v, _CHECK_COLORS["extra"])
                draw_rect(name, r, color)
        for name, p in (self.points if points is None else points).items():
            draw_point(name, p)
        w, h = self.ui
        self._check = f'<div id="check" class="a" style="left:0;top:0;width:{_n(w)}px;height:{_n(h)}px">{"".join(out)}</div>'
        return self._check

    # ---------------------------------------------------------------- page
    def modes_css(self):
        """-> engine CSS: base positioning, html.base hides .layer, html.check shows #check,
        html.<sprite> shows that sprite alone on a transparent background."""
        w, h = self.ui
        css = _ENGINE_CSS.format(w=_n(w), h=_n(h))
        for name in self.sprites:
            css += _SPRITE_CSS.format(s=esc(name))
        return css

    def registries_js(self):
        """-> <script> setting window.UI_SIZE [w, h], UI_RECTS {name: rect}, UI_EMPTY
        {screen: [rect, hex]} and UI_SPRITES {name: [w, h]}."""
        return ("<script>"
                f"window.UI_SIZE={json.dumps(list(self.ui))};"
                f"window.UI_RECTS={json.dumps(self.rects)};"
                f"window.UI_EMPTY={json.dumps(self.empty)};"
                f"window.UI_SPRITES={json.dumps(self.sprites)};"
                "</script>")

    def html(self):
        """-> the full page: head (engine CSS, font CSS, project CSS), #ui, #check, sprites, registries."""
        return ('<!doctype html><html><head><meta charset="utf-8">'
                f"<title>{esc(self.title)}</title>"
                f"<style>{self.modes_css()}{self.font_css}{self.css}</style></head><body>"
                f'<div id="ui">{"".join(self._parts)}</div>'
                f"{self._check}{''.join(self._sprite_html.values())}"
                f"{self.registries_js()}</body></html>")

    def write(self, path):
        """Write html() to path (utf-8, temp name then rename). -> count of data-in elements."""
        page = self.html()
        tmp = path + ".part"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(page)
        os.replace(tmp, path)
        return page.count("data-in=")
