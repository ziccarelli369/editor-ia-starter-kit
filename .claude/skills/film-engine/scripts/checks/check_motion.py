"""check_motion.py: quick check of filmkit.arc, filmkit.camera and filmkit.hero_points. Standard library only.

Proves: an arc lands exactly at its landing time and height (an apex-0 arc slides flat); squash keeps
volume; frame_solve puts every point group inside its margin (and one group touches it); the auto-aperture
never drops under the need and never reverses inside a camera hold; yaw keys unwrap across a flip, and a hop
in place adds no travel bias; project / unproject / aim_dir / look_at_euler agree, a top-down (E = 90) view
included; a Rig keyed up to top-down and a shake past vertical both clamp at the pole (no 180 deg flip); the hero point cloud poses
as the spec says and shows the expression set blender/hero.py shows; the shot list is continuous through
every crossing kind. Exit 1 on any failure.
"""
import sys
sys.dont_write_bytecode = True
import importlib.util
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..")))
from filmkit import arc, camera, ease, hero_points, timebase, vec  # noqa: E402

FPS = 30
FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)


def close(a, b, tol=1e-9):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def isolated_steps(values, floor, ratio=4.0):
    """-> indices where a step is > floor and > ratio x both neighbours (the 480 Hz continuity rule)."""
    out = []
    for i in range(2, len(values) - 1):
        d0, d1, d2 = abs(values[i - 1] - values[i - 2]), abs(values[i] - values[i - 1]), abs(values[i + 1] - values[i])
        if d1 > floor and d1 > ratio * d0 and d1 > ratio * d2:
            out.append(i)
    return out


# ---------------------------------------------------------------- arcs
def check_arcs():
    p0, p1, t0, t1, apex = (0.1, -0.2, 0.0), (0.5, 0.3, 0.02), 1.03, 1.5, 0.12
    for v0, gs in ((None, None), ((0.4, -0.2), None), (None, (1.6, 0.0)), ((0.3, 0.1), (1.6, 0.0))):
        a = arc.ballistic(p0, p1, t0, t1, apex, v0=v0, ground_speed=gs)
        land, u = a(t1)
        check(close(land, p1, 1e-12) and u == 1.0, f"arc v0={v0} gs={gs}: lands at {land}, not {p1}")
        check(close(a(t0)[0], p0, 1e-12), f"arc v0={v0} gs={gs}: starts at {a(t0)[0]}, not {p0}")
        check(close(a(t1 + 1.0)[0], p1, 1e-12), "arc: not clamped after landing")
        zp = max(p0[2], p1[2]) + apex
        check(abs(a.z_of_u(a.uv) - zp) < 1e-12, f"arc apex {a.z_of_u(a.uv)} != {zp}")
        check(max(a(t0 + (t1 - t0) * i / 200)[0][2] for i in range(201)) <= zp + 1e-12, "arc rises over its apex")
        if v0 is not None:
            h = 1e-6
            vx = (a(t0 + h)[0][0] - p0[0]) / h
            vy = (a(t0 + h)[0][1] - p0[1]) / h
            check(abs(vx - v0[0]) < 1e-3 and abs(vy - v0[1]) < 1e-3, f"arc carry: start velocity ({vx:.4f}, {vy:.4f}) != {v0}")
    D = arc.duration_from_apex(0.0, 0.02, 0.12, 9.81)
    a = arc.ballistic(p0, p1, 0.0, D, 0.12)
    check(abs(a.g_eff - 9.81) < 1e-9, f"duration_from_apex: g_eff {a.g_eff} != 9.81")
    check(abs(a.travel - math.atan2(0.4, -0.5)) < 1e-12, "arc travel heading")
    check(arc.ballistic((0.3, 0.2, 0.0), (0.3, 0.2, 0.0), 0.0, 0.4, 0.1).travel is None, "a hop in place has no travel heading (None, not pi)")
    # zero apex between equal heights: a flat slide at z0, never a division by zero
    q0, q1 = (0.1, -0.2, 0.02), (0.5, 0.3, 0.02)
    flat = arc.ballistic(q0, q1, 1.0, 1.4, 0.0)
    zs = [flat.z_of_u(u) for u in (0.0, 0.5, 1.0)] + [flat(1.0 + 0.4 * i / 40)[0][2] for i in range(41)]
    check(all(z == 0.02 for z in zs) and flat.kz == 0.0 and flat.uv == 0.5 and flat.g_eff == 0.0,
          f"flat arc: z {min(zs)}..{max(zs)}, kz {flat.kz}, uv {flat.uv}")
    check(close(flat(1.4)[0], q1, 1e-12) and close(flat(1.2)[0], (0.3, 0.05, 0.02), 1e-12), "flat arc travel")
    D0 = arc.duration_from_apex(0.02, 0.02, 0.0, 9.81)
    check(D0 == 0.0, f"duration_from_apex at apex 0, equal heights: {D0} (want 0.0)")
    js = arc.resolve_jumps([("slide", 1.0, 1.4, (0.4, 0.5), 0.0, "hop", "tile", 0.0)], (0.0, 0.0), None, STYLES, FPS)
    check([J["arc"](1.2)[0][2] for J in js] == [0.0], "resolve_jumps: an apex-0 row slides flat")


STYLES = {"hop": dict(crouch=0.11, c_a=0.14, st=0.09, c_l=0.15, lean=0.06),
          "leap": dict(crouch=0.16, c_a=0.22, st=0.16, c_l=0.26, lean=0.10, ground_speed=(1.6, 0.0), tuck=0.12)}
ROWS = [("j1", 2.2, 2.5, (0.1, 0.0), 0.06, "hop", "btn:a", 0.0),
        ("j2", 2.9, 3.0, (0.2, 0.1), 0.04, "hop", "btn:a", 0.0),
        ("j3", 3.3, 3.5, (-0.3, 0.2), 0.30, "leap", "tile", 0.004)]


def surface(target, t):
    return -0.003 if (target == "btn:a" and t >= 2.5) else None


