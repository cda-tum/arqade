"""Time Brawl-Ket's frame: one 60 Hz fight step plus the full render, headless.

    cd brawl-ket && uv run python tools/benchmark.py            # the dev machine
    python3 benchmark.py /userdata/games/brawl_ket              # on the cabinet

Bot-against-bot fights for every pairing, then the title's demo through the
real Match, all drawn to a 640x360 surface (the display's upscale is not
included: SDL does that on the GPU). A frame has 16.7 ms; the plan's budget
for the game's own part is under 2 ms on the dev machine.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

FRAMES = 1800       # 30 s of play per pairing


def report(name: str, times: list[float]) -> None:
    times = sorted(times)
    mean = sum(times) / len(times)
    print(f"{name:14s} mean {mean * 1e3:5.2f} ms   p99 {times[int(len(times) * 0.99)] * 1e3:5.2f} ms"
          f"   max {times[-1] * 1e3:5.2f} ms")


def main(argv: list[str]) -> None:
    sys.path.insert(0, argv[0] if argv else str(Path(__file__).resolve().parents[1] / "src"))
    import pygame

    from brawl_ket import match as M
    from brawl_ket.bot import Bot
    from brawl_ket.fight import Fight
    from brawl_ket.match import PLAYERS
    from brawl_ket.moves import CHARACTERS
    from brawl_ket.render import Renderer

    pygame.init()
    try:
        pygame.display.set_mode((1, 1))     # the dummy display; Batocera's SDL has none, and
    except pygame.error:                    # Renderer then skips its convert()
        pass
    surface = pygame.Surface((640, 360))
    renderer = Renderer(surface)
    chars = list(CHARACTERS.values())
    for c1 in chars:
        for c2 in chars:
            fight, times = None, []
            for i in range(FRAMES):
                if fight is None or fight.over:
                    fight = Fight({"p1": c1, "p2": c2})
                    bots = {p: Bot(p, i + k) for k, p in enumerate(PLAYERS)}
                t = time.perf_counter()
                events = fight.step({p: b.input(fight) for p, b in bots.items()})
                renderer.draw_fight(fight, events, {"p1": 0, "p2": 0})
                times.append(time.perf_counter() - t)
            report(f"{c1.name} v {c2.name}", times[60:])     # the first second warms the text caches
    m, times = M.Match(), []
    for _ in range(FRAMES):
        t = time.perf_counter()
        renderer.draw(m, m.update(M.FrameInput()))
        times.append(time.perf_counter() - t)
    report("title + demo", times[60:])


if __name__ == "__main__":
    main(sys.argv[1:])
