"""Scene machine and main loop.

Title -> Join -> LevelSelect -> Round -> Results -> Title, plus the input test
(F1 on the title). Start + Select on one pad quits from anywhere; holding
Select on the title quits too. Any screen left idle for IDLE_TIMEOUT falls
back to the title, so the cabinet resets itself for the next visitors.
"""

from __future__ import annotations

import pygame

from overquqed import config, palette
from overquqed.display import make_display, present
from overquqed.fonts import text
from overquqed.input import Input


class Scene:
    """One screen. `update` may call `app.switch(...)` to move on."""

    idle_resets = True  # fall back to the title after IDLE_TIMEOUT

    def __init__(self, app: "App") -> None:
        self.app = app

    def update(self, dt: float, inp: Input) -> None:
        pass

    def draw(self, surf: pygame.Surface) -> None:
        pass


class TitleScene(Scene):
    idle_resets = False

    def __init__(self, app: "App") -> None:
        super().__init__(app)
        self.t = 0.0

    def update(self, dt: float, inp: Input) -> None:
        self.t += dt
        if inp.select_held_time >= config.BACK_HOLD_TO_QUIT:
            self.app.running = False

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(palette.BG)
        logo = text("OVERQUQED", 32, palette.GOLD, shadow=palette.INK)
        surf.blit(logo, ((config.INTERNAL_WIDTH - logo.get_width()) // 2, 110))
        if int(self.t * 2) % 2 == 0:
            prompt = text("PRESS START", 8, palette.TEXT)
            surf.blit(prompt, ((config.INTERNAL_WIDTH - prompt.get_width()) // 2, 240))


class App:
    def __init__(self, surface: pygame.Surface, window: pygame.Surface | None, show_fps: bool) -> None:
        self.surface = surface
        self.window = window
        self.show_fps = show_fps
        self.clock = pygame.time.Clock()
        self.inp = Input()
        self.running = True
        self.idle = 0.0
        self.scene: Scene = TitleScene(self)

    def switch(self, scene: Scene) -> None:
        self.scene = scene

    def to_title(self) -> None:
        self.switch(TitleScene(self))

    def input_test(self) -> None:
        from overquqed.input_test import run_input_test

        run_input_test(self.surface, self.window)
        self.inp = Input()
        self.to_title()

    def step(self, dt: float, events: list[pygame.event.Event]) -> None:
        """One frame of logic (no drawing), split out so tests can drive it."""
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F3:
                self.show_fps = not self.show_fps
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F1 and isinstance(self.scene, TitleScene):
                self.input_test()
                return
            self.inp.handle(event)
        self.inp.update(dt)
        if self.inp.quit_combo() or (self.inp.keyboard_quit and isinstance(self.scene, TitleScene)):
            self.running = False
            return
        self.idle = 0.0 if self.inp.activity else self.idle + dt
        if self.idle >= config.IDLE_TIMEOUT and self.scene.idle_resets:
            self.idle = 0.0
            self.to_title()
            return
        self.scene.update(dt, self.inp)

    def draw(self) -> None:
        self.scene.draw(self.surface)
        if self.show_fps:
            self.surface.blit(text(f"{self.clock.get_fps():.0f}", 8, palette.GOLD, shadow=palette.INK), (2, 2))
        present(self.surface, self.window)
        pygame.display.flip()

    def run(self) -> None:
        while self.running:
            dt = min(self.clock.tick(config.FPS) / 1000.0, 1 / 20)
            self.step(dt, pygame.event.get())
            if self.running:
                self.draw()


def run(*, fullscreen: bool, window_size: str, show_fps: bool) -> None:
    pygame.init()
    pygame.joystick.init()
    surface, window = make_display(fullscreen, window_size)
    pygame.display.set_caption("Overquqed")
    pygame.mouse.set_visible(not fullscreen)
    App(surface, window, show_fps).run()
