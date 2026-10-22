"""verify_final.py: probe and scan a delivered MP4 against the plan. Owner: checker. Kit venv (numpy) + ffmpeg/ffprobe.

Checks: ffprobe frame count (decoded), duration, codecs, profile, pixel format, colour tags, size, fps;
per-frame mean luma (decoded from the MP4, or from the PNG frames with --frames-dir); black frames; the
biggest frame-to-frame luma steps (listed for the director: each must be a designed event); audio
cross-correlation lag against the WAV (must be 0 samples) and the decoded sample count.
Writes a JSON report (inside the cwd: filmkit.outpath.under refuses anything else) and exits 1 on any
failed expectation.

CLI:
  python -B verify_final.py --mp4 renders/film.mp4 --wav build/sound.wav --fps 30 --n 360 --duration 12.0
      [--frames-dir renders/frames] [--steps 10] [--black-below 2] [--json renders/verify.json]
      [--expect-size 1920x1080]
"""
import sys
sys.dont_write_bytecode = True
import argparse
import json
import math
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from filmkit import measure, outpath  # noqa: E402

FFPROBE = os.environ.get("FFPROBE", "ffprobe")


def probe(mp4):
    """-> {'nb_frames', 'duration', 'width', 'height', 'fps', 'vcodec', 'profile', 'pix_fmt',
    'color_space', 'color_transfer', 'color_primaries', 'acodec', 'sample_rate', 'channels'}.
    nb_frames counts decoded frames (-count_frames)."""
    r = subprocess.run([FFPROBE, "-v", "error", "-count_frames", "-show_entries",
                        "stream=codec_type,codec_name,profile,width,height,pix_fmt,color_space,color_transfer,"
                        "color_primaries,avg_frame_rate,nb_read_frames,sample_rate,channels:format=duration",
                        "-of", "json", mp4], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"ffprobe failed on {mp4}: {r.stderr.strip()}")
    doc = json.loads(r.stdout)
    out = {"nb_frames": 0, "duration": float(doc.get("format", {}).get("duration") or 0.0), "width": 0, "height": 0,
           "fps": 0.0, "vcodec": None, "profile": None, "pix_fmt": None, "color_space": None, "color_transfer": None,
           "color_primaries": None, "acodec": None, "sample_rate": None, "channels": 0}
    for s in doc.get("streams", []):
        if s.get("codec_type") == "video" and out["vcodec"] is None:
            num, den = (s.get("avg_frame_rate") or "0/1").split("/")
            out.update(nb_frames=int(s.get("nb_read_frames") or 0), width=int(s.get("width") or 0),
                       height=int(s.get("height") or 0), fps=float(num) / float(den) if float(den) else 0.0,
                       vcodec=s.get("codec_name"), profile=s.get("profile"), pix_fmt=s.get("pix_fmt"),
                       color_space=s.get("color_space"), color_transfer=s.get("color_transfer"),
                       color_primaries=s.get("color_primaries"))
        elif s.get("codec_type") == "audio" and out["acodec"] is None:
            out.update(acodec=s.get("codec_name"), sample_rate=int(s.get("sample_rate") or 0),
                       channels=int(s.get("channels") or 0))
    return out


def luma_scan(mp4_or_dir, n, size=(96, 54), fps=30):
    """-> [mean luma per frame] via ffmpeg gray rawvideo (an MP4, or a ####.png folder)."""
    if os.path.isfile(mp4_or_dir):
        lum = measure.luma_scan(mp4_or_dir, n, size, fps)
    else:
        lum = measure.luma_scan(mp4_or_dir, range(1, n + 1), size, fps)
    return [lum[f] for f in sorted(lum)]


