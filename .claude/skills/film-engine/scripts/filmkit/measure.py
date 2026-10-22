"""measure: pixel measurements of rendered images. Owner: checker. Needs numpy and ffmpeg (kit venv).

Not imported by check.py (it takes these results as data). Blender's stills.py imports it for the
region maths (measure_arrays and the mask helpers, numpy only); the ffmpeg readers stay venv-side.
Boxes are [x0, y0, x1, y1] in the source image's px. Caches carry a signature
of every frame's size and mtime plus the parameters, so a rerun is free.
PNGs are read through ffmpeg (rawvideo pipes), so no image library is needed.
"""
import hashlib
import json
import os
import subprocess

import numpy as np

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
LUMA = (0.2126, 0.7152, 0.0722)


def erode_mask(m, n):
    """Erode a bool (h, w) mask by n px (4-neighbour steps). The frame border is padded with its own
    edge value, so a region that touches the frame edge keeps that edge (no wrap-around)."""
    for _ in range(int(n)):
        p = np.pad(m, 1, mode="edge")
        m = m & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
    return m


def dilate_mask(m, n):
    """Dilate a bool (h, w) mask by n px (the dual of erode_mask)."""
    return ~erode_mask(~m, n)


def band_region(msk8, band):
    """-> bool (h, w): pixels of an 8-bit class mask (h, w, 3) whose channel lies in band
    (channel 'R'|'G'|'B' or 0..2, lo, hi), lo <= v < hi."""
    ch, lo, hi = band
    c = msk8[..., "RGB".index(ch) if isinstance(ch, str) else int(ch)]
    return (c >= lo) & (c < hi)


def class_erosion(reg, erode, thin_px):
    """-> how many px to erode a class band: `erode`, or min(erode, 1) for a thin class. A class is thin when
    its band eroded by 1 px holds fewer than thin_px pixels (the raw band count is not used: the anti-aliased
    ramps between neighbouring levels on the same channel fall into every band they cross, so a 3 px belt
    bar reads about 290 raw px of which 40 survive 1 px; 2 px leaves 0 and the class never reaches the
    report). thin_px None or 0 turns the rule off."""
    if not thin_px or erode <= 1:
        return int(erode)
    return int(erode) if int(erode_mask(reg, 1).sum()) >= int(thin_px) else 1


