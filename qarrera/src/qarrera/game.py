"""The main loop: input -> match -> sound and drawing (OpenGL), at 60 fps."""

from __future__ import annotations

import asyncio
import random

import pygame
from arqade_common import runtime, web
from arqade_common.input import PadLayout

from qarrera import config, gfx
from qarrera.input import Input
from qarrera.match import COUNTDOWN, RACE, Match
from qarrera.render import Renderer
from qarrera.sound import load_sounds

# Same as the folder name in the web build and the "id" in game.json.
GAME_ID = "qarrera"
# While a match is being raced, for the page events. The title, the racer
# select, HOW TO PLAY and the match result are outside it.
PLAYING = (COUNTDOWN, RACE)


async def _let_go(inp: Input, renderer: Renderer) -> None:
    """Wait for the quit buttons to be let go, or the title would quit again at once."""
    while inp.quit_combo():
        for event in pygame.event.get():
            inp.handle(event)
        inp.update(0.0)
        renderer.present()
        pygame.display.flip()
        await asyncio.sleep(0)


async def run(fullscreen: bool, window_size: str, show_fps: bool, pad_layout: PadLayout | None = None) -> None:
    pygame.init()
    pygame.joystick.init()
    if runtime.is_browser():
        # The page scales the canvas to fit, so the window is the frame itself.
        (w, h), fullscreen = (config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT), False
    else:
        w, h = (int(v) for v in window_size.lower().split("x"))
    size, es = gfx.open_window((w, h), fullscreen)
    pygame.display.set_caption("Qarrera")
    pygame.mouse.set_visible(False)

    inp = Input(pad_layout)
    sounds = load_sounds()
    match = Match(random.Random())
    renderer = Renderer(size, es, inp.devices)
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
        leave = inp.quit_combo()
        events = []
        if not quit_requested and not leave:
            events = match.update(dt, inp.frame_input())
            leave = match.quit  # QUIT on the title: the same clean exit as Start + Select
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
            sounds.update_drift(None, (), 1.0)  # the drift squeal fades out at once
            await _let_go(inp, renderer)
            match.back_to_title()
            continue

        sounds.play_events(events, match.people)
        racing = match.state == RACE and not match.paused
        sounds.update_drift(match.race if racing else None, match.people, dt)
        renderer.show_fps = clock.get_fps() if show_fps else None
        renderer.draw(match, events, dt)
        renderer.present()
        pygame.display.flip()
        await asyncio.sleep(0)  # hand the frame to the browser (pygbag); no-op elsewhere
