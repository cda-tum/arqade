"""Dev tool: frame-time budget of a busy round, headless.

    uv run python tools/bench.py [level_key]

Bots play the round while every frame is fully updated and drawn; prints
the mean / 99th-percentile / worst frame cost. The cabinet's Pi 4 is
several times slower than a laptop, so keep the mean far below 16.7 ms.
"""

from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from overquqed import game, levels  # noqa: E402
from overquqed.bot import Bot  # noqa: E402
from overquqed.round_scene import RoundScene  # noqa: E402


def main() -> None:
    key = sys.argv[1] if len(sys.argv) > 1 else "cosmic"
    pygame.init()
    surface = pygame.display.set_mode((480, 360))
    app = game.App(surface, None, False)
    rs = RoundScene(app, levels.LEVELS_BY_KEY[key], [0, 1], seed=1)
    app.switch(rs)
    bot = Bot(rs.world)
    rs.chef_inputs = lambda inp: bot.update(1 / 60)
    times = []
    for _ in range(60 * 60):
        t0 = time.perf_counter()
        app.step(1 / 60, [])
        app.scene.draw(app.surface)
        times.append((time.perf_counter() - t0) * 1000)
        if app.scene is not rs:
            break
    times.sort()
    n = len(times)
    print(f"{key}: {n} frames  mean {sum(times) / n:.2f} ms  p99 {times[int(n * 0.99)]:.2f} ms  "
          f"max {times[-1]:.2f} ms  items at end {len(rs.world.items())}")


if __name__ == "__main__":
    main()