def check_jumps():
    js = arc.resolve_jumps(ROWS, (0.0, 0.0), surface, STYLES, FPS)
    check([j["id"] for j in js] == ["j1", "j2", "j3"], "resolve_jumps order")
    check(close(js[0]["arc"](2.5)[0], (0.1, 0.0, -0.003), 1e-12), f"j1 lands at {js[0]['arc'](2.5)[0]} (pressed button)")
    check(abs(js[1]["from"][2] + 0.003) < 1e-12, "j2 takes off from the pressed height")
    check(close(js[2]["from"], js[1]["to"], 1e-12), "j3 starts where j2 landed")
    check(abs(js[2]["to"][2] - 0.004) < 1e-12, "j3 lands at its surface_z")
    check(js[2]["frame"] == timebase.frame(3.5, FPS) == 106, "landing frame = frame(t1)")
    check(abs(js[1]["crouch"] - 0.11) < 1e-12 and abs(js[1]["crouch_t0"] - 2.79) < 1e-12, "crouch clipped to the style")
    rows2 = list(ROWS) + [("j4", 3.45, 3.9, (0.0, 0.0), 0.05, "hop", "tile", 0.0)]
    try:
        arc.resolve_jumps(rows2, (0.0, 0.0), None, STYLES, FPS)
        check(False, "overlapping jumps did not raise")
    except ValueError:
        pass
    try:
        arc.resolve_jumps([("x", 1.0, 1.2, (0, 0), 0.1, "fly", "t", 0.0)], (0.0, 0.0), None, STYLES, FPS)
        check(False, "unknown style did not raise")
    except KeyError:
        pass
    for t, want in ((2.0, ("ground", None)), (2.15, ("crouch", "j1")), (2.3, ("air", "j1")), (2.6, ("ground", "j1")),
                    (3.6, ("ground", "j3"))):
        ph, J = arc.phase(js, t)
        check((ph, J["id"] if J else None) == want, f"phase({t}) = {(ph, J and J['id'])}, want {want}")
    # squash keeps volume
    for c in (-0.2, 0.0, 0.1, 0.3, 0.5, 0.7):
        sx, sy, sz = arc.squash_scale(c)
        check(sx == sy and abs(sx * sy * sz - 1.0) < 1e-12, f"squash_scale({c}) volume {sx * sy * sz}")
        check(sz >= 0.45, "squash floor")
    check(arc.squash_scale(0.7)[2] == 0.45, "squash floor value")
    check(abs(arc.squash_scale(0.3, pin=1.0)[0] - 0.7 ** (-0.2)) < 1e-12, "pinned squash spreads less")
    # compression: continuous at 480 Hz, stretches at takeoff, squashes on landing
    track = [arc.compression(i / 480, js, STYLES) for i in range(int(2.0 * 480), int(3.9 * 480))]
    check(not isolated_steps(track, 5e-3), f"compression has isolated steps at {isolated_steps(track, 5e-3)[:3]}")
    check(abs(arc.compression(2.2, js, STYLES) + 0.09) < 1e-9, "stretch at takeoff = -st")
    check(arc.compression(2.5 + 0.04, js, STYLES) > 0.1, "landing squash")
    check(arc.compression(2.0, js, STYLES) == 0.0, "no compression before the first crouch")
    check(abs(arc.compression(2.0, js, STYLES, lambda t: 0.012) - 0.012) < 1e-12, "idle_fn adds")
    # pose about a pivot: the anchor point stays put
    R = vec.rot_xyz(0.3, -0.1, 0.8)
    Ry = vec.rot_z(0.8)
    piv = (0.03, 0.0, 0.0)
    pos = arc.pose_about_pivot((1.0, 2.0, 0.0), piv, R, Ry)
    check(close(vec.transform(R, pos, piv), vec.transform(Ry, (1.0, 2.0, 0.0), piv), 1e-12), "pose_about_pivot keeps the pivot")
    # press intervals and depth
    iv = arc.press_intervals([(2.5, "a"), (3.0, "a"), (4.5, "b")], None)
    check(iv == {"a": [(2.5, 4.5)], "b": [(4.5, math.inf)]}, f"press_intervals merge: {iv}")
    iv = arc.press_intervals([(2.5, "a"), (3.0, "a"), (4.5, "b")], 0.3)
    check(iv == {"a": [(2.5, 3.3)], "b": [(4.5, 4.8)]}, f"press_intervals release_after: {iv}")
    iv = arc.press_intervals([(2.5, "a", 2.9), (4.5, "b", None)], lambda t, b: t + 1.0)
    check(iv == {"a": [(2.5, 2.9)], "b": [(4.5, 5.5)]}, f"press_intervals t_leave: {iv}")
    hit = lambda tau, dur: min(1.0, tau / 0.1)  # noqa: E731
    rel = lambda x: math.exp(-x / 0.05)  # noqa: E731
    check(abs(arc.press_depth(2.55, [(2.5, 3.3)], hit, rel) - 0.5) < 1e-12, "press_depth inside")
    check(abs(arc.press_depth(3.35, [(2.5, 3.3)], hit, rel) - math.exp(-1.0)) < 1e-12, "press_depth release")
    check(arc.press_depth(2.0, [(2.5, 3.3)], hit, rel) == 0.0, "press_depth before")


# ---------------------------------------------------------------- yaw unwrap
def check_yaw():
    rad = math.radians
    for keys, want in (([(0.0, rad(170)), (1.0, rad(-170)), (2.0, rad(-160))], (rad(190), rad(200))),
                       ([(0.0, rad(-170)), (1.0, rad(170)), (2.0, rad(160))], (rad(-190), rad(-200)))):
        yaw = arc.yaw_track(keys)
        check(abs(yaw(1.0) - want[0]) < 1e-12 and abs(yaw(2.0) - want[1]) < 1e-12,
              f"yaw_track unwrap: {math.degrees(yaw(1.0)):.1f}, {math.degrees(yaw(2.0)):.1f} deg")
        steps = [abs(yaw((i + 1) / 480) - yaw(i / 480)) for i in range(2 * 480)]
        check(max(steps) < 0.02, f"yaw_track spins back: max step {max(steps):.3f} rad at 480 Hz")
    yaw = arc.yaw_track([(0.0, 0.0), (1.0, 1.0)], air_bias_fn=lambda t: 0.1, idle_fn=lambda t: 0.01)
    check(abs(yaw(0.0) - 0.11) < 1e-12 and abs(yaw.keyed(0.0)) < 1e-12, "yaw_track composes bias and idle")
    js = arc.resolve_jumps(ROWS, (0.0, 0.0), surface, STYLES, FPS)
    bias = arc.travel_bias(js, yaw.keyed, lambda J: 0.5)
    check(bias(2.0) == 0.0 and abs(bias(2.2)) < 1e-9 and abs(bias(2.5 - 1e-9)) < 1e-6 and bias(2.35) != 0.0,
          "travel_bias is zero on the ground and at both ends of a flight")
    # a hop in place (Arc.travel None) adds no yaw and never raises; the jumps before it keep their turn
    rows = ROWS + [("j4", 3.8, 4.0, (-0.3, 0.2), 0.05, "hop", "tile", 0.004)]
    js2 = arc.resolve_jumps(rows, (0.0, 0.0), surface, STYLES, FPS)
    bias2 = arc.travel_bias(js2, yaw.keyed, lambda J: 0.5)
    check(js2[3]["arc"].travel is None and bias2(3.9) == 0.0 and bias2(3.4) == bias(3.4) != 0.0,
          f"travel_bias on a hop in place: {js2[3]['arc'].travel} -> bias {bias2(3.9)} (want 0.0), j3 keeps {bias(3.4):.4f}")


