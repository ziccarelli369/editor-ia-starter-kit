"""build.py: run this project's build chain (the engine's build.py with this folder as the project).

  python -B build.py [--upto <step>] [--from <step>] [--only <step>] [--force] [--dry]
  steps: timeline ui comp sound blend check stills animatic final encode verify (and, with a build.json
  stills_9x16 list, check_9x16 stills_9x16 final_9x16 encode_9x16 verify_9x16: the vertical check, stills and final)

Every step refuses to run on stale inputs (API.md 'Freshness rule') and stamps its outputs. Knobs
that are not taste (stills frames, crf, encode preset, animatic samples, UI font, contact sheet step)
live in build.json. Env: FILM_ENGINE (engine scripts folder), FILM_PYTHON (the kit venv), BLENDER,
CHROME, NODE. Mechanical.
"""
import sys
sys.dont_write_bytecode = True
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.environ.get("FILM_ENGINE") or os.path.normpath(
    os.path.join(HERE, "..", "..", ".claude", "skills", "film-engine", "scripts"))
os.environ["FILM_ENGINE"] = ENGINE
sys.path.insert(0, ENGINE)

import build as engine_build  # noqa: E402

if __name__ == "__main__":
    sys.exit(engine_build.main([HERE] + sys.argv[1:]))
