"""The main loop: input -> match -> sound and render, at 60 fps."""

from __future__ import annotations

import asyncio
import random

import pygame
from arqade_common import runtime, web

from gate_drop import config
from gate_drop.audio import make_audio
from gate_drop.display import make_display, present
from gate_drop.fonts import load_font
from gate_drop.input import Input, get_events, last_device, start_devices
from gate_drop.match import COUNTDOWN, LEVEL_CLEAR, ROUND, ROUND_RESULT, TITLE, Match
from gate_drop.render import Renderer

# Same as the folder name in the web build and the "id" in game.json.
GAME_ID = "gate-drop"
# While a match is being played (a round, the pause, the pauses between rounds),
# for the page events. Results, name entry and the title are outside it.
PLAYING = (COUNTDOWN, ROUND, ROUND_RESULT, LEVEL_CLEAR)


async def _leave(inp: Input, match: Match, surface: pygame.Surface, window: pygame.Surface | None) -> bool:
    """A player asked to quit: True ends the program. In the browser there is
    nothing to hand back to, so instead the game tells the page (which may
    take the player back to its game list) and returns to its title -- once
    the quit buttons are let go, or the title would quit again at once."""
    if not runtime.is_browser():
        return True
    web.post_event(web.QUIT, GAME_ID)
    clock = pygame.time.Clock()
    while True:
        get_events()
        inp.update(clock.tick(config.FPS) / 1000.0)
        if not inp.quit_combo() and inp.select_held_time == 0.0:
            break
        present(surface, window)
        pygame.display.flip()
        await asyncio.sleep(0)
    match.quit_requested = False
    match.back_to_title()
    return False


async def run(fullscreen: bool, window_size: str, show_fps: bool) -> None:
    pygame.init()
    pygame.joystick.init()
    start_devices()
    surface, window = make_display(fullscreen, window_size)
    pygame.display.set_caption("Gate Drop")
    pygame.mouse.set_visible(False)

    inp = Input()
    audio = make_audio()
    match = Match(random.Random())
    renderer = Renderer(surface, last_device())
    fps_font = load_font(8)
    clock = pygame.time.Clock()
    playing = False  # a match is on (for the page's game-start / game-end events)

    while True:
        dt = min(runtime.frame_seconds(clock.tick(config.FPS) / 1000.0), 0.05)
        quit_requested = False
        for event in get_events():
            if event.type == pygame.QUIT:
                quit_requested = True
            inp.handle(event)
        inp.update(dt)
        if inp.quit_combo() or (match.state == TITLE and inp.select_held_time >= config.BACK_HOLD_TO_QUIT):
            quit_requested = True
        if quit_requested:
            if playing:  # the match ends before the player leaves
                playing = False
                web.post_event(web.GAME_END, GAME_ID)
            if await _leave(inp, match, surface, window):
                break
            continue

        events = match.update(dt, inp.frame_input())
        if match.quit_requested:  # QUIT on the title: the same clean exit as Start + Select
            if await _leave(inp, match, surface, window):
                break
            continue
        if (match.state in PLAYING) != playing:
            playing = not playing
            web.post_event(web.GAME_START if playing else web.GAME_END, GAME_ID)
        audio.play_events(events)
        renderer.draw(match, events, dt)
        if show_fps:
            label = fps_font.render(f"{clock.get_fps():.0f} FPS", False, config.COLOR_FPS)
            surface.blit(label, (config.INTERNAL_WIDTH - label.get_width() - 4, config.INTERNAL_HEIGHT - 10))
        present(surface, window)
        pygame.display.flip()
        await asyncio.sleep(0)  # hand the frame to the browser (pygbag); no-op elsewhere
