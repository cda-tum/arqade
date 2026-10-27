"""Scene machine and main loop.

Title -> Join -> LevelSelect -> HowToPlay -> Round -> Results -> LevelSelect, plus the input test
(F1 on the title). Start + Select on one pad quits from anywhere; holding
Select on the title quits too. Any screen left idle for IDLE_TIMEOUT falls
back to the title, so the cabinet resets itself for the next visitors.
"""

from __future__ import annotations

import asyncio

import pygame
from arqade_common import runtime, web
from arqade_common.input import PadLayout

from overquqed import config, hiscores, palette
from overquqed.display import make_display, present
from overquqed.fonts import text
from overquqed.input import Input


# Same as the folder name in the web build and the "id" in game.json.
GAME_ID = "overquqed"


class Scene:
    """One screen. `update` may call `app.switch(...)` to move on."""

    idle_resets = True  # fall back to the title after IDLE_TIMEOUT

    def __init__(self, app: "App") -> None:
        self.app = app

    def update(self, dt: float, inp: Input) -> None:
        pass

    def draw(self, surf: pygame.Surface) -> None:
        pass

    def on_idle(self) -> None:
        """Called just before an idle timeout sends the cabinet to the title."""


def _is_title(scene: Scene) -> bool:
    return type(scene).__name__ == "TitleScene"


class App:
    def __init__(self, surface: pygame.Surface, window: pygame.Surface | None, show_fps: bool,
                 pad_layout: PadLayout | None = None) -> None:
        self.surface = surface
        self.window = window
        self.show_fps = show_fps
        self.clock = pygame.time.Clock()
        self.pad_layout = pad_layout
        self.inp = Input(pad_layout)
        self.playing = False  # a round is on (for the page's game-start / game-end events)
        self.running = True
        self.idle = 0.0
        self.session: dict = {}  # per-power-on memory, e.g. "played_tutorial"
        self.hiscores = hiscores.load(config.HISCORE_FILE)
        self.audio = None
        self.scene: Scene = Scene(self)
        self.to_title()

    def switch(self, scene: Scene) -> None:
        self.scene = scene

    def to_title(self) -> None:
        from overquqed.scenes import TitleScene

        self.switch(TitleScene(self))

    # --- audio hooks (no-ops until audio.py is wired in) ---
    def sfx(self, name: str) -> None:
        if self.audio is not None:
            self.audio.play(name)

    def music(self, name: str) -> None:
        if self.audio is not None:
            self.audio.music(name)

    def music_tempo(self, fast: bool) -> None:
        if self.audio is not None:
            self.audio.tempo(fast)

    def input_test(self) -> None:
        from overquqed.input_test import run_input_test

        run_input_test(self.surface, self.window)
        self.inp = Input(self.pad_layout)
        self.to_title()

    def step(self, dt: float, events: list[pygame.event.Event]) -> None:
        """One frame of logic (no drawing), split out so tests can drive it."""
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F3:
                self.show_fps = not self.show_fps
            elif (event.type == pygame.KEYDOWN and event.key == pygame.K_F1 and _is_title(self.scene)
                  and not runtime.is_browser()):  # its loop doesn't hand frames to the browser
                self.input_test()
                return
            self.inp.handle(event)
        self.inp.update(dt)
        if self.audio is not None:
            self.audio.update()
        if self.inp.quit_combo():
            self.running = False
            return
        self.idle = 0.0 if self.inp.activity else self.idle + dt
        if self.idle >= config.IDLE_TIMEOUT and self.scene.idle_resets:
            self.idle = 0.0
            self.scene.on_idle()
            self.to_title()
            return
        self.scene.update(dt, self.inp)

    def draw(self) -> None:
        self.scene.draw(self.surface)
        if self.show_fps:
            self.surface.blit(text(f"{self.clock.get_fps():.0f}", 8, palette.GOLD, shadow=palette.INK), (2, 2))
        present(self.surface, self.window)
        pygame.display.flip()

    def _note_playing(self) -> None:
        now = type(self.scene).__name__ == "RoundScene" and self.running
        if now != self.playing:
            self.playing = now
            web.post_event(web.GAME_START if now else web.GAME_END, GAME_ID)

    async def _leave(self) -> bool:
        """A player asked to quit: True ends the program. In the browser there
        is nothing to hand back to, so instead the game tells the page (which
        may take the player back to its game list) and returns to its title --
        once the quit buttons are let go, or the title would quit again at once."""
        if not runtime.is_browser():
            return True
        web.post_event(web.QUIT, GAME_ID)
        while self.inp.quit_combo() or self.inp.select_held_time > 0:
            for event in pygame.event.get():
                self.inp.handle(event)
            self.inp.update(0.0)
            present(self.surface, self.window)
            pygame.display.flip()
            await asyncio.sleep(0)
        self.running = True
        self.to_title()
        return False

    async def run(self) -> None:
        while True:
            dt = min(self.clock.tick(config.FPS) / 1000.0, 1 / 20)
            self.step(dt, pygame.event.get())
            self._note_playing()
            if not self.running:  # QUIT, Start + Select, or the window closed
                if await self._leave():
                    break
                continue
            self.draw()
            await asyncio.sleep(0)  # hand the frame to the browser (pygbag); no-op elsewhere


async def run(*, fullscreen: bool, window_size: str, show_fps: bool, pad_layout: PadLayout | None = None) -> None:
    from overquqed.audio import SAMPLE_RATE, make_audio

    pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, 512)
    pygame.init()
    pygame.joystick.init()
    surface, window = make_display(fullscreen, window_size)
    pygame.display.set_caption("Overquqed")
    pygame.mouse.set_visible(not fullscreen)
    app = App(surface, window, show_fps, pad_layout)
    app.audio = make_audio()
    app.to_title()  # restart the title so its music request reaches the audio
    await app.run()
