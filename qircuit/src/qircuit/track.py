"""Track geometry. Pure (no pygame), so it is unit tested.

A track is a closed centre line built from straights and arcs, like
slot-car track pieces, with config.LANES wires running alongside it. Places
along it are stations s (px along the centre line, 0..length). Across it, a
lane coordinate u is a wire index, fractional while a car changes wires.
Wire i sits (i - 1.5) * LANE_W to the right of the centre line, right as
seen driving, so wire 0 is the car's leftmost and wire 3 its rightmost.

Where a track splits, wires 0-1 and 2-3 part around an island and rejoin.
Each wire gets its own polyline, so its length through a corner (inner wires
are shorter), its curvature (inner wires are tighter) and its shape through
a split all come from the same numbers the cars drive on.

The track also has a height along it: humps (the figure 8's bridge) and
kickers, short ramps that end in a lip and throw a fast car into the air.
Boost pads sit on chosen wires.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from qircuit import config

@dataclass(frozen=True)
class Gate:
    """A fixed gate on the track. lanes is one wire for H and M, (control,
    target) for a CNOT and the two swapped wires for a SWAP. (The item gates,
    ERR and ZENO, are not fixed: the race spawns them, see race.Item.)"""

    kind: str  # "H", "M", "SWAP" or "CNOT"
    s: float
    lanes: tuple[int, ...]


@dataclass(frozen=True)
class TrackDef:
    name: str
    start: tuple[float, float]
    heading: float  # degrees in screen coordinates: 0 is right, 90 is down
    pieces: tuple  # ("S", length) or ("A", radius, degrees); positive degrees turn right
    start_s: float  # where the start/finish line is
    gates: tuple[Gate, ...] = ()
    split: tuple[float, float] | None = None  # stations where wires 0-1 and 2-3 part
    bridge: tuple[float, float] | None = None  # stations drawn over everything else
    underpass: tuple[float, float] | None = None  # stations that run under the bridge
    items: int = 0  # item gates on the track at any one time, spawned by the race
    dynamic_gates: int = 0  # quantum gates the race keeps coming and going
    humps: tuple = ()  # (from, to, height): the track rises smoothly and comes back down
    kickers: tuple = ()  # stations of the lips of the jump ramps, across all wires
    boosts: tuple = ()  # (station, wires) of the boost pads
    env: str = "space"  # its scene, see scenes.py


def piece_length(piece: tuple) -> float:
    if piece[0] == "S":
        return float(piece[1])
    return abs(math.radians(piece[2])) * piece[1]


def piece_starts(pieces: tuple) -> list[float]:
    """The station at which each piece starts, plus the total length at the end."""
    out = [0.0]
    for piece in pieces:
        out.append(out[-1] + piece_length(piece))
    return out


def rounded(corners: tuple) -> tuple[tuple[float, float], float, tuple]:
    """A closed track around a polygon with every corner rounded off:
    corners is ((x, y, radius), ...) in driving order. Returns (start,
    heading in degrees, pieces), starting where the straight out of the first
    corner begins. The pieces alternate: the straight from corner i to i+1,
    then the arc of corner i+1 (the last arc is corner 0's), so with
    m = piece_starts(pieces), straight i runs m[2i]..m[2i+1] and the arc of
    corner i+1 m[2i+1]..m[2i+2]. It closes by construction; corners too close
    together for their radii raise ValueError."""
    n = len(corners)
    pts = [(x, y) for x, y, _ in corners]
    heads = [math.atan2(pts[(i + 1) % n][1] - pts[i][1], pts[(i + 1) % n][0] - pts[i][0]) for i in range(n)]
    turns = [wrap_angle(heads[i] - heads[i - 1]) for i in range(n)]
    cut = [corners[i][2] * math.tan(abs(turns[i]) / 2) for i in range(n)]
    pieces = []
    for i in range(n):
        j = (i + 1) % n
        length = math.dist(pts[i], pts[j]) - cut[i] - cut[j]
        if length < -1e-6:
            raise ValueError(f"corners {i} and {j} are too close for their radii")
        pieces += [("S", max(0.0, length)), ("A", corners[j][2], math.degrees(turns[j]))]
    start = (pts[0][0] + math.cos(heads[0]) * cut[0], pts[0][1] + math.sin(heads[0]) * cut[0])
    return start, math.degrees(heads[0]), tuple(pieces)


def wrap_angle(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


def in_range(s: float, span: tuple[float, float] | None, length: float) -> bool:
    """Is station s inside span, which may wrap past the start of the track?"""
    if span is None:
        return False
    a, b = span[0] % length, span[1] % length
    s %= length
    return a <= s <= b if a <= b else (s >= a or s <= b)


def _walk(d: TrackDef, stations: list[float]) -> list[tuple[float, float, float, float]]:
    """(x, y, heading, signed curvature) at each of the sorted stations."""
    out = []
    x, y = d.start
    h = math.radians(d.heading)
    base = 0.0
    pieces = list(d.pieces)
    i = 0
    for s in stations:
        while i < len(pieces) - 1 and s > base + piece_length(pieces[i]):
            x, y, h = _end_of(pieces[i], x, y, h)
            base += piece_length(pieces[i])
            i += 1
        out.append(_point_on(pieces[i], x, y, h, s - base))
    return out


def _point_on(piece: tuple, x: float, y: float, h: float, t: float):
    if piece[0] == "S":
        return x + math.cos(h) * t, y + math.sin(h) * t, h, 0.0
    radius, degrees = piece[1], piece[2]
    sign = 1.0 if degrees > 0 else -1.0
    k = sign / radius
    nx, ny = -math.sin(h), math.cos(h)  # the right-hand normal
    cx, cy = x + sign * radius * nx, y + sign * radius * ny
    ht = h + k * t
    return cx - sign * radius * -math.sin(ht), cy - sign * radius * math.cos(ht), ht, k


def _end_of(piece: tuple, x: float, y: float, h: float):
    px, py, ph, _ = _point_on(piece, x, y, h, piece_length(piece))
    return px, py, ph


def split_amount(s: float, split: tuple[float, float] | None, length: float) -> float:
    """0 where the wires run together, 1 where they are fully apart, with
    smooth (cosine) ramps of SPLIT_RAMP at either end."""
    if split is None or not in_range(s, split, length):
        return 0.0
    a = split[0] % length
    span = (split[1] - split[0]) % length
    into = (s - a) % length
    t = min(into, span - into, config.SPLIT_RAMP) / config.SPLIT_RAMP
    return (1 - math.cos(math.pi * t)) / 2


def hump_height(s: float, hump: tuple[float, float, float], length: float) -> float:
    """A smooth rise over the first third, flat on top, a smooth fall over the last third."""
    a, b, h = hump
    if not in_range(s, (a, b), length):
        return 0.0
    span = (b - a) % length
    into = (s - a) % length
    ramp = span / 3
    t = min(into, span - into, ramp) / ramp
    return h * (1 - math.cos(math.pi * t)) / 2


def kicker_height(s: float, lip: float, length: float) -> float:
    """A straight ramp up to KICKER_HEIGHT at the lip, nothing after it."""
    into = (s - (lip - config.KICKER_LEN)) % length
    if into > config.KICKER_LEN:
        return 0.0
    return config.KICKER_HEIGHT * into / config.KICKER_LEN


def lane_offset(lane: int, amount: float) -> float:
    side = -1.0 if lane < config.LANES // 2 else 1.0
    return (lane - (config.LANES - 1) / 2) * config.LANE_W + side * config.SPLIT_GAP * amount


class Track:
    def __init__(self, d: TrackDef) -> None:
        self.d = d
        self.name = d.name
        self.gates = d.gates
        self.length = sum(piece_length(p) for p in d.pieces)
        self.n = n = max(16, round(self.length))
        self.ds = self.length / n
        samples = _walk(d, [k * self.ds for k in range(n + 1)])
        end = samples[-1]
        self.closure_error = math.hypot(end[0] - d.start[0], end[1] - d.start[1])
        self.heading_error = abs(wrap_angle(end[2] - math.radians(d.heading)))
        samples = samples[:n]
        self.cx = [p[0] for p in samples]
        self.cy = [p[1] for p in samples]
        self.ch = [p[2] for p in samples]
        self.split = [split_amount(k * self.ds, d.split, self.length) for k in range(n)]
        self.elev = [sum(hump_height(k * self.ds, h, self.length) for h in d.humps)
                     + sum(kicker_height(k * self.ds, lip, self.length) for lip in d.kickers)
                     for k in range(n)]
        self.off = [[lane_offset(i, self.split[k]) for k in range(n)] for i in range(config.LANES)]
        self.lx: list[list[float]] = []
        self.ly: list[list[float]] = []
        self.lh: list[list[float]] = []  # heading of each wire's segment k -> k+1
        self.lf: list[list[float]] = []  # each wire's segment length over the centre line's
        self.lk: list[list[float]] = []  # each wire's signed curvature (positive turns right)
        for i in range(config.LANES):
            xs = [self.cx[k] - math.sin(self.ch[k]) * self.off[i][k] for k in range(n)]
            ys = [self.cy[k] + math.cos(self.ch[k]) * self.off[i][k] for k in range(n)]
            seg = []
            heads = []
            for k in range(n):
                dx, dy = xs[(k + 1) % n] - xs[k], ys[(k + 1) % n] - ys[k]
                seg.append(max(1e-6, math.hypot(dx, dy)))
                heads.append(math.atan2(dy, dx))
            raw = [wrap_angle(heads[k] - heads[k - 1]) / ((seg[k] + seg[k - 1]) / 2) for k in range(n)]
            curv = [sum(raw[(k + j) % n] for j in (-2, -1, 0, 1, 2)) / 5 for k in range(n)]
            self.lx.append(xs)
            self.ly.append(ys)
            self.lh.append(heads)
            self.lf.append([sg / self.ds for sg in seg])
            self.lk.append(curv)

    # --- lookups --------------------------------------------------------------------

    def _index(self, s: float) -> tuple[int, float]:
        f = (s % self.length) / self.ds
        k = int(f)
        return k % self.n, f - k

    @staticmethod
    def _lanes(u: float) -> tuple[int, int, float]:
        i0 = max(0, min(config.LANES - 1, int(math.floor(u))))
        i1 = min(i0 + 1, config.LANES - 1)
        return i0, i1, max(0.0, min(1.0, u - i0))

    def pose(self, u: float, s: float) -> tuple[float, float, float]:
        """(x, y, heading) of lane coordinate u at station s."""
        k, t = self._index(s)
        k1 = (k + 1) % self.n
        i0, i1, w = self._lanes(u)
        x0 = self.lx[i0][k] + (self.lx[i0][k1] - self.lx[i0][k]) * t
        y0 = self.ly[i0][k] + (self.ly[i0][k1] - self.ly[i0][k]) * t
        x1 = self.lx[i1][k] + (self.lx[i1][k1] - self.lx[i1][k]) * t
        y1 = self.ly[i1][k] + (self.ly[i1][k1] - self.ly[i1][k]) * t
        h0 = self.lh[i0][k]
        h = h0 + wrap_angle(self.lh[i1][k] - h0) * w
        return x0 + (x1 - x0) * w, y0 + (y1 - y0) * w, h

    def factor(self, u: float, s: float) -> float:
        """How much longer (> 1) or shorter (< 1) lane coordinate u is than
        the centre line at station s: a car there covers speed / factor of
        centre line per second."""
        k, _ = self._index(s)
        i0, i1, w = self._lanes(u)
        return self.lf[i0][k] + (self.lf[i1][k] - self.lf[i0][k]) * w

    def curvature(self, u: float, s: float) -> float:
        """Signed curvature (1 / radius, positive turning right) of lane coordinate u at s."""
        k, _ = self._index(s)
        i0, i1, w = self._lanes(u)
        return self.lk[i0][k] + (self.lk[i1][k] - self.lk[i0][k]) * w

    def split_at(self, s: float) -> float:
        return self.split[self._index(s)[0]]

    def height(self, s: float) -> float:
        """The track's surface height at station s."""
        k, t = self._index(s)
        return self.elev[k] + (self.elev[(k + 1) % self.n] - self.elev[k]) * t

    def can_switch(self, s: float, lane: int, target: int) -> bool:
        """A car on `lane` at s may change to the neighbouring wire `target`."""
        if not 0 <= target < config.LANES or abs(target - lane) != 1:
            return False
        middle = (config.LANES // 2 - 1, config.LANES // 2)
        if {lane, target} == set(middle) and self.split_at(s) > config.SPLIT_NO_SWITCH:
            return False
        return True

    def in_bridge(self, s: float) -> bool:
        return in_range(s, self.d.bridge, self.length)

    def in_underpass(self, s: float) -> bool:
        return in_range(s, self.d.underpass, self.length)
