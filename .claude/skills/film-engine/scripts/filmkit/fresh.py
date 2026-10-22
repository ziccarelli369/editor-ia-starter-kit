"""fresh: derived artifacts must be newer than their inputs and stamped with the timeline hash.
Owner: checker. Standard library only.

Stamps live in <build>/stamps.json: {artifact: {'hash': tl_hash, 'inputs': {path: mtime},
'written': mtime, 'step': name}}. A step stamps its outputs after its own checks pass, with the
input mtimes it read before its first command ran (input_mtimes), so a source edited while the
step ran reads 'changed since the stamp'. The next
step calls require_fresh() and refuses to run when any input artifact is stale: older than one
of its inputs, an input changed since the stamp, stamped with another timeline hash, missing,
or missing its stamp. An input that is itself a stamped artifact must be fresh too.
Paths are relative to the project folder (the parent of build_dir); absolute paths are accepted.
"""
import hashlib
import json
import os

STAMPS = "stamps.json"


def _project(build_dir):
    return os.path.dirname(os.path.abspath(build_dir))


def _abs(project, path):
    return path if os.path.isabs(path) else os.path.join(project, path)


def _rel(project, path):
    return os.path.relpath(_abs(project, path), project).replace("\\", "/")


def file_hash(path):
    """-> 12 hex chars: sha1 of the file bytes."""
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def newest_mtime(paths):
    """-> max mtime over files and, for a folder, over every file in it. None when nothing exists."""
    best = None
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    m = os.path.getmtime(os.path.join(root, f))
                    best = m if best is None else max(best, m)
        elif os.path.exists(p):
            m = os.path.getmtime(p)
            best = m if best is None else max(best, m)
    return best


def load_stamps(build_dir):
    """-> dict from <build_dir>/stamps.json (empty when missing)."""
    path = os.path.join(build_dir, STAMPS)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _save_stamps(build_dir, stamps):
    os.makedirs(build_dir, exist_ok=True)
    path = os.path.join(build_dir, STAMPS)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(stamps, fh, indent=1, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def current_hash(build_dir):
    """-> the 'hash' of <build_dir>/timeline.json, or None when missing."""
    path = os.path.join(build_dir, "timeline.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh).get("hash")


def input_mtimes(build_dir, inputs):
    """-> {project-relative input: newest mtime (None when it does not exist)}, read now. build.py reads this
    before a step's first command runs and hands it to stamp(), so a source edited while the step runs is
    'changed since the stamp': the artifact was built from the old source."""
    project = _project(build_dir)
    return {_rel(project, p): newest_mtime([_abs(project, p)]) for p in inputs}


def stamp(build_dir, artifact, inputs, tl_hash, step=None, mtimes=None):
    """Record artifact as fresh: its inputs' mtimes and the timeline hash. Writes stamps.json.
    step: the build step that wrote it (named in the rerun advice). An input that does not exist is not
    an input (an optional project file), so it is left out of the stamp. mtimes: the inputs' mtimes as
    input_mtimes read them before the step ran (default: read now)."""
    project = _project(build_dir)
    mt = input_mtimes(build_dir, inputs) if mtimes is None else dict(mtimes)
    rec = {"hash": tl_hash,
           "inputs": {k: v for k, v in mt.items() if v is not None},
           "written": newest_mtime([_abs(project, artifact)])}
    if step:
        rec["step"] = step
    stamps = load_stamps(build_dir)
    stamps[_rel(project, artifact)] = rec
    _save_stamps(build_dir, stamps)
    return rec


def status(build_dir, artifact, tl_hash, _seen=None):
    """-> ('fresh', []) or ('stale', [reasons]) for one artifact (stamped inputs are checked too)."""
    project = _project(build_dir)
    key = _rel(project, artifact)
    stamps = load_stamps(build_dir)
    rec = stamps.get(key)
    if rec is None:
        return "stale", [f"{key}: no stamp"]
    reasons = []
    if rec.get("hash") != tl_hash:
        reasons.append(f"{key}: stamped for timeline {rec.get('hash')}, the timeline is {tl_hash}")
    art_m = newest_mtime([_abs(project, key)])
    if art_m is None:
        reasons.append(f"{key}: missing")
    seen = set(_seen or ()) | {key}
    for inp, m0 in rec.get("inputs", {}).items():
        m1 = newest_mtime([_abs(project, inp)])
        if m1 is None:
            reasons.append(f"{key}: input {inp} is missing")
        elif m0 is None or abs(m1 - m0) > 1e-6:
            reasons.append(f"{key}: input {inp} changed since the stamp")
        elif art_m is not None and m1 > art_m + 1e-6:
            reasons.append(f"{key}: older than its input {inp}")
        if inp in stamps and inp not in seen:
            sub, why = status(build_dir, inp, tl_hash, seen)
            if sub == "stale":
                reasons += [f"{key}: input {w}" for w in why]
    return ("stale", reasons) if reasons else ("fresh", [])


def require_fresh(build_dir, artifacts, tl_hash):
    """Check every artifact. Raises SystemExit(2) with the list of stale items and the step to rerun."""
    project = _project(build_dir)
    stamps = load_stamps(build_dir)
    stale = []
    for a in artifacts:
        st, why = status(build_dir, a, tl_hash)
        if st == "stale":
            stale.append((_rel(project, a), why))
    if not stale:
        return
    import sys
    for key, why in stale:
        for w in why:
            print(f"STALE {w}", file=sys.stderr)
        step = stamps.get(key, {}).get("step")
        print(f"rerun: {('step ' + step) if step else 'the step that writes ' + key}", file=sys.stderr)
    raise SystemExit(2)


def main(argv=None):
    """CLI: python -B -m filmkit.fresh <project_dir> [--require a,b,...] [--status]
    Exit 0 fresh, 2 stale (prints what to rerun)."""
    import sys
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv:
        print(main.__doc__)
        return 2
    project = os.path.abspath(argv[0])
    build = os.path.join(project, "build")
    tl_hash = current_hash(build)
    if "--status" in argv:
        for key in sorted(load_stamps(build)):
            st, why = status(build, key, tl_hash)
            print(f"{st:<5} {key}" + ("".join("\n      " + w for w in why) if why else ""))
    if "--require" in argv:
        names = argv[argv.index("--require") + 1].split(",")
        try:
            require_fresh(build, names, tl_hash)
        except SystemExit as e:
            return int(e.code or 2)
        print(f"fresh: {', '.join(names)}")
    return 0


if __name__ == "__main__":
    import sys
    sys.dont_write_bytecode = True
    sys.exit(main())
