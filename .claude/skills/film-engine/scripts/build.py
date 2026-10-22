"""build.py: run the build chain for a project in order, stamping freshness after each step. Owner: checker.
Standard library; it spawns python, node, blender and ffmpeg.

Steps (API.md, 'Build chain'): timeline ui comp sound blend check check_9x16 stills stills_9x16 animatic final
encode verify final_9x16 encode_9x16 verify_9x16. The five 9x16 steps run only when build.json names
'stills_9x16' (else they print 'skipped'). final_9x16 renders every frame through the 'camera_9x16' object at
the 'film_9x16' size (stills.py --final: the look's final preset, persistent data on, the .blend never saved)
into renders/frames_9x16; encode_9x16 writes renders/<slug>-9x16.mp4; verify_9x16 probes it (size asserted)
into renders/verify_9x16.json. They are gated like the 16:9 ones: final_9x16 needs fresh vertical stills.
A step runs only when every stamped artifact it reads is fresh (filmkit.fresh.require_fresh, exit 2 with
the list to rerun). --from X runs X and everything after it; --upto X runs everything up to X (both
together give a range); --only X runs one step; --force skips the freshness gate for the named steps.
Outputs are stamped with the timeline hash and the inputs' mtimes read before the step's first command
ran, so a source edited while the step runs leaves the artifact stale (it was built from the old source).

Inputs are complete, not a hand-written list: a step's Python sources are its entry script plus every
project .py it imports, followed through the project (project_sources: `import a`, `from a import b`,
`importlib.import_module('a')` with a literal name); the blend step also reads every sequence folder
under build/ (one per comp sequence, found by its 0001.png) and every sprite PNG the timeline layout
names; the stills step reads the module of the points function; the sound step reads checks_config.py
(its SOUND dict gates the step's exit code). So a change to set.py, poses.py, a second shot list,
build/clock/ or a sprite marks build/film.blend stale, and a tightened SOUND marks build/sound.wav stale.
Gates: stills need a model report with 'VIOLATIONS: 0' (stills_9x16: build/model_report_9x16.txt, written by
check_9x16 = `check_model.py --shots <shots_9x16>`); the final needs fresh stills (the director looks
at them in chat; the runner only checks they exist and are fresh); final_9x16 the same with the vertical stills. The timeline step stamps film.json (the
film format new-video writes), never project.json: deliver rewrites project.json and must not stale the film.
Tool paths: env BLENDER, CHROME, FILM_PYTHON (kit venv python; default the kit's .venv when the engine
lives in the kit, else this interpreter), NODE, FILM_ENGINE; defaults in API.md.

Project knobs (build.json in the project folder, every value optional, placeholders otherwise):
  {"slug": "<folder name>", "stills": [1, <mid>, <last>], "mask": true, "crf": 17, "preset": "slow",
   "vignette": null, "animatic_samples": 16, "audio_kbps": 320, "ui_font": null, "contact_every": 15,
   "points": "motion:hero_points",
   "stills_9x16": [frames], "shots_9x16": "shots_9x16", "camera_9x16": "camera_9x16", "film_9x16": [1080, 1920]}
  stills_9x16: the vertical review stills (absent = no 9x16 steps); shots_9x16: the vertical shot module
  check_model.py --shots takes (its sources feed the stamp); camera_9x16: the camera object scene.py built
  for it; film_9x16: its size (default: the master film turned on its side).
  mask: stills render the class mask and measure it (needs LOOK['mask']['classes']); ui_font: the face
  ui-render proves (null = not proven); contact_every: comp contact sheet step in frames; points: the
  project function f(t) -> world points that fills stills.json silhouette.model_w (default
  motion:hero_points when the project has a motion.py; null = no model width).

CLI:
  python -B build.py <project_dir> [--from timeline] [--upto check] [--only check] [--force] [--dry]
"""
import sys
sys.dont_write_bytecode = True
import ast
import json
import os
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from filmkit import fresh  # noqa: E402