# ---------------------------------------------------------------- pinhole
def check_pinhole():
    rnd = ease.mulberry32(7)
    for film in ((1920, 1080), (1080, 1920)):
        P, target, lens = (0.3, -1.2, 0.8), (0.05, 0.1, 0.0), 35.0
        check(close(camera.project(P, target, lens, target, film), (0.0, 0.0, vec.length(vec.sub(target, P))), 1e-12),
              "project(target) is the centre")
        rot = camera.look_at_euler(P, target)
        R = vec.rot_xyz(*rot)
        check(close(vec.mat_vec(R, (0.0, 0.0, -1.0)), vec.norm(vec.sub(target, P)), 1e-12), "look_at_euler forward")
        check(vec.mat_vec(R, (0.0, 1.0, 0.0))[2] > 0 and abs(vec.mat_vec(R, (1.0, 0.0, 0.0))[2]) < 1e-12 and rot[1] == 0.0,
              "look_at_euler has roll")
        for _ in range(20):
            X = (rnd() * 2 - 1, rnd() * 2 - 1, rnd() * 0.3)
            nx, ny, z = camera.project(P, target, lens, X, film)
            back = camera.unproject(P, target, lens, (nx, ny), X[2], film)
            check(back is not None and close(back, X, 1e-9), f"unproject(project(X)) != X for {X}")
            s = (rnd() * 1.8 - 0.9, rnd() * 1.8 - 0.9)
            f = camera.aim_dir(P, lens, X, s, film)
            got = camera.project(P, vec.add(P, f), lens, X, film)
            check(close(got[:2], s, 1e-9), f"aim_dir misses: {got[:2]} != {s}")
        A, E = 0.6, 0.4
        check(close(camera.heading_elev(camera.cam_basis(A, E)[2]), (A, E), 1e-12), "heading_elev inverts cam_basis")
    check(camera.project((0, 0, 1), (0, 1, 1), 50, (0, -1, 1))[0] == 99.0, "behind the camera -> 99")


