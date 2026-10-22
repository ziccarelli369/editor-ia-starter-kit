"""camera: pinhole model, framing solver, shot list, focus and aperture. Owner: motion. Standard library only.

The model matches Blender exactly: sensor_w mm (default 36), sensor_fit
HORIZONTAL, no shift, no roll, rotation_mode 'XYZ'. ndc: x, y in -1..1
inside the frame; depth in metres along the view axis. Heading A: rad, 0 =
looking north (+Y), positive east. Elevation E: rad, positive looking down.
Film (w, h) px gives the aspect. Lens in mm. Taste (A, E, lens, margins,
crossing kinds, shake amplitudes, blur budgets) comes in as arguments.

A camera dict: {'pos': (x,y,z), 'target': (x,y,z), 'lens': mm, 'fstop': N,
'focus_distance': m, 'rot': (rx, ry, rz), 'heading': A rad or None}. A vertical view
(E = +-90 deg, VERTICAL_EPS) has no no-roll basis of its own: 'heading' sets its roll, so
pass it as heading= to project / unproject / basis_from_dir / look_at_euler.

Crossing params (ShotList.crossings values, every number taste):
  'ease'  {'ease': 'smooth' | 'smoother' | 'trap' | callable}
  'orbit' {'ease', 'clamp': (a, b) soft bound of the subject's screen position (default (0.72, 0.86)),
           'release': share of the crossing over which the clamp lets go (None = mid-crossing only),
           'push': share the camera closes in mid-blend (default 0), 'ride': share at each end over
           which the camera eases into riding with the subject (default 0.45, 0 = off)}
  'truck' {'arc': the subject's arc (arc.Arc), 'whip': s of orbit into the rig (default 0.2),
           'ramp': (in, out) s of the rig's speed ramps (default (0.2, 0.2)), 'zf': share of the arc's
           lift the rig rises with (default 0.8), 'push', 'ease', 'points_fn': fn(t) -> subject points
           added (shifted) to the hold's framing groups, 'margin': their margin (default 0.06)}
"""
import math

from . import ease
from . import vec as V


VERTICAL_EPS = 1e-9
"""A unit view direction whose horizontal part is under this is vertical (straight down or up). There the
no-roll right vector (f.y, -f.x, 0) is rounding noise (float64 pos/target arithmetic leaves <= 1e-12 for
|pos| <= 100 m and a 0.05 m focus distance), so the roll comes from a heading instead: the basis snaps
to cam_basis(heading, +-90 deg), an aim error <= 1e-9 rad (<= 1e-8 ndc)."""


def cam_basis(A, E):
    """-> (right, up, forward) unit vectors for heading A and elevation ease."""
    f = (math.cos(E) * math.sin(A), math.cos(E) * math.cos(A), -math.sin(E))
    r = (math.cos(A), -math.sin(A), 0.0)
    return r, V.cross(r, f), f


STEEP_DEG = 80.0
"""A view steeper than this (|E| >= 80 deg) is 'steep': its no-roll basis still exists, but the roll it implies
turns fast with the heading (at E 85 the right vector is the heading's perpendicular, so a few degrees of aim
change near the pole roll the whole image). A crossing with a steep end therefore blends in (heading, elevation)
like one with a vertical end (ShotList._blend_dir), so an orbit from E 85 into an oblique hold turns once
instead of spinning and spinning back. A mechanism constant, not taste: oblique-to-oblique crossings (both
ends under 80 deg) are untouched."""


def _vertical(f):
    """True when unit f is within VERTICAL_EPS of straight down or up (the zero vector is not)."""
    return abs(f[2]) > 0.5 and math.hypot(f[0], f[1]) < VERTICAL_EPS


def _steep(f):
    """True when unit f looks down or up at |E| >= STEEP_DEG (a vertical view included; the zero vector is not)."""
    n = V.length(f)
    return n > 0.0 and abs(f[2]) / n >= math.sin(math.radians(STEEP_DEG)) - 1e-12


def basis_from_dir(f, heading=None):
    """View direction f -> (right, up, forward), no roll, world Z up.

    heading: rad (cam_basis convention), read only when f is vertical (VERTICAL_EPS): the basis is then
    cam_basis(heading, +-pi/2); None = 0 (north up, Blender rz 0). Other views ignore it."""
    f = V.norm(f)
    if _vertical(f):
        return cam_basis(heading or 0.0, math.copysign(math.pi / 2, -f[2]))
    r = V.norm((f[1], -f[0], 0.0))
    return r, V.cross(r, f), f


