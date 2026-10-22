"""check_node.py: quick check of the [node] modules. Standard library only; needs node and Chrome.

1. ui_html.Page builds a tiny app page (3 panels, 2 buttons, one flat screen rect, one sprite,
   one layer, a texture-px ruler, the check overlay) from a plain layout dict.
2. ui-render.mjs at scale 2 passes the contract and writes PNGs of the expected sizes; a page
   with one element outside its rect, and a page with a mark inside the flat screen rect, each
   exit 1 and leave no PNG behind.
3. frames-render.mjs renders a tiny canvas page (10 frames, 2 pages, 2 sequences) with the
   engine injected as window.FilmKit / FilmEase; a second render is byte-identical (md5);
   a page whose render(3) reports a failed check exits 1 and leaves no frame behind; a page whose
   tc sequence skips even frames exits 1 with the gap message and leaves nothing behind, and passes
   with --frames 1,3,5 (the gap check uses the requested frames).
Env: NODE (default node on PATH), CHROME (else filmkit.tools discovery). Exit 1 on any failure.
"""
import sys
sys.dont_write_bytecode = True
import hashlib
import json
import os
import shutil
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
sys.path.insert(0, SCRIPTS)
from filmkit import tools, ui_html  # noqa: E402

NODE = os.environ.get("NODE") or shutil.which("node") or "node"
CHROME = tools.find_chrome()
UI = (200, 120)
SCALE = 2
LAYOUT = {
    "ui": UI, "px_to_m": 0.0025,
    "panels": {"top": (0, 0, 200, 40), "left": (0, 40, 100, 80), "right": (100, 40, 100, 80)},
    "buttons": {"btn:a": (10, 50, 30, 20), "btn:b": (110, 50, 30, 20)},
    "screens": {"view": ((120, 80, 60, 30), "#000000")},
    "sprites": {"chip": (40, 16)},
    "points": {"spawn": (50, 20)},
}
FONT_CSS = ('@font-face{font-family:CheckFont;src:local("Arial"),local("Segoe UI"),local("Helvetica"),'
            'local("DejaVu Sans"),local("Liberation Sans");}')
CSS = "body,#ui{background:#202020;}.t{font-family:CheckFont,sans-serif;color:#dddddd;}"
COMP = (64, 36)
FRAMES = 10

