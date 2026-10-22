"""step: the sound build step a project's sound.py calls. Owner: sound. Kit venv (numpy, scipy,
pedalboard; ffmpeg on PATH).

run(project_dir, score) builds build/sound.wav from the score module and build/timeline.json
(mix.build), then proves it: the hit table (timing and presence per kind), per-block loudness vs
score.REFERENCE, true peak vs score.MASTER['ceiling_dbtp'], the re-read length, the ffmpeg ebur128
cross-check, the check PNG with event markers, and the mutation check (soundcheck.mutation_check over
every kind that has a stem: mute it in the mix, score the muted mix against the unmuted stems, every
row of that kind must fail; the same muted builds give every row its audibility: the kind over the rest
of the pre-master mix, phone band, best 5 ms). Writes build/sound.wav, build/sound_report.txt (HITS /
PRESENCE MISSING / TAPS / AUDIBLE / TRUE PEAK / LENGTH / MUTATION lines) and build/sound_check.png.
Prints one line per hit and a summary.
-> exit code: 1 when a hit is missing, a measured row has no audibility (the mutation builds measured
it and the kind adds nothing to the mix there: its sound sits in its stem and not in the mix, so the row
reads 'aud none NO' and its kind ESCAPED, with no floor set), the length is wrong, the true peak is over
the ceiling, a kind escapes the mutation check, the loudness contour misses score.REFERENCE by more than
SOUND['contour_lu'], a tap lands more than SOUND['tap_ms'] off its frame, or a row of SOUND['audible_kinds']
(default: every kind) reads under SOUND['audible_db'] (SOUND from the project's checks_config.py when
it defines it; keys contour_lu, tap_ms, tap_kinds (default ('tap',)), audible_db, audible_kinds; absent
= not enforced, only reported). With mutation=False no audibility is measured, so no row fails on it and
an audible_db floor reads UNDER (every listed row unmeasured): the floor needs the mutation builds.
"""
import importlib
import math
import os

from .. import timebase
from . import SR, mix, soundcheck


def sound_rules(project_dir):
    """-> the project's checks_config.SOUND dict ({} when the module or the name is absent)."""
    if not os.path.isfile(os.path.join(project_dir, "checks_config.py")):
        return {}
    import sys
    added = project_dir not in sys.path
    if added:
        sys.path.insert(0, project_dir)
    try:
        return dict(getattr(importlib.import_module("checks_config"), "SOUND", None) or {})
    finally:
        if added:
            sys.path.remove(project_dir)


def run(project_dir, score, mutation=True, log=print, rules=None):
    """See the module doc. score: the project's score module (HANDLERS, MASTER, REFERENCE; SILENT,
    MARKER_COLOURS, music, bus_chain optional). mutation False skips the mutation check (the report then
    says 'MUTATION: not run'). rules: the SOUND dict (default: sound_rules(project_dir)). -> exit code."""
    build = os.path.join(project_dir, "build")
    rules = sound_rules(project_dir) if rules is None else dict(rules)
    doc = timebase.load_timeline(os.path.join(build, "timeline.json"))
    fmt = doc["format"]
    clock = mix.Clock(fmt["fps"], SR, fmt["duration"])
    out, makeup, stems, _pre = mix.build(score, clock, doc)
    wav = os.path.join(build, "sound.wav")
    n = mix.write_wav(wav, out, SR)
    rows = soundcheck.hit_table(doc["events"], out, stems, clock)
    blocks = soundcheck.block_lufs(out, SR)
    tp_db = 20.0 * math.log10(max(soundcheck.true_peak(out, SR), 1e-12))
    ff = soundcheck.ffmpeg_ebur128(wav)
    silent = set(getattr(score, "SILENT", ()))
    colours = getattr(score, "MARKER_COLOURS", {})
    markers = [(e["t"], colours.get(e["kind"], "#ffffff")) for e in doc["events"] if e["kind"] not in silent]
    soundcheck.check_png(wav, os.path.join(build, "sound_check.png"), markers)
    caught = None
    if mutation:
        def build_fn(muted):
            r = mix.build(score, clock, doc, mute=muted)
            return r[0], r[2], r[3]
        audible = {}
        caught = soundcheck.mutation_check(build_fn, sorted(stems), clock, doc["events"], stems=stems, pre=_pre,
                                           audible=audible)
        for r in rows:
            r["audible_db"] = audible.get(r["id"])
            if r["audible_db"] is None:       # measured, and the kind adds nothing to the mix there: a dropped sound
                r["ok"] = False
    code = soundcheck.report(os.path.join(build, "sound_report.txt"), blocks, getattr(score, "REFERENCE", None),
                             tp_db, n, clock.n, makeup, rows, ff, ceiling_dbtp=score.MASTER.get("ceiling_dbtp"),
                             mutation=caught, contour_lu=rules.get("contour_lu"), tap_ms=rules.get("tap_ms"),
                             tap_kinds=tuple(rules.get("tap_kinds", ("tap",))), audible_db=rules.get("audible_db"),
                             audible_kinds=rules.get("audible_kinds"))
    for r in rows:
        mm = "none" if r["mix_ms"] is None else f"{r['mix_ms']:+.1f} ms"
        au = "none" if r.get("audible_db") is None else f"{r['audible_db']:+.1f} dB"
        log(f"hit {r['id']:<10} f{r['frame']:>4} mix {mm:>9} stem {r['stem_db']:6.1f} dB aud {au:>8} {'ok' if r['ok'] else 'NO'}")
    mut = "not run" if caught is None else f"{sum(caught.values())}/{len(caught)} kinds caught"
    gate = ", ".join(f"{k} {v}" for k, v in rules.items()) or "none"
    log(f"sound: {n} samples, true peak {tp_db:.2f} dBTP, makeup {makeup:+.1f} dB, hits "
        f"{sum(r['ok'] for r in rows)}/{len(rows)}, mutation {mut}, SOUND gate {gate} -> build/sound.wav, "
        f"sound_report.txt, sound_check.png")
    return code
