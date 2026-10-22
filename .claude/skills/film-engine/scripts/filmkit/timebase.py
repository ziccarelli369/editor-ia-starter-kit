"""timebase: the one clock every reader shares. Owner: core. Standard library only.

Units: seconds (float), 1-based frames (int), beats (float, 0 = film start).
frame(t) = floor(t*fps + 0.5) + 1; time(f) = (f-1)/fps. Never Python round().
Image sequences: 0001.png = frame 1 = t 0.

A project timeline.py builds a Format, a Layout (layout.py), an Events registry
and a pure state(t) function, then calls export_timeline(). Python readers
import the project module; JS readers read build/timeline.json.

Write every hit time as time(f) or beat(n). A decimal half-frame such as 2.05
at 30 fps is float-ambiguous (2.05 * 30 = 61.4999...), and Events.validate
reports it: frame(t) must equal the first frame whose state flips.
"""
import hashlib
import json
import math
import os

_T_EPS = 1e-9


class Format:
    """Film format. All taste-free numbers a film supplies once.

    fps: int. duration: s. bpm: beats per minute (None if no beat grid).
    film: (w, h) px of the render. ui: (w, h) CSS px of the app page.
    ui_scale: device scale of the UI screenshot (texture px per UI px).
    px_to_m: metres per UI px. comp: (w, h) px of the per-frame result canvas or None.
    Derived: frames (int, = frame(duration) - 1), beat (s), beat_frames (float).
    """

    def __init__(self, fps, duration, bpm=None, film=(1920, 1080), ui=(1280, 720),
                 ui_scale=3, px_to_m=0.0025, comp=None):
        if fps <= 0 or int(fps) != fps:
            raise ValueError(f"fps must be a positive integer, got {fps!r}")
        if duration <= 0:
            raise ValueError(f"duration must be positive seconds, got {duration!r}")
        self.fps = int(fps)
        self.duration = float(duration)
        self.bpm = bpm
        self.film = (film[0], film[1])
        self.ui = (ui[0], ui[1])
        self.ui_scale = ui_scale
        self.px_to_m = px_to_m
        self.comp = None if comp is None else (comp[0], comp[1])
        self.frames = frame(self.duration, self.fps) - 1
        self.beat = None if bpm is None else 60.0 / bpm
        self.beat_frames = None if bpm is None else self.beat * self.fps

    def to_json(self):
        """-> dict with every field plus the derived ones (frames, beat, beat_frames)."""
        return jsonable({
            "fps": self.fps, "duration": self.duration, "bpm": self.bpm, "film": self.film, "ui": self.ui,
            "ui_scale": self.ui_scale, "px_to_m": self.px_to_m, "comp": self.comp, "frames": self.frames,
            "beat": self.beat, "beat_frames": self.beat_frames,
        })


def frame(t, fps):
    """Film time (s) -> 1-based frame. Half-frame times round up, everywhere."""
    return int(math.floor(t * fps + 0.5)) + 1


def time(f, fps):
    """1-based frame -> film time (s)."""
    return (f - 1) / fps


def snap(t, fps):
    """-> the exact frame time nearest t: time(frame(t))."""
    return time(frame(t, fps), fps)


def is_whole_frame(t, fps, eps=1e-6):
    """True when t sits on an exact frame time within eps seconds."""
    return abs(t - snap(t, fps)) <= eps


def first_frame_at_or_after(t, fps):
    """-> the first f with time(f) >= t - 1e-9. Must equal frame(t) for every hit."""
    return int(math.ceil((t - _T_EPS) * fps)) + 1


def beat(n, bpm):
    """Beat index n (float allowed) -> seconds."""
    return n * 60.0 / bpm


def beats_of(t, bpm):
    """Seconds -> beat index (float)."""
    return t * bpm / 60.0


def on_beat(t, bpm, fps, eps=1e-6):
    """True when t is a whole beat and that beat is a whole frame."""
    n = math.floor(beats_of(t, bpm) + 0.5)
    tb = beat(n, bpm)
    return abs(t - tb) <= eps and is_whole_frame(tb, fps, eps)


def sixteenth_frames(bpm, fps):
    """-> frames per sixteenth note (float): fps * 15 / bpm."""
    return fps * 15.0 / bpm


def bpm_grid_ok(bpm, fps):
    """True when a sixteenth is a whole number of frames (so beat grid == frame grid)."""
    s = sixteenth_frames(bpm, fps)
    return s >= 1.0 and abs(s - math.floor(s + 0.5)) < 1e-9


