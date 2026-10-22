"""arc: jumps, squash-and-stretch, pressable responses, visibility culling. Owner: motion. Standard library only.

World metres, seconds, radians. A jump row from the project is
(id, takeoff_t, land_t, to_xy, apex_m, style, target, surface_z) where to_xy
is world metres (the project converts UI px first), style names an entry in the
project's STYLE table and target names a layout rect. Landings sit on beat
frames by project rule; takeoffs may float. Every number in STYLE is taste.

Style keys read here (every one taste; the defaults are the reference film's
envelope shape, override per style):
  crouch       anticipation length s (clipped to the time since the last landing)
  crouch_min   shortest anticipation s (default 0)
  c_a          crouch compression (positive = squash)
  st           air stretch (positive number; applied negative = stretch)
  c_l          landing squash impulse height
  lean         pitch lean rad (read by the project, not here)
  ground_speed None = constant ground speed, or (s0, s1) factors of the mean
  tuck         extra compression bell mid-flight (default 0)
  crouch_share share of the crouch that squashes before the unload (default 0.75)
  air_fade     share of the flight over which the stretch decays (default 0.45)
  pre_land     (u0, span) stretch returning before the landing (default (0.6, 0.35))
  land         (tp, decay, period) landing impulse (default (0.04, 0.06, 0.32))
  land_fade    s to fade the landing ring at the next crouch (default 0.08)
  unload       s after takeoff over which the stretch release completes (default 0.03)
"""
import math

from . import ease as E
from . import vec as V

_DEFAULTS = {
    "crouch_min": 0.0, "ground_speed": None, "tuck": 0.0, "crouch_share": 0.75,
    "air_fade": 0.45, "pre_land": (0.6, 0.35), "land": (0.04, 0.06, 0.32),
    "land_fade": 0.08, "unload": 0.03,
}


def _style_get(S, key):
    return S.get(key, _DEFAULTS[key]) if key in _DEFAULTS else S[key]


class Arc:
    """A solved vertical parabola with ground travel.

    Fields: t0, t1, p0, p1 (x, y, z), zp (apex height), kz, uv, v0, ground_speed,
    duration, g_eff (effective gravity m/s^2), travel (heading rad, 0 = -Y; None for a hop in
    place, under 1e-9 m of ground travel: a yaw track keeps its running value).
    A zero rise (zp at both ends, s = sqrt(zp - z0) + sqrt(zp - z1) < 1e-12) is a flat slide at zp:
    kz = 0, uv = 0.5, g_eff = 0.
    """

    def __init__(self, p0, p1, t0, t1, zp, v0=None, ground_speed=None):
        self.p0, self.p1 = tuple(p0), tuple(p1)
        self.t0, self.t1 = float(t0), float(t1)
        self.duration = self.t1 - self.t0
        self.zp = float(zp)
        s = math.sqrt(zp - p0[2]) + math.sqrt(zp - p1[2])
        self.kz = s * s if s >= 1e-12 else 0.0
        self.uv = math.sqrt(zp - p0[2]) / s if s >= 1e-12 else 0.5
        self.v0 = None if v0 is None else (float(v0[0]), float(v0[1]))
        self.ground_speed = None if ground_speed is None else (float(ground_speed[0]), float(ground_speed[1]))
        self.g_eff = 2.0 * self.kz / (self.duration * self.duration)
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        self.travel = None if math.hypot(dx, dy) < 1e-9 else math.atan2(dx, -dy)

    def _h(self, u):
        """-> (share of the ground travel done at flight share u, its slope at u = 0)."""
        if self.ground_speed is None:
            return u, 1.0
        s0, s1 = self.ground_speed
        return (s0 + s1 - 2.0) * u ** 3 + (3.0 - 2.0 * s0 - s1) * u ** 2 + s0 * u, s0

    def __call__(self, t):
        """-> ((x, y, z), u) with u = share of flight clamped 0..1."""
        D = self.duration
        u = E.clamp((t - self.t0) / D) if D > 0 else 1.0
        x0, y0, _ = self.p0
        dx, dy = self.p1[0] - x0, self.p1[1] - y0
        h, h0 = self._h(u)
        x, y = x0 + dx * h, y0 + dy * h
        if self.v0 is not None:
            b = u * (1.0 - u) ** (4 if self.ground_speed is not None else 2)
            x += (self.v0[0] * D - dx * h0) * b
            y += (self.v0[1] * D - dy * h0) * b
        return (x, y, self.z_of_u(u)), u

    def z_of_u(self, u):
        """-> height at flight share u."""
        return self.zp - self.kz * (u - self.uv) ** 2


