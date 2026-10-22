"""check_template.py: quick check of templates/project (the scaffold a director copies). Standard library.

Copies the template into a temp folder and, with FILM_ENGINE pointing at this engine, runs the
Python-only part of its chain: timeline.py with a film.json next to it (film 1920x1080 and fps from
it, as new-video --kind film writes them; a fractional fps raises), then without it (events valid,
build/timeline.json written, 60 frames, film 1280x720), check_model.py (VIOLATIONS: 0, previs.svg
written), build.py --dry (every step has a command, the stills one with --points, the 9x16 steps
skipped) and build.py --only ui refusing on a stale stamp.
Also asserts every taste file carries a '# TASTE:' mark and no template file holds a machine path.
Chrome, Blender and the GPU are not touched here: the greybox film itself (the same files, every
step) is the integration proof, run by hand.
"""
import sys
sys.dont_write_bytecode = True
import json
import os
import re
import shutil
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.dirname(HERE)
TEMPLATE = os.path.join(os.path.dirname(ENGINE), "templates", "project")
TASTE_FILES = ("timeline.py", "hero_spec.py", "motion.py", "shots.py", "look.py", "ui_build.py", "comp.js",
               "score.py", "checks_config.py")
FAILS = []


def expect(cond, msg):
    if not cond:
        FAILS.append(msg)
        print("  FAIL " + msg)


def run(args, cwd):
    env = dict(os.environ, FILM_ENGINE=ENGINE, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, "-B"] + args, cwd=cwd, env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def main():
    expect(os.path.isdir(TEMPLATE), f"no template folder at {TEMPLATE}")
    for name in TASTE_FILES:
        path = os.path.join(TEMPLATE, name)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        expect("TASTE" in text, f"{name} has no TASTE mark")
        # the kit's own machine-path rule, spelled so this line never matches it
        expect(not re.search(r"[A-Z]:[\\/](Users|home)[\\/]|[/]Users[/]|[/]home[/][a-z]", text), f"{name} holds a machine path")
    tmp = tempfile.mkdtemp(prefix="film-template-")
    try:
        for name in os.listdir(TEMPLATE):
            src = os.path.join(TEMPLATE, name)
            if os.path.isfile(src):
                shutil.copy(src, tmp)
        pj = os.path.join(tmp, "film.json")
        with open(pj, "w", encoding="utf-8") as fh:
            json.dump({"width": 1920, "height": 1080, "fps": 30}, fh)
        code, out = run(["timeline.py"], tmp)
        expect(code == 0 and "film 1920x1080" in out and "60 frames" in out,
               f"timeline.py reads film.json: exit {code}: {out.strip().splitlines()[-1:]}")
        with open(pj, "w", encoding="utf-8") as fh:
            json.dump({"width": 1920, "height": 1080, "fps": 29.97}, fh)
        code, out = run(["timeline.py"], tmp)
        expect(code != 0 and "whole number" in out, f"timeline.py refuses a fractional fps: exit {code}: {out[-200:]}")
        os.remove(pj)
        code, out = run(["timeline.py"], tmp)
        expect(code == 0, f"timeline.py exit {code}: {out[-400:]}")
        expect(os.path.exists(os.path.join(tmp, "build", "timeline.json")), "timeline.json not written")
        expect("60 frames" in out and "6 events" in out and "film 1280x720" in out,
               f"timeline summary: {out.strip().splitlines()[-1:]}")
        code, out = run(["check_model.py"], tmp)
        expect(code == 0 and "VIOLATIONS: 0" in out, f"check_model exit {code}: {out[-600:]}")
        expect(os.path.exists(os.path.join(tmp, "build", "previs.svg")), "previs.svg not written")
        code, out = run(["build.py", "--dry"], tmp)
        steps = [ln.split("]")[0][1:] for ln in out.splitlines() if ln.startswith("[")]
        expect(code == 0 and len(set(steps)) == 16, f"build --dry: exit {code}, steps {sorted(set(steps))}")
        expect(all(f"[{s}] skipped" in out for s in ("check_9x16", "stills_9x16", "final_9x16", "encode_9x16", "verify_9x16")),
               "the 9x16 steps are skipped without a stills_9x16 list")
        expect("--points motion:hero_points" in out, "the stills step passes the points hook")
        code, out = run(["build.py", "--only", "ui"], tmp)
        expect(code == 2 and "no stamp" in out, f"ui step must refuse unstamped inputs: exit {code}: {out[-300:]}")
        code, out = run(["build.py", "--upto", "timeline"], tmp)
        expect(code == 0 and "stamped build/timeline.json" in out, f"build --upto timeline: exit {code}: {out[-300:]}")
        print(f"template: timeline ok, VIOLATIONS: 0, dry run {len(set(steps))} steps, stale refusal, --upto ok")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if FAILS:
        print(f"check_template: {len(FAILS)} failures")
        return 1
    print("check_template: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