def verify(mp4, wav, fps, n, duration, frames_dir=None, steps=10, black_below=2.0, expect_size=None):
    """-> report dict with 'ok' and 'failures' (strings), 'probe', 'luma' {min, max, black, steps}, 'audio'."""
    failures = []
    p = probe(mp4)
    rep = {"mp4": mp4, "probe": p, "expect": {"fps": fps, "n": n, "duration": duration}}

    def expect(name, got, want, ok=None):
        good = (got == want) if ok is None else ok
        if not good:
            failures.append(f"{name}: {got!r}, expected {want!r}")

    expect("frames", p["nb_frames"], n)
    expect("duration", round(p["duration"], 3), duration, abs(p["duration"] - duration) <= 1.0 / fps + 1e-6)
    expect("fps", p["fps"], fps, abs(p["fps"] - fps) < 1e-6)
    expect("vcodec", p["vcodec"], "h264")
    expect("profile", p["profile"], "High")
    expect("pix_fmt", p["pix_fmt"], "yuv420p")
    for k in ("color_space", "color_transfer", "color_primaries"):
        expect(k, p[k], "bt709")
    if expect_size:
        expect("size", (p["width"], p["height"]), tuple(expect_size))
    lum = luma_scan(frames_dir or mp4, n, fps=fps)
    lumas = {f + 1: v for f, v in enumerate(lum)}
    black = measure.black_frames(lumas, black_below)
    big = measure.biggest_steps(lumas, steps)
    rep["luma"] = {"source": frames_dir or mp4, "n": len(lum), "min": round(min(lum), 1) if lum else None,
                   "max": round(max(lum), 1) if lum else None, "black": black,
                   "steps": [[f, round(d, 1)] for f, d in big]}
    expect("luma frames", len(lum), n)
    if black:
        failures.append(f"black frames: {black[:10]}{'...' if len(black) > 10 else ''} (mean luma < {black_below})")
    if wav:
        expect("acodec", p["acodec"], "aac")
        expect("sample_rate", p["sample_rate"], 48000)
        sr = 48000
        lag = measure.audio_lag(mp4, wav, sr, duration)
        got = len(measure.decode_audio(mp4, sr))
        want = int(math.floor(duration * sr + 0.5))      # sound.mix.Clock.n, never Python round()
        rep["audio"] = {"wav": wav, "lag_samples": lag, "samples": got, "expected": want, "sr": sr}
        expect("audio lag (samples)", lag, 0)
        expect("audio samples", got, want, want <= got <= want + 4096)
    else:
        rep["audio"] = None
    rep["failures"] = failures
    rep["ok"] = not failures
    return rep


def _size(s):
    w, h = s.lower().split("x")
    return int(w), int(h)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mp4", required=True)
    ap.add_argument("--wav")
    ap.add_argument("--fps", type=int, required=True)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--duration", type=float, required=True)
    ap.add_argument("--frames-dir")
    ap.add_argument("--steps", type=int, default=10)
    ap.add_argument("--black-below", type=float, default=2.0)
    ap.add_argument("--json")
    ap.add_argument("--expect-size", type=_size)
    a = ap.parse_args(argv)
    if a.json:
        a.json = outpath.under(os.getcwd(), a.json)
    rep = verify(a.mp4, a.wav, a.fps, a.n, a.duration, a.frames_dir, a.steps, a.black_below, a.expect_size)
    if a.json:
        os.makedirs(os.path.dirname(a.json), exist_ok=True)
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=1)
    p = rep["probe"]
    print(f"{a.mp4}: {p['nb_frames']} frames, {p['duration']:.3f} s, {p['width']}x{p['height']} {p['fps']:g} fps,"
          f" {p['vcodec']} {p['profile']} {p['pix_fmt']} {p['color_space']}/{p['color_transfer']}/{p['color_primaries']},"
          f" audio {p['acodec']} {p['sample_rate']} Hz x{p['channels']}")
    L = rep["luma"]
    print(f"luma: {L['n']} frames, mean {L['min']}..{L['max']}, black {len(L['black'])}; biggest steps: "
          + ", ".join(f"f{f} {d}" for f, d in L["steps"]))
    if rep["audio"]:
        A = rep["audio"]
        print(f"audio: lag {A['lag_samples']} samples, {A['samples']} samples decoded (expected {A['expected']})")
    for f in rep["failures"]:
        print(f"FAIL {f}")
    print("VERIFY: " + ("OK" if rep["ok"] else f"{len(rep['failures'])} failures"))
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
