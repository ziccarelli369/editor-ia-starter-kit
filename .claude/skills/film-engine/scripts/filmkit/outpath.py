"""outpath: the fence on every output path the engine writes. Standard library. Owner: checker.

Blender resolves a plain relative render path against the drive root (a stills run once wrote to
C:\\renders). under() returns a path absolute inside one base folder or raises; root_problem() is the
last-line rule gpu.py applies inside Blender before any render.
"""
import os

SEPS = "/\\"


def rooted_no_drive(path):
    """-> True for a Windows path that starts at a root with no drive ('/renders', '\\\\renders')."""
    return os.name == "nt" and str(path)[:1] in SEPS and not os.path.splitdrive(path)[0]


def is_root(folder):
    """-> True when folder is a filesystem or drive root ('/', 'C:/', '//server/share/')."""
    return not os.path.splitdrive(os.path.normpath(folder))[1].strip(SEPS)


def under(base, path, cwd=None):
    """-> `path` absolute and normalised, inside `base`: a relative path is taken from `cwd` (default: base);
    a trailing separator (a Blender frame folder) is kept. Raises ValueError when base is relative or a root,
    when path is rooted with no drive, or when the result leaves base."""
    base = os.path.normpath(base)
    if rooted_no_drive(base) or not os.path.isabs(base):
        raise ValueError(f"outpath: base {base!r} is not an absolute folder")
    if is_root(base):
        raise ValueError(f"outpath: base {base!r} is a drive root")
    if rooted_no_drive(path):
        raise ValueError(f"outpath: {path!r} starts at the drive root with no drive (Blender would write there)")
    full = os.path.normpath(os.path.join(cwd or base, path))
    try:
        inside = os.path.commonpath([os.path.normcase(base), os.path.normcase(full)]) == os.path.normcase(base)
    except ValueError:
        inside = False
    if not inside:
        raise ValueError(f"outpath: {path!r} resolves to {full}, outside {base}")
    return full + os.sep if str(path).endswith(tuple(SEPS)) else full


def root_problem(path):
    """-> why Blender must not render to `path` (a scene.render.filepath after bpy.path.abspath): empty,
    rooted with no drive, relative, or a file or sequence folder at a filesystem or drive root. None when safe."""
    p = str(path or "")
    if not p:
        return "the render path is empty"
    if rooted_no_drive(p):
        return f"{p!r} starts at the drive root with no drive"
    if not os.path.isabs(p):
        return f"{p!r} is relative (Blender resolves it against the drive root)"
    folder = p if p[-1] in SEPS else os.path.dirname(p)
    if is_root(folder):
        return f"{p!r} writes at a drive root"
    return None