def heading_elev(f):
    """View direction -> (A, E) rad, the inverse of cam_basis."""
    return math.atan2(f[0], f[1]), math.asin(max(-1.0, min(1.0, -f[2])))


def look_at_euler(pos, target, heading=None):
    """-> Blender camera rotation_euler 'XYZ' looking from pos at target, no roll.

    A vertical view (VERTICAL_EPS) takes its rz from heading (rad; None = 0) exactly as basis_from_dir
    does: (0 down | pi up, 0, wrap(-heading))."""
    d = V.norm(V.sub(target, pos))
    if _vertical(d):
        A = heading or 0.0
        return (0.0 if d[2] < 0 else math.pi, 0.0, math.atan2(-math.sin(A), math.cos(A)))
    return (math.atan2(math.hypot(d[0], d[1]), -d[2]), 0.0, math.atan2(-d[0], d[1]))


def tan_half(lens, sensor_w=36.0):
    """-> tan of the half horizontal field: sensor_w / 2 / lens."""
    return sensor_w / 2.0 / lens


def project(pos, target, lens, X, film=(1920, 1080), sensor_w=36.0, heading=None):
    """World point -> (ndc_x, ndc_y, depth). (99, 99, depth) when the point is behind the camera.
    heading: the roll reference of a vertical view (basis_from_dir); pass the camera dict's 'heading'."""
    r, u, f = basis_from_dir(V.sub(target, pos), heading)
    d = V.sub(X, pos)
    zc = V.dot(d, f)
    if zc <= 1e-6:
        return (99.0, 99.0, zc)
    tx = tan_half(lens, sensor_w)
    ty = tx * film[1] / film[0]
    return (V.dot(d, r) / (zc * tx), V.dot(d, u) / (zc * ty), zc)


def unproject(pos, target, lens, s, plane_z=0.0, film=(1920, 1080), sensor_w=36.0, heading=None):
    """Screen ndc s = (sx, sy) -> world point on the plane z = plane_z (None if the ray misses it).
    heading: as in project."""
    r, u, f = basis_from_dir(V.sub(target, pos), heading)
    tx = tan_half(lens, sensor_w)
    ty = tx * film[1] / film[0]
    d = V.norm(V.add(V.add(f, V.mul(r, s[0] * tx)), V.mul(u, s[1] * ty)))
    if abs(d[2]) < 1e-9:
        return None
    k = (plane_z - pos[2]) / d[2]
    if k <= 0:
        return None
    return V.add(pos, V.mul(d, k))


def aim_dir(P, lens, X, s, film=(1920, 1080), sensor_w=36.0):
    """-> the no-roll view direction from P that puts world point X at ndc s (bisection on elevation)."""
    tx = tan_half(lens, sensor_w)
    ty = tx * film[1] / film[0]
    a, b = s[0] * tx, s[1] * ty
    D = V.sub(X, P)
    dh = math.hypot(D[0], D[1])
    tphi = -D[2] / max(dh, 1e-9)

    def g(E):
        return (b * math.cos(E) - math.sin(E)) + tphi * math.sqrt((math.cos(E) + b * math.sin(E)) ** 2 + a * a)
    lo, hi = -1.5, 1.5
    glo = g(lo)
    for _ in range(48):
        mid = 0.5 * (lo + hi)
        gm = g(mid)
        if (gm > 0) == (glo > 0):
            lo, glo = mid, gm
        else:
            hi = mid
    E = 0.5 * (lo + hi)
    k = math.cos(E) + b * math.sin(E)
    A = math.atan2(D[0], D[1]) - math.atan2(a, k)
    return cam_basis(A, E)[2]