def check_vertical():
    """E = 90 deg: a solved top-down hold projects through cam_basis(A, 90 deg), never onto the centre."""
    film, lens = (1920, 1080), 35.0
    tx = camera.tan_half(lens)
    ty = tx * film[1] / film[0]
    pts = [(0.7 + x, 0.4 + y, 0.0) for x in (-0.3, 0.3) for y in (-0.2, 0.2)]     # off the origin: target - pos
    probe = pts + [(0.45, 0.25, 0.0), (0.95, 0.25, 0.0), (0.7, 0.55, 0.02)]        # loses the heading residue
    for A in (0.0, 30.0, -135.0):
        sl = camera.ShotList([camera.Hold("top", 0.0, 1.0, A, 90.0, lens, lambda t: [(pts, 0.05)])], film=film).solve()
        st = camera.camera_state(sl, 0.5, lambda t: (0.7, 0.4, 0.0), None, film=film)
        P, T, hd = st["pos"], st["target"], st["heading"]
        r, u, f = camera.cam_basis(math.radians(A), math.pi / 2)
        check(hd == math.radians(A) and st["raw"]["heading"] == hd, f"top A{A}: heading {hd}")
        got = camera.basis_from_dir(vec.sub(T, P), hd)
        check(all(close(a, b, 1e-12) for a, b in zip(got, (r, u, f))), f"top A{A}: basis {got} != cam_basis(A, 90)")
        check(close(vec.cross(got[0], got[1]), vec.mul(got[2], -1.0), 1e-12), f"top A{A}: basis not right-handed")
        worst = 0.0
        for X in probe:
            d = vec.sub(X, P)
            zc = vec.dot(d, f)
            want = (vec.dot(d, r) / (zc * tx), vec.dot(d, u) / (zc * ty), zc)
            worst = max(worst, max(abs(a - b) for a, b in zip(camera.project(P, T, lens, X, film, 36.0, hd), want)))
        check(worst < 1e-9, f"top A{A}: max |project - basis| {worst:.2e} ndc")
        a, b = (camera.project(P, T, lens, X, film, 36.0, hd)[0] for X in probe[-3:-1])
        check(abs(b - a) > 0.1 and (b - a) * math.cos(math.radians(A)) > 0, f"top A{A}: world X 0.45 / 0.95 -> ndc x {a:.4f} / {b:.4f}")
        m = hero_points.silhouette(pts, st, film)["margin"]
        check(abs(m - 0.05) < 1e-9, f"top A{A}: solved margin {m:.6f} through project, want 0.05")
        R = vec.rot_xyz(*st["rot"])
        check(close(vec.mat_vec(R, (1.0, 0.0, 0.0)), r, 1e-12) and close(vec.mat_vec(R, (0.0, 1.0, 0.0)), u, 1e-12)
              and close(vec.mat_vec(R, (0.0, 0.0, -1.0)), f, 1e-12), f"top A{A}: rot {st['rot']} is not the basis")
        check(abs(st["rot"][2] - math.atan2(r[1], r[0])) < 1e-12, f"top A{A}: rz {st['rot'][2]} != basis rz")
    # no heading: north up (cam_basis(0, +-90)), the same as look_at_euler without one
    P, T = (0.7, 0.4, 1.2), (0.7, 0.4, 0.0)
    check(close(camera.project(P, T, lens, (0.9, 0.4, 0.0), film)[:2], (0.2 / (1.2 * tx), 0.0), 1e-12)
          and camera.look_at_euler(P, T) == (0.0, 0.0, 0.0), "vertical view without a heading is north up")
    up = camera.basis_from_dir((0.0, 0.0, 1.0), 0.5)
    check(all(close(a, b, 1e-12) for a, b in zip(up, camera.cam_basis(0.5, -math.pi / 2))), "looking up takes cam_basis(A, -90)")
    check(camera.basis_from_dir((0.0, 0.0, 0.0), 0.5)[0] == (0.0, 0.0, 0.0), "zero direction keeps its zero basis")
    # a crossing between two top-down holds turns the roll smoothly (heading eased, rz continuous at 480 Hz)
    sl = camera.ShotList([camera.Hold("t0", 0.0, 0.5, 0.0, 90.0, lens, lambda t: [(pts, 0.05)]),
                          camera.Hold("t1", 1.0, 1.5, 60.0, 90.0, lens, lambda t: [(pts, 0.05)])], film=film).solve()
    rz = [camera.camera_state(sl, i / 480, lambda t: (0.7, 0.4, 0.0), None, film=film)["rot"][2] for i in range(int(1.5 * 480) + 1)]
    check(abs(rz[0]) < 1e-12 and abs(rz[-1] + math.radians(60)) < 1e-12 and not isolated_steps(rz, 2e-3),
          f"top crossing: rz {rz[0]:.4f} -> {rz[-1]:.4f}, steps at {isolated_steps(rz, 2e-3)[:3]}")
    # an oblique hold into a top-down hold (and back out): every crossing kind keeps rz continuous at 480 Hz and
    # lands on the vertical hold's heading; the oblique end keeps its own basis (the blend starts on its view)
    subject = lambda t: (0.7, 0.4, 0.0)  # noqa: E731
    flight = arc.ballistic((0.7, 0.4, 0.0), (0.7, 0.4, 0.0), 0.5, 0.9, 0.1)
    for kind in ("ease", "orbit", ("truck", {"arc": flight, "whip": 0.3})):
        name = kind if isinstance(kind, str) else kind[0]
        sl = camera.ShotList([camera.Hold("ob", 0.0, 0.5, 20.0, 45.0, lens, lambda t: [(pts, 0.05)]),
                              camera.Hold("top", 1.0, 1.5, -120.0, 90.0, lens, lambda t: [(pts, 0.05)]),
                              camera.Hold("ob2", 2.0, 2.5, 160.0, 35.0, lens, lambda t: [(pts, 0.05)])],
                             {("ob", "top"): kind, ("top", "ob2"): kind}, subject_fn=subject, film=film).solve()
        # rz wraps at +-pi (the bake unwraps it, item 7): compare the unwrapped series
        rz = ease.unwrap_series([camera.camera_state(sl, i / 480, subject, None, film=film)["rot"][2] for i in range(int(2.5 * 480) + 1)])
        steps = isolated_steps(rz, 2e-3)
        at_top = rz[int(1.2 * 480)]
        f_in = sl.eval(0.5)[1]
        check(not steps and abs(math.atan2(-math.sin(math.radians(-120)), math.cos(math.radians(-120))) - math.atan2(math.sin(at_top), math.cos(at_top))) < 1e-9,
              f"{name} crossing into a top-down hold: rz steps at {[round(i / 480, 3) for i in steps[:3]]}, rz on the hold {math.degrees(at_top):.1f}")
        check(close(f_in, camera.cam_basis(math.radians(20.0), math.radians(45.0))[2], 1e-12), f"{name}: the oblique end keeps its view")
        hd = ease.unwrap_series([sl.heading(i / 480) for i in range(int(2.5 * 480) + 1)])
        check(not isolated_steps(hd, 2e-3), f"{name}: heading(t) continuous")
    # a crossing between two oblique holds is unchanged (bit-identical to the plain blend)
    sl = camera.ShotList([camera.Hold("a", 0.0, 0.5, 20.0, 45.0, lens, lambda t: [(pts, 0.05)]),
                          camera.Hold("b", 1.0, 1.5, -60.0, 30.0, lens, lambda t: [(pts, 0.05)])], film=film).solve()
    A, B = sl._eval_shot(sl.by_name["a"], 0.7), sl._eval_shot(sl.by_name["b"], 0.7)
    check(sl.eval(0.7) == camera._plain_blend(A, B, ease.smoothstep((0.7 - 0.5) / (1.0 - 0.5))), "oblique-to-oblique crossing is the plain blend")
    # a steep end (E 85, under vertical) is blended like a vertical one: an orbit from E 85 north-up into an
    # oblique hold 120 deg round turns the image once, no spin-back, image spin <= 10 deg/frame (8.5; the no-roll
    # blend alone turns it 17 deg/frame near the pole, and 42 in the tap-to-submit 9:16 open); a 79 deg end stays
    # the plain blend (11.6 deg/frame either way: that is the turn itself, spread over the crossing)
    def image_spin(sl, f0, f1, film):
        out, prev = [], None
        for f in range(f0, f1 + 1):
            R = vec.rot_xyz(*camera.camera_state(sl, (f - 1) / FPS, subject, None, film=film)["rot"])
            if prev is not None:
                Rr = vec.mat_mul(vec.mat_t(prev), R)
                ang = math.acos(max(-1.0, min(1.0, (Rr[0][0] + Rr[1][1] + Rr[2][2] - 1) / 2)))
                ax = (Rr[2][1] - Rr[1][2], Rr[0][2] - Rr[2][0], Rr[1][0] - Rr[0][1])
                n = math.sqrt(sum(a * a for a in ax)) or 1.0
                out.append(math.degrees(ang) * (-ax[2] / n) if ang >= 1e-9 else 0.0)
            prev = R
        return out
    tall = (1080, 1920)
    spine = [(0.7 + x, 0.4 + y, 0.0) for x in (-0.12, 0.12) for y in (-0.35, 0.35)]
    for E_top, limit in ((85.0, 10.0), (79.0, None)):
        sl = camera.ShotList([camera.Hold("top", 0.0, 0.4, 0.0, E_top, 17.0, lambda t: [(spine, 0.12)]),
                              camera.Hold("ob", 1.2, 1.6, 120.0, 42.0, 24.0, lambda t: [(pts, 0.08)])],
                             {("top", "ob"): ("orbit", {"ease": "smoother"})}, subject_fn=subject, film=tall).solve()
        spins = image_spin(sl, 1, int(1.6 * FPS) + 1, tall)
        signs = [s for s in spins if abs(s) > 0.5]
        if limit is not None:
            check(max(abs(s) for s in spins) <= limit and (not signs or all((s < 0) == (signs[0] < 0) for s in signs)),
                  f"E {E_top} orbit into an oblique hold: image spin max {max(abs(s) for s in spins):.1f} deg/frame, "
                  f"spin-back {any((s < 0) != (signs[0] < 0) for s in signs) if signs else False}")
            check(not isolated_steps(ease.unwrap_series([sl.heading(i / 480) for i in range(int(1.6 * 480) + 1)]), 2e-3),
                  f"E {E_top}: heading(t) continuous")
        else:
            A, B = sl._eval_shot(sl.by_name["top"], 0.8), sl._eval_shot(sl.by_name["ob"], 0.8)
            check(not camera._steep(A[1]) and camera._steep(camera.cam_basis(0.0, math.radians(80.0))[2]),
                  f"_steep: E {E_top} is not steep, E 80 is")
    # the same shape with a vertical top end keeps the earlier contract (one smooth turn)
    check(camera.STEEP_DEG == 80.0, "STEEP_DEG is the documented 80 deg")


