"""score.py: the sound design as event handlers (filmkit.sound.mix module docstring, 'Score contract').

HANDLERS maps every event kind in timeline.json to a function(event, ctx) or the kind is in SILENT.
music(ctx) fills the music buses; MASTER holds the mastering numbers; REFERENCE the loudness contour
(None = unchecked). The greybox plays one click per landing over a quiet chord bed. Every patch,
level and number here is TASTE; nobody has listened to the engine's starter generators.
"""
import sys
sys.dont_write_bytecode = True
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.environ.get("FILM_ENGINE") or os.path.normpath(
    os.path.join(HERE, "..", "..", ".claude", "skills", "film-engine", "scripts"))
sys.path[:0] = [p for p in (HERE, ENGINE) if p not in sys.path]

from filmkit.sound import synth  # noqa: E402

# TASTE: levels in dB per sound.
MIX = {"land": -8.0, "bed": -30.0}
# TASTE: marker colours of the sound check image, by kind.
MARKER_COLOURS = {"land": "#ff4040"}


def land(ev, ctx):
    """A landing: one click on the picture frame of the event (ctx.clock.at)."""
    # TASTE: the patch. synth.click(sr, seed, dur, f) is a placeholder generator.
    sig = synth.click(ctx.clock.sr, ctx.seed, dur=0.012, f=2500.0)
    ctx.add("fx", sig, ctx.clock.at(ev["t"]), gain_db=MIX["land"])


HANDLERS = {"land": land}
# Kinds that make no sound, on purpose.
SILENT = ("takeoff", "press")


def music(ctx):
    """The bed: a quiet chord over the whole film (TASTE)."""
    dur = ctx.clock.duration
    sig = synth.chord(ctx.clock.sr, [48, 55, 60], dur, cutoff_hz=900.0)
    ctx.add("music", sig, ctx.clock.at(0.0), gain_db=MIX["bed"])


# TASTE: mastering. target_lufs None = no makeup loop; a film names its target and loudness window.
MASTER = {"target_lufs": -24.0, "window_s": (0.0, 2.0), "ceiling_dbtp": -1.0, "fade_s": (1.9, 2.0),
          "fade_pow": 2.6, "hp_hz": 25.0, "comp": {"threshold_db": -22, "ratio": 3, "attack_ms": 10, "release_ms": 120}}
# TASTE: LUFS per 0.5 s block to compare against (None = unchecked, or a list as long as the block count).
REFERENCE = None