def frame_solve(A, E, lens, groups, film=(1920, 1080), sensor_w=36.0, bias_r=0.5, bias_u=0.0,
                near=0.2, cap=None):
    """Closest camera at heading A, elevation E, lens that keeps every point group inside its margin.

    groups: [(points, margin)] margin = frame fraction kept free at each edge (< 0 lets it spill).
    bias_r / bias_u: where the camera sits in the free right / up interval (0 = low side).
    cap: (width_fn, w_max) pulls back until width_fn(P, f, lens) <= w_max (silhouette width share);
    the pull-back step reads the depth of the first group (the subject).
    -> (P, f) position and forward direction. Raises when every group is empty.
    """
    r, u, f = cam_basis(A, E)
    tx = tan_half(lens, sensor_w)
    ty = tx * film[1] / film[0]
    groups = [(pts, m) for pts, m in groups if pts]
    if not groups:
        raise ValueError("frame_solve: no points to frame")
    los = {}
    pf = 1e9
    for axis, vec, tt in (("r", r, tx), ("u", u, ty)):
        D, C = [], []
        for pts, m in groups:
            a = (1.0 - 2.0 * m) * tt
            cr = [(V.dot(X, vec), V.dot(X, f)) for X in pts]
            D.append((max(xr - a * xf for xr, xf in cr), a))
            C.append((min(xr + a * xf for xr, xf in cr), a))
        for dg, ag in D:
            for ch, ah in C:
                pf = min(pf, (ch - dg) / (ag + ah))
        los[axis] = (D, C)
    pf = min(pf, min(V.dot(X, f) for pts, _ in groups for X in pts) - near)

    def place(pf_):
        co = {}
        for axis, bias in (("r", bias_r), ("u", bias_u)):
            D, C = los[axis]
            lo = max(dg + ag * pf_ for dg, ag in D)
            hi = min(ch - ah * pf_ for ch, ah in C)
            co[axis] = lo + (hi - lo) * bias
        return V.add(V.add(V.mul(r, co["r"]), V.mul(u, co["u"])), V.mul(f, pf_))

    P = place(pf)
    if cap is not None:
        width_fn, wmax = cap
        subject = groups[0][0]
        for _ in range(6):
            w = width_fn(P, f, lens)
            if w <= wmax * 1.001:
                break
            depth = sum(V.dot(V.sub(X, P), f) for X in subject) / len(subject)
            pf -= depth * (w / wmax - 1.0)
            P = place(pf)
    return P, f


class Hold:
    """A still shot. groups_fn(t) -> [(points, margin)] evaluated over the hold window.

    name, t0, t1: s. A, E: deg. lens: mm. position: explicit (x, y, z) skips the solve.
    bias: (bias_r, bias_u). cap: (width_fn, w_max) or None. solve_at: [t] samples (default: 5 over the window).
    Group i of every sample is merged into one group (the first sample's margin). The first group is the
    subject (the cap reads its depth). After ShotList.solve: .P, .f, .groups.
    """

    def __init__(self, name, t0, t1, A, E, lens, groups_fn, bias=(0.5, 0.0), cap=None,
                 position=None, solve_at=None):
        if t1 < t0:
            raise ValueError(f"Hold {name!r}: t1 {t1} < t0 {t0}")
        self.name, self.t0, self.t1 = name, float(t0), float(t1)
        self.A, self.E = math.radians(A), math.radians(E)
        self.lens, self.groups_fn, self.bias, self.cap = float(lens), groups_fn, bias, cap
        self.position = None if position is None else tuple(position)
        if solve_at is None:
            n = 4 if t1 > t0 else 0
            solve_at = [t0 + (t1 - t0) * i / 4 for i in range(n + 1)]
        self.solve_at = list(solve_at)
        self.P = self.f = self.groups = None
        self.kind = "hold"

    def merged_groups(self):
        """-> [(points, margin)]: groups_fn sampled at solve_at, group i merged across samples."""
        merged = []
        for t in self.solve_at:
            for i, (pts, m) in enumerate(self.groups_fn(t) or []):
                if i == len(merged):
                    merged.append([list(pts), m])
                else:
                    merged[i][0].extend(pts)
        return [(pts, m) for pts, m in merged]

    def heading(self, t):
        """-> A rad (the roll reference when the view is vertical)."""
        return self.A