def check_pole():
    """Past vertical the no-roll basis takes heading A + 180 (the image flips). A Rig keyed up to top-down
    (E 60 -> 90 -> 90) overshoots 90 on Catmull-Rom over the whole hold, and a shake on a steep hold can push
    E past 90: both clamp at the pole, so rz stays -A (the roll from the heading) and a world point at +X
    stays on its side of the frame."""
    film, A = (1080, 1920), 30.0
    rig = camera.Rig("rise", 0.0, 2.0, lambda t: (0.0, 0.0, 0.0),
                     [(0.0, A, 60.0, 2.0, 35.0), (1.0, A, 90.0, 2.0, 35.0), (2.0, A, 90.0, 2.0, 35.0)])
    sl = camera.ShotList([rig], film=film)
    origin = lambda t: (0.0, 0.0, 0.0)  # noqa: E731
    rz, xs, Es = [], [], []
    for i in range(int(0.95 * 480), int(2.0 * 480) + 1):
        st = camera.camera_state(sl, i / 480, origin, None, film=film)
        rz.append(st["rot"][2])
        xs.append(camera.project(st["pos"], st["target"], st["lens"], (0.2, 0.0, 0.0), film, 36.0, st["heading"])[0])
        Es.append(math.degrees(math.asin(-sl.eval(i / 480)[1][2])))
    rz = ease.unwrap_series(rz)
    check(max(abs(r + math.radians(A)) for r in rz) < 1e-9 and not isolated_steps(rz, 2e-3),
          f"rig 60 -> 90 -> 90: rz {math.degrees(min(rz)):.1f}..{math.degrees(max(rz)):.1f} deg over the hold, want -{A:.0f} throughout")
    check(all(x > 0 for x in xs), f"rig at the pole: a world point at +X changes side ({min(xs):+.3f}..{max(xs):+.3f} ndc)")
    check(abs(max(Es) - 90.0) < 1e-9 and min(Es) > 80.0, f"rig elevation clamped at 90: {min(Es):.2f}..{max(Es):.2f} deg")
    # a 5 deg shake on an E 88 hold: the elevation reaches the pole (clamped at 90) and never flips; the roll stays
    # within the shake's own amplitude of -A (at the clamp the heading part of the shake leaves the roll)
    frame = [(0.7 + x, 0.4 + y, 0.0) for x in (-0.3, 0.3) for y in (-0.2, 0.2)]
    sl = camera.ShotList([camera.Hold("top", 0.0, 1.0, A, 88.0, 35.0, lambda t: [(frame, 0.05)])], film=film).solve()
    shakes = [(0.3, 5.0, 0.1, 7.0, 9.0)]
    subject = lambda t: (0.7, 0.4, 0.0)  # noqa: E731
    rz, xs, Es = [], [], []
    for i in range(int(0.3 * 480), int(0.9 * 480) + 1):
        st = camera.camera_state(sl, i / 480, subject, None, shakes, film)
        rz.append(st["rot"][2])
        xs.append(camera.project(st["pos"], st["target"], st["lens"], (0.9, 0.4, 0.0), film, 36.0, st["heading"])[0])
        Es.append(math.degrees(math.asin(-(st["target"][2] - st["pos"][2]) / st["focus_distance"])))
    rz = ease.unwrap_series(rz)
    check(abs(max(Es) - 90.0) < 1e-9, f"the shake reaches the pole (E clamped at 90): max E {max(Es):.3f}")
    check(max(abs(r + math.radians(A)) for r in rz) <= math.radians(5.0) + 1e-9 and all(x > 0 for x in xs),
          f"shaken steep hold: rz {math.degrees(min(rz)):.1f}..{math.degrees(max(rz)):.1f} deg (want within 5 of -{A:.0f}), "
          f"probe ndc x {min(xs):+.3f}..{max(xs):+.3f}")


# ---------------------------------------------------------------- hero
HERO = {
    "name": "hero", "euler_order": "XYZ", "facing": "-Y",
    "parts": [
        {"name": "body", "parent": None, "shape": "rbox", "size": (0.12, 0.06, 0.08), "r": 0.012, "k": 7,
         "pivot": (0, 0, 0.06), "offset": (0, 0, 0), "axis": None, "material": "body", "pass_index": 1},
        {"name": "arm_px", "parent": "body", "shape": "capsule", "a": (0, 0, 0), "b": (0.03, 0, 0), "r": 0.008,
         "pivot": (0.052, 0, -0.005), "offset": (-0.014, 0, 0), "axis": "Y", "material": "body", "pass_index": 1},
        {"name": "arm_nx", "parent": "body", "shape": "capsule", "a": (0, 0, 0), "b": (-0.03, 0, 0), "r": 0.008,
         "pivot": (-0.052, 0, -0.005), "offset": (0.014, 0, 0), "axis": "Y", "material": "body", "pass_index": 1},
        {"name": "leg_f_px", "parent": "body", "shape": "rbox", "size": (0.02, 0.02, 0.028), "r": 0.006,
         "pivot": (0.021, -0.013, -0.036), "offset": (0, 0, -0.01), "axis": "X", "material": "body", "pass_index": 1},
        {"name": "leg_f_nx", "parent": "body", "shape": "rbox", "size": (0.02, 0.02, 0.028), "r": 0.006,
         "pivot": (-0.021, -0.013, -0.036), "offset": (0, 0, -0.01), "axis": "X", "material": "body", "pass_index": 1},
        {"name": "eye_px_open", "parent": "body", "shape": "rbox", "size": (0.01, 0.004, 0.02), "r": 0.0042,
         "pivot": (0.035, -0.031, 0.01), "offset": (0, 0, 0), "axis": None, "material": "eye", "pass_index": 2, "expression": "open"},
        {"name": "eye_nx_open", "parent": "body", "shape": "rbox", "size": (0.01, 0.004, 0.02), "r": 0.0042,
         "pivot": (-0.035, -0.031, 0.01), "offset": (0, 0, 0), "axis": None, "material": "eye", "pass_index": 2, "expression": "open"},
        {"name": "eye_px_happy", "parent": "body", "shape": "sphere", "r": 0.006,
         "pivot": (0.035, -0.031, 0.01), "offset": (0, 0, 0), "axis": None, "material": "eye", "pass_index": 2, "expression": "happy"},
    ],
    "expressions": {"open": ["eye_px_open", "eye_nx_open"], "happy": ["eye_px_happy"]},
    "slides": {"lift_px": {"part": "arm_px", "delta": (-0.007, 0.015, 0.049)}},
    "materials": {"body": "toy", "eye": "flat"},
}