def ballistic(p0, p1, t0, t1, apex, v0=None, ground_speed=None):
    """Parabola through p0 at t0 and p1 at t1 with apex `apex` above the higher end.

    ground_speed: None = constant ground speed; (s0, s1) = cubic ease of the
    travel with start/end speed as factors of the mean. v0: carried start
    velocity (vx, vy) m/s when leaving a moving platform; faded by mid-flight.
    apex 0 between equal heights is a flat slide at that height (Arc's zero-rise case).
    -> Arc.
    """
    if t1 <= t0:
        raise ValueError(f"ballistic: land {t1} <= takeoff {t0}")
    if apex < 0:
        raise ValueError(f"ballistic: apex {apex} < 0")
    zp = max(p0[2], p1[2]) + apex
    return Arc(p0, p1, t0, t1, zp, v0, ground_speed)


def duration_from_apex(z0, z1, apex, g):
    """-> flight seconds for a parabola with one gravity g (for films that want one weight).
    Always finite for apex >= 0 and g > 0. apex 0 between equal heights -> 0.0 (no rise, no flight time
    under gravity): a flat move takes its duration from the beat sheet, as ballistic needs t1 > t0."""
    zp = max(z0, z1) + apex
    return math.sqrt(2.0 * (zp - z0) / g) + math.sqrt(2.0 * (zp - z1) / g)


def resolve_jumps(rows, start_xy, surface_z_fn, styles, fps):
    """Chain jump rows into records. Each takeoff starts where the last landing ended.

    rows: [(id, t0, t1, to_xy, apex, style, target, surface_z)].
    surface_z_fn(target, t) -> z of the landing surface at t (a pressed button sits lower),
      or None to use the row's surface_z; the function itself may be None.
    start_xy: (x, y) or (x, y, z) of the first takeoff (z defaults to 0).
    styles: {style: {'crouch': s, 'c_a': .., 'st': .., 'c_l': .., 'lean': .., ...}} (taste).
    -> [{'id', 'k', 'arc', 'style', 'S', 'target', 't0', 't1', 'crouch', 'crouch_t0', 'to', 'from',
         'surface_z', 'apex'}] time-sorted. 'from'/'to' are (x, y, z); 'to' z already sits at the
    surface the landing meets. fps: records 'frame' = frame(t1) for readers that list hits.
    Raises on overlap, a landing before its takeoff, or an unknown style.
    A jump off a moving platform: rebuild rec['arc'] = ballistic(platform_at(t0), rec['to'],
    t0, t1, apex, v0=carry, ground_speed=...) and set rec['from'] in the project.
    """
    def z_of(target, t, rest):
        z = surface_z_fn(target, t) if surface_z_fn is not None else None
        return rest if z is None else z

    out = []
    prev_xy = (start_xy[0], start_xy[1])
    prev_z = start_xy[2] if len(start_xy) > 2 else 0.0
    prev_t1, prev_target, prev_rest = None, None, prev_z
    for k, (jid, t0, t1, to_xy, apex, style, target, sz) in enumerate(rows):
        if style not in styles:
            raise KeyError(f"resolve_jumps: jump {jid!r} uses unknown style {style!r}")
        if t1 <= t0:
            raise ValueError(f"resolve_jumps: jump {jid!r} lands at {t1} before its takeoff {t0}")
        if prev_t1 is not None and t0 < prev_t1 - 1e-9:
            raise ValueError(f"resolve_jumps: jump {jid!r} takes off at {t0} before the previous landing {prev_t1}")
        S = styles[style]
        since = t0 - prev_t1 if prev_t1 is not None else S["crouch"]
        crouch = max(_style_get(S, "crouch_min"), min(S["crouch"], since))
        z0 = z_of(prev_target, t0, prev_rest) if prev_target is not None else prev_z
        z1 = z_of(target, t1, sz)
        p0 = (prev_xy[0], prev_xy[1], z0)
        p1 = (to_xy[0], to_xy[1], z1)
        arc = ballistic(p0, p1, t0, t1, apex, ground_speed=_style_get(S, "ground_speed"))
        out.append({"id": jid, "k": k, "arc": arc, "style": style, "S": S, "target": target,
                    "t0": float(t0), "t1": float(t1), "crouch": crouch, "crouch_t0": t0 - crouch,
                    "to": p1, "from": p0, "surface_z": sz, "apex": apex, "c_l": S["c_l"],
                    "frame": int(math.floor(t1 * fps + 0.5)) + 1})
        prev_xy, prev_t1, prev_target, prev_rest = (p1[0], p1[1]), t1, target, sz
    return out


def phase(jumps, t):
    """-> ('ground' | 'crouch' | 'air', jump_or_None) at t.

    'crouch' and 'air' return that jump; 'ground' returns the last landed jump (None before the first)."""
    last = None
    for J in jumps:
        if J["t0"] <= t < J["t1"]:
            return "air", J
        if J["crouch_t0"] <= t < J["t0"]:
            return "crouch", J
        if J["t1"] <= t:
            last = J
    return "ground", last


