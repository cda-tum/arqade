"""The main loop: input -> fixed 60 Hz fight steps -> render once per frame.

For now there is no title or select screen: it starts a TRIO mirror match and,
when a round ends, a new one. (Task 10 puts the match flow on top.)
"""

from __future__ import annotations

from dataclasses import replace

import pygame

from . import config
from .display import make_display, present
from .fight import Fight
from .fighter import IDLE, FighterInput
from .fonts import load_font
from .input import PLAYERS, Input
from .moves import TRIO
from .render import Renderer

STEP = 1.0 / config.FPS
MAX_FRAME_DT = 0.1      # a stall (a window drag, a slow load) must not make the sim sprint to catch up


def new_fight() -> Fight:
    return Fight({"p1": TRIO, "p2": TRIO})


def merge_pending(pending: dict[str, FighterInput], now: dict[str, FighterInput]) -> dict[str, FighterInput]:
    """Fold a display frame's input into what no step has consumed yet: the stick is
    whatever it is now, a button press stays pending until a step uses it."""
    return {
        p: replace(now[p], a=pending[p].a or now[p].a, b=pending[p].b or now[p].b,
                   x=pending[p].x or now[p].x)
        for p in PLAYERS
    }


def consume(pending: dict[str, FighterInput]) -> dict[str, FighterInput]:
    """What a step runs on: the stick still held, but presses already spent."""
    return {p: replace(f, a=False, b=False, x=False) for p, f in pending.items()}


def run(fullscreen: bool, window_size: str, show_fps: bool) -> None:
    pygame.init()
    pygame.joystick.init()
    surface, window = make_display(fullscreen, window_size)
    pygame.display.set_caption("Brawl-Ket")
    pygame.mouse.set_visible(False)

    inp = Input()
    renderer = Renderer(surface)
    fps_font = load_font(8)
    clock = pygame.time.Clock()

    fight = new_fight()
    wins = {p: 0 for p in PLAYERS}
    over_steps = 0
    pending = {p: IDLE for p in PLAYERS}
    acc = 0.0

    while True:
        dt = min(clock.tick(config.FPS) / 1000.0, MAX_FRAME_DT)
        quit_requested = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_requested = True
            inp.handle(event)
        inp.update(dt)
        if quit_requested or inp.quit_combo() or inp.keyboard_quit:
            break
        if inp.select_held_time * config.FPS >= config.BACK_HOLD_TO_QUIT:
            break

        pending = merge_pending(pending, inp.frame_input().fighters)
        acc += dt
        events: list = []
        while acc >= STEP:
            acc -= STEP
            events += fight.step(pending)
            pending = consume(pending)
            if fight.over:
                if over_steps == 0 and fight.winner:
                    wins[fight.winner] += 1
                over_steps += 1
                if over_steps >= config.ROUND_END_FRAMES:
                    if max(wins.values()) >= config.ROUNDS_TO_WIN:
                        wins = {p: 0 for p in PLAYERS}      # a first to ROUNDS_TO_WIN match is done
                    fight, over_steps = new_fight(), 0
                    break

        renderer.draw_fight(fight, events, wins)
        if show_fps:
            label = fps_font.render(f"{clock.get_fps():.0f} FPS", False, config.COLOR_FPS)
            surface.blit(label, (config.INTERNAL_WIDTH - label.get_width() - 4, config.INTERNAL_HEIGHT - 10))
        present(surface, window)
        pygame.display.flip()
