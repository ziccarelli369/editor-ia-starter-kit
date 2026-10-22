"""check_encode_venv.py: quick check of encode.py, verify_final.py and contact.py. Needs the kit venv
(Pillow, numpy) and ffmpeg/ffprobe on PATH.

Makes 30 PNG frames (320x180, a moving bar, a flash on frame 15) and a 1.0 s 48 kHz WAV (seeded noise
with clicks) in a temp folder, encodes them with encode.py (16:9 with audio, and a 9:16 crop without),
then verify_final.py must report 30 frames, 1.0 s, H.264 High, yuv420p, BT.709 tags, AAC 48 kHz, 0 black
frames, audio lag 0, and the biggest luma step at the flash. contact.py tiles every 10th frame plus the
last into a sheet of the documented size. encode.py must refuse a missing frame.
"""
import sys
sys.dont_write_bytecode = True
import json
import os
import subprocess
import tempfile
import wave

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
FAILS = []


def expect(cond, msg):
    if not cond:
        FAILS.append(msg)
        print("  FAIL " + msg)


def run(args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-B"] + args, capture_output=True, text=True, env=env)
    return r.returncode, (r.stdout + r.stderr).strip()


def make_frames(d, n=30, size=(320, 180)):
    os.makedirs(d, exist_ok=True)
    for f in range(1, n + 1):
        im = Image.new("RGB", size, (40, 40, 40) if f != 15 else (230, 230, 230))
        dr = ImageDraw.Draw(im)
        x = (f - 1) * 10
        dr.rectangle([x, 60, x + 20, 120], fill=(220, 120, 80))
        dr.rectangle([10, 10, 60, 30], fill=(40 + f * 5, 90, 160))
        im.save(os.path.join(d, f"{f:04d}.png"))


def make_wav(path, sr=48000, seconds=1.0):
    rng = np.random.default_rng(1)
    n = int(sr * seconds)
    x = rng.standard_normal(n) * 0.05
    for k in range(4):
        i = int(k * 0.25 * sr)
        x[i:i + 48] += 0.8
    pcm = np.clip(x * 32767, -32768, 32767).astype("<i2")
    stereo = np.repeat(pcm[:, None], 2, axis=1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(stereo.tobytes())


def main():
    with tempfile.TemporaryDirectory() as tmp:
        frames = os.path.join(tmp, "frames")
        wav = os.path.join(tmp, "sound.wav")
        mp4 = os.path.join(tmp, "film.mp4")
        make_frames(frames)
        make_wav(wav)
        enc = os.path.join(SCRIPTS, "encode.py")
        code, out = run([enc, "--frames", frames, "--wav", wav, "--out", mp4, "--fps", "30", "--n", "30",
                         "--duration", "1.0", "--crf", "20", "--preset", "veryfast"])
        print(out)
        expect(code == 0 and os.path.exists(mp4), f"encode exit {code}")
        expect(not os.path.exists(os.path.join(tmp, "film.part.mp4")), "temp mp4 renamed away")
        rep_path = os.path.join(tmp, "verify.json")
        code, out = run([os.path.join(SCRIPTS, "verify_final.py"), "--mp4", mp4, "--wav", wav, "--fps", "30", "--n", "30",
                         "--duration", "1.0", "--json", rep_path, "--expect-size", "320x180", "--frames-dir", frames])
        print(out)
        expect(code == 0, f"verify exit {code}")
        with open(rep_path, encoding="utf-8") as fh:
            rep = json.load(fh)
        p = rep["probe"]
        expect(rep["ok"] and not rep["failures"], f"verify failures: {rep['failures']}")
        expect(p["nb_frames"] == 30, f"frames {p['nb_frames']}")
        expect(abs(p["duration"] - 1.0) <= 1 / 30, f"duration {p['duration']}")
        expect(p["vcodec"] == "h264" and p["profile"] == "High" and p["pix_fmt"] == "yuv420p", "H.264 High yuv420p")
        expect(all(p[k] == "bt709" for k in ("color_space", "color_transfer", "color_primaries")), "BT.709 tags")
        expect(p["acodec"] == "aac" and p["sample_rate"] == 48000, "AAC 48 kHz")
        expect(rep["audio"]["lag_samples"] == 0, f"audio lag {rep['audio']['lag_samples']}")
        expect(rep["luma"]["black"] == [], "no black frames")
        expect(rep["luma"]["steps"][0][0] in (15, 16), f"biggest luma step at the flash, got {rep['luma']['steps'][:2]}")
        # the luma scan decoded from the MP4 itself agrees on the flash
        code, out = run([os.path.join(SCRIPTS, "verify_final.py"), "--mp4", mp4, "--wav", wav, "--fps", "30", "--n", "30",
                         "--duration", "1.0", "--json", rep_path])
        with open(rep_path, encoding="utf-8") as fh:
            rep2 = json.load(fh)
        expect(code == 0 and rep2["luma"]["steps"][0][0] in (15, 16), "luma scan from the MP4")
        # a 9:16 crop without audio
        tall = os.path.join(tmp, "tall.mp4")
        code, out = run([enc, "--frames", frames, "--out", tall, "--fps", "30", "--n", "30", "--duration", "1.0",
                         "--preset", "veryfast", "--size", "91x160", "--fit", "crop", "--no-audio"])     # odd width rounds down to 90
        expect(code == 0, f"9:16 encode exit {code}: {out}")
        code, out = run([os.path.join(SCRIPTS, "verify_final.py"), "--mp4", tall, "--fps", "30", "--n", "30",
                         "--duration", "1.0", "--expect-size", "90x160"])
        expect(code == 0, f"9:16 verify: {out}")
        # odd source frames (321x181) round down to 320x180 instead of crashing libx264
        odd_frames, odd = os.path.join(tmp, "odd"), os.path.join(tmp, "odd.mp4")
        make_frames(odd_frames, size=(321, 181))
        code, out = run([enc, "--frames", odd_frames, "--out", odd, "--fps", "30", "--n", "30", "--duration", "1.0",
                         "--preset", "veryfast", "--no-audio"])
        expect(code == 0, f"odd-size encode exit {code}: {out}")
        code, out = run([os.path.join(SCRIPTS, "verify_final.py"), "--mp4", odd, "--fps", "30", "--n", "30",
                         "--duration", "1.0", "--expect-size", "320x180"])
        expect(code == 0, f"odd-size verify (320x180): {out}")
        # a missing frame is refused
        code, out = run([enc, "--frames", frames, "--wav", wav, "--out", os.path.join(tmp, "bad.mp4"), "--fps", "30",
                         "--n", "31", "--duration", "1.0"])
        expect(code != 0 and "missing" in out, f"encode must refuse a missing frame: {code} {out}")
        # contact sheet: frames 1, 11, 21 + last 30 -> 4 cells of 160x90 + 20 label, gap 4
        sheet = os.path.join(tmp, "sheet.png")
        code, out = run([os.path.join(SCRIPTS, "contact.py"), "--seq", frames, "--every", "10", "--fps", "30", "--cols", "4",
                         "--cell", "160x90", "--label-h", "20", "--gap", "4", "--last", "--out", sheet])
        print(out)
        expect(code == 0, f"contact exit {code}")
        with Image.open(sheet) as im:
            expect(im.size == (4 * 160 + 5 * 4, 90 + 20 + 2 * 4), f"sheet size {im.size}")
        code, out = run([os.path.join(SCRIPTS, "contact.py"), "--strips", frames, "--every", "2", "--per-sheet", "10",
                         "--cols", "5", "--cell", "96x54", "--out-prefix", os.path.join(tmp, "strip")])
        expect(code == 0 and os.path.exists(os.path.join(tmp, "strip_2.png")), f"filmstrips: {out}")
    if FAILS:
        print(f"check_encode_venv: {len(FAILS)} failures")
        return 1
    print("check_encode_venv: ok (encode 16:9 + 9:16, verify, contact sheet, filmstrips)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