class Rig:
    """A camera carried by a moving anchor. anchor_fn(t) -> world point; keys: [(t, A_deg, E_deg, dist_m, lens)]
    on Catmull-Rom. The camera sits at anchor - forward(A, E) * dist and aims at the anchor.
    Past t1 the anchor runs on at its last speed (a smooth hand-off to the next shot)."""

    def __init__(self, name, t0, t1, anchor_fn, keys):
        if t1 < t0:
            raise ValueError(f"Rig {name!r}: t1 {t1} < t0 {t0}")
        if not keys:
            raise ValueError(f"Rig {name!r}: no keys")
        self.name, self.t0, self.t1 = name, float(t0), float(t1)
        self.anchor_fn = anchor_fn
        self.keys = sorted(keys, key=lambda k: k[0])
        self.lens = float(self.keys[0][4])
        self.kind = "rig"

    def anchor(self, t):
        """-> the anchor at t, extrapolated linearly past t1."""
        if t > self.t1:
            a, b = self.anchor_fn(self.t1 - 1e-3), self.anchor_fn(self.t1)
            return V.add(b, V.mul(V.sub(b, a), (t - self.t1) / 1e-3))
        return self.anchor_fn(t)

    def eval(self, t):
        """-> (P, f, lens) at t. The keyed elevation is clamped to +-90 deg: Catmull-Rom overshoots past a
        top-down key (E 60 -> 90 -> 90 runs over 90 for the whole hold), and past vertical the no-roll basis
        takes heading A + 180 (a 180 deg flip of the image). At 90 the vertical branch takes its roll from
        Rig.heading, continuous with the basis just under 90."""
        A, E, d, L = (ease.catmull([(k[0], k[j]) for k in self.keys], t) for j in (1, 2, 3, 4))
        E = max(-90.0, min(90.0, E))
        f = cam_basis(math.radians(A), math.radians(E))[2]
        return V.sub(self.anchor(t), V.mul(f, d)), f, L

    def heading(self, t):
        """-> the keyed A at t, rad (the roll reference when the view is vertical)."""
        return math.radians(ease.catmull([(k[0], k[1]) for k in self.keys], t))


_EASES = {"smooth": ease.smoothstep, "smoother": ease.smootherstep, "trap": ease.trap}


def _sclamp(x, a=0.72, b=0.86):
    """Identity inside +-a, a smooth (C1) saturation to +-b beyond."""
    ax = abs(x)
    if ax <= a:
        return x
    w = b - a
    return math.copysign(a + w * (1.0 - math.exp(-(ax - a) / w)), x)


def _slerp_len(a, b, u):
    """Between two offsets: the direction on the great circle, the length geometric."""
    la, lb = V.length(a), V.length(b)
    da, db = V.mul(a, 1.0 / la), V.mul(b, 1.0 / lb)
    om = math.acos(max(-1.0, min(1.0, V.dot(da, db))))
    if om < 1e-6:
        d = da
    else:
        d = V.add(V.mul(da, math.sin((1 - u) * om) / math.sin(om)), V.mul(db, math.sin(u * om) / math.sin(om)))
    return V.mul(d, math.exp(ease.lerp(math.log(la), math.log(lb), u)))


def _plain_blend(Ka, Kb, e):
    return (V.lerp3(Ka[0], Kb[0], e), V.norm(V.lerp3(Ka[1], Kb[1], e)),
            math.exp(ease.lerp(math.log(Ka[2]), math.log(Kb[2]), e)))


def _orbit_blend(Ka, Kb, C, e, film, sensor_w, u=None, ride=None, ride_share=0.45, push=0.0,
                 clamp=(0.72, 0.86), release=None):
    """Between two cameras around pivot C: offsets on a great circle, C's screen position slides between
    where each camera sees it (soft-clamped mid-crossing). Exactly Ka at e = 0 and Kb at e = 1."""
    if e <= 0.0:
        return Ka
    if e >= 1.0:
        return Kb
    (Pa, fa, La), (Pb, fb, Lb) = Ka, Kb
    off = _slerp_len(V.sub(Pa, C), V.sub(Pb, C), e)
    if ride is not None and u is not None and ride_share > 0:
        w = ease.smootherstep(u / ride_share) * ease.smootherstep((1.0 - u) / ride_share)
        if w > 0.0:
            off = V.lerp3(off, _slerp_len(ride[0], ride[1], e), w)
    if push:
        off = V.mul(off, math.exp(-push * math.sin(math.pi * e) ** 2))
    P = V.add(C, off)
    L = math.exp(ease.lerp(math.log(La), math.log(Lb), e))
    sa = project(Pa, V.add(Pa, fa), La, C, film, sensor_w)
    sb = project(Pb, V.add(Pb, fb), Lb, C, film, sensor_w)
    raw = (ease.lerp(sa[0], sb[0], e), ease.lerp(sa[1], sb[1], e))
    cl = (ease.lerp(_sclamp(sa[0], *clamp), _sclamp(sb[0], *clamp), e),
          ease.lerp(_sclamp(sa[1], *clamp), _sclamp(sb[1], *clamp), e))
    if release is None or u is None:
        k = 16.0 * e * e * (1.0 - e) * (1.0 - e)
    else:
        k = ease.smoothstep(u / release) * ease.smoothstep((1.0 - u) / release)
    s = (ease.lerp(raw[0], cl[0], k), ease.lerp(raw[1], cl[1], k))
    return P, aim_dir(P, L, C, s, film, sensor_w), L