def _jump_compression(t, J, next_crouch_start):
    S = J["S"]
    t0, t1, cr = J["t0"], J["t1"], max(J["crouch"], 1e-6)
    st, c_a = S["st"], S["c_a"]
    share = _style_get(S, "crouch_share")
    if t < t0 - cr:
        return 0.0
    if t < t0:
        tau = t - t0
        if tau < -(1.0 - share) * cr:
            return c_a * E.smoothstep((tau + cr) / (share * cr))
        return E.lerp(c_a, -st, E.smoothstep((tau + (1.0 - share) * cr) / ((1.0 - share) * cr)))
    if t < t1:
        u = (t - t0) / (t1 - t0)
        u0, span = _style_get(S, "pre_land")
        c = -st * (1.0 - E.smoothstep(u / _style_get(S, "air_fade"))) - 0.5 * st * E.smoothstep((u - u0) / span)
        tuck = _style_get(S, "tuck")
        if tuck:
            c += tuck * E.bell(u, 0.1, 0.9)
        return c
    tau = t - t1
    tp, decay, period = _style_get(S, "land")
    c_l = J.get("c_l", S["c_l"])
    c = -0.5 * st * max(0.0, 1.0 - tau / _style_get(S, "unload")) + c_l * E.impulse(tau, tp, decay, period)
    if next_crouch_start is not None:
        c *= 1.0 - E.smoothstep((t - next_crouch_start) / _style_get(S, "land_fade"))
    return c


def compression(t, jumps, styles, idle_fn=None):
    """Sum of per-jump compression envelopes (crouch, unload, air stretch, landing impulse with ringing)
    plus idle_fn(t) if given. -> c (positive = squash, negative = stretch).

    Each record's 'c_l' (landing squash) defaults to its style's; set rec['c_l'] for one bigger hit."""
    c = 0.0
    for i, J in enumerate(jumps):
        nxt = jumps[i + 1]["crouch_t0"] if i + 1 < len(jumps) else None
        if t < J["crouch_t0"] - 0.01 or (nxt is not None and t > nxt + 0.1 and t > J["t1"] + 0.6):
            continue
        c += _jump_compression(t, J, nxt)
    if idle_fn is not None:
        c += idle_fn(t)
    return c


def squash_scale(c, floor=0.45, pin=0.0):
    """-> (s_xy, s_xy, s_z): s_z = max(floor, 1 - c), s_xy = s_z ** (-0.5 + 0.3 pin) (volume kept at pin 0)."""
    s_z = max(floor, 1.0 - c)
    s_xy = s_z ** (-0.5 + 0.3 * pin)
    return (s_xy, s_xy, s_z)


def pose_about_pivot(anchor, pivot_local, R_full, R_yaw):
    """Root position so the body rotates about pivot_local while the soles anchor stays put:
    anchor + R_yaw pivot - R_full pivot."""
    return V.add(V.sub(anchor, V.mat_vec(R_full, pivot_local)), V.mat_vec(R_yaw, pivot_local))


def yaw_track(keys, air_bias_fn=None, idle_fn=None, ease=None):
    """keys: [(t, yaw_target)]; each target unwrapped against the running value so a bake never spins back.
    air_bias_fn(t) -> extra yaw; idle_fn(t) -> sway. -> callable(t) -> yaw (continuous).
    The callable carries .keys (the unwrapped list) and .keyed(t) (the key track alone)."""
    if not keys:
        raise ValueError("yaw_track: no keys")
    keys = sorted(keys, key=lambda k: k[0])
    cur = keys[0][1]
    unwrapped = []
    for tk, y in keys:
        cur = E.unwrap_to(y, cur)
        unwrapped.append((tk, cur))

    def keyed(t):
        return E.keyed(unwrapped, t, ease)

    def yaw(t):
        y = keyed(t)
        if air_bias_fn is not None:
            y += air_bias_fn(t)
        if idle_fn is not None:
            y += idle_fn(t)
        return y

    yaw.keys = unwrapped
    yaw.keyed = keyed
    return yaw


def travel_bias(jumps, keyed_fn, bias_of):
    """Mid-air turn toward the travel direction. bias_of(jump) -> share 0..1 of the turn (0 = none).
    The turn is wrap(travel - keyed yaw at mid-flight) scaled by sin(pi u): exact zero at both ends.
    A hop in place (Arc.travel None) has no travel direction and adds no turn.
    -> callable(t) -> extra yaw, for yaw_track(air_bias_fn=...)."""
    def bias(t):
        ph, J = phase(jumps, t)
        if ph != "air":
            return 0.0
        b = bias_of(J)
        if not b or J["arc"].travel is None:
            return 0.0
        u = (t - J["t0"]) / (J["t1"] - J["t0"])
        d = E.wrap(J["arc"].travel - keyed_fn(0.5 * (J["t0"] + J["t1"])))
        return b * d * math.sin(math.pi * u)
    return bias


