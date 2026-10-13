"""Time the road renderer: two 480x540 views side by side, then one 960x540 view, each plain
and then with the boost, warp and Task 5d effects at their heaviest.

    uv run python tools/benchmark.py [--frames 3000] [--profile]

Plain surfaces and pygame.font.init() only, with no display at all, because the cabinet's
SDL has no dummy video driver: it runs the same on the cabinet and on a desktop without a
screen. Each frame is the whole road: the background, the road, every roadside sprite, the
race's arches and item boxes, a row of 3 arches always coming up, and 6 cars. The "warp"
runs add what a player sees in the LIGHT SPEED! warp, in every view at once (the worst
case): the field of view widened (a projection constant and the camera pulled in), the
camera shake, exhaust flames on every car, the marker over the right arch, the
star-streak tunnel and the edge tint; and the second playtest's: every car tilted in a
drift with its sparks, a noise storm of clouds and mines ahead, a DECOHERENCE cloud, the
gantry and its lights, and the minimap. It prints the mean, 95th percentile and worst
milliseconds per frame. Desktop guide: worst <= 4 ms.
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
from gate_prix.minimap import Minimap
from gate_prix.render import MAP, Renderer, fov, shake
from gate_prix.road import RoadView
from gate_prix.sprites import SpriteCache, tilt_kind

W, H = config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT
CPU = ("green", "white", "lime", "steel")


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


def run(views, frames: int, fridge, statics, cache, renderer=None) -> list[float]:
    """Time `frames` frames; with a renderer, with the warp's effects (see the top)."""
    screen = renderer.surface if renderer else pygame.Surface((W, H))
    sprites: list = []
    cams = [[0.0, 0.0], [-3000.0, -0.3]][: len(views)]
    times = []
    step = config.TOP_SPEED / config.FPS
    speed = 2.0 * config.TOP_SPEED  # a perfect check's warp
    widen = fov(speed, 1.0)
    for frame in range(frames):
        for i, cam in enumerate(cams):
            cam[0] += step
            cam[1] = 0.9 * math.sin(frame / 70 + i)
        objects = objects_for(fridge, statics, cams, frame)
        if renderer:
            cars = [(z, x, kind) for z, x, kind in objects if kind.startswith("car:")]
            objects = [o for o in objects if not o[2].startswith("car:")]
            objects += [(z, x, tilt_kind(kind, 9 * math.sin(frame / 20))) for z, x, kind in cars]
            objects += [(z - 1.0, x, f"flame:{frame // 3 % 4}") for z, x, _ in cars]
            objects += [(z - 0.5, x, f"spark:2:{frame // 3 % 3}") for z, x, _ in cars]
            lead = cams[0][0]
            objects += [(lead + 3000 + 2500 * k, 0.5 * math.sin(k), ("static:1", "mine:0", "deco:2")[k % 3])
                        for k in range(8)]
            objects += [(n * fridge.lap_length(), 0.0, "gantry") for n in range(config.LAPS + 1)]
        start = time.perf_counter()
        for i, (view, (cam_z, cam_x)) in enumerate(zip(views, cams)):
            if renderer is None:
                view.draw(screen, fridge, cam_z, cam_x, sprites, objects)
                view.draw_sprites(screen, sprites, cache)
                continue
            ahead = config.CAR_AHEAD / widen
            view.draw(screen, fridge, cam_z + config.CAR_AHEAD - ahead, cam_x, sprites,
                      objects, depth=config.CAMERA_DEPTH / widen, ahead=ahead,
                      lift=shake(speed, frame, i))
            view.draw_sprites(screen, sprites, cache)
            renderer._sprites = sprites
            renderer.frame = frame
            renderer._markers_over_right_arches(view)
            renderer._gantry_lights(screen, view, sprites, ("red", 5))
            k = (frame // 2) % len(renderer._tunnel[view.rect.size])
            screen.blit(renderer._tunnel[view.rect.size][k], view.rect.topleft)
            for strip, (x, y) in renderer._tint[view.rect.size][-1]:
                screen.blit(strip, (view.rect.x + x, view.rect.y + y))
        if renderer:
            Minimap.for_track(fridge, MAP).draw(screen, (10, H - MAP[1] - 10),
                                                [(f"{c}", cams[0][0] + 900 * i) for i, c in
                                                 enumerate(config.CAR_COLORS)], ("p1", "p2"))
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
    vw, vh = config.VIEW_2P
    views2 = [RoadView((0, 0, vw, vh), spread=config.VIEW_2P_SPREAD),
              RoadView((W - vw, 0, vw, vh), spread=config.VIEW_2P_SPREAD)]
    views1 = [RoadView((0, 0, W, H))]
    print(f"start-up (sprites + backgrounds): {(time.perf_counter() - start) * 1000:.0f} ms")
    fridge = track.fridge()
    target = circuit.random_target(random.Random(1), config.SLOTS)
    rows = track.gate_rows(fridge, target, 1)
    statics = track.arch_objects(rows) + track.box_objects(fridge, config.LAPS)

    renderer = Renderer(pygame.Surface((W, H)))
    # warm up for 4 s: every sprite size blitted once (RLE encodes on the first blit), and
    # the CPU up to its clock (on a desktop the first seconds can run 2-3x slower)
    warm = time.perf_counter()
    while time.perf_counter() - warm < 4.0:
        for views in (views2, views1):
            run(views, 150, fridge, statics, cache)
            run(views, 150, fridge, statics, cache, renderer)
    if args.profile:
        profiler = cProfile.Profile()
        profiler.enable()
    times2 = run(views2, args.frames, fridge, statics, cache)
    if args.profile:
        profiler.disable()
        pstats.Stats(profiler).sort_stats("tottime").print_stats(15)
    times1 = run(views1, args.frames, fridge, statics, cache)
    warp2 = run(views2, args.frames, fridge, statics, cache, renderer)
    warp1 = run(views1, args.frames, fridge, statics, cache, renderer)
    report("2 views of 480x540", times2)
    report("1 view of 960x540", times1)
    report("2 views, warp", warp2)
    report("1 view, warp", warp1)


if __name__ == "__main__":
    main()