class ShotList:
    """Ordered shots with crossings between consecutive ones.

    crossings: {(name_a, name_b): 'ease' | 'orbit' | 'truck' | (kind, params)}; default 'ease'.
    'ease': lerp position, nlerp aim, log-lerp lens. 'orbit': slerp the offset around subject_fn(t) with
    the subject's screen position interpolated and soft-clamped. 'truck': the next hold shifted along
    subject motion with a trapezoid speed. ease_fn: default smoothstep.
    subject_fn(t) -> world point of the subject (None when hidden: the crossing falls back to 'ease').
    """

    def __init__(self, shots, crossings=None, subject_fn=None, film=(1920, 1080), sensor_w=36.0, ease_fn=None):
        self.shots = sorted(shots, key=lambda s: s.t0)
        for a, b in zip(self.shots, self.shots[1:]):
            if b.t0 < a.t1 - 1e-9:
                raise ValueError(f"ShotList: {b.name!r} starts at {b.t0} before {a.name!r} ends at {a.t1}")
        self.crossings = dict(crossings or {})
        self.subject_fn = subject_fn
        self.film, self.sensor_w = film, sensor_w
        self.ease_fn = ease_fn or ease.smoothstep
        self.by_name = {s.name: s for s in self.shots}
        if len(self.by_name) != len(self.shots):
            raise ValueError("ShotList: duplicate shot names")
        self._solved = False

    # ---- crossings
    def crossing(self, a, b):
        """-> (kind, params) of the crossing from shot a into shot b."""
        c = self.crossings.get((a.name, b.name), "ease")
        if isinstance(c, str):
            return c, {}
        kind, params = c
        return kind, dict(params or {})

    def _ease(self, params):
        e = params.get("ease")
        if e is None:
            return self.ease_fn
        return _EASES[e] if isinstance(e, str) else e

    def _into(self, b):
        """-> (shot_a, kind, params) of the crossing into shot b, or None for the first shot."""
        i = self.shots.index(b)
        if i == 0:
            return None
        a = self.shots[i - 1]
        kind, params = self.crossing(a, b)
        return a, kind, params

    def truck_shift(self, name_b, t):
        """World offset of the truck rig from the hold it lands on (name_b), at t."""
        b = self.by_name[name_b]
        into = self._into(b)
        if into is None or into[1] != "truck":
            raise ValueError(f"truck_shift: no truck crossing into {name_b!r}")
        _, _, params = into
        arc = params["arc"]
        li, lo = params.get("ramp", (0.2, 0.2))
        tb = b.t0
        t_start = arc.t0 - li / 2
        k = (tb - t_start - (li + lo) / 2) / arc.duration
        Tv = (k * (arc.p1[0] - arc.p0[0]), k * (arc.p1[1] - arc.p0[1]), 0.0)
        total = li / 2 + (tb - t_start - li - lo) + lo / 2
        x = t - t_start
        if x <= 0:
            sg = 0.0
        elif x < li:
            u = x / li
            sg = li * (u ** 3 - u ** 4 / 2) / total
        elif t < tb - lo:
            sg = (li / 2 + x - li) / total
        else:
            u = min(1.0, (t - (tb - lo)) / lo)
            sg = (li / 2 + (tb - lo - t_start - li) + lo * (u - u ** 3 + u ** 4 / 2)) / total
        xs = ease.clamp((t - arc.t0) / (tb - arc.t0))
        lift = params.get("zf", 0.8) * (arc.zp - 0.5 * (arc.p0[2] + arc.p1[2])) * 64.0 * xs ** 3 * (1 - xs) ** 3
        return (-Tv[0] * (1 - sg), -Tv[1] * (1 - sg), lift)

    # ---- solving
    def solve(self):
        """Solve every Hold position once (cached). -> self."""
        if self._solved:
            return self
        for s in self.shots:
            if s.kind != "hold":
                continue
            if s.position is not None:
                s.P, s.f = s.position, cam_basis(s.A, s.E)[2]
                s.groups = []
                continue
            groups = s.merged_groups()
            into = self._into(s)
            if into is not None and into[1] == "truck" and into[2].get("points_fn"):
                a, _, params = into
                tw, tb = a.t1 + params.get("whip", 0.2), s.t0
                pts = []
                for k in range(int((tb - tw) * 60) + 1):
                    t = tw + k / 60.0
                    sh = self.truck_shift(s.name, t)
                    pts += [V.sub(X, sh) for X in params["points_fn"](t)]
                groups.append((pts, params.get("margin", 0.06)))
            s.groups = groups
            s.P, s.f = frame_solve(s.A, s.E, s.lens, groups, self.film, self.sensor_w,
                                   s.bias[0], s.bias[1], cap=s.cap)
        self._solved = True
        return self

    def _eval_shot(self, s, t):
        if s.kind == "rig":
            return s.eval(t)
        if s.P is None:
            raise RuntimeError(f"ShotList: call solve() first ({s.name!r} unsolved)")
        return s.P, s.f, s.lens

    def shot_at(self, t):
        """-> (shot, 'hold' | 'rig' | 'crossing'); a crossing returns the shot it goes into."""
        for s in self.shots:
            if s.t0 <= t <= s.t1:
                return s, s.kind
        if t < self.shots[0].t0:
            return self.shots[0], self.shots[0].kind
        for a, b in zip(self.shots, self.shots[1:]):
            if a.t1 < t < b.t0:
                return b, "crossing"
        return self.shots[-1], self.shots[-1].kind

    @staticmethod
    def _end_dir(s, t, f):
        """-> (heading, elevation) rad of shot s's view f at t; a vertical view takes the shot's heading."""
        if _vertical(f):
            return s.heading(t), math.copysign(math.pi / 2, -f[2])
        return heading_elev(f)

    def _blend_dir(self, a, b, t, Ka, Kb, e):
        """Crossing direction when either end is vertical or steep (STEEP_DEG): eased in (heading, elevation)
        space, the second heading unwrapped to the first (the same blend heading(t) reports), so the no-roll
        basis of the oblique part turns into the steep hold's heading in one smooth turn instead of popping by
        their difference on the last frame (vertical end) or rolling and rolling back near the pole (steep end)."""
        (Ha, Ea), (Hb, Eb) = self._end_dir(a, t, Ka[1]), self._end_dir(b, t, Kb[1])
        e = ease.clamp(e)
        return cam_basis(ease.lerp(Ha, ease.unwrap_to(Hb, Ha), e), ease.lerp(Ea, Eb, e))[2]

    def eval(self, t):
        """-> (P, f, lens) at t: inside a hold its solved pose, between holds the crossing. A crossing with a
        vertical or steep end (|E| >= STEEP_DEG, 80 deg) takes its direction from _blend_dir; every other
        crossing (both ends under 80 deg) is unchanged."""
        self.solve()
        s, kind = self.shot_at(t)
        if kind != "crossing":
            return self._eval_shot(s, t)
        a, kind, params = self._into(s)
        b = s
        ta, tb = a.t1, b.t0
        u = ease.clamp((t - ta) / (tb - ta))
        Ka, Kb = self._eval_shot(a, t), self._eval_shot(b, t)
        steep_end = _steep(Ka[1]) or _steep(Kb[1])
        C = self.subject_fn(t) if (self.subject_fn is not None and kind != "ease") else None
        if kind == "ease" or C is None:
            e = self._ease(params)(u)
            P, f, L = _plain_blend(Ka, Kb, e)
        elif kind == "orbit":
            Ca, Cb = self.subject_fn(ta), self.subject_fn(tb)
            ride = None
            if Ca is not None and Cb is not None:
                ride = (V.sub(self._eval_shot(a, ta)[0], Ca), V.sub(self._eval_shot(b, tb)[0], Cb))
            e = self._ease(params)(u)
            P, f, L = _orbit_blend(Ka, Kb, C, e, self.film, self.sensor_w, u, ride,
                                   params.get("ride", 0.45), params.get("push", 0.0),
                                   params.get("clamp", (0.72, 0.86)), params.get("release"))
        elif kind == "truck":
            sh = self.truck_shift(b.name, t)
            R = (V.add(Kb[0], sh), Kb[1], Kb[2])
            e = self._ease(params)((t - ta) / params.get("whip", 0.2))
            P, f, L = _orbit_blend(Ka, R, C, e, self.film, self.sensor_w, push=params.get("push", 0.0))
        else:
            raise ValueError(f"ShotList: unknown crossing kind {kind!r}")
        if steep_end:
            f = self._blend_dir(a, b, t, Ka, Kb, e)
        return P, f, L

    def heading(self, t):
        """-> heading rad at t, the roll reference of a vertical view (basis_from_dir, look_at_euler).
        Inside a shot its heading(t); in a crossing the two shots' headings (the second unwrapped to the
        first) on the crossing's ease ('truck': over its whip)."""
        s, kind = self.shot_at(t)
        if kind != "crossing":
            return s.heading(t)
        a, kind, params = self._into(s)
        ta, tb = a.t1, s.t0
        span = params.get("whip", 0.2) if kind == "truck" else tb - ta
        e = self._ease(params)(ease.clamp((t - ta) / span))
        ha = a.heading(t)
        return ease.lerp(ha, ease.unwrap_to(s.heading(t), ha), e)

    def holds(self):
        """-> [(name, t0, t1)] of every Hold and Rig window (for the checker)."""
        return [(s.name, s.t0, s.t1) for s in self.shots]

    def whip_windows(self):
        """-> [(t0, t1)] of 'orbit' crossings and the whip part of 'truck' crossings (exempt from the smoothness rule)."""
        out = []
        for a, b in zip(self.shots, self.shots[1:]):
            kind, params = self.crossing(a, b)
            if kind == "orbit":
                out.append((a.t1, b.t0))
            elif kind == "truck":
                out.append((a.t1, min(b.t0, a.t1 + params.get("whip", 0.2))))
        return out


