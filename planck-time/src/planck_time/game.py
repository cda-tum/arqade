"""The main loop: input -> session -> sound and render, at 60 fps."""

from __future__ import annotations

import random

import pygame

from planck_time import config
from planck_time.audio import make_audio
from planck_time.display import make_display, present
from planck_time.fonts import load_font
from planck_time.hiscores import Hiscores
from planck_time.input import Input
from planck_time.render import Renderer
from planck_time.session import TITLE, Session


def run(fullscreen: bool, window_size: str, show_fps: bool) -> None:
    pygame.init()
    pygame.joystick.init()
    surface, window = make_display(fullscreen, window_size)
    pygame.display.set_caption("Planck Time")
    pygame.mouse.set_visible(False)

    inp = Input()
    audio = make_audio()
    session = Session(random.Random(), Hiscores(config.SCORE_FILE))
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
        if session.state == TITLE and inp.select_held_time >= config.BACK_HOLD_TO_QUIT:
            break

        events = session.update(dt, inp.frame_input())
        audio.music("title" if session.state == TITLE else "game")
        audio.tempo(session.level)
        audio.update()
        audio.play_events(events)
        renderer.draw(session, events, dt)
        if show_fps:
            label = fps_font.render(f"{clock.get_fps():.0f} FPS", False, config.COLOR_FPS)
            surface.blit(label, (config.INTERNAL_WIDTH - label.get_width() - 4, config.INTERNAL_HEIGHT - 10))
        present(surface, window)
        pygame.display.flip()
