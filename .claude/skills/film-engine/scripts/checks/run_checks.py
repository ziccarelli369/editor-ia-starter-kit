"""run_checks.py: discover check_*.py in this folder and run each one. Standard library only.

A check is a script that exits 0 on pass and non-zero on fail; its stdout and
stderr are shown under its name. The runner prints PASS or FAIL per check
and exits 1 when any check fails. It runs every check with the same
interpreter as itself, with -B, and never writes bytecode.

  python -B run_checks.py [--only name] [--python <path to the kit venv python>]
  --only matches a substring of the file name. --python runs checks that need numpy/Pillow (the file
  name says so: check_*_venv.py) with that interpreter; without it those checks are reported SKIP.
  A relative --python is taken from the caller's cwd (checks run with cwd = this folder); a --python
  that does not exist prints one line and exits 2. Every child gets PYTHONDONTWRITEBYTECODE=1 and -B.
"""
import sys
sys.dont_write_bytecode = True
import glob
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))


def discover(only=None):
    """-> sorted check_*.py paths in HERE, filtered by substring `only`."""
    paths = sorted(glob.glob(os.path.join(HERE, "check_*.py")))
    if only:
        paths = [p for p in paths if only in os.path.basename(p)]
    return paths


def run_one(path, venv_python=None):
    """Run one check. -> (status, output) with status PASS | FAIL | SKIP."""
    needs_venv = os.path.basename(path).endswith("_venv.py")
    exe = venv_python if needs_venv else sys.executable
    if needs_venv and not venv_python:
        return "SKIP", "needs --python <kit venv>"
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    proc = subprocess.run([exe, "-B", path], capture_output=True, text=True, env=env, cwd=HERE)
    out = (proc.stdout + proc.stderr).strip()
    return ("PASS" if proc.returncode == 0 else "FAIL"), out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    venv_python = argv[argv.index("--python") + 1] if "--python" in argv else None
    if venv_python:
        venv_python = os.path.abspath(venv_python)      # checks run with cwd=HERE; a kit-relative path must survive that
        if not os.path.isfile(venv_python):
            print(f"run_checks: --python {venv_python} does not exist (give the kit venv python)")
            return 2
    paths = discover(only)
    failed = 0
    for path in paths:
        name = os.path.basename(path)[:-3]
        status, out = run_one(path, venv_python)
        print(f"{status:<4} {name}")
        if out and status != "PASS":
            for line in out.splitlines():
                print(f"     {line}")
        failed += status == "FAIL"
    print(f"checks: {len(paths)} found, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