def add_shake(P, f, lens, t, shakes):
    """shakes: [(t_hit, amp_deg, decay_s, f_heading_hz, f_elev_hz)]. -> (P, f', lens) with f rotated by the
    decaying shake on heading and elevation only. Call on the final pose; never on the aperture input.
    The shaken elevation is clamped to +-90 deg: a shake that would carry a steep view past vertical holds
    at the pole (past it the no-roll basis flips 180 deg); on those samples the view is vertical, so its
    roll comes from the camera dict's heading and the heading part of the shake (under amp) leaves the roll."""
    sa = se = 0.0
    for i, (t0, amp, dec, fh, fe) in enumerate(shakes):
        x = t - t0
        if 0.0 <= x < 6 * dec:
            env = math.radians(amp) * math.exp(-x / dec) * ease.smoothstep(x / 0.02)
            sa += env * math.sin(2.0 * math.pi * fh * x + i)
            se += env * math.sin(2.0 * math.pi * fe * x + 2 * i + 1)
    if sa or se:
        A, E = heading_elev(f)
        f = cam_basis(A + sa, max(-math.pi / 2, min(math.pi / 2, E + se)))[2]
    return P, f, lens


def focus_distance(P, f, point):
    """-> distance of point along the view axis f from P (clamped >= 0.05)."""
    return max(0.05, V.dot(V.sub(point, P), V.norm(f)))


