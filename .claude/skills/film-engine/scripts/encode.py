"""encode.py: PNG sequence + WAV -> MP4. Owner: checker. Standard library + ffmpeg/ffprobe on PATH.

H.264 High, CRF 17, preset slow, explicit BT.709 conversion (scale=out_color_matrix=bt709:out_range=tv)
and BT.709 tags, yuv420p, optional vignette, AAC 320k 48 kHz, -t duration, +faststart. Refuses to run when
a frame or the WAV is missing. --size WxH with --fit pad|crop|scale makes another aspect (9:16) from the
same frames. The MP4 is written to a temp name and renamed after a probe shows the frame count.

CLI:
  python -B encode.py --frames renders/frames --wav build/sound.wav --out renders/film.mp4
      --fps 30 --n 360 --duration 12.0 [--crf 17] [--preset slow] [--vignette PI/5]
      [--size 1080x1920 --fit crop] [--no-audio] [--audio-kbps 320]
"""
import sys
sys.dont_write_bytecode = True
import argparse
import json
import os
import subprocess

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE", "ffprobe")


def missing_frames(frames_dir, n):
    """-> [frame numbers] without a ####.png in frames_dir."""
    return [f for f in range(1, n + 1) if not os.path.exists(os.path.join(frames_dir, f"{f:04d}.png"))]


def video_filter(vignette=None, size=None, fit="pad"):
    """-> the -vf chain: [vignette,] scale (BT.709 matrix, tv range[, geometry]) [,pad|crop], format=yuv420p,
    setparams (BT.709 primaries, transfer, matrix, tv range on every frame)."""
    chain = []
    if vignette:
        chain.append(f"vignette=angle={vignette}:mode=forward")
    conv = "out_color_matrix=bt709:out_range=tv"
    if size:
        w, h = (v - v % 2 for v in size)       # libx264 yuv420p needs even sizes
        if fit == "scale":
            chain.append(f"scale={w}:{h}:{conv}")
        elif fit == "crop":
            chain.append(f"scale={w}:{h}:force_original_aspect_ratio=increase:{conv}")
            chain.append(f"crop={w}:{h}")
        else:
            chain.append(f"scale={w}:{h}:force_original_aspect_ratio=decrease:{conv}")
            chain.append(f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2")
    else:
        chain.append(f"scale=trunc(iw/2)*2:trunc(ih/2)*2:{conv}")     # an odd PNG size would crash libx264
    chain.append("format=yuv420p")
    # the frame tags travel with the graph: without setparams the encoder writes only the matrix (ffmpeg 8.1)
    chain.append("setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv")
    return ",".join(chain)


def ffmpeg_args(frames_dir, wav, out, fps, duration, crf=17, preset="slow", vignette=None, size=None,
                fit="pad", audio_kbps=320):
    """-> the ffmpeg argument list (for tests and logs). wav None = no audio track."""
    args = [FFMPEG, "-y", "-loglevel", "error", "-framerate", str(fps), "-start_number", "1",
            "-i", os.path.join(frames_dir, "%04d.png")]
    if wav:
        args += ["-i", wav]
    args += ["-vf", video_filter(vignette, size, fit),
             "-c:v", "libx264", "-profile:v", "high", "-preset", preset, "-crf", str(crf), "-r", str(fps),
             "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]
    if wav:
        args += ["-c:a", "aac", "-b:a", f"{audio_kbps}k", "-ar", "48000"]
    args += ["-t", str(duration), "-movflags", "+faststart", out]
    return args


def probe_frames(path):
    """-> (nb_frames, duration_s) of the first video stream (container values, no decode)."""
    r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=nb_frames:format=duration", "-of", "json", path], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"ffprobe failed on {path}: {r.stderr.strip()}")
    doc = json.loads(r.stdout)
    nb = int((doc.get("streams") or [{}])[0].get("nb_frames") or 0)
    return nb, float(doc.get("format", {}).get("duration") or 0.0)


def encode(frames_dir, wav, out, fps, n, duration, crf=17, preset="slow", vignette=None, size=None,
           fit="pad", audio_kbps=320):
    """Run ffmpeg. Raises SystemExit with the missing list when inputs are incomplete. -> out size bytes."""
    miss = missing_frames(frames_dir, n)
    if miss:
        raise SystemExit(f"{len(miss)} frames missing in {frames_dir}, first: {miss[:5]}")
    if wav and not os.path.exists(wav):
        raise SystemExit(f"missing {wav}")
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    tmp = os.path.splitext(out)[0] + ".part.mp4"
    args = ffmpeg_args(frames_dir, wav, tmp, fps, duration, crf, preset, vignette, size, fit, audio_kbps)
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode or not os.path.exists(tmp):
        raise SystemExit(f"ffmpeg failed ({r.returncode}): {r.stderr.strip()}")
    nb, dur = probe_frames(tmp)
    if nb != n:
        os.remove(tmp)
        raise SystemExit(f"encode: {nb} frames in the MP4, expected {n}")
    os.replace(tmp, out)
    return os.path.getsize(out)


def _size(s):
    w, h = s.lower().split("x")
    return int(w), int(h)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--frames", required=True)
    ap.add_argument("--wav")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, required=True)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--duration", type=float, required=True)
    ap.add_argument("--crf", type=int, default=17)
    ap.add_argument("--preset", default="slow")
    ap.add_argument("--vignette", default=None, help="ffmpeg vignette angle, e.g. PI/5")
    ap.add_argument("--size", type=_size, default=None)
    ap.add_argument("--fit", choices=("pad", "crop", "scale"), default="pad")
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--audio-kbps", type=int, default=320)
    a = ap.parse_args(argv)
    if not a.no_audio and not a.wav:
        ap.error("--wav is required unless --no-audio")
    size = encode(a.frames, None if a.no_audio else a.wav, a.out, a.fps, a.n, a.duration, a.crf, a.preset,
                  a.vignette, a.size, a.fit, a.audio_kbps)
    print(f"wrote {a.out} ({size / 1e6:.1f} MB, {a.n} frames, {a.duration} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
