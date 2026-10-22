"""sound.py: build build/sound.wav from score.py and the timeline, then prove it (filmkit.sound.step).

Runs in the kit venv (numpy, scipy, pedalboard; ffmpeg on PATH). Writes build/sound.wav,
build/sound_report.txt (HITS / PRESENCE MISSING / TRUE PEAK / LENGTH / MUTATION lines) and
build/sound_check.png. Exit 1 when a hit is missing, the length is wrong, the true peak is over the
ceiling or a kind escapes the mutation check. Mechanical: the step lives in the engine.
"""
import sys
sys.dont_write_bytecode = True
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.environ.get("FILM_ENGINE") or os.path.normpath(
    os.path.join(HERE, "..", "..", ".claude", "skills", "film-engine", "scripts"))
sys.path[:0] = [p for p in (HERE, ENGINE) if p not in sys.path]

from filmkit.sound import step  # noqa: E402
import score  # noqa: E402

if __name__ == "__main__":
    sys.exit(step.run(HERE, score))
