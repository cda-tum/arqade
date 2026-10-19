"""The main loop: input -> match -> sound and picture, on a fixed 60 Hz clock.

The match always steps by exactly 1/60 s. When a frame took longer (the Pi falling behind)
it steps up to MAX_STEPS times to catch up, the presses going to the first step only, so
the game keeps its speed instead of slowing down; it never steps less than once a frame.

Start + Select on one pad (or Esc on the keyboard) quits, as do QUIT on the title and
closing the window. Both
are armed (see input.py), so nothing held at launch can quit the game at once.
"""

from __future__ import annotations

import random

import pygame

from gate_prix import config
from gate_prix.audio import NullAudio, make_audio
from gate_prix.display import make_display, present
from gate_prix.input import Input
from gate_prix.match import HOWTO, RACE, TITLE, Match
from gate_prix.render import Renderer, loading_screen
from gate_prix.sprites import font

DT = 1.0 / config.FPS
MAX_STEPS = 3


def run(fullscreen: bool, window_size: str, show_fps: bool, seed: int | None = None,
        selftest: float | None = None, shots: str | None = None) -> int:
    """Play until quit; returns the exit code (a failed self-test is 1)."""
    pygame.init()
    pygame.joystick.init()
    surface, window = make_display(fullscreen, window_size)
    pygame.display.set_caption("GATE PRIX")
    pygame.mouse.set_visible(False)
    loading_screen(surface)
    present(surface, window)
    pygame.display.flip()
    pygame.event.pump()

    renderer = Renderer(surface)  # every sprite and background, drawn once, now
    audio = make_audio() if selftest is None else NullAudio()
    match = Match(random.Random(seed))
    inp = Input()
    script = None
    if selftest is not None:
        from gate_prix.selftest import Script

        script = Script(match, seed if seed is not None else 1, shots)
    clock = pygame.time.Clock()
    fps_img, fps_shown = None, -1
    acc = 0.0
    while True:
        real = DT if script else min(0.1, clock.tick(config.FPS) / 1000.0)
        quit_requested = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_requested = True
            inp.handle(event)
        inp.update(real)
        if quit_requested or inp.quit_combo() or inp.keyboard_quit:
            return 0
        if script is not None:
            if script.done or script.time >= selftest:
                return script.finish()
            frame = script.next()
        else:
            frame = inp.frame
        acc += real
        steps = max(1, min(MAX_STEPS, int(acc / DT + 1e-6)))
        acc = max(-DT, min(DT, acc - steps * DT))
        events: list = []
        for k in range(steps):
            events += match.update(DT, frame if k == 0 else frame.held_only())
        if match.quit_requested:  # QUIT on the title: the same clean exit as Start + Select
            return script.finish() if script is not None else 0
        audio.play_events(events, match.players)
        racing = match.state == RACE and not match.attract and match.race is not None
        audio.nitro({p: match.race.racer(p).car.boost for p in match.players} if racing else {})
        audio.menu_music(match.state in (TITLE, HOWTO))
        renderer.draw(match)
        if show_fps:
            fps = round(clock.get_fps())
            if fps != fps_shown:
                fps_img, fps_shown = font(14).render(f"{fps} FPS", True, (230, 235, 255)), fps
            surface.blit(fps_img, (config.INTERNAL_WIDTH - fps_img.get_width() - 8,
                                   config.INTERNAL_HEIGHT - 22))
        if script is not None:
            script.after_draw(surface)
        present(surface, window)
        pygame.display.flip()
