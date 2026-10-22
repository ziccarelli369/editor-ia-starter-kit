"""check_build.py: quick check of build.py (the chain runner) without running any tool. Standard library.

In a temp project with a build/timeline.json: every step has a command; --dry prints them and exits 0;
a step whose stamped inputs are missing or stale exits 2 (the freshness rule); the stills gate refuses a
model report with violations; a step that runs a command stamps its outputs (the timeline step is run for
real with a tiny timeline.py that writes build/timeline.json); a step's inputs follow the project imports
(scene.py -> shots_9x16.py -> shots.py -> importlib 'set' -> set.py), the sequence folders under build/
and the sprite PNGs the layout names, so touching set.py or build/clock/0001.png marks a stamped
build/film.blend stale; a source saved with a BOM still contributes its imports; film.json (never
project.json) feeds the timeline stamp; the points knob reaches the stills command (default
motion:hero_points, null = off) and its module joins the stills inputs; every Blender call passes
--python-exit-code 1 right after -b (a script exception must fail the step); the 9x16 steps are skipped
without a stills_9x16 list and, with one, run check_model.py --shots <module> and stills.py --camera
--film on the vertical frames, gated on build/model_report_9x16.txt; the sound step's inputs carry
checks_config.py (its SOUND gates decide the exit code); a step whose source is rewritten while it runs (a
fake check_model.py edits checks_config.py, then writes its report) leaves its artifact stale, because the
stamp holds the mtimes read before the first command ran.
"""
import sys
sys.dont_write_bytecode = True
import contextlib
import io
import json
import os
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import build  # noqa: E402
from filmkit import fresh  # noqa: E402

FAILS = []
TL = {"format": {"fps": 30, "duration": 1.0, "frames": 30}, "layout": {"sprites": {"chip": [8, 8]}}, "hash": "abc123def456"}
FILES = {
    "timeline.py": "import json, os\nos.makedirs('build', exist_ok=True)\n"
                   f"json.dump({TL!r}, open(os.path.join('build', 'timeline.json'), 'w'))\n",
    "scene.py": "\ufeffimport shots_9x16\nimport look\n",      # saved with a BOM by some editors
    "shots_9x16.py": "import shots as S16\n",
    "shots.py": "import importlib\nARENA = importlib.import_module('set')\nfrom hero_spec import HERO\n",
    "set.py": "X = 1\n", "hero_spec.py": "HERO = {}\n", "look.py": "LOOK = {}\n",
    "motion.py": "import poses\n\n\ndef hero_points(t):\n    return []\n", "poses.py": "P = 1\n",
    "sound.py": "import score\n", "score.py": "HANDLERS = {}\n", "checks_config.py": "LIMIT = 1\n",
    # a check step that rewrites one of its own sources while it runs, then writes its report from the OLD value
    "check_model.py": "import os, time\nimport checks_config\n"
                      "with open('checks_config.py', 'w') as fh:\n    fh.write('LIMIT = 99\\n')\n"
                      "time.sleep(0.05)\nos.makedirs('build', exist_ok=True)\n"
                      "with open(os.path.join('build', 'model_report.txt'), 'w') as fh:\n"
                      "    fh.write(f'LIMIT {checks_config.LIMIT}\\nVIOLATIONS: 0\\n')\n"
                      "with open(os.path.join('build', 'previs.svg'), 'w') as fh:\n    fh.write('<svg/>')\n",
    "project.json": "{}\n", "film.json": "{}\n",
    "build/comp/0001.png": "", "build/clock/0001.png": "", "build/chip.png": "", "build/ui.png": "",
    "build/comp_bbox.json": "{}", "build/timeline.json": json.dumps(TL),
}


def expect(cond, msg):
    if not cond:
        FAILS.append(msg)
        print("  FAIL " + msg)


