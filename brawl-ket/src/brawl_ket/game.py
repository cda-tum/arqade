"""The main loop: input -> fixed 60 Hz match steps -> sound and render once per frame."""

from __future__ import annotations

from dataclasses import replace

import pygame

from . import config
from .audio import make_audio, music_for
from .display import make_display, present
from .fonts import load_font
from .input import PLAYERS, Input
from .match import TITLE, FrameInput, Match
from .render import Renderer

STEP = 1.0 / config.FPS
MAX_FRAME_DT = 0.1      # a stall (a window drag, a slow load) must not make the sim sprint to catch up


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


def run(fullscreen: bool, window_size: str, show_fps: bool) -> None:
    pygame.init()
    pygame.joystick.init()
    surface, window = make_display(fullscreen, window_size)
    pygame.display.set_caption("Brawl-Ket")
    pygame.mouse.set_visible(False)

    inp = Input()
    audio = make_audio()
    match = Match()
    renderer = Renderer(surface)
    fps_font = load_font(8)
    clock = pygame.time.Clock()
    pending = FrameInput()
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
        if match.state == TITLE and inp.select_held_time * config.FPS >= config.BACK_HOLD_TO_QUIT:
            break

        pending = merge_pending(pending, inp.frame_input())
        acc += dt
        events: list = []
        while acc >= STEP:
            acc -= STEP
            events += match.update(pending)
            pending = consume(pending)
        if match.quit:          # QUIT on the title: the same way out as Start + Select
            break

        audio.music(music_for(match))
        audio.update()
        audio.play_events(events)
        renderer.draw(match, events)
        if show_fps:
            label = fps_font.render(f"{clock.get_fps():.0f} FPS", False, config.COLOR_FPS)
            surface.blit(label, (config.INTERNAL_WIDTH - label.get_width() - 4, config.INTERNAL_HEIGHT - 10))
        present(surface, window)
        pygame.display.flip()
