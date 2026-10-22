"""tools: where Blender and Chrome live on this machine. Standard library. Owner: checker.

Order: env (BLENDER, CHROME), then the install folders of this OS, then PATH. When nothing is found
the first place looked at comes back, so a doctor line names it. build.tool_paths() and every check
read these; the Node renderers use the same list in scripts/tool-paths.mjs.
"""
import os
import re
import shutil
import sys

CHROME_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")


def _versioned(root, pattern=r"Blender (\d+)\.(\d+)", min_major=5):
    """-> folder names under root matching the pattern with major >= min_major, newest first (numeric)."""
    try:
        names = os.listdir(root)
    except OSError:
        return []
    found = [(tuple(int(g) for g in m.groups()), n) for n in names for m in [re.fullmatch(pattern, n)] if m]
    return [n for v, n in sorted(found, reverse=True) if v[0] >= min_major]


def blender_candidates(platform=sys.platform, env=os.environ, which=shutil.which):
    """-> [paths] where Blender may be on this platform, in the order the engine tries them. Windows: the
    newest 'Blender 5.*' folder under %ProgramFiles%/Blender Foundation, then PATH; macOS: /Applications and
    ~/Applications, then PATH; Linux: PATH, then /snap/bin/blender."""
    on_path = which("blender")
    if platform == "win32":
        root = os.path.join(env.get("ProgramFiles") or "C:\\Program Files", "Blender Foundation")
        found = [os.path.join(root, n, "blender.exe") for n in _versioned(root)]
        return found + ([on_path] if on_path else []) or [os.path.join(root, "Blender 5.x", "blender.exe")]
    if platform == "darwin":
        app = "Applications/Blender.app/Contents/MacOS/Blender"
        home = env.get("HOME") or os.path.expanduser("~")
        return [f"/{app}", f"{home}/{app}"] + ([on_path] if on_path else [])
    return ([on_path] if on_path else []) + ["/snap/bin/blender"]


def _on_path(which, names):
    return [p for p in (which(n) for n in names) if p]


def chrome_candidates(platform=sys.platform, env=os.environ, which=shutil.which):
    """-> [paths] where Chrome may be on this platform. Windows: ProgramFiles, ProgramFiles(x86) and
    LOCALAPPDATA under Google/Chrome/Application, then PATH chrome, chromium; macOS: Google Chrome.app and
    Chromium.app, then PATH; Linux: PATH google-chrome, google-chrome-stable, chromium, chromium-browser."""
    if platform == "win32":
        roots = [env.get(k) for k in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
        found = [os.path.join(r, "Google", "Chrome", "Application", "chrome.exe") for r in (roots if any(roots) else ["C:\\Program Files"]) if r]
        return found + _on_path(which, ("chrome", "chromium"))
    if platform == "darwin":
        apps = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Chromium.app/Contents/MacOS/Chromium"]
        return apps + _on_path(which, CHROME_NAMES)
    return _on_path(which, CHROME_NAMES) or [CHROME_NAMES[0]]


def _first(paths):
    return next((p for p in paths if os.path.isfile(p)), paths[0])


def find_blender(env=os.environ):
    """-> env BLENDER, else the first Blender candidate that exists, else the first place looked at."""
    return env.get("BLENDER") or _first(blender_candidates(env=env))


def find_chrome(env=os.environ):
    """-> env CHROME, else the first Chrome candidate that exists, else the first place looked at."""
    return env.get("CHROME") or _first(chrome_candidates(env=env))