def bpm_candidates(fps, lo=80, hi=180):
    """-> [bpm] in [lo, hi] whose sixteenth is whole frames (fps*15/k for integer k), ascending.

    A whole-number bpm is returned as int, the others as float.
    """
    if lo <= 0:
        raise ValueError("bpm_candidates: lo must be > 0")
    out = []
    k = 1
    while fps * 15.0 / k >= lo:
        b = fps * 15.0 / k
        if b <= hi:
            out.append(int(b) if b == int(b) else b)
        k += 1
    return sorted(out)


def timecode(seconds, fps):
    """Seconds -> 'H:MM:SS:FF' with FF = round-half-up of the frame fraction (a clock: 0 at t 0)."""
    f = int(math.floor(seconds * fps + 0.5))
    s, ff = divmod(f, fps)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}:{ff:02d}"


def jsonable(x):
    """-> x with tuples as lists and dict keys as str, recursively (JSON-safe, hash-stable)."""
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    return x


def _fields_text(ev):
    parts = []
    for k, v in ev.items():
        if k in ("id", "t", "kind", "frame"):
            continue
        parts.append(f"{k}={v if isinstance(v, str) else json.dumps(jsonable(v), separators=(',', ':'))}")
    return " ".join(parts)


def _hit_line(ev):
    return f"f{ev['frame']:>4} {ev['t']:>8.4f}s {ev['kind']:<12} {ev['id']:<18} {_fields_text(ev)}".rstrip()


class Events:
    """Registry of every hit. Each event is a dict {id, t, kind, frame, **fields}.

    id defaults to '<kind>#<n>' (n counts that kind from 1). Readers look events
    up by id or kind, never by list position. An interval event carries 'end' (s).
    """

    def __init__(self, fmt):
        self.fmt = fmt
        self._events = []
        self._by_id = {}
        self._counts = {}

    def __len__(self):
        return len(self._events)

    def __iter__(self):
        return iter(self.sorted())

    def add(self, t, kind, id=None, **fields):
        """Register an event at t (s). Stamps frame = frame(t). -> the event dict.

        Raises ValueError on a duplicate id or an 'end' before t.
        """
        self._counts[kind] = self._counts.get(kind, 0) + 1
        if id is None:
            id = f"{kind}#{self._counts[kind]}"
        if id in self._by_id:
            raise ValueError(f"duplicate event id {id!r}")
        if "end" in fields and fields["end"] < t:
            raise ValueError(f"event {id!r}: end {fields['end']} before t {t}")
        ev = {"id": id, "t": t, "kind": kind, "frame": frame(t, self.fmt.fps)}
        ev.update(fields)
        self._events.append(ev)
        self._by_id[id] = ev
        return ev

    def get(self, id):
        """-> the event with that id (KeyError if none)."""
        return self._by_id[id]

    def of_kind(self, kind):
        """-> [events] of that kind, time-sorted."""
        return sorted((e for e in self._events if e["kind"] == kind), key=lambda e: (e["t"], e["id"]))

    def kinds(self):
        """-> sorted list of distinct kinds."""
        return sorted(set(e["kind"] for e in self._events))

    def sorted(self):
        """-> all events sorted by (t, kind, id)."""
        return sorted(self._events, key=lambda e: (e["t"], e["kind"], e["id"]))

    def validate(self, whole_frame_kinds=(), on_beat_kinds=(), exceptions=(),
                 no_overlap=(), eps=1e-6):
        """Rule check. -> [problem strings] (empty = ok).

        whole_frame_kinds: kinds whose t must be an exact frame time and whose
          frame must equal first_frame_at_or_after(t).
        on_beat_kinds: kinds whose t must be a whole beat (needs fmt.bpm).
        exceptions: event ids excused from both rules (named, on purpose).
        no_overlap: [(start_kind, end_kind)] pairs; the intervals formed by
          pairing the i-th start with the i-th end must not overlap each other.
        Every event must also lie in [0, duration] and end its interval there.
        """
        fps, bpm, dur = self.fmt.fps, self.fmt.bpm, self.fmt.duration
        problems = []
        if on_beat_kinds and bpm is None:
            problems.append("on_beat_kinds given but Format.bpm is None")
        for ev in self.sorted():
            eid, t, kind = ev["id"], ev["t"], ev["kind"]
            if t < -eps or t > dur + eps:
                problems.append(f"{eid}: t={t!r} outside [0, {dur}]")
            if "end" in ev and ev["end"] > dur + eps:
                problems.append(f"{eid}: end={ev['end']!r} after the film ends at {dur}")
            if eid in exceptions:
                continue
            if kind in whole_frame_kinds:
                ffa = first_frame_at_or_after(t, fps)
                if not is_whole_frame(t, fps, eps) or ev["frame"] != ffa:
                    problems.append(f"{eid}: t={t!r} is not a frame time (frame {ev['frame']}, state flips at "
                                    f"frame {ffa}, nearest frame time {snap(t, fps)!r})")
            if kind in on_beat_kinds and bpm is not None and not on_beat(t, bpm, fps, eps):
                problems.append(f"{eid}: t={t!r} is not on a whole-frame beat (beat {beats_of(t, bpm):.4f})")
        for start_kind, end_kind in no_overlap:
            starts, ends = self.of_kind(start_kind), self.of_kind(end_kind)
            if len(starts) != len(ends):
                problems.append(f"no_overlap {start_kind}/{end_kind}: {len(starts)} starts, {len(ends)} ends")
                continue
            spans = []
            for s, e in zip(starts, ends):
                if e["t"] < s["t"]:
                    problems.append(f"{e['id']} ({e['t']!r}) ends before {s['id']} starts ({s['t']!r})")
                spans.append((s["t"], e["t"], s["id"], e["id"]))
            spans.sort()
            for a, b in zip(spans, spans[1:]):
                if b[0] < a[1] - eps:
                    problems.append(f"{b[2]} starts at {b[0]!r} before {a[3]} ends at {a[1]!r}")
        return problems

    def hit_table(self, kinds=None):
        """-> text table 'f### t.tts kind id fields' for review, one line per event."""
        return "\n".join(_hit_line(e) for e in self.sorted() if kinds is None or e["kind"] in kinds)

    def to_json(self):
        """-> [event dicts] time-sorted, JSON-safe."""
        return [jsonable(e) for e in self.sorted()]


