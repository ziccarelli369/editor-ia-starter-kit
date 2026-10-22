"""contact.py: contact sheets and labelled grids with Pillow (never ffmpeg drawtext). Owner: checker.
Runs in the kit venv (Pillow).

Layout: cells of `cell` px (image scaled to fit, padded with the background), a label strip of
label_h px under each, `gap` px around and between cells. Sheet size = cols * cell_w + (cols + 1) * gap
by rows * (cell_h + label_h) + (rows + 1) * gap. Outputs go to a temp name and are renamed on success.
Colours (background, label) are neutral placeholders; --bg and --fg override them.

CLI:
  python -B contact.py --out sheet.png --cols 6 [--cell 640x360] [--label-h 40] [--font path]
      img1.png[:label] img2.png[:label] ...
  python -B contact.py --seq renders/frames --every 15 --fps 30 --out sheet.png [--cols 6]
      [--label "f{f} {t:.2f}s"] [--last]
  python -B contact.py --strips renders/animatic --every 2 --per-sheet 60 --cols 10 --out-prefix strip
"""
import sys
sys.dont_write_bytecode = True
import argparse
import os

from PIL import Image, ImageDraw, ImageFont

BG = (20, 20, 20)
FG = (232, 232, 232)
FONTS = ("consola.ttf", "DejaVuSansMono.ttf", "arial.ttf", "DejaVuSans.ttf")


