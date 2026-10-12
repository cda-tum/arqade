"""How THE FRIDGE drives: a scripted driver follows the racing line for a lap.

    uv run python tools/handling.py [--boost F] [--lookahead Z] [--stick S]

For every piece of the lap it prints the sharpest curve, the stick that curve needs just to
hold a line at top speed, the most stick the driver used, the frames it braked, the slowest
speed and the furthest it strayed from the centre. --boost drives the whole lap boosted, and
--stick caps the stick (0.75: a driver who never pushes it more than three quarters).
"""

from __future__ import annotations

import argparse
import sys

from gate_prix import config, track
from gate_prix.car import Car, aim
from gate_prix.track import _PIECES

DT = 1 / 60


def pieces():
    start = 0
    for name, enter, hold, leave, *_ in _PIECES:
        n = enter + hold + leave
        yield name, start, start + n
        start += n


def lap(boost: float = 0.0, lookahead: float = 600.0, stick: float = 1.0):
    """Drive one lap; per piece: (name, curve, hold, steer, brake frames, min speed, max |x|)."""
    fridge = track.fridge()
    car = Car("p1", "p1", 0.0)
    car.speed = config.TOP_SPEED * (1 + boost)
    stats = {}
    while car.z < fridge.lap_length():
        if boost:
            car.boost, car.boost_time = boost, 99.0
        seg = fridge.segment_at(car.z)
        steer, brake = aim(car, fridge.segment_at(car.z + lookahead).line, seg)
        steer = max(-stick, min(stick, steer))
        car.update(DT, steer, brake, seg)
        s = stats.setdefault(seg.index, [0.0, 0, 1e9, 0.0])
        s[0] = max(s[0], abs(steer))
        s[1] += brake > 0
        s[2] = min(s[2], car.speed)
        s[3] = max(s[3], abs(car.x))
    rows = []
    for name, a, b in pieces():
        curve = max(abs(fridge.segments[i].curve) for i in range(a, b))
        hold = config.CURVE_PUSH * curve * (1 + boost) / config.STEER_RATE
        got = [stats[i] for i in range(a, b) if i in stats]
        rows.append((name, curve, hold, max(g[0] for g in got), sum(g[1] for g in got),
                     min(g[2] for g in got), max(g[3] for g in got)))
    return rows


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--boost", type=float, default=0.0)
    parser.add_argument("--lookahead", type=float, default=600.0)
    parser.add_argument("--stick", type=float, default=1.0)
    args = parser.parse_args(argv)
    print(f"{'piece':22} {'curve':>5} {'hold':>5} {'stick':>5} {'brake':>5} {'v min':>6} {'|x|':>5}")
    for name, curve, hold, steer, brakes, vmin, xmax in lap(args.boost, args.lookahead, args.stick):
        print(f"{name:22} {curve:5.2f} {hold:5.0%} {steer:5.0%} {brakes:5d} "
              f"{vmin / config.TOP_SPEED:6.0%} {xmax:5.2f}")


if __name__ == "__main__":
    main(sys.argv[1:])
