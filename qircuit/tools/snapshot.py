"""Render a few screens headless to PNGs, with real OpenGL (SDL's offscreen
driver), for checking the look without a cabinet: the title, the racer
select, the HOW TO PLAY card, every track mid-race with bots driving, and a match result. Usage, from qircuit/: `uv run python tools/snapshot.py [out_dir]`.
"""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "offscreen")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from qircuit import config, gfx  # noqa: E402
from qircuit.ai import Driver  # noqa: E402
from qircuit.match import MATCH_END, RACE, FrameInput, Match  # noqa: E402
from qircuit.render import Renderer  # noqa: E402

DT = 1 / 60


def frames(match: Match, renderer: Renderer, seconds: float, people: dict) -> None:
    """Bots drive the people's racers too; the match's own bots drive theirs."""
    for _ in range(int(seconds / DT)):
        if match.state == RACE:
            controls = {p: d.controls(match.race, DT) for p, d in people.items()}
            controls.update({p: d.controls(match.race, DT) for p, d in match.drivers.items()})
            events = match.pack.update(DT, controls)
            match.t += DT
            match._score(DT, events)
        else:
            events = match.update(DT, FrameInput(activity=True))
        renderer.draw(match, events, DT)


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    pygame.init()
    size, es = gfx.open_window((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT), False)
    renderer = Renderer(size, es)
    match = Match(random.Random(5))
    for _ in range(120):
        renderer.draw(match, match.update(DT, FrameInput()), DT)
    pygame.image.save(renderer.snapshot(), str(out / "title.png"))
    for index, name in enumerate(("figure8", "split", "hairpin")):
        match = Match(random.Random(5 + index))
        match.humans, match.bots, match.level = 2, 4, "TOUGH"
        match.track_index = index
        match.update(DT, FrameInput(confirm=True))  # to the racer select
        for _ in range(40):
            renderer.draw(match, match.update(DT, FrameInput(activity=True)), DT)
        if index == 0:
            pygame.image.save(renderer.snapshot(), str(out / "select.png"))
        match.update(DT, FrameInput(pause=True))  # Start: the HOW TO PLAY card
        for _ in range(150):
            renderer.draw(match, match.update(DT, FrameInput(activity=True)), DT)
        if index == 0:
            pygame.image.save(renderer.snapshot(), str(out / "tutorial.png"))
        match.update(DT, FrameInput(any_button=True))  # any button: race
        people = {p: Driver(p, "BRUTAL", random.Random(index)) for p in match.people}
        frames(match, renderer, config.COUNTDOWN + 6.0, people)
        pygame.image.save(renderer.snapshot(), str(out / f"race_{name}.png"))
        frames(match, renderer, 6.0, people)
        pygame.image.save(renderer.snapshot(), str(out / f"race_{name}_later.png"))
    holder = match.pack.holder or "p1"
    match.pack.lead_time[holder] = match.target - 0.05
    frames(match, renderer, 1.5, people)
    if match.state == MATCH_END:
        pygame.image.save(renderer.snapshot(), str(out / "match_end.png"))
    print(f"saved to {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("snapshots"))