def pose(**kw):
    p = {"root": {"pos": (0.0, 0.0, 0.0), "euler": (0.0, 0.0, 0.0)}, "squash": (1.0, 1.0, 1.0),
         "joints": {}, "slides": {}, "expression": "open", "visible": True}
    p.update(kw)
    return p


def check_hero():
    pts = hero_points.rbox_points((0.0, 0.0, 0.0), (0.06, 0.03, 0.04), 0.012)
    check(len(pts) == 56, f"rbox_points gives {len(pts)} points")
    check(all(abs(p[0]) <= 0.06 + 1e-12 and abs(p[1]) <= 0.03 + 1e-12 and abs(p[2]) <= 0.04 + 1e-12 for p in pts),
          "rbox points leave the box")
    check(max(p[0] for p in pts) == 0.06 and min(p[2] for p in pts) == -0.04, "rbox points reach the faces")
    c = 0.012 / math.sqrt(3)
    check(any(close(p, (0.048 + c, 0.018 + c, 0.028 + c), 1e-12) for p in pts), "rbox corner on the rounded edge")
    cap = hero_points.capsule_points((0, 0, 0), (0.03, 0, 0), 0.008)
    check(len(cap) == 50 and max(p[0] for p in cap) == 0.038 and min(p[0] for p in cap) == -0.008, "capsule extent")
    check(len(hero_points.sphere_points((0, 0, 0), 0.01)) == 26 and len(hero_points.sphere_points((0, 0, 0), 0.01, 40)) == 40,
          "sphere point counts")
    check(len(hero_points.cylinder_points((0, 0, 0), 0.08, 0.1, 16)) == 32, "cylinder point count")
    check(abs(hero_points.extent_width(HERO) - 0.152) < 1e-12, f"extent_width {hero_points.extent_width(HERO)}")
    rest = hero_points.hero_points(HERO, pose())
    check(len(rest) == 56 + 100 + 112 + 112, f"rest point count {len(rest)}")
    check(len(hero_points.hero_points(HERO, pose(expression="happy"))) == 56 + 100 + 112 + 26, "expression swap")
    check(len(hero_points.hero_points(HERO, pose(expression=None))) == 56 + 100 + 112, "no expression hides the eyes")
    check(hero_points.hero_points(HERO, pose(visible=False)) == [], "hidden hero has no points")
    check(abs(max(p[2] for p in rest) - 0.10) < 1e-12 and abs(min(p[2] for p in rest) - 0.0) < 1e-12, "rest height 0.10, soles at 0")
    arm = hero_points.hero_points(HERO, pose(), parts=["arm_px"])
    check(abs(max(p[0] for p in arm) - 0.076) < 1e-12, "arm tip at rest")
    raised = hero_points.hero_points(HERO, pose(joints={"arm_px": -math.pi / 2}), parts=["arm_px"])
    tip = max(raised, key=lambda p: p[2])
    check(close(tip, (0.052, 0.0, 0.055 + 0.016 + 0.008), 1e-12), f"arm raised about Y: tip {tip}")
    body2 = hero_points.hero_points(HERO, pose(joints={"arm_px": -math.pi / 2}), parts=["body"])
    check(body2 == hero_points.hero_points(HERO, pose(), parts=["body"]), "a joint moves only its part")
    lifted = hero_points.hero_points(HERO, pose(slides={"lift_px": 1.0}), parts=["arm_px"])
    check(all(close(vec.sub(b, a), (-0.007, 0.015, 0.049), 1e-12) for a, b in zip(arm, lifted)), "slide shifts the pivot")
    tall = hero_points.hero_points(HERO, pose(squash=(0.8, 0.8, 1.5)))
    check(abs(max(p[2] for p in tall) - 0.15) < 1e-12 and abs(max(p[0] for p in tall) - 0.8 * 0.076) < 1e-12, "squash scales from the soles")
    yawed = hero_points.hero_points(HERO, pose(root={"pos": (1.0, 2.0, 0.0), "euler": (0.0, 0.0, math.pi / 2)}), parts=["arm_px"])
    check(abs(max(p[1] for p in yawed) - 2.076) < 1e-12, "root yaw turns +X into +Y")
    blocks = hero_points.hero_blocks(HERO, pose(root={"pos": (1.0, 2.0, 0.0), "euler": (0.0, 0.0, 0.0)}))
    check(len(blocks) == 7 and close(blocks[0][0], (1.0, 2.0, 0.06), 1e-12) and close(blocks[0][1], (0.06, 0.03, 0.04), 1e-12),
          "hero_blocks body block")
    cam = {"pos": (0.0, -0.8, 0.5), "target": (0.0, 0.0, 0.05), "lens": 50.0}
    sil = hero_points.silhouette(rest, cam)
    check(0 < sil["width"] < 1 and 0 < sil["height"] < 1 and 0 < sil["margin"] < 0.5 and abs(sil["cx"]) < 1e-9,
          f"silhouette {sil}")
    check(hero_points.silhouette(rest, {"pos": (0.0, 0.8, 0.5), "target": (0.0, 2.0, 0.5), "lens": 50.0})["margin"] == -1.0,
          "silhouette behind the camera -> -1")


def check_expressions():
    """hero_points reads expressions as blender/hero.py does: the default set when a pose names none,
    the table's members even untagged, a ValueError on an unknown name."""
    path = os.path.normpath(os.path.join(HERE, "..", "..", "templates", "project", "hero_spec.py"))
    mod = importlib.util.spec_from_file_location("template_hero_spec", path)
    T = importlib.util.module_from_spec(mod)
    mod.loader.exec_module(T)
    spec = T.HERO
    sets = hero_points.expression_sets(spec)
    check(hero_points.default_expression(spec) == "open" and set(sets) == {"open", "happy"}, f"template sets {sets}")

    def count(pose, names):
        return len(hero_points.hero_points(spec, pose, parts=names))
    n_open = sum(len(hero_points.part_points(p)) for p in spec["parts"] if p["name"] in sets["open"])
    n_happy = sum(len(hero_points.part_points(p)) for p in spec["parts"] if p["name"] in sets["happy"])
    got = (count({}, sets["open"]), count({}, sets["happy"]), count({"expression": "happy"}, sets["open"]),
           count({"expression": "happy"}, sets["happy"]), count({"expression": None}, sets["open"] + sets["happy"]))
    check(got == (n_open, 0, 0, n_happy, 0), f"template expressions: {got}, want {(n_open, 0, 0, n_happy, 0)}")
    n_all = len(hero_points.hero_points(spec, {"expression": None}))
    check(len(hero_points.hero_points(spec, {})) == n_all + n_open, f"hero_points(spec, {{}}) = {len(hero_points.hero_points(spec, {}))}, want {n_all + n_open}")
    untagged = dict(HERO, parts=[dict(p, expression=None) if p["name"] == "eye_px_happy" else p for p in HERO["parts"]])
    check(len(hero_points.hero_points(untagged, pose())) == 56 + 100 + 112 + 112, "a table member without a tag stays hidden")
    check(hero_points.default_expression(dict(untagged, default_expression=None)) == "open", "default = the first set")
    try:
        hero_points.hero_points(spec, {"expression": "sad"})
        check(False, "an unknown expression did not raise")
    except ValueError:
        pass


