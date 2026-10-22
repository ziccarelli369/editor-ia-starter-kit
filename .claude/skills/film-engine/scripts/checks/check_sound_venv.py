"""check_sound_venv.py: quick check of filmkit.sound (synth, mix, soundcheck). Needs the kit venv
(numpy, scipy, pedalboard) and ffmpeg on PATH.

Builds a 2 s test score from three generic generators on a 120 BPM grid with
five events (two share a frame; one is a sub-frame 'exact' event), masters it
to a target, and asserts: length = round(2 * 48000); true peak <= the ceiling;
every event found within one frame in the mix and in its own stem; two builds
byte-identical; silencing any one kind makes the hit table fail for it; the
WAV re-reads at the right length; the check PNG and the report are written,
the report carrying the mutation check (MUTATION: 3/3) and failing on an
escaped kind; the step module (sound.step.run) builds a temp project end to
end with the MUTATION line in its report; a score whose bus chain drops the fx
bus (stems intact, a hi-hat groove on the grid) has its dropped kinds read
ESCAPED and their rows fail on a None audibility, so the step exits 1 with no
SOUND floor set; the K-weighting computed for 48 kHz
equals the published constants. Outputs go to a temp folder (removed on pass,
kept and named on fail). The numbers below are check fixtures, not a sound
design.

  <kit venv python> -B check_sound_venv.py
"""
import sys
sys.dont_write_bytecode = True
import json
import math
import os
import shutil
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import numpy as np  # noqa: E402
from filmkit import ease, timebase  # noqa: E402
from filmkit.sound import mix, soundcheck, step, synth  # noqa: E402

FPS, SR, DURATION, BPM = 30, 48000, 2.0, 120


def beat(n):
    return n * 60.0 / BPM


def make_timeline():
    """-> a minimal timeline doc: five events of three kinds on the beat grid."""
    rows = [("thump", beat(1), None), ("blip", beat(2), None), ("click", beat(2), None),
            ("thump", beat(3), None), ("blip", beat(3.5), "exact")]
    count, events = {}, []
    for kind, t, place in rows:
        n = count[kind] = count.get(kind, 0) + 1
        ev = {"id": f"{kind}#{n}", "t": t, "kind": kind, "frame": timebase.frame(t, FPS)}
        if place:
            ev["place"] = place
        events.append(ev)
    events.sort(key=lambda e: (e["t"], e["kind"], e["id"]))
    return {"format": {"fps": FPS, "duration": DURATION, "bpm": BPM}, "events": events}


class Score:
    """Check fixture in the score.py shape (see mix.py's score contract)."""

    @staticmethod
    def thump(ev, ctx):
        ctx.add("fx", synth.thump(ctx.clock.sr, ctx.seed), ctx.clock.at(ev["t"]), gain_db=-6.0)

    @staticmethod
    def blip(ev, ctx):
        start = ctx.clock.exact(ev["t"]) if ev.get("place") == "exact" else ctx.clock.at(ev["t"])
        sig = synth.blip(ctx.clock.sr, ctx.seed)
        ctx.add("fx", sig, start, gain_db=-10.0, pan=0.3)
        ctx.add("verb", sig, start, gain_db=-20.0)

    @staticmethod
    def click(ev, ctx):
        ctx.add("fx", synth.click(ctx.clock.sr, ctx.seed), ctx.clock.at(ev["t"]), gain_db=-8.0, pan=-0.3)

    HANDLERS = {"thump": thump.__func__, "blip": blip.__func__, "click": click.__func__}

    @staticmethod
    def music(ctx):
        sig = synth.chord(ctx.clock.sr, [48, 55, 60], 1.8, cutoff_hz=1200.0)
        ctx.add("music", sig, ctx.clock.at(0.0), gain_db=-24.0)

    @staticmethod
    def bus_chain(buses):
        import pedalboard as pb
        verb = mix.fx_board(synth.hp(buses["verb"].x, 180.0, SR), SR,
                            pb.Reverb(room_size=0.3, wet_level=1.0, dry_level=0.0))
        return buses["music"].x + buses["fx"].x + verb

    MASTER = {"target_lufs": -22.0, "window_s": (0.0, 2.0), "ceiling_dbtp": -1.0, "fade_s": (1.9, 2.0),
              "fade_pow": 2.6, "hp_hz": 25.0,
              "comp": {"threshold_db": -22, "ratio": 3, "attack_ms": 10, "release_ms": 120}}


