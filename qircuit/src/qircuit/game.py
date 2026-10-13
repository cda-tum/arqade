"""The main loop: input -> match -> sound and drawing (OpenGL), at 60 fps."""

from __future__ import annotations

import random

import pygame

from qircuit import config, gfx
from qircuit.input import Input
from qircuit.match import RACE, Match
from qircuit.render import Renderer
from qircuit.sound import load_sounds


def run(fullscreen: bool, window_size: str, show_fps: bool) -> None:
    pygame.init()
    pygame.joystick.init()
    w, h = (int(v) for v in window_size.lower().split("x"))
    size, es = gfx.open_window((w, h), fullscreen)
    pygame.display.set_caption("Qircuit")
    pygame.mouse.set_visible(False)

    inp = Input()
    sounds = load_sounds()
    match = Match(random.Random())
    renderer = Renderer(size, es)
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

        events = match.update(dt, inp.frame_input())
        if match.quit:  # QUIT on the title: back to the cabinet's menu
            break
        sounds.play_events(events, match.people)
        racing = match.state == RACE and not match.paused
        sounds.update_drift(match.race if racing else None, match.people, dt)
        renderer.show_fps = clock.get_fps() if show_fps else None
        renderer.draw(match, events, dt)
        renderer.present()
        pygame.display.flip()