def measure_arrays(img, msk, bands, target_srgb=None, erode=2, hot=245, grow=3, hero="body", studio="studio",
                   min_px=30, studio_guard=8, thin_px=200):
    """The region measurements of a beauty frame against its class mask, both (h, w, 3) float 0..255,
    top-down. bands: {class: (channel, lo, hi)} (materials.mask_bands).
    colour: per class the pixel count and sRGB median (and 'err' vs target_srgb (r, g, b) 0..255 when
    given) over the band eroded by `erode` px (a thin class, under thin_px after 1 px, by 1 px only:
    class_erosion; never the studio class); classes under min_px are left out.
    silhouette: hero band width/height as frame fractions (columns/rows with >= 2 pixels).
    hot: pixels with a channel >= hot outside the hero grown by grow px (count, bbox, max outside).
    void: studio band share (top = per-column run from the top edge to the first non-studio pixels,
    all = every studio pixel). studio_luma: luma median over the guarded studio region.
    The studio class is eroded by max(erode, studio_guard) px: a motion-blurred edge of a bright class
    on the same channel sweeps through the studio band (its ramp crosses the band's levels), and the
    false ring it leaves is a few px wide and next to pixels of no class, so a 2 px erosion keeps it; the
    guard removes every studio pixel within studio_guard px of any pixel outside the band.
    -> {'colour', 'silhouette', 'hot', 'void', 'studio_luma', 'max'}."""
    img = np.asarray(img, float)
    msk = np.asarray(msk, float)
    h, w = img.shape[:2]
    guard = max(int(erode), int(studio_guard))
    colour = {}
    for name, band in bands.items():
        raw = band_region(msk, band)
        reg = erode_mask(raw, guard if name == studio else class_erosion(raw, erode, thin_px))
        n = int(reg.sum())
        if n < min_px:
            continue
        med = np.median(img[reg], axis=0)
        entry = {"n": n, "median": [round(float(v), 1) for v in med]}
        if target_srgb is not None:
            entry["err"] = [round(float(v - t), 1) for v, t in zip(med, target_srgb)]
        colour[name] = entry
    out = {"colour": colour, "silhouette": None, "hot": None, "void": None, "studio_luma": None,
           "max": round(float(img.max()), 1)}
    hero_px = band_region(msk, bands[hero]) if hero in bands else np.zeros((h, w), bool)
    cols, rows = np.nonzero(hero_px.sum(axis=0) >= 2)[0], np.nonzero(hero_px.sum(axis=1) >= 2)[0]
    if len(cols):
        out["silhouette"] = {"mask_w": round(float(cols[-1] - cols[0] + 1) / w, 4),
                             "mask_h": round(float(rows[-1] - rows[0] + 1) / h, 4)}
    outside = ~dilate_mask(hero_px, grow)
    hot_px = (img.max(axis=2) >= hot) & outside
    ys, xs = np.nonzero(hot_px)
    out["hot"] = {"n": int(hot_px.sum()),
                  "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None,
                  "max_outside": round(float(img[outside].max()), 1) if outside.any() else None}
    if studio in bands:
        st = band_region(msk, bands[studio])
        ns = ~st
        ns2 = ns[:-1] & ns[1:]
        first = np.where(ns2.any(axis=0), ns2.argmax(axis=0), h)
        out["void"] = {"top": round(float(first.mean()) / h, 4), "all": round(float(st.mean()), 4)}
        st_e = erode_mask(st, guard)
        if st_e.sum() >= min_px:
            out["studio_luma"] = round(float(np.median(img[st_e] @ np.array(LUMA))), 1)
    return out


def _path(pattern, f):
    return pattern % f if "%" in pattern else os.path.join(pattern, f"{f:04d}.png")


def sequence_signature(pattern, frames, params):
    """-> md5 hex of 'size:mtime' of every frame file plus repr(params). pattern: '<dir>/%04d.png' or a folder."""
    sig = []
    for f in frames:
        st = os.stat(_path(pattern, f))
        sig.append(f"{st.st_size}:{int(st.st_mtime)}")
    sig.append(repr(params))
    return hashlib.md5("|".join(sig).encode()).hexdigest()


