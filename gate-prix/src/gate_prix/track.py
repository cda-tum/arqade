"""THE FRIDGE as data: the road's segments, where the gate rows and item boxes stand, the
roadside sprites, the racing line, and each race's gate rows.

Pure Python, no pygame. z is distance along the track in world units (SEG per segment), and
lateral positions are in road half-widths (-1 to 1 is the road). A segment's `curve` is how
much the road bends over it (positive bends right) and its `hill` how much it climbs: the
renderer accumulates the first into a sideways offset and the second into a height. For the
top-down plan, a curve of c turns the heading by c / SEG radians per segment, so a lap whose
curves add up to 2 pi * SEG closes.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from functools import lru_cache

from gate_prix import config
from gate_prix.circuit import GATES

SEG = config.SEG


@dataclass(frozen=True, slots=True)
class Segment:
    index: int
    z: float  # where it starts, from the lap line
    curve: float
    hill: float  # the height gained over it
    y: float  # the height at its start
    line: float  # the racing line's lateral offset


@dataclass(frozen=True, slots=True)
class Arch:
    gate: str
    offset: float  # the arch's centre, in road half-widths
    right: bool  # the target's gate for this slot

    @property
    def half_width(self) -> float:
        """How far from its centre a car goes through it: as wide as it is drawn (a decoy
        is drawn smaller than the right arch)."""
        return config.ARCH_HALF_WIDTH if self.right else config.DECOY_HALF_WIDTH


@dataclass(frozen=True, slots=True)
class GateRow:
    slot: int
    z: float  # race distance from the start line: lap * lap_length + the row's position
    arches: tuple[Arch, ...]


# --- THE FRIDGE ---------------------------------------------------------------------------
# Pieces: (name, enter, hold, leave, curve, rise). The curve eases in over `enter` segments,
# holds, and eases out over `leave`; the height changes by `rise` over the whole piece, eased
# at both ends. Two straights' lengths were solved so that the plan closes.
_PIECES = (
    ("start straight", 0, 120, 0, 0.0, 0.0),
    ("cryostat sweeper", 30, 100, 30, 2.4, 0.0),
    ("cold straight", 0, 90, 0, 0.0, 1800.0),
    ("s-bend left", 20, 40, 20, -3.2, 0.0),
    ("s-bend right", 20, 40, 20, 3.2, 0.0),
    ("mixing straight", 0, 150, 0, 0.0, 0.0),
    ("still drop", 0, 80, 0, 0.0, -4200.0),
    ("cold plate run", 0, 84, 0, 0.0, 0.0),
    ("coax corner", 25, 55, 25, 4.4, 0.0),
    ("attenuator straight", 0, 296, 0, 0.0, 2400.0),
    ("left kink", 20, 30, 20, -1.8, 0.0),
    ("long sweeper", 40, 150, 40, 2.0, 0.0),
    ("mixing chamber drop", 0, 80, 0, 0.0, -4200.0),
    ("base straight", 0, 323, 0, 0.0, 0.0),
    ("closing sweeper", 35, 110, 35, 2.0, 4200.0),
    ("finish straight", 0, 120, 0, 0.0, 0.0),
)
# The 8 gate rows and 2 item box lines, as segment indices from the lap line.
_ROW_SEGMENTS = (100, 300, 610, 820, 1110, 1400, 1720, 2020)
_BOX_SEGMENTS = (200, 1260)
_BOX_OFFSETS = (-0.55, 0.0, 0.55)


def _smooth(t: float) -> float:
    return t * t * (3 - 2 * t)


def _build_pieces(pieces) -> tuple[list[float], list[float], list[tuple[int, int]]]:
    curves: list[float] = []
    hills: list[float] = []
    drops: list[tuple[int, int]] = []
    for _name, enter, hold, leave, curve, rise in pieces:
        start = len(curves)
        n = enter + hold + leave
        for i in range(enter):
            curves.append(curve * _smooth((i + 0.5) / enter))
        curves.extend([curve] * hold)
        for i in range(leave):
            curves.append(curve * (1 - _smooth((i + 0.5) / leave)))
        for i in range(n):
            a = (1 - math.cos(math.pi * i / n)) / 2
            b = (1 - math.cos(math.pi * (i + 1) / n)) / 2
            hills.append(rise * (b - a))
        if rise < 0:
            drops.append((start, start + n))
    return curves, hills, drops


def _racing_line(curves: list[float], window: int = 12) -> list[float]:
    """The inside of every bend: the curve averaged over +-window segments, scaled."""
    n = len(curves)
    line = []
    for i in range(n):
        avg = sum(curves[(i + d) % n] for d in range(-window, window + 1)) / (2 * window + 1)
        line.append(max(-0.6, min(0.6, avg / 3.0 * 0.6)))
    return line


def _roadside(count: int, drops: list[tuple[int, int]]) -> list[list[tuple[float, str]]]:
    """Coax trees all along, attenuators beside the straights, standoffs on the drops: all
    close to the road, so that they rush past (the sense of speed)."""
    sprites: list[list[tuple[float, str]]] = [[] for _ in range(count)]
    for i in range(0, count, 6):
        sprites[i].append((-1.3 if (i // 6) % 2 else 1.3, "coax"))
        if i % 24 == 0:
            sprites[i].append((1.9 if (i // 24) % 2 else -1.9, "coax"))
    for i in range(21, count, 45):
        sprites[i].append((-1.22 if (i // 45) % 2 else 1.22, "attenuator"))
    for start, end in drops:
        for i in range(start + 3, end, 9):
            sprites[i].append((-1.55, "standoff"))
            sprites[i].append((1.55, "standoff"))
    return sprites


class Track:
    """A closed lap of segments, with its rows, boxes and roadside sprites."""

    def __init__(
        self,
        curves: list[float],
        hills: list[float],
        rows: list[float] | None = None,
        boxes: list[tuple[float, tuple[float, ...]]] | None = None,
        roadside: list[list[tuple[float, str]]] | None = None,
        drops: list[tuple[int, int]] | None = None,
    ) -> None:
        count = len(curves)
        line = _racing_line(curves)
        self.segments: list[Segment] = []
        y = 0.0
        for i, (curve, hill) in enumerate(zip(curves, hills)):
            self.segments.append(Segment(i, i * SEG, curve, hill, y, line[i]))
            y += hill
        self.rows: list[float] = list(rows or [])
        self.boxes: list[tuple[float, tuple[float, ...]]] = list(boxes or [])
        self.roadside: list[list[tuple[float, str]]] = roadside or [[] for _ in range(count)]
        self.drops: list[tuple[int, int]] = list(drops or [])
        # plain lists for the renderer, running on past the lap line by its draw distance
        wrap = config.DRAW_SEGMENTS + 2
        self.curves = [seg.curve for seg in self.segments]
        self.heights = [seg.y for seg in self.segments]
        self.curves += self.curves[:wrap]
        self.heights += self.heights[:wrap]
        # the heading (radians) at the start of each segment, and the lap's whole turn
        self._heading = [0.0]
        for curve in curves:
            self._heading.append(self._heading[-1] + curve / SEG)
        self.turn = self._heading[-1]

    def lap_length(self) -> float:
        return len(self.segments) * SEG

    def segment_at(self, z: float) -> Segment:
        """The segment under race distance z, wrapping round the lap (and below zero)."""
        return self.segments[int(z // SEG) % len(self.segments)]

    def height_at(self, z: float) -> float:
        """The road's height at race distance z."""
        seg = self.segment_at(z)
        return seg.y + seg.hill * (z / SEG - math.floor(z / SEG))

    def heading_at(self, z: float) -> float:
        """The road's heading at race distance z: it keeps growing lap after lap."""
        laps, rest = divmod(z, self.lap_length())
        i = min(len(self.segments) - 1, int(rest // SEG))  # rest can round up to a lap
        f = rest / SEG - i
        return laps * self.turn + self._heading[i] + (self._heading[i + 1] - self._heading[i]) * f

    def plan(self) -> list[tuple[float, float]]:
        """The lap seen from above: the start of every segment, and the lap line again."""
        x = y = 0.0
        points = [(x, y)]
        for i in range(len(self.segments)):
            heading = (self._heading[i] + self._heading[i + 1]) / 2
            x += SEG * math.sin(heading)
            y += SEG * math.cos(heading)
            points.append((x, y))
        return points


@lru_cache(maxsize=1)
def fridge() -> Track:
    """THE FRIDGE: down through a dilution refrigerator's stages and round again."""
    curves, hills, drops = _build_pieces(_PIECES)
    # scale the bends so that the lap turns exactly once: no seam in the heading
    scale = 2 * math.pi * SEG / sum(curves)
    curves = [c * scale for c in curves]
    return Track(
        curves,
        hills,
        rows=[i * SEG for i in _ROW_SEGMENTS],
        boxes=[(i * SEG, _BOX_OFFSETS) for i in _BOX_SEGMENTS],
        roadside=_roadside(len(curves), drops),
        drops=drops,
    )


def segment_at(z: float) -> Segment:
    return fridge().segment_at(z)


def lap_length() -> float:
    return fridge().lap_length()


# --- Gate rows ------------------------------------------------------------------------------


def _offsets(rng: random.Random, n: int) -> list[float]:
    """n arch centres in [-ARCH_OFFSET_MAX, ARCH_OFFSET_MAX], sorted, never overlapping,
    with one gap between two of them (or beside a lone arch) of at least an arch's width."""
    h = config.ARCH_HALF_WIDTH
    reach = config.ARCH_OFFSET_MAX
    if n == 1:
        return [rng.uniform(-reach, reach)]  # the road beside it is always wider than 2h
    big = rng.randrange(n - 1)
    gaps = [2 * h if i == big else config.ARCH_MIN_GAP for i in range(n - 1)]
    span = sum(gaps) + 2 * h * (n - 1)  # first centre to last
    slack = 2 * reach - span
    # share the slack out at random between the margin at the left and the gaps
    cuts = sorted(rng.uniform(0, slack) for _ in range(n))
    shares = [b - a for a, b in zip([0.0] + cuts, cuts + [slack])]
    x = -reach + shares[0]
    offsets = [x]
    for i in range(n - 1):
        x += 2 * h + gaps[i] + shares[i + 1]
        offsets.append(x)
    return offsets


def gate_rows(track: Track, target: list[str], seed: int) -> list[GateRow]:
    """One row per slot of the target, at the track's row positions lap after lap: the
    target's SLOTS fill laps 1 and 2, and the final lap has none."""
    rng = random.Random(seed)
    per_lap = len(track.rows)
    rows = []
    for slot, gate in enumerate(target):
        lap, k = divmod(slot, per_lap)
        n = rng.randint(config.ARCHES_MIN, config.ARCHES_MAX)
        decoys = rng.sample([g for g in GATES if g != gate], n - 1)
        gates = [gate] + decoys
        rng.shuffle(gates)
        offsets = _offsets(rng, n)
        arches = tuple(Arch(g, round(x, 6), g == gate) for g, x in zip(gates, offsets))
        rows.append(GateRow(slot, lap * track.lap_length() + track.rows[k], arches))
    return rows


def arch_objects(rows: list[GateRow]) -> list[tuple[float, float, str]]:
    """The renderer's (z, x, kind) objects for the arches: the right ones lit."""
    return [
        (row.z, a.offset, f"arch:{a.gate}:lit" if a.right else f"arch:{a.gate}")
        for row in rows
        for a in row.arches
    ]


def box_objects(track: Track, laps: int) -> list[tuple[float, float, str]]:
    """Every item box of the race, lap after lap."""
    lap = track.lap_length()
    return [(n * lap + z, x, "box") for n in range(laps) for z, offsets in track.boxes for x in offsets]

