"""The main loop: input -> match -> sound and picture, on a fixed 60 Hz clock.

The match always steps by exactly 1/60 s. When a frame took longer (the Pi falling behind)
it steps up to MAX_STEPS times to catch up, the presses going to the first step only, so
the game keeps its speed instead of slowing down; it never steps less than once a frame.

Start + Select on one pad (or one player's keys) quits, as do QUIT on the title and
closing the window. The combo is armed (see input.py), so nothing held at launch can quit
the game at once. In the browser there is nothing to quit to: the game tells the page
(`arqade:quit`) and goes back to its title instead.

The loop is async: every frame ends with `await asyncio.sleep(0)`, which hands the frame to
the browser (pygbag) and does nothing elsewhere.
"""

from __future__ import annotations

import asyncio
import random

import pygame
from arqade_common import runtime, web
from arqade_common.input import PadLayout

from gate_prix import config
from gate_prix.audio import NullAudio, make_audio
from gate_prix.display import make_display, present
from gate_prix.input import Input
from gate_prix.match import COUNTDOWN, HOWTO, PAUSED, RACE, TITLE, Match
from gate_prix.render import Renderer, loading_screen
from gate_prix.sprites import SpriteCache, font

DT = 1.0 / config.FPS
MAX_STEPS = 3
# Same as the folder name in the web build and the "id" in game.json.
GAME_ID = "gate-prix"
# While a match is on, for the page's game-start / game-end events: the countdown, the
# race and its pause. The title (and its attract race), HOW TO PLAY and the result are not.
PLAYING = (COUNTDOWN, RACE, PAUSED)


async def _build_sprites(surface: pygame.Surface, window: pygame.Surface | None) -> None:
    """Draw every sprite once, behind the loading screen. In the browser this is a few
    seconds of work, so the frame is handed back between the sprite kinds (the page stays
    responsive) and the loading screen shows how far it got."""
    for done in SpriteCache.building():
        if runtime.is_browser():
            loading_screen(surface, done)
            present(surface, window)
            pygame.display.flip()
            await asyncio.sleep(0)


async def run(fullscreen: bool, window_size: str, show_fps: bool, seed: int | None = None,
              selftest: float | None = None, shots: str | None = None,
              pad_layout: PadLayout | None = None) -> int:
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
    await asyncio.sleep(0)  # show it (in the browser, nothing is shown until the frame is handed back)

    await _build_sprites(surface, window)
    inp = Input(pad_layout)
    renderer = Renderer(surface, inp.devices)  # every other piece, drawn once, now
    audio = make_audio() if selftest is None else NullAudio()
    match = Match(random.Random(seed))
    script = None
    if selftest is not None:
        from gate_prix.selftest import Script

        script = Script(match, seed if seed is not None else 1, shots)
    clock = pygame.time.Clock()
    fps_img, fps_shown = None, -1
    acc = 0.0
    playing = False  # a match is on (for the page's game-start / game-end events)

    def leave() -> bool:
        """A player asked to quit: True ends the program. In the browser the game tells the
        page instead (which may take the player back to its game list) and goes back to its
        title, which waits for the buttons to be let go."""
        nonlocal playing
        if script is not None or not runtime.is_browser():
            return True
        if playing:  # the match ends before the player leaves
            playing = False
            web.post_event(web.GAME_END, GAME_ID)
        web.post_event(web.QUIT, GAME_ID)
        match.back_to_title()
        return False

    while True:
        real = DT if script else min(0.1, runtime.frame_seconds(clock.tick(config.FPS) / 1000.0))
        quit_requested = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_requested = True
            inp.handle(event)
        inp.update(real)
        if (quit_requested or inp.quit_combo()) and leave():
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
        if match.quit_requested and leave():  # QUIT on the title: the same as Start + Select
            return script.finish() if script is not None else 0
        if (match.state in PLAYING) != playing:
            playing = not playing
            web.post_event(web.GAME_START if playing else web.GAME_END, GAME_ID)
        audio.update()
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
        await asyncio.sleep(0)  # hand the frame to the browser (pygbag); no-op elsewhere