def press_intervals(landings, release_after):
    """landings: [(t, button_id)] or [(t, button_id, t_leave)] -> {button: [(t_start, t_end)]}
    merging consecutive landings on one button (first start, last end).

    t_end = t_leave when given; else t + release_after (number), release_after(t, button) (callable), or
    for None the next landing on another button (inf after the last)."""
    seq = sorted(landings, key=lambda e: e[0])
    out = {}
    runs = []
    for i, ev in enumerate(seq):
        t, b = ev[0], ev[1]
        if len(ev) > 2 and ev[2] is not None:
            end = ev[2]
        elif release_after is None:
            end = next((e[0] for e in seq[i + 1:] if e[1] != b), math.inf)
        elif callable(release_after):
            end = release_after(t, b)
        else:
            end = t + release_after
        if runs and runs[-1][0] == b:
            runs[-1][2] = max(runs[-1][2], end)
        else:
            runs.append([b, t, end])
    for b, t0, t1 in runs:
        out.setdefault(b, []).append((t0, t1))
    return out


def press_depth(t, intervals, hit_fn, release_fn):
    """-> depth 0..max for a button: hit_fn(tau, dur) inside an interval (tau since its start, dur its
    length), hit_fn(dur, dur) * release_fn(tau_since_end) after. intervals: [(t_start, t_end)] of one button."""
    d = 0.0
    for t0, t1 in intervals:
        if t0 <= t < t1:
            d = max(d, hit_fn(t - t0, t1 - t0))
        elif t >= t1:
            d = max(d, hit_fn(t1 - t0, t1 - t0) * release_fn(t - t1))
    return d


def _in_frame(ndc, pts):
    """Is any part of the hull of these screen points inside the unit frame?"""
    xs, ys = [p[0] for p in ndc], [p[1] for p in ndc]
    if max(xs) < -1 or min(xs) > 1 or max(ys) < -1 or min(ys) > 1:
        return False
    if any(abs(px) <= 1 and abs(py) <= 1 for px, py in ndc):
        return True
    hl = V.hull2d(ndc)
    if len(hl) < 3:
        return False
    for q in ((-1, -1), (1, -1), (1, 1), (-1, 1), (0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
        if V.in_hull2d(q, hl):
            return True
    for k in range(len(hl)):
        a, b = hl[k], hl[(k + 1) % len(hl)]
        for j in range(1, 16):
            px, py = a[0] + (b[0] - a[0]) * j / 16, a[1] + (b[1] - a[1]) * j / 16
            if abs(px) <= 1 and abs(py) <= 1:
                return True
    return False


def exit_time(corners_fn, camera_fn, t0, t_end, rate=240, floor_z=None, occluder_fn=None,
              film=(1920, 1080), sensor_w=36.0):
    """First t >= t0 (sampled at rate Hz) where every corner of a falling object is off frame, under an
    occluder hull, or below floor_z. corners_fn(t) -> [pts]; camera_fn(t) -> dict with pos, target, lens.
    occluder_fn(t) -> world points of a standing occluder: the object is hidden when every corner lies
    below the occluder's lowest point and inside its screen hull. A corner behind the lens counts as seen.
    The camera dict's optional 'heading' sets the roll of a vertical view (camera.project). -> t or None."""
    from . import camera as C
    t = t0
    step = 1.0 / rate
    while t <= t_end + 1e-9:
        pts = corners_fn(t)
        if pts:
            if floor_z is not None and min(p[2] for p in pts) < floor_z:
                return t
            cam = camera_fn(t)
            hd = cam.get("heading")
            ndc, behind = [], False
            for X in pts:
                a = C.project(cam["pos"], cam["target"], cam["lens"], X, film, sensor_w, hd)
                if a[2] <= 0.01:
                    behind = True
                    break
                ndc.append((a[0], a[1]))
            if not behind:
                if not _in_frame(ndc, pts):
                    return t
                if occluder_fn is not None:
                    occ = occluder_fn(t)
                    if occ and max(p[2] for p in pts) < min(o[2] for o in occ):
                        oc = [C.project(cam["pos"], cam["target"], cam["lens"], X, film, sensor_w, hd) for X in occ]
                        if all(c[2] > 0.01 for c in oc):
                            hull = V.hull2d([(c[0], c[1]) for c in oc])
                            if len(hull) >= 3 and all(V.in_hull2d(q, hull) for q in ndc):
                                return t
        t += step
    return None