STEPS = ["timeline", "ui", "comp", "sound", "blend", "check", "check_9x16", "stills", "stills_9x16", "animatic", "final",
         "encode", "verify", "final_9x16", "encode_9x16", "verify_9x16"]
STEPS_9X16 = ("check_9x16", "stills_9x16", "final_9x16", "encode_9x16", "verify_9x16")


def kit_venv_python(engine=HERE):
    """-> the kit's .venv python when the engine sits at <kit>/.claude/skills/film-engine/scripts, else None."""
    kit = os.path.normpath(os.path.join(engine, "..", "..", "..", ".."))
    for rel in (("Scripts", "python.exe"), ("bin", "python")):
        p = os.path.join(kit, ".venv", *rel)
        if os.path.isfile(p):
            return p
    return None


def tool_paths():
    """-> {'blender', 'chrome', 'python', 'node', 'engine'} from env with documented defaults."""
    engine = os.environ.get("FILM_ENGINE") or HERE
    return {"blender": os.environ.get("BLENDER") or "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe",
            "chrome": os.environ.get("CHROME") or "C:/Program Files/Google/Chrome/Application/chrome.exe",
            "python": os.environ.get("FILM_PYTHON") or kit_venv_python(engine) or sys.executable,
            "node": os.environ.get("NODE") or "node",
            "engine": engine}


def _timeline(project_dir):
    """-> the build/timeline.json dict, or {} before the timeline step."""
    path = os.path.join(project_dir, "build", "timeline.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _format(project_dir):
    """-> (fps, frames, duration) from build/timeline.json, or (None, None, None) before the timeline step."""
    fmt = _timeline(project_dir).get("format", {})
    return fmt.get("fps"), fmt.get("frames"), fmt.get("duration")


def _film(project_dir):
    """-> (w, h) of the master film from build/timeline.json, or (None, None) before the timeline step."""
    film = _timeline(project_dir).get("format", {}).get("film") or (None, None)
    return tuple(film)


def _knobs(project_dir, frames):
    path = os.path.join(project_dir, "build.json")
    k = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            k = json.load(fh)
    mid = (frames or 2) // 2 or 1
    points_default = "motion:hero_points" if os.path.isfile(os.path.join(project_dir, "motion.py")) else None
    w, h = _film(project_dir)
    film9 = k.get("film_9x16") or ((h, w) if w and h else None)
    return {"slug": k.get("slug") or os.path.basename(os.path.abspath(project_dir)),
            "stills_9x16": k.get("stills_9x16"), "shots_9x16": k.get("shots_9x16") or "shots_9x16",
            "camera_9x16": k.get("camera_9x16") or "camera_9x16", "film_9x16": film9,
            "stills": k.get("stills") or [1, mid, frames or 1], "mask": bool(k.get("mask", True)),
            "crf": k.get("crf", 17), "preset": k.get("preset", "slow"),
            "vignette": k.get("vignette"), "animatic_samples": k.get("animatic_samples", 16),
            "audio_kbps": k.get("audio_kbps", 320), "ui_font": k.get("ui_font"),
            "contact_every": int(k.get("contact_every", 15)),
            "points": k["points"] if "points" in k else points_default}


def _import_names(tree):
    """-> module names a parsed file imports: import a / from a import b / importlib.import_module('a')."""
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module.split(".")[0])
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "import_module"
              and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
            names.append(node.args[0].value.split(".")[0])
    return names


def project_sources(project_dir, entries):
    """-> sorted project-relative paths of the entry scripts that exist plus every project .py they import,
    directly or through other project modules (a name counts when <project>/<name>.py exists; engine and
    library modules are not project sources). Static scan; a file that does not parse contributes itself."""
    found, todo = [], list(entries)
    while todo:
        name = todo.pop(0)
        path = os.path.join(project_dir, name)
        if name in found or not os.path.isfile(path):
            continue
        found.append(name)
        try:
            with open(path, encoding="utf-8-sig") as fh:      # a BOM file would not parse and drop its imports
                tree = ast.parse(fh.read(), name)
        except (SyntaxError, ValueError):
            continue
        todo += [n + ".py" for n in _import_names(tree)]
    return sorted(found)


