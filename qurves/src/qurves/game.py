"""The main loop: input -> match -> sound and render, at 60 fps."""

from __future__ import annotations

import asyncio
import random

import pygame
from arqade_common import runtime, web
from arqade_common.input import PadLayout

from qurves import config
from qurves.display import make_display, present
from qurves.fonts import load_font
from qurves.input import Input
from qurves.match import COUNTDOWN, ROUND, ROUND_RESULT, TITLE, Cue, Match
from qurves.render import Renderer
from qurves.sound import load_sounds


# Same as the folder name in the web build and the "id" in game.json.
GAME_ID = "qurves"
# While a match is being played (the rounds and the pauses between them), for
# the page events. The title, HOW TO PLAY and the match result are outside it.
PLAYING = (COUNTDOWN, ROUND, ROUND_RESULT)


async def _let_go(inp: Input, surface: pygame.Surface, window: pygame.Surface | None) -> None:
    """Wait for the quit buttons to be let go, or the title would quit again at once."""
    while inp.quit_combo() or inp.select_held_time > 0:
        for event in pygame.event.get():
            inp.handle(event)
        inp.update(0.0)
        present(surface, window)
        pygame.display.flip()
        await asyncio.sleep(0)


async def run(fullscreen: bool, window_size: str, show_fps: bool, pad_layout: PadLayout | None = None) -> None:
    pygame.init()
    pygame.joystick.init()
    surface, window = make_display(fullscreen, window_size)
    pygame.display.set_caption("Qurves")
    pygame.mouse.set_visible(False)

    inp = Input(pad_layout)
    sounds = load_sounds()
    match = Match(random.Random())
    renderer = Renderer(surface, inp.devices)
    fps_font = load_font(8)
    clock = pygame.time.Clock()
    playing = False  # a match is on (for the page's game-start / game-end events)

    while True:
        dt = min(clock.tick(config.FPS) / 1000.0, 0.05)
        quit_requested = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_requested = True
            inp.handle(event)
        inp.update(dt)
        leave = inp.quit_combo() or (match.state == TITLE and inp.select_held_time >= config.BACK_HOLD_TO_QUIT)
        if not quit_requested and not leave:
            events = match.update(dt, inp.frame_input())
            leave = match.quit_requested  # QUIT on the title: the same clean exit as Start + Select
        now_playing = match.state in PLAYING and not (quit_requested or leave)
        if now_playing != playing:
            playing = now_playing
            web.post_event(web.GAME_START if playing else web.GAME_END, GAME_ID)
        if quit_requested:
            break
        if leave:
            # In the browser there is nothing to hand back to: tell the page
            # (which may take the player back to its game list) and go back
            # to the title instead.
            if not runtime.is_browser():
                break
            web.post_event(web.QUIT, GAME_ID)
            await _let_go(inp, surface, window)
            match = Match(random.Random())
            continue
        if Cue("ready") in events:  # the press that dismissed HOW TO PLAY must not steer
            inp.consume_held()
        sounds.play_events(events)
        renderer.draw(match, events, dt)
        if show_fps:
            label = fps_font.render(f"{clock.get_fps():.0f} FPS", False, config.COLOR_FPS)
            surface.blit(label, (config.INTERNAL_WIDTH - label.get_width() - 6, config.INTERNAL_HEIGHT - 14))
        present(surface, window)
        pygame.display.flip()
        await asyncio.sleep(0)  # hand the frame to the browser (pygbag); no-op elsewhere