def write(tmp, rel, text):
    path = os.path.join(tmp, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def main():
    with tempfile.TemporaryDirectory() as tmp:
        for rel, text in FILES.items():
            write(tmp, rel, text)
        tools = build.tool_paths()
        cmds = build.step_commands(tmp, tools)
        expect(list(cmds) == build.STEPS, f"steps: {list(cmds)}")
        expect(all(cmds[s][0] and cmds[s][2] for s in build.STEPS), "every step has a command and outputs")

        # inputs follow the imports, the sequences and the sprites
        blend_in = cmds["blend"][1]
        want = {"scene.py", "shots_9x16.py", "shots.py", "set.py", "hero_spec.py", "look.py",
                "build/clock", "build/comp", "build/chip.png", "build/ui.png", "build/timeline.json", "build/comp_bbox.json"}
        expect(want <= set(blend_in), f"blend inputs miss {sorted(want - set(blend_in))}: {blend_in}")
        expect("motion.py" not in blend_in, "blend inputs stop at what scene.py imports (motion.py is not imported here)")
        expect("film.json" in cmds["timeline"][1] and "project.json" not in cmds["timeline"][1],
               f"timeline inputs carry film.json, never project.json: {cmds['timeline'][1]}")
        expect("build/chip.png" in cmds["ui"][2], f"ui outputs carry the sprite PNGs: {cmds['ui'][2]}")
        expect({"build/clock", "build/comp"} <= set(cmds["comp"][2]), f"comp outputs carry every sequence folder: {cmds['comp'][2]}")
        st_argv, st_in = cmds["stills"][0][0], cmds["stills"][1]
        expect("--points" in st_argv and st_argv[st_argv.index("--points") + 1] == "motion:hero_points",
               f"stills command carries the default points hook: {st_argv[-4:]}")
        expect({"motion.py", "poses.py"} <= set(st_in), f"stills inputs carry the points module and its imports: {st_in}")
        expect({"build/timeline.json", "sound.py", "score.py", "checks_config.py"} <= set(cmds["sound"][1]),
               f"sound inputs carry checks_config.py (SOUND gates the step) next to sound.py and its imports: {cmds['sound'][1]}")
        expect(build.project_sources(tmp, ["missing.py"]) == [], "a missing entry gives no sources")
        bl = [(s, a) for s in build.STEPS for a in cmds[s][0] if a[0] == tools["blender"]]
        expect(len(bl) == 6 and all(a[1:4] == ["-b", "--python-exit-code", "1"] for _, a in bl),
               f"every Blender call carries --python-exit-code 1 after -b: {[(s, a[1:4]) for s, a in bl]}")
        expect(build.STEPS[-3:] == ["final_9x16", "encode_9x16", "verify_9x16"] and set(build.STEPS_9X16) <= set(build.STEPS),
               f"the vertical final steps close the chain: {build.STEPS[-3:]}")

        # the freshness repro: a stamped film.blend goes stale when set.py or build/clock changes
        blend_path = write(tmp, "build/film.blend", "blend")
        now = os.path.getmtime(blend_path)
        for rel in list(FILES) + ["build/clock", "build/comp"]:
            os.utime(os.path.join(tmp, rel), (now - 10, now - 10))
        os.utime(blend_path, (now, now))
        bdir = os.path.join(tmp, "build")
        fresh.stamp(bdir, "build/film.blend", blend_in, "abc123def456", step="blend")
        expect(fresh.status(bdir, "build/film.blend", "abc123def456")[0] == "fresh", "film.blend stamped fresh")
        os.utime(os.path.join(tmp, "set.py"), (now + 5, now + 5))
        st, why = fresh.status(bdir, "build/film.blend", "abc123def456")
        expect(st == "stale" and any("set.py" in w for w in why), f"touching set.py marks film.blend stale: {why}")
        os.utime(os.path.join(tmp, "set.py"), (now - 10, now - 10))
        os.utime(os.path.join(tmp, "build", "clock", "0001.png"), (now + 5, now + 5))
        st, why = fresh.status(bdir, "build/film.blend", "abc123def456")
        expect(st == "stale" and any("build/clock" in w for w in why), f"touching build/clock marks film.blend stale: {why}")
        os.remove(os.path.join(bdir, fresh.STAMPS))

        # the runner: dry run, refusal, a real timeline step, gates, knobs
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            expect(build.main([tmp, "--dry"]) == 0, "dry run exits 0")
            expect(build.run_step(tmp, "check", tools) == 2, "check step must refuse unstamped inputs")
            expect(build.run_step(tmp, "timeline", tools) == 0, "timeline step runs and stamps")
        expect("no stamp" in err.getvalue(), f"stale reason printed: {err.getvalue()[:200]}")
        st = fresh.status(bdir, "build/timeline.json", "abc123def456")
        expect(st[0] == "fresh", f"timeline.json stamped fresh: {st}")
        rec = fresh.load_stamps(bdir)["build/timeline.json"]
        expect({"timeline.py", "film.json"} <= set(rec["inputs"]), f"timeline stamp inputs: {sorted(rec['inputs'])}")
        # the 9x16 steps: skipped without the list, else gated on their own report, commands on the vertical camera
        expect(all(build._skipped(tmp, s) for s in build.STEPS_9X16) and not build._skipped(tmp, "stills")
               and not build._skipped(tmp, "final"), "9x16 steps skip without a stills_9x16 list")
        with contextlib.redirect_stdout(io.StringIO()):
            expect(build.run_step(tmp, "stills_9x16", tools) == 0, "a skipped step exits 0")
        with open(os.path.join(tmp, "build", "model_report.txt"), "w", encoding="utf-8") as fh:
            fh.write("model check: rules hero_margin\nVIOLATIONS: 2\n")
        expect(build._gate(tmp, "stills") is not None, "stills gate refuses violations")
        with open(os.path.join(tmp, "build", "model_report.txt"), "w", encoding="utf-8") as fh:
            fh.write("model check: rules hero_margin\nVIOLATIONS: 0\n")
        expect(build._gate(tmp, "stills") is None, "stills gate passes a clean report")
        with open(os.path.join(tmp, "build.json"), "w", encoding="utf-8") as fh:
            json.dump({"slug": "film-x", "stills": [1, 16, 30], "vignette": "PI/5", "points": None, "stills_9x16": [1, 30]}, fh)
        cmds = build.step_commands(tmp, tools)
        expect(cmds["encode"][2] == ["renders/film-x.mp4"] and "--vignette" in cmds["encode"][0][0], "build.json knobs apply")
        expect("1,16,30" in cmds["stills"][0][0], "stills frames from build.json")
        expect("--points" not in cmds["stills"][0][0] and "motion.py" not in cmds["stills"][1], "points null turns the hook off")
        with open(os.path.join(tmp, "build.json"), "w", encoding="utf-8") as fh:
            json.dump({"stills_9x16": [1, 30]}, fh)
        cmds = build.step_commands(tmp, tools)
        c9, s9 = cmds["check_9x16"], cmds["stills_9x16"]
        expect(not build._skipped(tmp, "stills_9x16"), "a stills_9x16 list turns the 9x16 steps on")
        expect(c9[0][0][-3:] == ["check_model.py", "--shots", "shots_9x16"] and "shots_9x16.py" in c9[1] and "shots.py" in c9[1]
               and c9[2] == ["build/model_report_9x16.txt", "build/previs_9x16.svg"], f"check_9x16 command: {c9}")
        a9 = s9[0][0]
        expect(a9[a9.index("--frames") + 1] == "1,30" and a9[a9.index("--camera") + 1] == "camera_9x16"
               and a9[a9.index("--out") + 1] == "renders/stills_9x16" and "--film" not in a9,
               f"stills_9x16 command (no film size before the timeline names one): {a9}")
        expect({"build/film.blend", "build/model_report_9x16.txt", "shots_9x16.py", "shots.py", "motion.py", "poses.py"} <= set(s9[1])
               and s9[2] == ["renders/stills_9x16/stills.json"], f"stills_9x16 inputs carry the report, the camera module and the points module: {s9}")
        with open(os.path.join(tmp, "build.json"), "w", encoding="utf-8") as fh:
            json.dump({"slug": "film-x", "stills_9x16": [1, 30]}, fh)
        cmds = build.step_commands(tmp, tools)
        f9, e9, v9 = (cmds[s] for s in ("final_9x16", "encode_9x16", "verify_9x16"))
        a9 = f9[0][0]
        expect(not build._skipped(tmp, "final_9x16") and a9[0] == tools["blender"] and "--final" in a9 and "-a" not in a9
               and a9[a9.index("--camera") + 1] == "camera_9x16" and a9[a9.index("--out") + 1] == "renders/frames_9x16"
               and "--film" not in a9 and f9[1] == ["build/film.blend", "renders/stills_9x16/stills.json"]
               and f9[2] == ["renders/frames_9x16"], f"final_9x16 command and gate: {f9}")
        expect(e9[0][0][e9[0][0].index("--frames") + 1] == "renders/frames_9x16" and e9[2] == ["renders/film-x-9x16.mp4"]
               and e9[1] == ["renders/frames_9x16", "build/sound.wav"], f"encode_9x16 writes renders/<slug>-9x16.mp4: {e9}")
        expect(v9[0][0][v9[0][0].index("--mp4") + 1] == "renders/film-x-9x16.mp4" and "--expect-size" not in v9[0][0]
               and v9[2] == ["renders/verify_9x16.json"] and v9[1] == ["renders/film-x-9x16.mp4", "build/sound.wav"],
               f"verify_9x16 probes the vertical mp4: {v9}")
        with open(os.path.join(tmp, "build", "timeline.json"), "w", encoding="utf-8") as fh:
            json.dump({**TL, "format": {**TL["format"], "film": [1920, 1080]}}, fh)
        cmds = build.step_commands(tmp, tools)
        a9 = cmds["stills_9x16"][0][0]
        expect(a9[a9.index("--film") + 1] == "1080x1920", f"film_9x16 defaults to the master turned on its side: {a9}")
        f9, v9 = cmds["final_9x16"][0][0], cmds["verify_9x16"][0][0]
        expect(f9[f9.index("--film") + 1] == "1080x1920" and v9[v9.index("--expect-size") + 1] == "1080x1920",
               f"final_9x16 renders and verify_9x16 asserts the vertical size: {f9[-4:]} {v9[-2:]}")
        expect(build._gate(tmp, "stills_9x16") is not None and "model_report_9x16" in build._gate(tmp, "stills_9x16"),
               "stills_9x16 gate needs its own report")
        with open(os.path.join(tmp, "build", "model_report_9x16.txt"), "w", encoding="utf-8") as fh:
            fh.write("model check 9x16: rules hero_margin\nVIOLATIONS: 0\n")
        expect(build._gate(tmp, "stills_9x16") is None, "stills_9x16 gate passes a clean report")
        # a source edited while its step runs is not the source the step used: the stamp must leave the artifact
        # stale (the fake check_model.py rewrites checks_config.py mid-run, then writes its report from LIMIT 1)
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = build.run_step(tmp, "check", tools, force=True)
        expect(code == 0, f"check step runs under --force: exit {code}: {err.getvalue()[-300:]}")
        with open(os.path.join(tmp, "build", "model_report.txt"), encoding="utf-8") as fh:
            expect(fh.read().startswith("LIMIT 1\n"), "the fake check wrote its report from the old source")
        st, why = fresh.status(bdir, "build/model_report.txt", "abc123def456")
        expect(st == "stale" and any("checks_config.py changed since the stamp" in w for w in why),
               f"a source rewritten while the step ran leaves its artifact stale: {st} {why}")
    if FAILS:
        print(f"check_build: {len(FAILS)} failures")
        return 1
    print("check_build: ok (commands, imports followed through a BOM, sequences + sprites, stale on set.py and "
          "build/clock, dry run, freshness refusal, film.json stamp, gates, knobs, points hook, 9x16 steps, "
          "checks_config.py in the sound inputs, a source edited mid-step stays stale)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