def sequence_dirs(project_dir):
    """-> sorted ['build/<name>', ...]: every folder under build/ holding a 0001.png (the comp step writes one
    per sequence the page renders)."""
    build = os.path.join(project_dir, "build")
    if not os.path.isdir(build):
        return []
    return sorted(f"build/{d}" for d in os.listdir(build) if os.path.isfile(os.path.join(build, d, "0001.png")))


def sprite_pngs(project_dir):
    """-> sorted ['build/<sprite>.png', ...] for every sprite the timeline layout names (ui-render writes them)."""
    sprites = (_timeline(project_dir).get("layout") or {}).get("sprites") or {}
    return sorted(f"build/{name}.png" for name in sprites)


def step_commands(project_dir, tools):
    """-> {step: (argvs, inputs, outputs)}: the commands of each step (a list of argv lists, run in order from
    the project folder) and its artifacts (paths relative to the project). Inputs under build/ or renders/
    must be fresh; other inputs (sources) only feed the stamp. Sources follow the imports (project_sources);
    sequences and sprites are discovered, so the comp outputs are re-read after the step runs."""
    E, py, venv, node, blender = tools["engine"], sys.executable, tools["python"], tools["node"], tools["blender"]
    bl = [blender, "-b", "--python-exit-code", "1"]     # without the flag a script exception still exits 0
    fps, n, dur = _format(project_dir)
    k = _knobs(project_dir, n)
    gpu = os.path.join(E, "filmkit", "blender", "gpu.py")
    stills_py = os.path.join(E, "filmkit", "blender", "stills.py")
    mp4 = f"renders/{k['slug']}.mp4"
    mp4_9 = f"renders/{k['slug']}-9x16.mp4"
    timing = ["--fps", str(fps), "--n", str(n), "--duration", str(dur)]
    enc = [py, "-B", os.path.join(E, "encode.py"), "--crf", str(k["crf"]), "--preset", k["preset"],
           "--audio-kbps", str(k["audio_kbps"])] + (["--vignette", str(k["vignette"])] if k["vignette"] else [])
    font = ["--font", k["ui_font"]] if k["ui_font"] else []
    mask = ["--mask"] if k["mask"] else []
    points = ["--points", k["points"]] if k["points"] else []
    points_src = project_sources(project_dir, [k["points"].split(":")[0] + ".py"]) if k["points"] else []
    seqs = sequence_dirs(project_dir) or ["build/comp"]
    sprites = sprite_pngs(project_dir)
    shots9 = k["shots_9x16"]
    size9 = "x".join(str(v) for v in k["film_9x16"]) if k["film_9x16"] else None
    film9 = ["--film", size9] if size9 else []
    expect9 = ["--expect-size", size9] if size9 else []
    frames9 = ",".join(str(f) for f in (k["stills_9x16"] or []))

    def src(*entries):
        return project_sources(project_dir, entries)

    return {
        "timeline": ([[py, "-B", "timeline.py"]], src("timeline.py") + ["film.json"], ["build/timeline.json"]),
        "ui": ([[py, "-B", "ui_build.py"],
                [node, os.path.join(E, "ui-render.mjs"), "--html", "build/ui.html", "--timeline", "build/timeline.json",
                 "--out", "build"] + font],
               ["build/timeline.json"] + src("ui_build.py"),
               ["build/ui.html", "build/ui.png", "build/ui_base.png", "build/ui_check.png"] + sprites),
        "comp": ([[node, os.path.join(E, "frames-render.mjs"), "--page", "comp.html", "--timeline", "build/timeline.json",
                   "--out", "build", "--contact", "comp_contact.png", "--contact-every", str(k["contact_every"])]],
                 ["build/timeline.json", "comp.html", "comp.js"], seqs + ["build/comp_bbox.json", "build/comp_contact.png"]),
        "sound": ([[venv, "-B", "sound.py"]], ["build/timeline.json"] + src("sound.py", "checks_config.py"), ["build/sound.wav"]),
        "blend": ([bl + ["--factory-startup", "-P", gpu, "-P", "scene.py"]],
                  ["build/timeline.json", "build/ui.png", "build/comp_bbox.json"] + sprites + seqs + src("scene.py"),
                  ["build/film.blend"]),
        "check": ([[py, "-B", "check_model.py"]],
                  ["build/timeline.json", "build/comp_bbox.json"] + src("check_model.py"),
                  ["build/model_report.txt", "build/previs.svg"]),
        "check_9x16": ([[py, "-B", "check_model.py", "--shots", shots9]],
                       ["build/timeline.json", "build/comp_bbox.json"] + src("check_model.py", shots9 + ".py"),
                       ["build/model_report_9x16.txt", "build/previs_9x16.svg"]),
        "stills": ([bl + ["build/film.blend", "-P", gpu, "-P", stills_py, "--", "--frames",
                     ",".join(str(f) for f in k["stills"]), "--out", "renders/stills", "--json", "stills.json"] + mask + points],
                   ["build/film.blend", "build/model_report.txt"] + points_src, ["renders/stills/stills.json"]),
        "stills_9x16": ([bl + ["build/film.blend", "-P", gpu, "-P", stills_py, "--", "--frames", frames9, "--camera",
                          k["camera_9x16"], "--out", "renders/stills_9x16", "--json", "stills.json"] + film9 + mask + points],
                        ["build/film.blend", "build/model_report_9x16.txt"] + sorted(set(points_src + src(shots9 + ".py"))),
                        ["renders/stills_9x16/stills.json"]),
        "animatic": ([bl + ["build/film.blend", "-P", gpu, "-P", stills_py, "--", "--animatic", "--out",
                       "renders/animatic", "--samples", str(k["animatic_samples"])],
                      enc + ["--frames", "renders/animatic", "--wav", "build/sound.wav", "--out", "renders/animatic.mp4"] + timing,
                      [venv, "-B", os.path.join(E, "contact.py"), "--strips", "renders/animatic", "--every", "2", "--per-sheet",
                       "60", "--cols", "10", "--fps", str(fps), "--out-prefix", "renders/animatic_strip"]],
                     ["build/film.blend", "build/sound.wav"], ["renders/animatic", "renders/animatic.mp4"]),
        "final": ([bl + ["build/film.blend", "-P", gpu, "-a"]], ["build/film.blend", "renders/stills/stills.json"],
                  ["renders/frames"]),
        "encode": ([enc + ["--frames", "renders/frames", "--wav", "build/sound.wav", "--out", mp4] + timing],
                   ["renders/frames", "build/sound.wav"], [mp4]),
        "verify": ([[venv, "-B", os.path.join(E, "verify_final.py"), "--mp4", mp4, "--wav", "build/sound.wav",
                     "--frames-dir", "renders/frames", "--json", "renders/verify.json"] + timing],
                   [mp4, "build/sound.wav"], ["renders/verify.json"]),
        "final_9x16": ([bl + ["build/film.blend", "-P", gpu, "-P", stills_py, "--", "--final", "--camera", k["camera_9x16"],
                        "--out", "renders/frames_9x16"] + film9],
                       ["build/film.blend", "renders/stills_9x16/stills.json"], ["renders/frames_9x16"]),
        "encode_9x16": ([enc + ["--frames", "renders/frames_9x16", "--wav", "build/sound.wav", "--out", mp4_9] + timing],
                        ["renders/frames_9x16", "build/sound.wav"], [mp4_9]),
        "verify_9x16": ([[venv, "-B", os.path.join(E, "verify_final.py"), "--mp4", mp4_9, "--wav", "build/sound.wav",
                          "--frames-dir", "renders/frames_9x16", "--json", "renders/verify_9x16.json"] + timing + expect9],
                        [mp4_9, "build/sound.wav"], ["renders/verify_9x16.json"]),
    }


