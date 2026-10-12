"""Time the road renderer: two 960x270 views, then one 960x540 view.

    uv run python tools/benchmark.py [--frames 3000] [--profile]

Plain surfaces and pygame.font.init() only, with no display at all, because the cabinet's
SDL has no dummy video driver: it runs the same on the cabinet and on a desktop without a
screen. Each frame is the whole road: the background, the road, every roadside sprite, the
race's arches and item boxes, a row of 3 arches always coming up, and 6 cars. It prints the
mean, 95th percentile and worst milliseconds per frame. Desktop guide: worst <= 4 ms.
"""

from __future__ import annotations

import argparse
import cProfile
import math
import pstats
import random
import statistics
import time

import pygame

from gate_prix import circuit, config, track
from gate_prix.road import RoadView
from gate_prix.sprites import SpriteCache

W, H = config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT
CPU = ("green", "white", "orange", "teal")


def objects_for(fridge, statics, cams, frame: int):
    """The race's own objects, a 3-arch row and 4 CPU cars always ahead of P1, and the
    players' cars."""
    lead = cams[0][0]
    cycle = 2.4 * config.TOP_SPEED  # the row sweeps from the draw distance to the car
    ahead = cycle - (frame * config.TOP_SPEED / config.FPS) % cycle + config.CAR_AHEAD
    row = [(lead + ahead, x, kind) for x, kind in
           ((-0.62, "arch:H:lit"), (0.0, "arch:X"), (0.62, "arch:Z"))]
    cars = [(lead + 1500 + 2600 * i + 900 * math.sin(frame / 40 + i), 0.5 * math.sin(i + frame / 90),
             f"car:{name}") for i, name in enumerate(CPU)]
    players = [(z + config.CAR_AHEAD, x, f"car:{name}") for (z, x), name in zip(cams, ("p1", "p2"))]
    return statics + row + cars + players


def run(views, frames: int, fridge, statics, cache) -> list[float]:
    screen = pygame.Surface((W, H))
    sprites: list = []
    cams = [[0.0, 0.0], [-3000.0, -0.3]][: len(views)]
    times = []
    step = config.TOP_SPEED / config.FPS
    for frame in range(frames):
        for i, cam in enumerate(cams):
            cam[0] += step
            cam[1] = 0.9 * math.sin(frame / 70 + i)
        objects = objects_for(fridge, statics, cams, frame)
        start = time.perf_counter()
        for view, (cam_z, cam_x) in zip(views, cams):
            view.draw(screen, fridge, cam_z, cam_x, sprites, objects)
            view.draw_sprites(screen, sprites, cache)
        times.append((time.perf_counter() - start) * 1000)
    return times


def report(name: str, times: list[float]) -> None:
    ordered = sorted(times)
    p95 = ordered[int(len(ordered) * 0.95) - 1]
    print(f"{name:>22}: mean {statistics.fmean(times):6.2f} ms   p95 {p95:6.2f} ms   "
          f"worst {ordered[-1]:6.2f} ms   ({len(times)} frames)")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--frames", type=int, default=3000)
    parser.add_argument("--profile", action="store_true", help="cProfile the 2-view run")
    args = parser.parse_args(argv)

    pygame.font.init()
    start = time.perf_counter()
    cache = SpriteCache.shared()
    views2 = [RoadView((0, 0, W, 270)), RoadView((0, 270, W, 270))]
    views1 = [RoadView((0, 0, W, H))]
    print(f"start-up (sprites + backgrounds): {(time.perf_counter() - start) * 1000:.0f} ms")
    fridge = track.fridge()
    target = circuit.random_target(random.Random(1), config.SLOTS)
    rows = track.gate_rows(fridge, target, 1)
    statics = track.arch_objects(rows) + track.box_objects(fridge, config.LAPS)

    run(views2, 60, fridge, statics, cache)  # warm up
    if args.profile:
        profiler = cProfile.Profile()
        profiler.enable()
    times2 = run(views2, args.frames, fridge, statics, cache)
    if args.profile:
        profiler.disable()
        pstats.Stats(profiler).sort_stats("tottime").print_stats(15)
    times1 = run(views1, args.frames, fridge, statics, cache)
    report("2 views of 960x270", times2)
    report("1 view of 960x540", times1)


if __name__ == "__main__":
    main()
