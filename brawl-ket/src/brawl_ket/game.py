"""The main loop: input -> fixed 60 Hz match steps -> sound and render once per frame."""

from __future__ import annotations

import asyncio
from dataclasses import replace

import pygame
from arqade_common import runtime, web
from arqade_common.input import PadLayout

from . import config
from .audio import make_audio
from .display import make_display, present
from .fonts import load_font
from .input import PLAYERS, Input
from .match import PAUSABLE, TITLE, FrameInput, Match
from .render import Renderer

STEP = 1.0 / config.FPS
MAX_FRAME_DT = 0.1      # a stall (a window drag, a slow load) must not make the sim sprint to catch up
# Same as the folder name in the web build and the "id" in game.json.
GAME_ID = "brawl-ket"
# While a match is being fought (the round calls, the rounds, the pause), for the page
# events. CHOOSE YOUR FIGHTER, the stage, HOW TO PLAY and the result are outside it.
PLAYING = PAUSABLE


def merge_pending(pending: FrameInput, now: FrameInput) -> FrameInput:
    """Fold a display frame's input into what no step has consumed yet: the stick and
    the held buttons are whatever they are now, a press stays pending until a step uses it."""
    def either(a: dict, b: dict) -> dict:
        return {p: a[p] or b[p] for p in PLAYERS}

    return replace(
        now,
        fighters={p: replace(now.fighters[p], a=pending.fighters[p].a or now.fighters[p].a,
                             b=pending.fighters[p].b or now.fighters[p].b,
                             x=pending.fighters[p].x or now.fighters[p].x,
                             y=pending.fighters[p].y or now.fighters[p].y) for p in PLAYERS},
        nav={p: now.nav[p] if now.nav[p] != (0, 0) else pending.nav[p] for p in PLAYERS},
        confirms=either(pending.confirms, now.confirms),
        backs=either(pending.backs, now.backs),
        pauses=either(pending.pauses, now.pauses),
        activity=pending.activity or now.activity,
        any_button=pending.any_button or now.any_button,
    )


def consume(pending: FrameInput) -> FrameInput:
    """What the next step runs on: the stick still held, but presses already spent."""
    none = {p: False for p in PLAYERS}
    return replace(
        pending,
        fighters={p: replace(f, a=False, b=False, x=False, y=False) for p, f in pending.fighters.items()},
        nav={p: (0, 0) for p in PLAYERS},
        confirms=dict(none), backs=dict(none), pauses=dict(none), any_button=False,
        activity=any(f.dx or f.up or f.down for f in pending.fighters.values()) or pending.held,
    )


async def _leave(inp: Input, match: Match, surface: pygame.Surface, window: pygame.Surface | None) -> bool:
    """A player asked to quit: True ends the program. In the browser there is nothing to
    hand back to, so instead the game tells the page (which may take the player back to
    its game list) and returns to its title -- once the quit buttons are let go, or the
    title would quit again at once."""
    if not runtime.is_browser():
        return True
    web.post_event(web.QUIT, GAME_ID)
    while inp.quit_combo() or inp.select_held_time > 0:
        for event in pygame.event.get():
            inp.handle(event)
        inp.update(0.0)
        present(surface, window)
        pygame.display.flip()
        await asyncio.sleep(0)
    match.back_to_title()
    return False


async def run(fullscreen: bool, window_size: str, show_fps: bool, pad_layout: PadLayout | None = None) -> None:
    pygame.init()
    pygame.joystick.init()
    surface, window = make_display(fullscreen, window_size)
    pygame.display.set_caption("Brawl-Ket")
    pygame.mouse.set_visible(False)

    inp = Input(pad_layout)
    audio = make_audio()
    match = Match()
    renderer = Renderer(surface, inp.devices)
    fps_font = load_font(8)
    clock = pygame.time.Clock()
    pending = FrameInput()
    acc = 0.0
    playing = False     # a match is on (for the page's game-start / game-end events)

    while True:
        dt = min(runtime.frame_seconds(clock.tick(config.FPS) / 1000.0), MAX_FRAME_DT)
        quit_requested = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_requested = True
            inp.handle(event)
        inp.update(dt)
        if inp.quit_combo():
            quit_requested = True
        if match.state == TITLE and inp.select_held_time * config.FPS >= config.BACK_HOLD_TO_QUIT:
            quit_requested = True

        events: list = []
        if not quit_requested:
            pending = merge_pending(pending, inp.frame_input())
            acc += dt
            while acc >= STEP:
                acc -= STEP
                events += match.update(pending)
                pending = consume(pending)
            quit_requested = match.quit     # QUIT on the title: the same way out as Start + Select
        now_playing = match.state in PLAYING and not quit_requested
        if now_playing != playing:
            playing = now_playing
            web.post_event(web.GAME_START if playing else web.GAME_END, GAME_ID)
        if quit_requested:
            if await _leave(inp, match, surface, window):
                break
            pending, acc = FrameInput(), 0.0
            continue

        audio.play_events(events)
        renderer.draw(match, events)
        if show_fps:
            label = fps_font.render(f"{clock.get_fps():.0f} FPS", False, config.COLOR_FPS)
            surface.blit(label, (config.INTERNAL_WIDTH - label.get_width() - 4, config.INTERNAL_HEIGHT - 10))
        present(surface, window)
        pygame.display.flip()
        await asyncio.sleep(0)  # hand the frame to the browser (pygbag); no-op elsewhere
