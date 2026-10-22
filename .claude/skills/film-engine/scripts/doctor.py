"""doctor.py: probe the machine for the film engine (character-film Gate 0). Standard library only.

Checks Blender (version >= 5, a GPU device and the kind gpu.py auto mode picks, the 5.x compositor
API), Chrome, Node >= 22 with puppeteer-core resolvable from the kit, ffmpeg and ffprobe, the kit venv
(numpy, scipy, pedalboard, Pillow) and free disk at the kit root (a finished film takes about 5 GB).
Tool paths come from build.tool_paths(), so the probe and the build agree.
Prints one line per check: 'ok    name: detail', 'FAIL  name: detail → fix hint' or 'warn  name: detail';
last 'DOCTOR: ok' or 'DOCTOR: N failed'; exit 1 when a required check fails. With CYCLES_DEVICE=CPU the
GPU line is a warn (the explicit, slow opt-in), not a FAIL.

CLI: python -B doctor.py
"""
import sys
sys.dont_write_bytecode = True
import os
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build import tool_paths  # noqa: E402

KIT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
KINDS = ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI")
MIN_FREE_GB = 10
HINTS = {
    "blender": "install Blender 5.x from https://www.blender.org/download/ or set BLENDER to its binary",
    "gpu device": "update the GPU driver (NVIDIA: OptiX/CUDA, AMD: HIP, Apple: Metal, Intel: oneAPI), "
                  "or set CYCLES_DEVICE=CPU as an explicit slow opt-in",
    "compositor api": "the engine needs Blender 5.x: https://www.blender.org/download/",
    "chrome": "install Chrome from https://www.google.com/chrome/ or set CHROME to its binary",
    "node": "install Node 22+ from https://nodejs.org/",
    "puppeteer-core": "run npm install in the kit root",
    "ffmpeg": "install ffmpeg from https://ffmpeg.org/download.html and put it on PATH",
    "ffprobe": "install ffmpeg from https://ffmpeg.org/download.html (ffprobe ships with it) and put it on PATH",
    "venv": "run npm run film:install",
}
BLENDER_PROBE = (
    "import bpy\n"
    "p = bpy.context.preferences.addons['cycles'].preferences\n"
    "found = []\n"
    "for kind in ('OPTIX', 'CUDA', 'HIP', 'METAL', 'ONEAPI'):\n"
    "    try:\n"
    "        p.compute_device_type = kind\n"
    "    except TypeError:\n"
    "        continue\n"
    "    p.get_devices()\n"
    "    found += [kind + ':' + d.name for d in p.devices if d.type == kind]\n"
    "print('PROBE_VERSION', bpy.app.version_string)\n"
    "print('PROBE_DEVICES', '|'.join(found))\n"
    "print('PROBE_COMPOSITOR', hasattr(bpy.context.scene, 'compositing_node_group'))\n"
)


def run(cmd, cwd=None, timeout=180):
    """-> (exit code, stdout + stderr) of a command; (127, message) when it cannot start."""
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, str(e)


def probe_line(text, key):
    """-> the value after KEY on the first line that starts with it, or ''."""
    for line in text.splitlines():
        if line.startswith(key + " "):
            return line[len(key) + 1:].strip()
    return ""


def gpu_pick(devices, wanted=None):
    """devices: 'KIND:name|...' from the probe. -> (kind gpu.py will use or None, [its device names])."""
    by_kind = {}
    for item in devices.split("|") if devices else []:
        kind, _, name = item.partition(":")
        by_kind.setdefault(kind, []).append(name)
    for kind in ([wanted] if wanted else KINDS):
        if by_kind.get(kind):
            return kind, by_kind[kind]
    return None, []


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tools = tool_paths()
    results = []

    def report(name, ok, detail, required=True):
        results.append(ok or not required)
        hint = f" → {HINTS[name]}" if not ok and required else ""
        print(f"{'ok  ' if ok else ('FAIL' if required else 'warn')}  {name}: {detail}{hint}")

    blender = tools["blender"]
    if os.path.isfile(blender):
        code, out = run([blender, "-b", "--factory-startup", "--python-expr", BLENDER_PROBE])
        version = probe_line(out, "PROBE_VERSION")
        devices = probe_line(out, "PROBE_DEVICES")
        report("blender", version[:1].isdigit() and int(version.split(".")[0]) >= 5, f"{version or out[-200:]} at {blender}")
        wanted = os.environ.get("CYCLES_DEVICE")
        if wanted == "CPU":
            report("gpu device", False, f"CYCLES_DEVICE=CPU: Cycles renders on the CPU, many times slower (GPUs seen: {devices or 'none'})",
                   required=False)
        else:
            kind, names = gpu_pick(devices, wanted)
            others = ", ".join(d for d in devices.split("|") if d and not d.startswith(kind + ":")) if kind else ""
            report("gpu device", bool(kind),
                   f"gpu.py picks {kind} ({', '.join(names)})" + (f"; also {others}" if others else "") if kind
                   else (f"CYCLES_DEVICE={wanted} but no {wanted} device (seen: {devices or 'none'})" if wanted
                         else "none: Cycles would run on the CPU"))
        report("compositor api", probe_line(out, "PROBE_COMPOSITOR") == "True", "scene.compositing_node_group")
    else:
        report("blender", False, f"not found at {blender}")

    report("chrome", os.path.isfile(tools["chrome"]), tools["chrome"] if os.path.isfile(tools["chrome"]) else f"not found at {tools['chrome']}")

    code, out = run([tools["node"], "--version"])
    major = int(out.strip().lstrip("v").split(".")[0]) if code == 0 and out.strip().lstrip("v")[:1].isdigit() else 0
    report("node", major >= 22, out.strip() or "not found")
    code, out = run([tools["node"], "-e", "console.log(require.resolve('puppeteer-core'))"], cwd=KIT)
    report("puppeteer-core", code == 0, out.strip().splitlines()[-1] if code == 0 and out.strip() else "not resolvable from the kit root")

    for exe in ("ffmpeg", "ffprobe"):
        path = shutil.which(exe)
        code, out = run([path, "-version"]) if path else (127, "")
        report(exe, code == 0, out.splitlines()[0] if code == 0 and out else "not on PATH")

    code, out = run([tools["python"], "-c",
                     "import numpy, scipy, pedalboard, PIL;"
                     "print(numpy.__version__, scipy.__version__, pedalboard.__version__, PIL.__version__)"])
    report("venv", code == 0, out.strip().splitlines()[-1] if code == 0 and out.strip() else f"numpy, scipy, pedalboard or Pillow missing in {tools['python']}")

    free_gb = shutil.disk_usage(KIT).free / 1e9
    report("disk", free_gb >= MIN_FREE_GB, f"{free_gb:.0f} GB free at the kit root (a finished film takes about 5 GB)", required=False)
    report("pdftotext", bool(shutil.which("pdftotext")), shutil.which("pdftotext") or "not found (only for PDF briefs)",
           required=False)

    failed = results.count(False)
    print(f"DOCTOR: {'ok' if not failed else f'{failed} failed'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