# ---------------------------------------------------------------- framing
def check_framing():
    hero =hero_points.hero_points(HERO, pose(root={"pos": (0.3, -0.1, 0.0), "euler": (0.0, 0.0, 0.4)}))
    content = [(x, y, 0.0) for x in (-0.2, 0.4) for y in (-0.3, 0.2)]
    ws = [(x, y, 0.0) for x in (-1.6, 1.6) for y in (-0.9, 0.9)]
    groups = [(hero, 0.05), (content, 0.02), (ws, -0.02)]
    for film in ((1920, 1080), (1080, 1920)):
        for A, E, lens in ((0, 58, 30), (35, 18, 50), (-70, 22, 85), (2, 76, 16)):
            for bias in ((0.5, 0.0), (0.2, 0.9)):
                P, f = camera.frame_solve(math.radians(A), math.radians(E), lens, groups, film, 36.0, bias[0], bias[1])
                cam = {"pos": P, "target": vec.add(P, f), "lens": lens}
                slack = []
                for pts, m in groups:
                    s = hero_points.silhouette(pts, cam, film)
                    check(s["margin"] >= m - 1e-9, f"frame_solve A{A} E{E} {lens}mm {film}: margin {s['margin']:.4f} < {m}")
                    slack.append(s["margin"] - m)
                check(min(slack) <= 1e-9, f"frame_solve A{A} E{E} {lens}mm {film}: no group touches its margin ({min(slack):.4f})")
                check(min(vec.dot(vec.sub(X, P), f) for X, _ in [(p, 0) for pts, _ in groups for p in pts]) >= 0.2 - 1e-9,
                      "frame_solve breaks the near limit")
                check(close(camera.heading_elev(f), (math.radians(A), math.radians(E)), 1e-9), "frame_solve changed the view")
    width_fn = lambda P, f, lens: hero_points.silhouette(hero, {"pos": P, "target": vec.add(P, f), "lens": lens})["width"]  # noqa: E731
    P0, f0 = camera.frame_solve(math.radians(20), math.radians(40), 50, [(hero, 0.05)])
    w0 = width_fn(P0, f0, 50)
    P, f = camera.frame_solve(math.radians(20), math.radians(40), 50, [(hero, 0.05)], cap=(width_fn, w0 * 0.5))
    w = width_fn(P, f, 50)
    check(w <= w0 * 0.5 * 1.001 and w > w0 * 0.4, f"cap: width {w:.4f} vs {w0:.4f} wanted <= {w0 * 0.5:.4f}")
    check(hero_points.silhouette(hero, {"pos": P, "target": vec.add(P, f), "lens": 50})["margin"] >= 0.05 - 1e-9, "cap broke the margin")
    try:
        camera.frame_solve(0.0, 0.5, 30, [([], 0.05)])
        check(False, "frame_solve with no points did not raise")
    except ValueError:
        pass


# ---------------------------------------------------------------- aperture
def check_aperture():
    def need(t):
        return 3.0 + 2.0 * math.sin(2 * math.pi * t / 0.37) + 1.5 * math.sin(2 * math.pi * t * 3.1)
    holds = [(1.0, 1.6), (2.5, 3.2), (4.0, 4.3)]
    flat = [(2.5, 3.2)]
    tr = camera.fstop_track(need, 0.0, 5.0, 120, (0.10, 0.10), (1.4, 11.0), holds, flat, 0.15)
    g = tr.grid
    check(len(g) == 601, "aperture grid length")
    under = [k for k in range(601) if g[k] < min(11.0, max(1.4, need(k / 120))) - 1e-9]
    check(not under, f"aperture under the need at {len(under)} samples (first t {under[0] / 120 if under else 0:.3f})")
    check(all(1.4 - 1e-12 <= v <= 11.0 + 1e-12 for v in g), "aperture out of range")
    for a, b in holds:
        seg = [g[k] for k in range(int(math.ceil(a * 120)), int(b * 120) + 1)]
        steps = [y - x for x, y in zip(seg, seg[1:]) if abs(y - x) > 1e-9]
        check(all(s > 0 for s in steps) or all(s < 0 for s in steps), f"aperture reverses inside hold {a}-{b}")
    for a, b in flat:
        seg = [g[k] for k in range(int(math.ceil(a * 120)), int(b * 120) + 1)]
        check(max(seg) - min(seg) <= 1e-9, f"flat hold {a}-{b} drifts {max(seg) - min(seg):.4f}")
    check(not isolated_steps(g, 0.02), f"aperture has isolated steps at {[round(k / 120, 3) for k in isolated_steps(g, 0.02)[:3]]}")
    check(abs(tr(2.75) - tr(2.6)) < 1e-9 and tr(-1.0) == g[0] and tr(9.0) == g[-1], "aperture callable")
    hero = hero_points.hero_points(HERO, pose())
    P, f = (0.0, -0.6, 0.4), vec.norm((0.0, 0.6, -0.35))
    df = camera.focus_distance(P, f, (0.0, 0.0, 0.05))
    n1 = camera.fstop_for(hero, P, f, df, 50.0, 3.0)
    n2 = camera.fstop_for(hero, P, f, df + 0.3, 50.0, 3.0)
    check(0 <= n1 < n2, f"fstop_for: focus on the hero {n1:.2f} should need less than off {n2:.2f}")
    check(camera.fstop_for([(0.0, 0.0, 0.05)], P, f, df, 50.0, 3.0) < 1e-9, "a point at the focus distance needs nothing")
    check(camera.focus_distance(P, f, P) == 0.05, "focus_distance floor")