def _font(path=None, size=None):
    """-> a truetype font (env FILM_FONT, then common system fonts), or Pillow's default."""
    size = size or 18
    for cand in ([path] if path else []) + [os.environ.get("FILM_FONT")] + list(FONTS):
        if not cand:
            continue
        try:
            return ImageFont.truetype(cand, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _fit(img, cell, bg=BG):
    """-> img scaled to fit cell (keep aspect), centred on a bg canvas of cell size."""
    img = img.convert("RGB")
    s = min(cell[0] / img.width, cell[1] / img.height)
    w, h = max(1, round(img.width * s)), max(1, round(img.height * s))
    out = Image.new("RGB", cell, bg)
    out.paste(img.resize((w, h), Image.LANCZOS), ((cell[0] - w) // 2, (cell[1] - h) // 2))
    return out


def label_image(img, text, label_h=40, font=None, bg=BG, fg=FG):
    """-> new image: img over a label strip of label_h px with text."""
    img = img.convert("RGB")
    out = Image.new("RGB", (img.width, img.height + label_h), bg)
    out.paste(img, (0, 0))
    if label_h > 0 and text:
        fnt = font if isinstance(font, ImageFont.FreeTypeFont) else _font(font, max(10, int(label_h * 0.55)))
        d = ImageDraw.Draw(out)
        box = d.textbbox((0, 0), text, font=fnt)
        d.text((8, img.height + (label_h - (box[3] - box[1])) / 2 - box[1]), text, font=fnt, fill=fg)
    return out


def _tile(images, out, cols, gap, bg):
    """images: [PIL images of one size]. Tiles by cols with gap. Writes out (temp then rename)."""
    if not images:
        raise SystemExit("contact: nothing to tile")
    cw, ch = images[0].size
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw + (cols + 1) * gap, rows * ch + (rows + 1) * gap), bg)
    for i, im in enumerate(images):
        sheet.paste(im, (gap + (i % cols) * (cw + gap), gap + (i // cols) * (ch + gap)))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    tmp = out + ".part.png"
    sheet.save(tmp)
    os.replace(tmp, out)
    return out


def contact_sheet(items, out, cols=6, cell=(640, 360), label_h=40, gap=4, font=None, bg=BG, fg=FG):
    """items: [(path, label)]. Scale each to cell (keep aspect, pad), add its label, tile by cols. -> out."""
    missing = [p for p, _ in items if not os.path.exists(p)]
    if missing:
        raise SystemExit(f"contact: missing {len(missing)} image(s), first: {missing[:3]}")
    fnt = _font(font, max(10, int(label_h * 0.55)))
    images = []
    for path, label in items:
        with Image.open(path) as im:
            images.append(label_image(_fit(im, cell, bg), label, label_h, fnt, bg, fg))
    return _tile(images, out, cols, gap, bg)


def _seq_frames(seq_dir, every, last, limit=None):
    """-> sorted frame numbers present in seq_dir (####.png), every n-th plus the last when last=True."""
    present = sorted(int(f[:4]) for f in os.listdir(seq_dir) if len(f) == 8 and f.endswith(".png") and f[:4].isdigit())
    if not present:
        raise SystemExit(f"contact: no ####.png in {seq_dir}")
    if limit:
        present = [f for f in present if limit[0] <= f <= limit[1]]
    chosen = [f for f in present if (f - present[0]) % every == 0]
    if last and present[-1] not in chosen:
        chosen.append(present[-1])
    return chosen


def sequence_sheet(seq_dir, every, fps, out, cols=6, cell=(384, 216), label="f{f} {t:.2f}s", last=True,
                   label_h=24, gap=4, font=None):
    """Every n-th frame of a 1-based 4-digit PNG sequence (plus the last when last=True). -> out."""
    frames = _seq_frames(seq_dir, every, last)
    items = [(os.path.join(seq_dir, f"{f:04d}.png"), label.format(f=f, t=(f - 1) / fps, ms=(f - 1) * 1000 / fps))
             for f in frames]
    return contact_sheet(items, out, cols, cell, label_h, gap, font)


def filmstrips(seq_dir, every=2, per_sheet=60, cols=10, cell=(384, 216), out_prefix="strip", fps=30,
               label_h=24, gap=2, font=None):
    """Sheets of every n-th frame with frame and ms labels: <out_prefix>_1.png, _2.png, ... -> [paths]."""
    frames = _seq_frames(seq_dir, every, last=False)
    paths = []
    for s in range(0, len(frames), per_sheet):
        chunk = frames[s:s + per_sheet]
        items = [(os.path.join(seq_dir, f"{f:04d}.png"), f"f{f}  {(f - 1) * 1000 / fps:.0f} ms") for f in chunk]
        paths.append(contact_sheet(items, f"{out_prefix}_{len(paths) + 1}.png", cols, cell, label_h, gap, font))
    return paths


def _size(s):
    w, h = s.lower().split("x")
    return int(w), int(h)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images", nargs="*", help="img.png[:label] ...")
    ap.add_argument("--out")
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--cell", type=_size, default=None)
    ap.add_argument("--label-h", type=int, default=None)
    ap.add_argument("--gap", type=int, default=None)
    ap.add_argument("--font")
    ap.add_argument("--seq", help="folder of ####.png")
    ap.add_argument("--every", type=int, default=15)
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--label", default="f{f} {t:.2f}s")
    ap.add_argument("--last", action="store_true")
    ap.add_argument("--strips", help="folder of ####.png -> filmstrip sheets")
    ap.add_argument("--per-sheet", type=int, default=60)
    ap.add_argument("--out-prefix", default="strip")
    a = ap.parse_args(argv)
    if a.strips:
        paths = filmstrips(a.strips, a.every, a.per_sheet, a.cols, a.cell or (384, 216), a.out_prefix, a.fps,
                           a.label_h if a.label_h is not None else 24, a.gap if a.gap is not None else 2, a.font)
        print("wrote " + ", ".join(paths))
        return 0
    if not a.out:
        ap.error("--out is required")
    if a.seq:
        out = sequence_sheet(a.seq, a.every, a.fps, a.out, a.cols, a.cell or (384, 216), a.label, a.last,
                             a.label_h if a.label_h is not None else 24, a.gap if a.gap is not None else 4, a.font)
    else:
        items = [(s.rsplit(":", 1) if ":" in s[2:] else (s, os.path.basename(s))) for s in a.images]
        items = [(p, lbl) for p, lbl in items]
        if not items:
            ap.error("give images, --seq or --strips")
        out = contact_sheet(items, a.out, a.cols, a.cell or (640, 360), a.label_h if a.label_h is not None else 40,
                            a.gap if a.gap is not None else 4, a.font)
    with Image.open(out) as im:
        print(f"wrote {out} ({im.width}x{im.height})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
