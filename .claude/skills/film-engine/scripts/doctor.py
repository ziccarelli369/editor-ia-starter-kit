"""doctor.py: probe the machine for the film engine (character-film Gate 0). Standard library only.

Checks Blender (version >= 5, a GPU device, the 5.x compositor API), Chrome, Node >= 22 with
puppeteer-core resolvable from the kit, ffmpeg and ffprobe, and the kit venv (numpy, scipy, pedalboard,
Pillow). Tool paths come from build.tool_paths(), so the probe and the build agree.
Prints one 'ok' or 'FAIL' line per check; exit 1 when a required check fails.

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


def main():
    tools = tool_paths()
    results = []

    def report(name, ok, detail, required=True):
        results.append((ok or not required))
        print(f"{'ok  ' if ok else ('FAIL' if required else 'warn')}  {name}: {detail}")

    blender = tools["blender"]
    if os.path.isfile(blender):
        code, out = run([blender, "-b", "--factory-startup", "--python-expr", BLENDER_PROBE])
        version = probe_line(out, "PROBE_VERSION")
        devices = probe_line(out, "PROBE_DEVICES")
        report("blender", version[:1].isdigit() and int(version.split(".")[0]) >= 5, version or out[-200:])
        report("gpu device", bool(devices), devices or "none (Cycles would run on the CPU)")
        report("compositor api", probe_line(out, "PROBE_COMPOSITOR") == "True", "scene.compositing_node_group")
    else:
        report("blender", False, f"not found at {blender} (set env BLENDER)")

    report("chrome", os.path.isfile(tools["chrome"]), tools["chrome"])

    code, out = run([tools["node"], "--version"])
    major = int(out.strip().lstrip("v").split(".")[0]) if code == 0 and out.strip().lstrip("v")[:1].isdigit() else 0
    report("node", major >= 22, out.strip() or "not found")
    code, out = run([tools["node"], "-e", "console.log(require.resolve('puppeteer-core'))"], cwd=KIT)
    report("puppeteer-core", code == 0, out.strip().splitlines()[-1] if out.strip() else "run npm install in the kit root")

    for exe in ("ffmpeg", "ffprobe"):
        path = shutil.which(exe)
        code, out = run([path, "-version"]) if path else (127, "")
        report(exe, code == 0, out.splitlines()[0] if code == 0 and out else "not on PATH")

    code, out = run([tools["python"], "-c",
                     "import numpy, scipy, pedalboard, PIL;"
                     "print(numpy.__version__, scipy.__version__, pedalboard.__version__, PIL.__version__)"])
    report("venv", code == 0, out.strip().splitlines()[-1] if out.strip() else tools["python"])

    report("pdftotext", bool(shutil.which("pdftotext")), shutil.which("pdftotext") or "not found (only for PDF briefs)",
           required=False)

    failed = results.count(False)
    print(f"DOCTOR: {'ok' if not failed else f'{failed} failed'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