COMP_PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>%s
html,body{margin:0;background:#111;}</style></head><body><canvas id="c" width="64" height="36"></canvas>
<script>
(function () {
  const K = window.FilmKit, E = window.FilmEase;
  if (!K || !E) throw new Error('engine not injected before the page script');
  let TL, W, H, ctx, dots;
  window.FilmPage = {
    loadFonts: () => K.loadFonts(['10px CheckFont'], '0:00'),
    init(tl) {
      TL = tl; [W, H] = tl.format.comp;
      const c = document.getElementById('c'); c.width = W; c.height = H; ctx = c.getContext('2d');
      const r = E.rng(7); dots = Array.from({ length: 5 }, () => [Math.floor(r() * W), Math.floor(r() * H)]);
    },
    render(f) {
      const st = TL.frames[f - 1];
      if (!st || st.f !== f) throw new Error('no state for frame ' + f);
      ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = '#888'; for (const [x, y] of dots) ctx.fillRect(x, y, 2, 2);
      const x = (f - 1) * 4;
      ctx.fillStyle = '#fff'; ctx.fillRect(x, 10, 8, 8);
      const tc = K.drawTimecode({ w: 40, h: 12, font: '10px CheckFont', color: '#fff', bg: '#222', pad: 2 },
                                K.timecode(st.t, TL.format.fps));
      const checks = window.BREAK_AT === f ? ['deliberate failure on frame ' + f] : [];
      const seq = { main: ctx.canvas.toDataURL('image/png') };
      if (!(window.GAP_TC && f %% 2 === 0)) seq.tc = tc;
      return { seq, bounds: { dot: K.box(x, 10, x + 8, 18) }, luma: K.lumaStats(ctx), checks };
    },
    bboxes() { return TL.frames.map((st) => ({ f: st.f, dot: K.box((st.f - 1) * 4, 10, (st.f - 1) * 4 + 8, 18) })); },
  };
})();
</script>%s</body></html>
"""


def build_page(variant=""):
    """-> ui_html.Page of the tiny app. variant: '' | 'overflow' | 'dirty_screen'."""
    p = ui_html.Page(LAYOUT, css=CSS, font_css=FONT_CSS, title="check")
    for name, r in LAYOUT["panels"].items():
        p.box(r, name, bg="#2a2a2a")
        p.text(r[0] + 4, r[1] + 10, name, name, 9)
    for bid, r in LAYOUT["buttons"].items():
        p.box(r, bid, bg="#3a3a3a", style="border:1px solid #555;border-radius:3px;")
        p.text(r[0] + r[2] / 2, r[1] + r[3] / 2, bid.split(":")[1], bid, 9, align="center")
    rect, hexcol = LAYOUT["screens"]["view"]
    p.box(rect, "view", bg=hexcol)
    p.hline(0, 39, 200, "top", "#111111")
    p.vline(99, 40, 80, "left", "#111111")
    p.texture_px_svg((0, 30, 200, 10), SCALE, [(10, 32, 0.5, 6), (20, 32, 0.5, 6), (30.25, 32, 1, 6, "#ffffff")], "top", "#888888")
    p.svg((150, 5, 20, 20), '<circle cx="10" cy="10" r="8"/>', "top", color="#aaaaaa", stroke=1.5)
    with p.layer():
        p.box((10, 96, 80, 15), "left", bg="#444444")
        p.text(14, 103.5, "layer block", "left", 8)
    with p.sprite("chip"):
        p.box((0, 0, 40, 16), "chip", bg="#4466aa", style="border-radius:8px;")
        p.text(6, 8, "fx", "chip", 9, color="#ffffff", weight=700)
    if variant == "overflow":
        p.text(90, 60, "overflow text", "left", 9)
    if variant == "dirty_screen":
        p.box((130, 90, 4, 4), "view", bg="#ff0000")
    p.check_overlay()
    return p


def run(args, cwd):
    proc = subprocess.run([NODE] + args, capture_output=True, text=True, cwd=cwd, env=dict(os.environ, CHROME=CHROME))
    return proc.returncode, (proc.stdout + proc.stderr)


def png_size(path):
    with open(path, "rb") as fh:
        b = fh.read(24)
    return int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")


def md5_tree(root):
    out = {}
    for dp, _dn, fn in os.walk(root):
        for f in sorted(fn):
            p = os.path.join(dp, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, root).replace("\\", "/")] = hashlib.md5(fh.read()).hexdigest()
    return out


def main():
    if not os.path.exists(CHROME):
        print(f"check_node: Chrome not found at {CHROME} (set env CHROME)")
        return 1
    tmp = tempfile.mkdtemp(prefix="film-engine-node-")
    fails = []
    try:
        tl = {"format": {"fps": 30, "frames": FRAMES, "ui": list(UI), "ui_scale": 3, "comp": list(COMP)},
              "layout": {k: v for k, v in LAYOUT.items() if k not in ("ui", "px_to_m")},
              "frames": [{"f": f, "t": round((f - 1) / 30, 4)} for f in range(1, FRAMES + 1)]}
        tl_path = os.path.join(tmp, "timeline.json")
        with open(tl_path, "w", encoding="utf-8") as fh:
            json.dump(tl, fh)

        # 1. the page
        n = build_page().write(os.path.join(tmp, "ui.html"))
        print(f"ui.html: {n} data-in elements")
        if n != 19:   # 3 panels x 2, 2 buttons x 2, screen, hline, vline, ruler svg, svg, layer x 2, sprite x 2
            fails.append(f"ui.html has {n} data-in elements, want 19")
        for variant in ("overflow", "dirty_screen"):
            build_page(variant).write(os.path.join(tmp, f"ui_{variant}.html"))

        # 2. ui-render: pass, then two failures
        ui_tool = os.path.join(SCRIPTS, "ui-render.mjs")
        out = os.path.join(tmp, "ui_out")
        code, log = run([ui_tool, "--html", os.path.join(tmp, "ui.html"), "--timeline", tl_path, "--out", out,
                         "--scale", str(SCALE), "--font", "CheckFont"], tmp)
        print(log.strip())
        if code != 0:
            fails.append(f"ui-render exit {code} on the good page")
        else:
            want = {"ui.png": (UI[0] * SCALE, UI[1] * SCALE), "ui_base.png": (UI[0] * SCALE, UI[1] * SCALE),
                    "ui_check.png": (UI[0] * SCALE, UI[1] * SCALE), "chip.png": (40 * SCALE, 16 * SCALE)}
            for f, size in want.items():
                p = os.path.join(out, f)
                if not os.path.exists(p):
                    fails.append(f"ui-render wrote no {f}")
                elif png_size(p) != size:
                    fails.append(f"{f} is {png_size(p)}, want {size}")
            if "contract:" not in log:
                fails.append("ui-render printed no contract line")
        for variant, needle in (("overflow", "outside"), ("dirty_screen", f"{4 * SCALE * 4 * SCALE} px differ from #000000")):
            vout = os.path.join(tmp, f"ui_out_{variant}")
            code, log = run([ui_tool, "--html", os.path.join(tmp, f"ui_{variant}.html"), "--timeline", tl_path,
                             "--out", vout, "--scale", str(SCALE), "--font", "CheckFont"], tmp)
            if code != 1:
                fails.append(f"ui-render exit {code} on the {variant} page, want 1")
            if needle not in log:
                fails.append(f"ui-render log for {variant} lacks '{needle}': {log.strip()[-300:]}")
            left = [f for f in os.listdir(vout)] if os.path.isdir(vout) else []
            if left:
                fails.append(f"ui-render left files behind on the {variant} failure: {left}")
            print(f"ui-render {variant}: exit {code}, {len(left)} files left (want exit 1, 0 files)")

        # 3. frames-render: determinism, sizes, bbox, contact; then a failing page
        with open(os.path.join(tmp, "comp.html"), "w", encoding="utf-8") as fh:
            fh.write(COMP_PAGE % (FONT_CSS, ""))
        with open(os.path.join(tmp, "comp_bad.html"), "w", encoding="utf-8") as fh:
            fh.write(COMP_PAGE % (FONT_CSS, "<script>window.BREAK_AT = 3;</script>"))
        with open(os.path.join(tmp, "comp_gap.html"), "w", encoding="utf-8") as fh:
            fh.write(COMP_PAGE % (FONT_CSS, "<script>window.GAP_TC = true;</script>"))
        fr_tool = os.path.join(SCRIPTS, "frames-render.mjs")
        sums = []
        for i in (1, 2):
            fout = os.path.join(tmp, f"frames_{i}")
            code, log = run([fr_tool, "--page", os.path.join(tmp, "comp.html"), "--timeline", tl_path, "--out", fout,
                             "--pages", "2", "--contact", "sheet.png", "--contact-every", "3", "--cols", "2"], tmp)
            if i == 1:
                print(log.strip())
            if code != 0:
                fails.append(f"frames-render exit {code} (run {i}): {log.strip()[-400:]}")
                continue
            for seq, size in (("main", COMP), ("tc", (40, 12))):
                frames = sorted(f for f in os.listdir(os.path.join(fout, seq)) if f.endswith(".png"))
                if frames != [f"{f:04d}.png" for f in range(1, FRAMES + 1)]:
                    fails.append(f"{seq}: frames {frames[:3]}.. ({len(frames)}), want 0001..{FRAMES:04d}")
                elif png_size(os.path.join(fout, seq, "0001.png")) != size:
                    fails.append(f"{seq}/0001.png is {png_size(os.path.join(fout, seq, '0001.png'))}, want {size}")
            with open(os.path.join(fout, "comp_bbox.json"), encoding="utf-8") as fh:
                bb = json.load(fh)
            if len(bb["frames"]) != FRAMES or bb["frames"][2]["dot"] != [8, 10, 16, 18]:
                fails.append(f"comp_bbox.json wrong: {bb['frames'][:3]}")
            if not os.path.exists(os.path.join(fout, "sheet.png")):
                fails.append("no contact sheet written")
            if any(f.endswith(".part") for _dp, _dn, fn in os.walk(fout) for f in fn):
                fails.append("temp .part files left after a passing run")
            sums.append(md5_tree(fout))
        if len(sums) == 2:
            if sums[0] != sums[1]:
                diff = [k for k in sums[0] if sums[0].get(k) != sums[1].get(k)]
                fails.append(f"re-render differs: {diff[:5]}")
            else:
                print(f"determinism: {len(sums[0])} files byte-identical across two renders")
        bout = os.path.join(tmp, "frames_bad")
        code, log = run([fr_tool, "--page", os.path.join(tmp, "comp_bad.html"), "--timeline", tl_path, "--out", bout,
                         "--pages", "2"], tmp)
        left = [os.path.join(dp, f) for dp, _dn, fn in os.walk(bout) for f in fn]
        if code != 1:
            fails.append(f"frames-render exit {code} on the failing page, want 1")
        if "deliberate failure on frame 3" not in log:
            fails.append(f"frames-render log lacks the page's check: {log.strip()[-300:]}")
        if left:
            fails.append(f"frames-render left files behind on failure: {[os.path.basename(p) for p in left][:5]}")
        print(f"frames-render failing page: exit {code}, {len(left)} files left (want exit 1, 0 files)")

        # a sequence with gaps: tc only on odd frames fails a full run, passes --frames 1,3,5
        gout = os.path.join(tmp, "frames_gap")
        code, log = run([fr_tool, "--page", os.path.join(tmp, "comp_gap.html"), "--timeline", tl_path, "--out", gout,
                         "--pages", "2"], tmp)
        left = [os.path.join(dp, f) for dp, _dn, fn in os.walk(gout) for f in fn]
        needle = "sequence tc: 5 of 10 requested frames missing: 2, 4, 6, 8, 10"
        if code != 1:
            fails.append(f"frames-render exit {code} on a page whose tc sequence skips even frames, want 1")
        if needle not in log:
            fails.append(f"frames-render log lacks '{needle}': {log.strip()[-300:]}")
        if left:
            fails.append(f"frames-render left files behind on the gap failure: {[os.path.basename(p) for p in left][:5]}")
        print(f"frames-render gap page: exit {code}, {len(left)} files left (want exit 1, 0 files)")
        pout = os.path.join(tmp, "frames_gap_partial")
        code, log = run([fr_tool, "--page", os.path.join(tmp, "comp_gap.html"), "--timeline", tl_path, "--out", pout,
                         "--frames", "1,3,5"], tmp)
        got = sorted(os.listdir(os.path.join(pout, "tc"))) if os.path.isdir(os.path.join(pout, "tc")) else []
        if code != 0 or got != ["0001.png", "0003.png", "0005.png"]:
            fails.append(f"frames-render --frames 1,3,5 on the gap page: exit {code}, tc {got}, want exit 0 and "
                         f"0001/0003/0005: {log.strip()[-300:]}")
        print(f"frames-render gap page --frames 1,3,5: exit {code}, tc {len(got)} frames (want exit 0, 3 frames)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for f in fails:
        print("FAIL: " + f)
    print("check_node: " + ("ok" if not fails else f"{len(fails)} failure(s)"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