def fstop_for(points, P, f, df, lens, blur_px, film=(1920, 1080), sensor_w=36.0, heading=None):
    """Smallest f-number keeping every in-frame point's thin-lens blur within blur_px (at film width).
    Points fade out of the budget by 20 % beyond the frame edge. lens mm, df m. -> N (0 when nothing needs it).
    heading: as in project."""
    lens_m = lens / 1000.0
    bmax = blur_px / film[0] * sensor_w / 1000.0
    r, u, f = basis_from_dir(f, heading)
    tx = tan_half(lens, sensor_w)
    ty = tx * film[1] / film[0]
    n = 0.0
    for X in points:
        d = V.sub(X, P)
        do = V.dot(d, f)
        if do > 0.05:
            edge = max(abs(V.dot(d, r) / (do * tx)), abs(V.dot(d, u) / (do * ty)))
            w = ease.smoothstep((1.2 - edge) / 0.2)
            n = max(n, w * lens_m * lens_m * abs(do - df) / (bmax * do * max(df - lens_m, 1e-3)))
    return n


def fstop_track(need_fn, t0, t1, rate=120, smooth=(0.10, 0.10), fstop_range=(1.4, 11.0),
                camera_holds=(), flat_holds=(), hold_ramp=0.15):
    """Sample need_fn(t) on a rate Hz grid, running max then running mean (never under the need),
    one direction inside each camera hold (t0, t1), one value inside each flat hold, rejoin over hold_ramp.
    -> callable(t) -> f-number (with .grid, .need, .rate, .t0 for audits).

    smooth: (max half-window s, mean half-window s), mean <= max so the result never drops under the need.
    A flat hold takes the largest need over its window plus the smoothing reach; the smoothing eases in
    and out. A camera hold keeps the smallest monotone cover (closing or opening, whichever adds less) and
    rejoins the curve over hold_ramp outside it, clipped to the gap to the next hold."""
    lo, hi = fstop_range
    a, b = (int(math.floor(x * rate + 0.5)) for x in smooth)
    if b > a:
        raise ValueError("fstop_track: smooth mean window must not exceed the max window")
    n = int(math.floor((t1 - t0) * rate + 0.5))
    need = [min(hi, max(lo, need_fn(t0 + k / rate))) for k in range(n + 1)]
    raw = list(need)

    def idx(t):
        return (t - t0) * rate
    sp = a + b
    for fa, fb in flat_holds:
        ka = max(0, int(math.ceil(idx(fa) - 1e-9)) - sp)
        kb = min(n, int(idx(fb) + 1e-9) + sp)
        if kb >= ka:
            top = max(need[ka:kb + 1])
            need[ka:kb + 1] = [top] * (kb + 1 - ka)
    mx = [max(need[max(0, k - a):k + a + 1]) for k in range(n + 1)]
    g = []
    for k in range(n + 1):
        win = mx[max(0, k - b):k + b + 1]
        g.append(sum(win) / len(win))
    holds = sorted(camera_holds)
    for i, (ha, hb) in enumerate(holds):
        ka, kb = int(math.ceil(idx(ha) - 1e-9)), min(n, int(idx(hb) + 1e-9))
        if kb <= ka or any(fa <= ha + 1e-9 and hb <= fb + 1e-9 for fa, fb in flat_holds):
            continue
        prev_end = holds[i - 1][1] if i > 0 else t0
        next_start = holds[i + 1][0] if i + 1 < len(holds) else t1
        seg = g[ka:kb + 1]
        up, dn = list(seg), list(seg)
        for k in range(1, len(up)):
            up[k] = max(up[k], up[k - 1])
        for k in range(len(dn) - 2, -1, -1):
            dn[k] = max(dn[k], dn[k + 1])
        if sum(up) <= sum(dn):
            g[ka:kb + 1] = up
            m = min(int(hold_ramp * rate), int((next_start - hb) * rate))
            for j in range(1, m + 1):
                if kb + j <= n:
                    g[kb + j] += max(0.0, up[-1] - g[kb + j]) * (1.0 - ease.smoothstep(j / m))
        else:
            g[ka:kb + 1] = dn
            m = min(int(hold_ramp * rate), int((ha - prev_end) * rate))
            for j in range(1, m + 1):
                if ka - j >= 0:
                    g[ka - j] += max(0.0, dn[0] - g[ka - j]) * (1.0 - ease.smoothstep(j / m))

    def track(t):
        x = min(max(idx(t), 0.0), float(n))
        k = min(int(x), n - 1) if n > 0 else 0
        if n == 0:
            return g[0]
        return min(hi, ease.lerp(g[k], g[k + 1], x - k))

    track.grid, track.need, track.rate, track.t0 = g, raw, rate, t0
    return track