def _decode(src, frames, size, pix_fmt, fps=30):
    """Stream frames of a PNG sequence (pattern or folder) or a video file through ffmpeg. -> uint8 array
    (n, h, w, c). frames: the 1-based list for a sequence (must be contiguous), or the count for a video."""
    w, h = size
    chans = {"gray": 1, "rgb24": 3}[pix_fmt]
    if os.path.isfile(src):
        n = int(frames)
        cmd = [FFMPEG, "-v", "error", "-i", src, "-frames:v", str(n)]
    else:
        frames = list(frames)
        n = len(frames)
        pattern = src if "%" in src else os.path.join(src, "%04d.png")
        cmd = [FFMPEG, "-v", "error", "-framerate", str(fps), "-start_number", str(frames[0]), "-i", pattern,
               "-frames:v", str(n)]
    cmd += ["-vf", f"scale={w}:{h}:flags=area", "-f", "rawvideo", "-pix_fmt", pix_fmt, "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode:
        raise RuntimeError(f"ffmpeg decode failed: {r.stderr.decode(errors='replace').strip()}")
    buf = np.frombuffer(r.stdout, np.uint8)
    got = len(buf) // (w * h * chans)
    if got < n:
        raise RuntimeError(f"ffmpeg decoded {got} frames of {n} from {src}")
    return buf[:n * w * h * chans].reshape(n, h, w, chans)


def _open(mask, px):
    """Morphological opening (erosion then dilation) with a (2px+1)^2 square."""
    if px <= 0:
        return mask
    h, w = mask.shape
    e = mask.copy()
    for _ in range(px):
        core = np.ones_like(e)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                core[1:-1, 1:-1] &= e[1 + dy:h - 1 + dy, 1 + dx:w - 1 + dx]
        core[0], core[-1], core[:, 0], core[:, -1] = False, False, False, False
        e = core
    for _ in range(px):
        d = e.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                d[1:-1, 1:-1] |= e[1 + dy:h - 1 + dy, 1 + dx:w - 1 + dx]
        e = d
    return e


def content_bboxes(pattern, frames, size=(960, 540), level=150, rule="R>=B", opening=3,
                   ignore=(), cache=None, fps=30, source_size=None):
    """Threshold 'content' per frame of a PNG sequence (ffmpeg rawvideo pipe at `size`).

    rule: 'R>=B' | 'any' | callable(rgb uint8 HxWx3) -> bool mask; the mask is AND-ed with max(RGB) > level.
    opening: px of a morphological opening (3 = one 3x3 pass). ignore: [(t0, t1, t_use, fps)] windows that
    take the box of frame(t_use) instead. source_size: (w, h) of the source frames (default: the first PNG's
    size read through ffprobe), so boxes come back in source px.
    -> {frame: [x0, y0, x1, y1] in source px | None}; writes/reads cache JSON when given.
    """
    frames = list(frames)
    params = (size, level, rule if isinstance(rule, str) else "callable", opening, list(ignore))
    sig = sequence_signature(pattern, frames, params)
    if cache and os.path.exists(cache):
        with open(cache, encoding="utf-8") as fh:
            old = json.load(fh)
        if old.get("signature") == sig:
            return {int(k): v for k, v in old["frames"].items()}
    sw, sh = source_size or _png_size(_path(pattern, frames[0]))
    w, h = size
    sx, sy = sw / w, sh / h
    arr = _decode(pattern, frames, size, "rgb24", fps)
    raw = {}
    for i, f in enumerate(frames):
        a = arr[i]
        m = a.max(axis=2) > level
        if rule == "R>=B":
            m &= a[:, :, 0] >= a[:, :, 2]
        elif callable(rule):
            m &= rule(a)
        m = _open(m, max(0, (opening - 1) // 2))
        ys, xs = np.nonzero(m)
        raw[f] = None if len(xs) == 0 else [float(xs.min() * sx), float(ys.min() * sy),
                                            float((xs.max() + 1) * sx), float((ys.max() + 1) * sy)]
    boxes = {}
    for f in frames:
        t = (f - 1) / fps
        src = f
        for t0, t1, tc, ifps in ignore:
            if t0 <= t < t1:
                src = int(np.floor(tc * ifps + 0.5)) + 1
        boxes[f] = raw.get(src, raw[f])
    if cache:
        out = {"signature": sig, "level": level, "size": list(size), "ignore": list(ignore),
               "units": f"source px ({sw} x {sh}), x0 y0 x1 y1", "frames": {str(k): v for k, v in boxes.items()}}
        tmp = cache + ".part"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=0)
        os.replace(tmp, cache)
    return boxes


def _png_size(path):
    """-> (w, h) from the PNG header (IHDR)."""
    with open(path, "rb") as fh:
        head = fh.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {path}")
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def luma_scan(pattern, frames, size=(96, 54), fps=30):
    """-> {frame: mean luma 0..255} from a downscaled gray decode. pattern: a sequence folder/pattern with
    `frames` the 1-based list, or a video file with `frames` the count."""
    if os.path.isfile(pattern):
        n = int(frames)
        arr = _decode(pattern, n, size, "gray", fps)
        return {f: float(arr[f - 1].mean()) for f in range(1, n + 1)}
    frames = list(frames)
    arr = _decode(pattern, frames, size, "gray", fps)
    return {f: float(arr[i].mean()) for i, f in enumerate(frames)}


def black_frames(lumas, below=2.0):
    """-> [frames] whose mean luma is below `below`."""
    return [f for f in sorted(lumas) if lumas[f] < below]


def biggest_steps(lumas, n=10):
    """-> [(frame, delta)] of the n largest frame-to-frame luma steps (into that frame), biggest first."""
    fs = sorted(lumas)
    steps = [(f, abs(lumas[f] - lumas[p])) for p, f in zip(fs, fs[1:])]
    return sorted(steps, key=lambda s: -s[1])[:n]


def _read_rgb(path):
    """PNG -> float array (h, w, 3) 0..255 through ffmpeg (native size)."""
    w, h = _png_size(path)
    return _decode(path, 1, (w, h), "rgb24")[0].astype(np.float64)


def region_medians(beauty_png, mask_png, classes, erode=2, min_px=30, thin_px=200):
    """classes: {name: (channel, lo, hi)} 8-bit bands of the class mask (lo <= v < hi).
    -> {name: {'n', 'median': (r, g, b)}} over the beauty's pixels in each band, eroded by `erode` px (a thin
    class, under thin_px after 1 px, by 1 px only: class_erosion); classes under min_px are left out."""
    img, msk = _read_rgb(beauty_png), _read_rgb(mask_png)
    out = {}
    for name, band in classes.items():
        raw = band_region(msk, band)
        reg = erode_mask(raw, class_erosion(raw, erode, thin_px))
        n = int(reg.sum())
        if n < min_px:
            continue
        med = np.median(img[reg], axis=0)
        out[name] = {"n": n, "median": tuple(round(float(v), 1) for v in med)}
    return out


def mask_extent(mask_png, channel=2, thresh=90, min_px=2):
    """Silhouette from a class mask: columns and rows with >= min_px pixels above thresh.
    -> (width_share, height_share) of the image, or (0, 0) when empty."""
    msk = _read_rgb(mask_png)
    body = msk[..., channel] > thresh
    cols = np.nonzero(body.sum(axis=0) >= min_px)[0]
    rows = np.nonzero(body.sum(axis=1) >= min_px)[0]
    if len(cols) == 0 or len(rows) == 0:
        return 0.0, 0.0
    h, w = body.shape
    return float(cols[-1] - cols[0] + 1) / w, float(rows[-1] - rows[0] + 1) / h


def hot_pixels(beauty_png, mask_png, level=245, grow=3, hero_channel=2, hero_thresh=90):
    """-> (count, bbox [x0, y0, x1, y1] | None) of pixels with any channel >= level outside the hero mask
    grown by grow px."""
    img, msk = _read_rgb(beauty_png), _read_rgb(mask_png)
    hero = dilate_mask(msk[..., hero_channel] > hero_thresh, grow)
    hot = (img.max(axis=2) >= level) & ~hero
    ys, xs = np.nonzero(hot)
    bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None
    return int(hot.sum()), bbox


def decode_audio(path, sr=48000, seconds=None):
    """-> float32 mono samples of any media file's first audio track at sr (ffmpeg)."""
    cmd = [FFMPEG, "-v", "error", "-i", path]
    if seconds is not None:
        cmd += ["-t", str(seconds)]
    cmd += ["-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode:
        raise RuntimeError(f"ffmpeg audio decode failed: {r.stderr.decode(errors='replace').strip()}")
    return np.frombuffer(r.stdout, np.float32)


def audio_lag(mp4, wav, sr=48000, seconds=12.0, max_lag_s=0.5):
    """Decode the MP4 audio with ffmpeg and cross-correlate (FFT) with the WAV over the first `seconds`.
    -> lag in samples (0 = aligned; positive = the MP4 track starts later than the WAV)."""
    a = decode_audio(mp4, sr, seconds).astype(np.float64)
    b = decode_audio(wav, sr, seconds).astype(np.float64)
    n = min(len(a), len(b))
    if n == 0:
        raise ValueError("no audio to compare")
    a, b = a[:n], b[:n]
    if not a.any() or not b.any():
        return 0
    size = 1
    while size < 2 * n:
        size *= 2
    c = np.fft.irfft(np.fft.rfft(a, size) * np.conj(np.fft.rfft(b, size)), size)
    m = int(max_lag_s * sr)
    lags = np.concatenate([np.arange(0, m + 1), np.arange(-m, 0)])
    vals = np.concatenate([c[:m + 1], c[size - m:]])
    return int(lags[int(np.argmax(vals))])
