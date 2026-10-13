"""The main loop: input -> match -> sound and render, at 60 fps."""

from __future__ import annotations

import random

import pygame

from qurves import config
from qurves.display import make_display, present
from qurves.fonts import load_font
from qurves.input import Input
from qurves.match import TITLE, Cue, Match
from qurves.render import Renderer
from qurves.sound import load_sounds


def run(fullscreen: bool, window_size: str, show_fps: bool) -> None:
    pygame.init()
    pygame.joystick.init()
    surface, window = make_display(fullscreen, window_size)
    pygame.display.set_caption("Qurves")
    pygame.mouse.set_visible(False)

    inp = Input()
    sounds = load_sounds()
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
        if Cue("ready") in events:  # the press that dismissed HOW TO PLAY must not steer
            inp.consume_held()
        sounds.play_events(events)
        renderer.draw(match, events, dt)
        if show_fps:
            label = fps_font.render(f"{clock.get_fps():.0f} FPS", False, config.COLOR_FPS)
            surface.blit(label, (config.INTERNAL_WIDTH - label.get_width() - 6, config.INTERNAL_HEIGHT - 14))
        present(surface, window)
        pygame.display.flip()
