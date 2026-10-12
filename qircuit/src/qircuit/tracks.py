"""The tracks. Each is a TrackDef: slot-car pieces (straights and arcs), its
hills, kickers and boost pads, how many gates and item gates the race keeps
coming and going on it, and its scene (scenes.py). Stations are placed
relative to the pieces, so moving a pad along a piece means changing a
fraction, not a raw number.

The chase camera shows a stretch of a few hundred units, so the tracks are
big: SCALE times the layouts first drawn to fit one 640x360 screen. The
figure 8 is built piece by piece; the others with track.rounded(), a
polygon whose corners each get their own radius, which always closes.
"""

from __future__ import annotations

import math

from qircuit.track import TrackDef, piece_starts, rounded

SCALE = 2.5
BRIDGE = 34.0  # high enough for any racer to drive under


def _figure_eight() -> TrackDef:
    """Two loops joined by two straights that cross in the middle, the
    second pass climbing over the first on a bridge. The right loop turns
    right and the left loop left, so every wire is the inner, shorter one in
    one loop and the outer one in the other."""
    radius, spread = 100.0 * SCALE, 175.0 * SCALE
    alpha = math.asin(radius / spread)
    leg = math.sqrt(spread**2 - radius**2)
    turn = 180 + 2 * math.degrees(alpha)
    pieces = (("S", leg), ("A", radius, turn), ("S", 2 * leg), ("A", radius, -turn), ("S", leg))
    m = piece_starts(pieces)
    return TrackDef(
        name="FIGURE 8",
        start=(320.0 * SCALE, 186.0 * SCALE),
        heading=-math.degrees(alpha),
        pieces=pieces,
        start_s=0.7 * leg,
        items=8,
        dynamic_gates=12,
        humps=((m[2] + 10, m[3] - 10, BRIDGE),),  # the second pass climbs over the first
        kickers=(m[0] + 0.5 * leg,),
        boosts=((m[2] + 30, (0, 1)), (m[4] + 0.25 * leg, (2, 3)), (m[1] + 0.5 * (m[2] - m[1]), (1, 2))),
        env="space",
    )


def _split() -> TrackDef:
    """A hill along the top into an S-bend, then the long split: the wires
    part 2 + 2 down the right-hand side and only rejoin at the end of the
    bottom straight, where both pairs jump a kicker. Through the sweeper
    between, the inner pair (wires 2-3) takes a tighter, shorter line and
    the outer pair (0-1) a faster, longer one."""
    corners = tuple((x * SCALE, y * SCALE, r * SCALE) for x, y, r in (
        (60, 75, 45),  # 0: top left, tight
        (320, 75, 50),  # 1, 2: the S-bend
        (380, 125, 50),
        (580, 125, 45),  # 3: top right
        (580, 295, 80),  # 4, 5: the split's two sweepers
        (60, 295, 80),
    ))
    start, heading, pieces = rounded(corners)
    m = piece_starts(pieces)

    def straight(i: int, f: float) -> float:
        return m[2 * i] + f * (m[2 * i + 1] - m[2 * i])

    return TrackDef(
        name="SPLIT",
        start=start,
        heading=heading,
        pieces=pieces,
        start_s=straight(0, 0.15),
        split=(m[6] - 10, m[9] - 10),
        items=8,
        dynamic_gates=12,
        humps=((straight(0, 0.3), straight(0, 0.95), 22.0),),
        kickers=(straight(4, 0.55),),  # both pairs jump, in the split
        boosts=((straight(2, 0.25), (2, 3)), (straight(5, 0.45), (0, 1)), (straight(4, 0.2), (0, 3))),
        env="chip",
    )


def _hairpin() -> TrackDef:
    """The longest straight of all along the top, with a boost pad and a
    kicker for a long flight, a hill down the left-hand side, and a tongue
    that pokes up from the bottom: a hairpin so tight its inside wire wants a
    crawl, while the outside one can carry real speed round."""
    corners = tuple((x * SCALE, y * SCALE, r * SCALE) for x, y, r in (
        (60, 70, 45),  # 0: top left
        (580, 70, 45),  # 1: top right
        (580, 300, 60),  # 2: bottom right
        (395, 300, 40),  # 3: into the tongue
        (395, 180, 37.5),  # 4, 5: the hairpin at its tip
        (320, 180, 37.5),
        (320, 300, 40),  # 6: out of the tongue
        (60, 300, 60),  # 7: bottom left
    ))
    start, heading, pieces = rounded(corners)
    m = piece_starts(pieces)

    def straight(i: int, f: float) -> float:
        return m[2 * i] + f * (m[2 * i + 1] - m[2 * i])

    return TrackDef(
        name="HAIRPIN",
        start=start,
        heading=heading,
        pieces=pieces,
        start_s=straight(0, 0.08),
        items=8,
        dynamic_gates=12,
        humps=((straight(7, 0.05), straight(7, 0.95), 26.0),),
        kickers=(straight(0, 0.62),),  # a long flight down the top straight
        boosts=((straight(0, 0.35), (1, 2)), (straight(6, 0.3), (0, 1)), (straight(1, 0.2), (2, 3))),
        env="surf",
    )


ALL = (_figure_eight(), _split(), _hairpin())