def _rounded(x, dp):
    if isinstance(x, bool) or x is None or isinstance(x, (int, str)):
        return x
    if isinstance(x, float):
        return round(x, dp)
    if isinstance(x, dict):
        return {str(k): _rounded(v, dp) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_rounded(v, dp) for v in x]
    return x


def bake_frames(fmt, state_fn, round_dp=4):
    """-> [state_fn(time(f)) for f in 1..frames] with floats rounded to round_dp.

    Every dict gets 'f' and 't' added (first keys; they win over the state's own).
    JS readers compare ages with a 1e-6 eps.
    """
    out = []
    for f in range(1, fmt.frames + 1):
        t = time(f, fmt.fps)
        st = _rounded(dict(state_fn(t)), round_dp)
        st.pop("f", None)
        st.pop("t", None)
        out.append({"f": f, "t": round(t, round_dp), **st})
    return out


def timeline_hash(doc):
    """-> 12 hex chars: sha1 of the canonical JSON of doc without its 'hash' key."""
    body = jsonable({k: v for k, v in doc.items() if k != "hash"})
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def export_timeline(fmt, layout, events, state_fn, extra=None, out=None):
    """Build the timeline document and optionally write it.

    -> {'format', 'layout', 'events', 'frames', 'extra', 'hash'} where
    extra is any JSON-safe project data (hero spec, theme, shots, ...).
    out: path of build/timeline.json; written with indent 1, utf-8, LF, to a
    temp name first and renamed on success. NaN or inf anywhere raises.
    """
    doc = {
        "format": fmt.to_json(), "layout": layout.to_json(), "events": events.to_json(),
        "frames": bake_frames(fmt, state_fn), "extra": jsonable(extra or {}),
    }
    doc["hash"] = timeline_hash(doc)
    if out:
        text = json.dumps(doc, indent=1, ensure_ascii=False, allow_nan=False)
        folder = os.path.dirname(os.path.abspath(out))
        os.makedirs(folder, exist_ok=True)
        tmp = out + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.write("\n")
        os.replace(tmp, out)
    return doc


def load_timeline(path):
    """Read build/timeline.json -> dict. Raises if the stored hash mismatches."""
    with open(path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    want = timeline_hash(doc)
    if doc.get("hash") != want:
        raise ValueError(f"{path}: hash {doc.get('hash')!r} != {want!r}; rerun timeline.py")
    return doc


def print_hits(doc, kinds=None):
    """Print the hit table of an exported document (CLI helper)."""
    for ev in doc["events"]:
        if kinds is None or ev["kind"] in kinds:
            print(_hit_line(ev))
