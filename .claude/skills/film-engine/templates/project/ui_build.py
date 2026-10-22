"""ui_build.py: build build/ui.html, the app page ui-render.mjs screenshots into the UI texture.

Every element is positioned at a LAYOUT rect and tagged with the rect it must stay inside
(filmkit.ui_html.Page); ui-render proves it. The page shows the FINAL state; anything that changes
over time is a screen (per-frame plane) or an object. Palette, fonts and labels are TASTE.
"""
import sys
sys.dont_write_bytecode = True
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.environ.get("FILM_ENGINE") or os.path.normpath(
    os.path.join(HERE, "..", "..", ".claude", "skills", "film-engine", "scripts"))
sys.path[:0] = [p for p in (HERE, ENGINE) if p not in sys.path]

from filmkit import layout as layout_mod, ui_html  # noqa: E402
import timeline as T  # noqa: E402

# TASTE: the UI font (a local() face list; ui-render proves it with build.json 'ui_font').
FONT_CSS = ('@font-face{font-family:UiFont;src:local("Segoe UI"),local("Arial"),local("Helvetica"),'
            'local("DejaVu Sans"),local("Liberation Sans");}')
# TASTE: the palette.
CSS = "body,#ui{background:#1a1a1a;}.t{font-family:UiFont,sans-serif;color:#d0d0d0;}"
PANEL_BG, PANEL_EDGE = "#2a2a2a", "#3a3a3a"
TILE_BG, TILE_EDGE = "#3c3c3c", "#5a5a5a"
LABELS = {"btn:a": "A", "btn:b": "B"}


def build():
    """-> ui_html.Page of the app in its final state."""
    page = ui_html.Page(T.LAYOUT, css=CSS, font_css=FONT_CSS, title="greybox app")
    for name, r in T.LAYOUT.panels.items():
        page.box(r, name, bg=PANEL_BG, style=f"border:1px solid {PANEL_EDGE};")
        page.text(r[0] + 8, r[1] + 14, name.upper(), name, 10, weight=600)
    for bid, r in T.LAYOUT.buttons.items():
        page.box(r, bid, bg=TILE_BG, style=f"border:1px solid {TILE_EDGE};border-radius:4px;")
        cx, cy = layout_mod.rect_center(r)
        page.text(cx, cy, LABELS.get(bid, bid), bid, 14, weight=700, align="center")
    for name, (r, flat) in T.LAYOUT.screens.items():
        page.box(r, name, bg=flat)                       # one flat colour: the per-frame plane sits here
    page.check_overlay()
    return page


def main():
    os.makedirs(os.path.join(HERE, "build"), exist_ok=True)
    n = build().write(os.path.join(HERE, "build", "ui.html"))
    print(f"ui_build: build/ui.html with {n} data-in elements")
    return 0


if __name__ == "__main__":
    sys.exit(main())
