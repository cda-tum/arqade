"""The main loop: input -> match -> sound and render, at 60 fps."""

from __future__ import annotations

import random

import pygame

from gate_drop import config
from gate_drop.audio import make_audio
from gate_drop.display import make_display, present
from gate_drop.fonts import load_font
from gate_drop.input import Input
from gate_drop.match import TITLE, Match
from gate_drop.render import Renderer


def run(fullscreen: bool, window_size: str, show_fps: bool) -> None:
    pygame.init()
    pygame.joystick.init()
    surface, window = make_display(fullscreen, window_size)
    pygame.display.set_caption("Gate Drop")
    pygame.mouse.set_visible(False)

    inp = Input()
    audio = make_audio()
    match = Match(random.Random())
    renderer = Renderer(surface)
    fps_font = load_font(8)
    clock = pygame.time.Clock()

    while True:
        dt = min(clock.tick(config.FPS) / 1000.0, 0.05)
        quit_requested = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_requested = True
            inp.handle(event)
        inp.update(dt)
        if quit_requested or inp.quit_combo() or inp.keyboard_quit:
            break
        if match.state == TITLE and inp.select_held_time >= config.BACK_HOLD_TO_QUIT:
            break

        events = match.update(dt, inp.frame_input())
        if match.quit_requested:  # QUIT on the title: the same clean exit as Start + Select
            break
        audio.music("title" if match.state == TITLE else "game")
        audio.tempo(match.danger)
        audio.update()
        audio.play_events(events)
        renderer.draw(match, events, dt)
        if show_fps:
            label = fps_font.render(f"{clock.get_fps():.0f} FPS", False, config.COLOR_FPS)
            surface.blit(label, (config.INTERNAL_WIDTH - label.get_width() - 4, config.INTERNAL_HEIGHT - 10))
        present(surface, window)
        pygame.display.flip()
