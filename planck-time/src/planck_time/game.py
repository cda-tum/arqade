"""The main loop: input -> session -> sound and render, at 60 fps."""

from __future__ import annotations

import asyncio
import random

import pygame
from arqade_common import runtime, web
from arqade_common.input import PadLayout

from planck_time import config
from planck_time.audio import make_audio
from planck_time.display import make_display, present
from planck_time.fonts import load_font
from planck_time.hiscores import Hiscores
from planck_time.input import Input
from planck_time.render import Renderer
from planck_time.session import PAUSABLE, TITLE, Session

# Same as the folder name in the web build and the "id" in game.json.
GAME_ID = "planck-time"


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
    pygame.display.set_caption("Planck Time")
    pygame.mouse.set_visible(False)

    inp = Input(pad_layout)
    audio = make_audio()
    hiscores = Hiscores(config.SCORE_FILE)
    session = Session(random.Random(), hiscores)
    renderer = Renderer(surface, inp.devices)
    fps_font = load_font(8)
    clock = pygame.time.Clock()
    playing = False  # a run is on (for the page's game-start / game-end events)

    while True:
        dt = min(clock.tick(config.FPS) / 1000.0, 0.05)
        quit_requested = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_requested = True
            inp.handle(event)
        inp.update(dt)
        leave = inp.quit_combo() or (session.state == TITLE and inp.select_held_time >= config.BACK_HOLD_TO_QUIT)
        if not quit_requested and not leave:
            events = session.update(dt, inp.frame_input())
            leave = session.quit_requested  # QUIT on the title: the same clean exit as Start + Select
        now_playing = session.state in PAUSABLE and not (quit_requested or leave)
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
            session = Session(random.Random(), hiscores)
            continue
        audio.play_events(events)
        renderer.draw(session, events, dt)
        if show_fps:
            label = fps_font.render(f"{clock.get_fps():.0f} FPS", False, config.COLOR_FPS)
            surface.blit(label, (config.INTERNAL_WIDTH - label.get_width() - 4, config.INTERNAL_HEIGHT - 10))
        present(surface, window)
        pygame.display.flip()
        await asyncio.sleep(0)  # hand the frame to the browser (pygbag); no-op elsewhere
