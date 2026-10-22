"""check_model.py: run the model critic on motion.py + shots.py (filmkit.check), no renderer.

Builds the model object the checker reads (check.py module docstring), runs checks_config.RULES,
writes build/model_report.txt (line 'VIOLATIONS: N' is the stills gate) and build/previs.svg
(top-down map, chart, storyboard tiles; rasterise with headless Chrome to look at it).
Exit 1 on any violation. Mechanical: no taste here beyond PREVIS layer colours.
"""
import sys
sys.dont_write_bytecode = True
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.environ.get("FILM_ENGINE") or os.path.normpath(
    os.path.join(HERE, "..", "..", ".claude", "skills", "film-engine", "scripts"))
sys.path[:0] = [p for p in (HERE, ENGINE) if p not in sys.path]

from filmkit import check  # noqa: E402
import checks_config as C  # noqa: E402
import motion as M  # noqa: E402
import shots as S  # noqa: E402
import timeline as T  # noqa: E402


class Model:
    """The model protocol of filmkit.check, wired to this project's modules."""
    name = "model check"
    fmt = T.FORMAT
    layout = T.LAYOUT
    events = T.EVENTS
    ground_poly = T.LAYOUT.rect_world((0, 0, T.UI[0], T.UI[1]))
    camera = staticmethod(S.camera_state)
    camera_raw = staticmethod(S.camera_raw)
    hero_points = staticmethod(M.hero_points)
    hero_blocks = staticmethod(M.hero_blocks)
    landings = staticmethod(M.landings)
    holds = staticmethod(S.holds)
    whip_windows = staticmethod(S.whip_windows)

    @staticmethod
    def probes():
        """Still world points for the hit-stillness measure: the set corners."""
        return list(S.SET)

    @staticmethod
    def channels(t):
        out = M.channels(t)
        out.update(S.channels(t))
        return out


def main():
    build = os.path.join(HERE, "build")
    os.makedirs(build, exist_ok=True)
    model = Model()
    rep = check.run(model, C.RULES)
    code = rep.write(os.path.join(build, "model_report.txt"))
    layers = [
        ("slabs", lambda t: [T.LAYOUT.rect_world(r) for r in T.LAYOUT.panels.values()], "fill:#2a2a2a;stroke:#666"),
        ("tiles", lambda t: [T.LAYOUT.rect_world(r, T.Z["tile"][1]) for r in T.LAYOUT.buttons.values()], "fill:#555;stroke:#999"),
        ("screens", lambda t: [T.LAYOUT.rect_world(r[0], T.Z["screen"]) for r in T.LAYOUT.screens.values()], "fill:#123;stroke:#36c"),
    ]
    check.write_previs_svg(model, C.PREVIS_MOMENTS, layers, os.path.join(build, "previs.svg"))
    text = rep.text().splitlines()
    print("\n".join(text[:2 + len(rep.violations)]))
    for line in rep.lines:
        print(line)
    print("wrote build/model_report.txt, build/previs.svg")
    return code


if __name__ == "__main__":
    sys.exit(main())