def _artifact(path):
    return path.startswith(("build/", "renders/"))


def _gate(project_dir, step):
    """Extra gates. -> None when ok, else the reason."""
    if step in ("stills", "stills_9x16"):
        name, check_step = ("model_report.txt", "check") if step == "stills" else ("model_report_9x16.txt", "check_9x16")
        rep = os.path.join(project_dir, "build", name)
        if not os.path.exists(rep):
            return f"no build/{name} (run the {check_step} step)"
        with open(rep, encoding="utf-8") as fh:
            if "VIOLATIONS: 0" not in fh.read().splitlines():
                return f"the model report build/{name} has violations (fix them, rerun the {check_step} step)"
    return None


def _skipped(project_dir, step):
    """-> why a step does not apply to this project (the 9x16 steps without a stills_9x16 list), else None."""
    if step in STEPS_9X16 and not _knobs(project_dir, None)["stills_9x16"]:
        return "no stills_9x16 list in build.json"
    return None


def run_step(project_dir, step, tools, force=False, dry=False):
    """Check freshness, run, stamp outputs on success (the output list is re-read after the run, so the
    sequences a comp step wrote are the ones stamped). -> exit code (2 = stale inputs or gate)."""
    skip = _skipped(project_dir, step)
    if skip:
        print(f"[{step}] skipped: {skip}")
        return 0
    argvs, inputs, outputs = step_commands(project_dir, tools)[step]
    build = os.path.join(project_dir, "build")
    if dry:
        for argv in argvs:
            print(f"[{step}] " + " ".join(argv))
        return 0
    if not force:
        try:
            fresh.require_fresh(build, [p for p in inputs if _artifact(p)], fresh.current_hash(build))
        except SystemExit as e:
            print(f"[{step}] stale inputs; rerun the steps above or pass --force", file=sys.stderr)
            return int(e.code or 2)
        why = _gate(project_dir, step)
        if why:
            print(f"[{step}] gate: {why}", file=sys.stderr)
            return 2
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", FILM_ENGINE=tools["engine"],
               BLENDER=tools["blender"], CHROME=tools["chrome"])
    mtimes = fresh.input_mtimes(build, inputs)     # before the first command: a source edited mid-run stays stale
    t0 = time.perf_counter()
    for argv in argvs:
        print(f"[{step}] " + " ".join(argv), flush=True)
        r = subprocess.run(argv, cwd=project_dir, env=env)
        if r.returncode:
            print(f"[{step}] failed with exit {r.returncode} after {time.perf_counter() - t0:.0f} s", file=sys.stderr)
            return r.returncode
    outputs = step_commands(project_dir, tools)[step][2]
    tl_hash = fresh.current_hash(build)
    for out in outputs:
        if not os.path.exists(os.path.join(project_dir, out)):
            print(f"[{step}] did not write {out}", file=sys.stderr)
            return 1
        fresh.stamp(build, out, inputs, tl_hash, step=step, mtimes=mtimes)
    print(f"[{step}] ok in {time.perf_counter() - t0:.0f} s; stamped {', '.join(outputs)}")
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        return 2
    project_dir = os.path.abspath(argv[0])
    force, dry = "--force" in argv, "--dry" in argv
    named = [argv[argv.index(flag) + 1] for flag in ("--only", "--from", "--upto") if flag in argv]
    for s in named:
        if s not in STEPS:
            print(f"unknown step {s}; steps: {' '.join(STEPS)}", file=sys.stderr)
            return 2
    if "--only" in argv:
        steps = [argv[argv.index("--only") + 1]]
    else:
        a = STEPS.index(argv[argv.index("--from") + 1]) if "--from" in argv else 0
        b = STEPS.index(argv[argv.index("--upto") + 1]) if "--upto" in argv else len(STEPS) - 1
        steps = STEPS[a:b + 1]
    tools = tool_paths()
    for step in steps:
        code = run_step(project_dir, step, tools, force, dry)
        if code:
            return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