def camera_state(shots, t, focus_fn, fstop_fn, shakes=(), film=(1920, 1080), sensor_w=36.0):
    """-> camera dict at t: pos, target, lens, fstop, focus, focus_distance, rot (look_at_euler), heading
    (shots.heading(t) rad, unshaken; None when shots has no heading), plus 'raw' (the unshaken pos,
    target, lens, heading) for the checker. focus_fn(t) -> world point; fstop_fn(t) -> N or None.
    Pass 'heading' to project / unproject / basis_from_dir: a vertical view takes its roll from it."""
    P, f, lens = shots.eval(t)
    hd = getattr(shots, "heading", None)
    A = hd(t) if hd is not None else None
    Ps, fs, _ = add_shake(P, f, lens, t, shakes) if shakes else (P, f, lens)
    foc = focus_fn(t)
    df = focus_distance(Ps, fs, foc)
    target = V.add(Ps, V.mul(fs, df))
    raw_target = V.add(P, V.mul(f, focus_distance(P, f, foc)))
    return {"pos": Ps, "target": target, "lens": lens, "fstop": fstop_fn(t) if fstop_fn else None,
            "focus": foc, "focus_distance": df, "rot": look_at_euler(Ps, target, A), "heading": A,
            "raw": {"pos": P, "target": raw_target, "lens": lens, "heading": A}}