# ---------------------------------------------------------------- shot list
def check_shots():
    hero_at = lambda t: (0.2 * t, -0.1, 0.05)  # noqa: E731
    cyl = lambda t: hero_points.cylinder_points((0.2 * t, -0.1, 0.0), 0.08, 0.10)  # noqa: E731

    def groups_fn(t):
        return [(cyl(t), 0.05)]
    flight = arc.ballistic((0.2 * 2.0, -0.1, 0.0), (0.2 * 2.4, -0.1, 0.0), 2.0, 2.4, 0.2)
    shots = [camera.Hold("a", 0.0, 0.5, 0, 58, 30, groups_fn),
             camera.Hold("b", 0.9, 1.3, 35, 18, 50, groups_fn, bias=(0.5, 0.4)),
             camera.Rig("r", 1.5, 1.8, hero_at, [(1.5, 10, 25, 0.5, 24), (1.8, -20, 30, 0.6, 28)]),
             camera.Hold("c", 2.6, 3.0, -70, 22, 85, groups_fn),
             camera.Hold("d", 3.3, 3.6, -20, 40, 35, groups_fn, position=(0.9, -1.0, 0.6))]
    cross = {("a", "b"): "orbit", ("b", "r"): ("ease", {"ease": "trap"}),
             ("r", "c"): ("truck", {"arc": flight, "whip": 0.2, "points_fn": cyl, "margin": 0.06}),
             ("c", "d"): ("orbit", {"clamp": (0.5, 0.62), "release": 0.3, "push": 0.1})}
    sl = camera.ShotList(shots, cross, subject_fn=hero_at).solve()
    check(sl.holds() == [("a", 0.0, 0.5), ("b", 0.9, 1.3), ("r", 1.5, 1.8), ("c", 2.6, 3.0), ("d", 3.3, 3.6)], "holds()")
    check(sl.whip_windows() == [(0.5, 0.9), (1.8, 2.0), (3.0, 3.3)], f"whip_windows {sl.whip_windows()}")
    check(close(sl.by_name["d"].P, (0.9, -1.0, 0.6)), "explicit position kept")
    for name, t0, t1 in sl.holds():
        s = sl.by_name[name]
        for t in (t0, 0.5 * (t0 + t1), t1):
            check(sl.eval(t) == sl._eval_shot(s, t), f"eval inside {name} is not the hold pose")
        if s.kind == "hold" and s.position is None:
            cam = {"pos": s.P, "target": vec.add(s.P, s.f), "lens": s.lens}
            for t in s.solve_at:
                check(hero_points.silhouette(cyl(t), cam)["margin"] >= 0.05 - 1e-9, f"hold {name} loses the subject at {t}")
    r = sl.by_name["r"]
    P, f, L = r.eval(1.5)
    check(close(vec.add(P, vec.mul(f, 0.5)), hero_at(1.5), 1e-12) and L == 24, "rig sits dist behind its aim")
    check(sl.shot_at(0.7) == (sl.by_name["b"], "crossing") and sl.shot_at(1.6) == (r, "rig"), "shot_at")
    tracks = {k: [] for k in ("px", "py", "pz", "fx", "fy", "fz", "lens")}
    for i in range(int(3.6 * 480) + 1):
        P, f, L = sl.eval(i / 480)
        for k, v in zip(tracks, (*P, *f, L)):
            tracks[k].append(v)
    for k, vals in tracks.items():
        floor = 0.05 if k == "lens" else 5e-4 if k[0] == "p" else 2e-3
        steps = isolated_steps(vals, floor)
        check(not steps, f"shot list channel {k} jumps at t {[round(i / 480, 3) for i in steps[:3]]}")
    shakes = [(1.0, 0.45, 0.16, 7.3, 9.1)]
    P, f, L = sl.eval(1.05)
    Ps, fs, Ls = camera.add_shake(P, f, L, 1.05, shakes)
    check(Ps == P and Ls == L and fs != f and abs(vec.length(fs) - 1.0) < 1e-12, "add_shake turns the view only")
    check(camera.add_shake(P, f, L, 0.5, shakes)[1] == f and camera.add_shake(P, f, L, 3.0, shakes)[1] == f, "shake outside its window")
    st = camera.camera_state(sl, 1.05, hero_at, lambda t: 4.0, shakes)
    check(st["lens"] == L and st["fstop"] == 4.0 and st["raw"]["pos"] == P and st["pos"] == P, "camera_state fields")
    check(close(st["rot"], camera.look_at_euler(st["pos"], st["target"]), 1e-12), "camera_state rot")
    check(abs(camera.focus_distance(st["pos"], vec.sub(st["target"], st["pos"]), st["focus"]) - st["focus_distance"]) < 1e-9,
          "camera_state target sits at the focus distance")
    try:
        camera.ShotList([camera.Hold("x", 0.0, 1.0, 0, 30, 30, groups_fn), camera.Hold("y", 0.5, 2.0, 0, 30, 30, groups_fn)])
        check(False, "overlapping shots did not raise")
    except ValueError:
        pass
    # exit_time: a box falling under a camera leaves the frame, and one under a slab is hidden at once
    cam_fn = lambda t: {"pos": (0.0, -0.8, 1.2), "target": (0.0, 0.0, 0.0), "lens": 30.0}  # noqa: E731
    box = lambda z: [(x, y, z) for x in (-0.05, 0.05) for y in (-0.05, 0.05)]  # noqa: E731
    fall = lambda t: box(-0.5 * 9.81 * t * t)  # noqa: E731
    te = arc.exit_time(fall, cam_fn, 0.0, 3.0)

    def inside(pts):
        c = cam_fn(0)
        return [max(abs(v) for v in camera.project(c["pos"], c["target"], c["lens"], X)[:2]) <= 1.0 for X in pts]
    check(te is not None and not any(inside(fall(te))) and any(inside(fall(te - 1 / 240))), f"exit_time off frame: {te}")
    check(abs(arc.exit_time(fall, cam_fn, 0.0, 3.0, floor_z=-1.0) - math.sqrt(2 / 9.81)) < 1 / 240 + 1e-9, "exit_time floor")
    slab = lambda t: [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (0.0, -0.03)]  # noqa: E731
    check(arc.exit_time(lambda t: box(-0.05), cam_fn, 0.0, 1.0, occluder_fn=slab) == 0.0, "exit_time under an occluder")
    check(arc.exit_time(lambda t: box(0.02), cam_fn, 0.0, 1.0, occluder_fn=slab) is None, "exit_time above the occluder stays seen")


def main():
    for fn in (check_arcs, check_jumps, check_yaw, check_pinhole, check_vertical, check_pole, check_hero, check_expressions,
               check_framing, check_aperture, check_shots):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            FAILS.append(f"{fn.__name__} raised {type(e).__name__}: {e}")
    for line in FAILS:
        print("FAIL", line)
    print(f"check_motion: {len(FAILS)} failures")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