class DroppedScore(Score):
    """The same score with the fx bus left out of the pre-master (a bus_chain slip): thump and click sound in
    their stems only, blip survives through the verb bus. A hi-hat on the 16th grid gives every target a mix
    onset, so the onset test alone passes every row."""

    @staticmethod
    def music(ctx):
        Score.music(ctx)
        hat = synth.click(ctx.clock.sr, 11)
        for k in range(16):
            ctx.add("music", hat, ctx.clock.exact(k * 0.125), gain_db=-14.0)

    @staticmethod
    def bus_chain(buses):
        import pedalboard as pb
        verb = mix.fx_board(synth.hp(buses["verb"].x, 180.0, SR), SR,
                            pb.Reverb(room_size=0.3, wet_level=1.0, dry_level=0.0))
        return buses["music"].x + verb


def main():
    clock = mix.Clock(FPS, SR, DURATION)
    tl = make_timeline()
    events = tl["events"]
    failures = []

    def check(cond, text):
        print(("ok   " if cond else "FAIL ") + text)
        if not cond:
            failures.append(text)

    def build_fn(muted=()):
        return mix.build(Score, clock, tl, mute=muted)

    out, makeup, stems, pre = build_fn()
    n_expected = int(math.floor(DURATION * SR + 0.5))
    check(clock.n == n_expected == 96000, f"clock.n = {clock.n} = round(2 * 48000)")
    check(out.shape == (2, n_expected), f"master output shape {out.shape}")
    tp_db = 20.0 * math.log10(soundcheck.true_peak(out, SR))
    check(tp_db <= Score.MASTER["ceiling_dbtp"], f"true peak {tp_db:.2f} dBTP <= {Score.MASTER['ceiling_dbtp']}")
    blocks = soundcheck.block_lufs(out, SR)
    mean_lufs = 10.0 * np.log10(np.mean(10.0 ** (blocks / 10.0)))
    check(abs(mean_lufs - Score.MASTER["target_lufs"]) <= 0.5,
          f"window loudness {mean_lufs:.2f} LUFS within 0.5 of target {Score.MASTER['target_lufs']} (makeup {makeup:+.1f} dB)")
    check(sorted(stems) == ["blip", "click", "thump"] and all(s.shape == (n_expected,) for s in stems.values()),
          "one mono stem per kind")

    rows = soundcheck.hit_table(events, out, stems, clock)
    worst = max(1e9 if v is None else abs(v) for r in rows for v in (r["mix_ms"], r["stem_ms"]))
    check(len(rows) == 5 and all(r["ok"] for r in rows), f"hit table {sum(r['ok'] for r in rows)}/{len(rows)} within one frame, worst {worst:.1f} ms")
    for r in rows:
        print(f"     {r['id']:<9} target {r['target']:>6} mix {r['mix_ms']:+6.1f} ms stem {r['stem_ms']:+6.1f} ms stem {r['stem_db']:6.1f} dB")
    exact_row = next(r for r in rows if r["id"] == "blip#2")
    check(exact_row["target"] == clock.exact(beat(3.5)) != clock.at(beat(3.5)), "place='exact' event targets its exact sample")
    check(soundcheck.presence(events, stems, clock) == [], "presence: no event without its own onset")

    check(soundcheck.determinism_check(lambda: build_fn()[0]), "determinism: two builds byte-identical")
    def mix_and_stems(muted):
        r = build_fn(muted)
        return r[0], r[2]

    caught = soundcheck.mutation_check(mix_and_stems, ["thump", "blip", "click"], clock, events)
    check(all(caught.values()), f"mutation: silencing a kind fails its rows {caught}")
    # case B (r3-11): the kind removed from the MIX, its stem kept. The old scoring (muted stems) never reads the
    # mix: with the unmuted stems and the old 'ok' alone every row still passes on a nearby onset. The new scoring
    # (unmuted stems + the muted pre-master as the rest) catches it: the kind adds nothing there (audible None).
    def mix_stems_pre(muted):
        r = build_fn(muted)
        return r[0], r[2], r[3]
    escaped = {}
    for k in ("thump", "blip", "click"):
        m_k, _s, _p = mix_stems_pre([k])
        rows_k = soundcheck.hit_table([e for e in events if e["kind"] == k], m_k, stems, clock)
        escaped[k] = any(r["ok"] for r in rows_k)
    check(any(escaped.values()), f"case B repro: with the stem kept, the onset test alone lets a kind through {escaped}")
    audible = {}
    caught_b = soundcheck.mutation_check(mix_stems_pre, ["thump", "blip", "click"], clock, events, stems=stems, pre=pre,
                                         audible=audible)
    check(all(caught_b.values()), f"case B: muting a kind in the mix, scored against the unmuted stems, is caught {caught_b}")
    check(sorted(audible) == sorted(e["id"] for e in events) and all(v is not None and math.isfinite(v) for v in audible.values()),
          f"mutation_check fills the real audibility per event: {audible}")
    # the audibility column: the kind over the rest of the pre-master in the phone band, best 5 ms of 40;
    # a loud kind over a quiet bed reads well above 0 dB; a kind absent from the mix reads None
    rests = {k: mix_stems_pre([k])[2] for k in ("thump", "blip", "click")}
    rows_a = soundcheck.hit_table(events, out, stems, clock, pre=pre, rests=rests)
    auds = {r["id"]: r["audible_db"] for r in rows_a}
    check(all(abs(auds[i] - audible[i]) < 1e-9 for i in auds), "hit_table(pre, rests) and mutation_check agree on audible_db")
    thump_rows = [r["audible_db"] for r in rows_a if r["kind"] == "thump"]
    check(all(a > 6.0 for a in thump_rows), f"a -6 dB thump over a -24 dB chord bed reads over +6 dB: {thump_rows}")
    gone = soundcheck.hit_table([e for e in events if e["kind"] == "thump"], rests["thump"], stems, clock,
                                pre=rests["thump"], rests={"thump": rests["thump"]})
    check(all(r["audible_db"] is None for r in gone), "a kind absent from the mix has no audibility (None)")
    one = soundcheck.audibility(np.zeros(SR), np.ones(SR) * 0.1, [100, SR + 5], SR)
    check(one == [None, None], f"audibility: a zero contribution and an out-of-range target read None: {one}")
    for r in rows:
        r["audible_db"] = audible.get(r["id"])
    # a kind dropped from the MIX (stem intact, a groove onset on its grid): the onset + stem test passes every row,
    # the real audibility reads None (a fact, no floor needed) and the mutation is ESCAPED: muting it changes nothing
    out_d, _mk, stems_d, pre_d = mix.build(DroppedScore, clock, tl)
    rows_d = soundcheck.hit_table(events, out_d, stems_d, clock)
    check(len(rows_d) == 5 and all(r["ok"] for r in rows_d),
          f"dropped-fx fixture: the onset + stem test alone passes every row {[(r['id'], r['ok']) for r in rows_d]}")

    def dropped_fn(muted):
        r = mix.build(DroppedScore, clock, tl, mute=muted)
        return r[0], r[2], r[3]
    aud_d = {}
    caught_d = soundcheck.mutation_check(dropped_fn, ["thump", "blip", "click"], clock, events, stems=stems_d, pre=pre_d, audible=aud_d)
    check(caught_d == {"thump": False, "blip": True, "click": False},
          f"mutation: a kind absent from the mix is ESCAPED, the kind still in it is caught: {caught_d}")
    check(all(aud_d[e["id"]] is None for e in events if e["kind"] != "blip") and all(aud_d[e["id"]] is not None for e in events if e["kind"] == "blip"),
          f"real audibility: None for the dropped kinds, measured for blip: {aud_d}")

    gens = {
        "click": synth.click(SR, 1), "thump": synth.thump(SR, 1), "boing": synth.boing(SR, 1),
        "thwack": synth.thwack(SR, 1), "whoosh": synth.whoosh(SR, 1, shape="bell"), "bell": synth.bell(SR, 1),
        "blip": synth.blip(SR, 1), "riser": synth.riser(SR, 1, dur=0.5), "zap": synth.zap(SR, 1),
        "chord": synth.chord(SR, [60, 64], 0.3, osc="square", cutoff_hz=3000.0),
    }
    bad = [k for k, y in gens.items()
           if y.ndim != 1 or not np.all(np.isfinite(y)) or abs(np.abs(y).max() - 1.0) > 1e-9 or y[0] != 0.0]
    check(not bad, f"every starter generator is mono, finite, peak 1, 0 on sample 0 (bad: {bad})")
    r = synth.riser(SR, 1, dur=0.5)
    segs = [np.abs(r[i * len(r) // 10:(i + 1) * len(r) // 10]).max() for i in range(10)]
    check(all(a < b for a, b in zip(segs, segs[1:])) and segs[-1] == 1.0, "riser: envelope rises to its end")
    n = 4800
    prim = {"saw": synth.saw(220.0, n, SR), "square": synth.square(220.0, n, SR, 0.25), "tri": synth.tri(220.0, n, SR),
            "fm": synth.fm(220.0, 2.0, 1.5, n, SR, synth.env_exp(n, SR, 0.05)), "pink": synth.noise(n, 3, "pink"),
            "sweep2": synth.sweep(np.vstack([synth.noise(n, 4), synth.noise(n, 5)]), np.linspace(200, 8000, n), SR, kind="bp"),
            "delay": synth.delay(synth.click(SR, 1), SR, 0.01, 0.5, 0.5), "drive": synth.tanh_drive(synth.sine(100.0, n, SR), 2.0)}
    check(all(np.all(np.isfinite(v)) and np.abs(v).max() <= 1.0 + 1e-9 for v in prim.values()), "oscillators, fm, pink, stereo sweep, delay, drive: finite, <= 1")
    adsr = synth.env_adsr(n, SR, 0.01, 0.02, 0.5, 0.01)
    check(adsr[0] == 0.0 and abs(adsr[2000] - 0.5) < 1e-12 and adsr[-1] == 0.0 and adsr.max() <= 1.0, "env_adsr: 0, sustain, 0")
    hot = mix.tp_limit(np.vstack([synth.sine(1000.0, n, SR)] * 2) * 4.0, SR, -1.1)
    hot_db = 20.0 * math.log10(soundcheck.true_peak(hot, SR))
    check(hot_db <= -1.0, f"tp_limit holds a +12 dB sine from sample 0 under the ceiling ({hot_db:.2f} dBTP)")
    duck = mix.duck_curve([0.05], 4800, SR, depth_db=-6.0)
    check(duck[0] == 1.0 and duck[2400] == 1.0 and synth.db(-6.0) <= duck.min() <= synth.db(-6.0) + 0.05
          and np.all(np.diff(duck[2400 + 192:]) >= 0), "duck_curve: unity before, near full depth after the attack, monotonic recovery")
    check(clock.frame_of(1600) == 2 and clock.frame_of(1599) == 1 and clock.at(4.95) == 149 * 1600, "Clock.frame_of and at() follow frame(t)")
    try:
        mix.Dispatcher(events, {"thump": Score.thump}, clock, {}, tl)
        check(False, "Dispatcher raises on a kind with no handler")
    except ValueError as e:
        check("blip" in str(e) and "click" in str(e), f"Dispatcher raises on a kind with no handler: {e}")
    d = mix.Dispatcher(events, Score.HANDLERS, clock, {}, tl, silent=())
    d.check_no_overlap("thump", "blip")
    try:
        d.check_no_overlap("blip", "thump")
        check(False, "check_no_overlap passes thump->blip pairs and catches a backwards pair")
    except ValueError as e:
        check(True, f"check_no_overlap passes thump->blip pairs and catches a backwards pair: {e}")

    k48 = soundcheck._k_coeffs(48000)
    ref = (([1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585]),
           ([1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621]))
    err = max(np.max(np.abs(np.array(c) - np.array(r))) for stage, rstage in zip(k48, ref) for c, r in zip(stage, rstage))
    check(err < 1e-6, f"K-weighting at 48 kHz matches the published constants (max diff {err:.1e})")

    try:
        check(mix.seed_of("thump", 2) == ease.seed_of("thump", 2), "mix.seed_of agrees with ease.seed_of")
    except NotImplementedError:
        print("skip ease.seed_of not implemented yet; mix.seed_of uses the documented formula")

    tmp = tempfile.mkdtemp(prefix="film-sound-check-")
    try:
        wav = os.path.join(tmp, "sound.wav")
        n = mix.write_wav(wav, out, SR)
        back, sr_back = mix.read_wav(wav)
        check(n == n_expected and back.shape == (2, n_expected) and sr_back == SR, f"WAV re-read: {back.shape} at {sr_back} Hz")
        check(abs(back - out).max() < 2e-7 * 2, f"24-bit round trip error {abs(back - out).max():.2e}")
        png = os.path.join(tmp, "sound_check.png")
        soundcheck.check_png(wav, png, [(e["t"], "#ff0000" if e["kind"] == "thump" else "cyan") for e in events])
        check(os.path.isfile(png) and os.path.getsize(png) > 1000, f"check PNG written ({os.path.getsize(png) if os.path.isfile(png) else 0} bytes)")
        ff = soundcheck.ffmpeg_ebur128(wav)
        check(ff["integrated"] is not None and abs(ff["integrated"] - soundcheck.integrated_lufs(back, SR)) <= 1.0,
              f"ffmpeg integrated {ff['integrated']} vs own {soundcheck.integrated_lufs(back, SR):.1f} LUFS within 1.0")
        rep = os.path.join(tmp, "sound_report.txt")
        code = soundcheck.report(rep, blocks, [None] * len(blocks), tp_db, n, n_expected, makeup, rows, ff,
                                 ceiling_dbtp=Score.MASTER["ceiling_dbtp"], mutation=caught)
        text = open(rep, encoding="utf-8").read()
        check(code == 0 and "HITS: 5/5" in text and "PRESENCE MISSING: 0" in text and f"LENGTH: {n} OK" in text
              and "MUTATION: 3/3 kinds caught" in text,
              "report: exit 0, HITS 5/5, PRESENCE MISSING 0, LENGTH OK, MUTATION 3/3")
        code = soundcheck.report(rep, blocks, [None] * len(blocks), tp_db, n, n_expected, makeup, rows, ff,
                                 ceiling_dbtp=Score.MASTER["ceiling_dbtp"], mutation={"thump": True, "blip": False})
        text = open(rep, encoding="utf-8").read()
        check(code == 1 and "MUTATION: 1/2 kinds caught" in text and "blip          ESCAPED" in text,
              "report: an escaped kind fails the step and is named")
        code = soundcheck.report(rep, blocks, [None] * len(blocks), tp_db, n, n_expected, makeup, rows, ff)
        check(code == 0 and "MUTATION: not run" in open(rep, encoding="utf-8").read(), "report without the mutation check says so")
        # the SOUND gate: a contour 2 LU off its reference fails contour_lu 1.0; a thump 7 ms off fails tap_ms 5
        shifted = [b + 2.0 for b in blocks]
        code = soundcheck.report(rep, blocks, shifted, tp_db, n, n_expected, makeup, rows, ff, contour_lu=1.0, tap_ms=5.0,
                                 tap_kinds=("thump",))
        text = open(rep, encoding="utf-8").read()
        check(code == 1 and "CONTOUR: 2.0 LU max" in text and "(limit 1.0) OVER" in text and "TAPS:" in text and "thump rows (limit 5.0) OK" in text,
              f"report: a 2 LU contour miss fails contour_lu 1.0 and names it: {[ln for ln in text.splitlines() if ln.startswith(('CONTOUR', 'TAPS'))]}")
        late = [dict(r, mix_ms=7.0) if r["kind"] == "thump" else r for r in rows]
        code = soundcheck.report(rep, blocks, shifted, tp_db, n, n_expected, makeup, late, ff, contour_lu=2.5, tap_ms=5.0,
                                 tap_kinds=("thump",))
        text = open(rep, encoding="utf-8").read()
        check(code == 1 and "(limit 2.5) OK" in text and "TAPS: 7.0 ms max" in text and "(limit 5.0) OVER" in text,
              "report: a thump 7 ms off fails tap_ms 5.0 while the contour passes 2.5")
        code = soundcheck.report(rep, blocks, shifted, tp_db, n, n_expected, makeup, late, ff, contour_lu=2.5, tap_ms=10.0,
                                 tap_kinds=("thump",))
        check(code == 0, "report: both limits held -> exit 0")
        # the audibility floor: every row carries its value; a floor under the quietest row passes, one over the
        # loudest fails and names the minimum; a listed row without a value (not measured) is UNDER
        lo, hi = min(audible.values()), max(audible.values())
        code = soundcheck.report(rep, blocks, [None] * len(blocks), tp_db, n, n_expected, makeup, rows, ff, audible_db=lo - 1.0)
        text = open(rep, encoding="utf-8").read()
        check(code == 0 and f"AUDIBLE: {lo:+.1f} dB min over 5/5 measured rows of blip/click/thump (floor {lo - 1.0}) OK" in text
              and "aud dB" in text, f"report: the AUDIBLE line and column, floor under the quietest row -> OK: {[ln for ln in text.splitlines() if ln.startswith('AUDIBLE')]}")
        code = soundcheck.report(rep, blocks, [None] * len(blocks), tp_db, n, n_expected, makeup, rows, ff, audible_db=hi + 1.0,
                                 audible_kinds=("thump",))
        text = open(rep, encoding="utf-8").read()
        check(code == 1 and "measured rows of thump (floor" in text and "UNDER" in text, "report: a floor over the loudest thump fails and names the kind")
        unmeasured = [dict(r, audible_db=None) if r["kind"] == "blip" else r for r in rows]
        code = soundcheck.report(rep, blocks, [None] * len(blocks), tp_db, n, n_expected, makeup, unmeasured, ff, audible_db=-60.0)
        check(code == 1 and "3/5 measured rows" in open(rep, encoding="utf-8").read(), "report: an unmeasured listed row is UNDER the floor")

        proj = os.path.join(tmp, "proj")
        os.makedirs(os.path.join(proj, "build"))
        with open(os.path.join(proj, "checks_config.py"), "w", encoding="utf-8") as fh:
            fh.write("SOUND = {'contour_lu': 1.0, 'tap_ms': 5.0, 'tap_kinds': ['thump']}\n")
        check(step.sound_rules(proj) == {"contour_lu": 1.0, "tap_ms": 5.0, "tap_kinds": ["thump"]}, "step.sound_rules reads checks_config.SOUND")
        doc = dict(tl, layout={}, frames=[], extra={})
        doc["hash"] = timebase.timeline_hash(doc)
        with open(os.path.join(proj, "build", "timeline.json"), "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        logged = []
        code = step.run(proj, Score, log=logged.append)
        text = open(os.path.join(proj, "build", "sound_report.txt"), encoding="utf-8").read()
        check(code == 0 and "MUTATION: 3/3 kinds caught" in text and "HITS: 5/5" in text
              and os.path.isfile(os.path.join(proj, "build", "sound.wav"))
              and os.path.isfile(os.path.join(proj, "build", "sound_check.png")),
              "step.run: temp project built, report with HITS 5/5 and MUTATION 3/3, wav and png written")
        check(any("mutation 3/3 kinds caught" in line for line in logged), f"step.run summary names the mutation count: {logged[-1:]}")
        check(any("SOUND gate contour_lu 1.0, tap_ms 5.0" in line for line in logged) and "thump rows (limit 5.0) OK" in text,
              f"step.run reads the SOUND gate from checks_config.py and the report names it: {logged[-1:]}")
        # the dropped-fx score through the step, no SOUND floor set: the rows of the dropped kinds fail (measured, no
        # contribution), their kinds read ESCAPED, exit 1
        proj2 = os.path.join(tmp, "proj_dropped")
        os.makedirs(os.path.join(proj2, "build"))
        with open(os.path.join(proj2, "build", "timeline.json"), "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        logged2 = []
        code = step.run(proj2, DroppedScore, log=logged2.append)
        text = open(os.path.join(proj2, "build", "sound_report.txt"), encoding="utf-8").read()
        check(code == 1 and "HITS: 2/5" in text and "MUTATION: 1/3 kinds caught" in text and "thump         ESCAPED" in text
              and "click         ESCAPED" in text and "AUDIBLE:" in text and "2/5 measured rows" in text,
              f"step.run: a kind dropped from the mix fails the step without a SOUND floor: exit {code}, "
              f"{[ln for ln in text.splitlines() if ln.startswith(('HITS', 'MUTATION', 'AUDIBLE'))]}")
        check(sum("aud     none NO" in line for line in logged2) == 3,
              f"step.run logs the three dropped rows as 'aud none NO': {[ln for ln in logged2 if ln.startswith('hit')]}")
    finally:
        if failures:
            print(f"outputs kept in {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    print(f"sound check: {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
