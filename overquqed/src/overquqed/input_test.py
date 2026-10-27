"""Diagnostic mode: shows live joystick/keyboard state to find real button indices.

Run with `--input-test` (or F1 on the title screen). Not unit tested (needs a
real display/input); this is the tool for discovering the cabinet's actual
button/axis mapping. Besides the raw state it shows which logical actions
each player's pad currently resolves to -- that's the quickest way to check
the still-unconfirmed Start/Select indices in config.INPUT_CONFIG.

Leave with Esc, or by holding Select for 2 s.
"""

from __future__ import annotations

import pygame

from overquqed import config, palette
from overquqed.display import present
from overquqed.fonts import text
from overquqed.input import PLAYERS, Input


def _joystick_lines(joy: pygame.joystick.JoystickType) -> list[str]:
    lines = [f"[{joy.get_id()}] {joy.get_name()[:52]}"]
    axes = [f"{joy.get_axis(i):+.2f}" for i in range(joy.get_numaxes())]
    lines.append("axes: " + (" ".join(axes) if axes else "(none)"))
    pressed = [str(i) for i in range(joy.get_numbuttons()) if joy.get_button(i)]
    lines.append("buttons down: " + (", ".join(pressed) if pressed else "(none)"))
    hats = [str(joy.get_hat(i)) for i in range(joy.get_numhats())]
    lines.append("hats: " + (" ".join(hats) if hats else "(none)"))
    return lines


def draw_input_test(surface: pygame.Surface, inp: Input) -> None:
    surface.fill(palette.BG)
    y = 8
    surface.blit(text(f"INPUT TEST  {len(inp.joysticks)} joystick(s)", 8, palette.GOLD), (8, y))
    y += 12
    surface.blit(text("Esc or hold SELECT 2s to leave", 8, palette.TEXT_DIM), (8, y))
    y += 18
    if not inp.joysticks:
        surface.blit(text("No joysticks -- keyboard only.", 8, palette.TEXT), (8, y))
        y += 14
    for joy in inp.joysticks[:4]:
        for line in _joystick_lines(joy):
            surface.blit(text(line, 8, palette.TEXT), (8, y))
            y += 11
        y += 6

    y = max(y, 200)
    for p, color in zip(PLAYERS, palette.PLAYER_COLORS):
        acts = " ".join(sorted(inp.held[p])) or "-"
        surface.blit(text(f"{p.upper()} actions: {acts}"[:58], 8, color), (8, y))
        y += 12
    y += 4
    buttons = inp.pad_layout.buttons
    surface.blit(
        text(f"{inp.pad_layout.name}: start={buttons['start']} select={buttons['select']}", 8, palette.TEXT_DIM),
        (8, y),
    )

    keys = pygame.key.get_pressed()
    names = [pygame.key.name(k) for k in range(len(keys)) if keys[k]]
    line = "keys down: " + (", ".join(names) if names else "(none)")
    surface.blit(text(line[:58], 8, palette.TEXT), (8, config.INTERNAL_HEIGHT - 16))


def run_input_test(surface: pygame.Surface, window: pygame.Surface | None) -> None:
    clock = pygame.time.Clock()
    inp = Input()
    while True:
        dt = clock.tick(config.FPS) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            inp.handle(event)
        inp.update(dt)
        # Esc works even with --no-keyboard: this is a diagnostic screen.
        if pygame.key.get_pressed()[pygame.K_ESCAPE] or inp.select_held_time >= config.BACK_HOLD_TO_QUIT:
            return
        draw_input_test(surface, inp)
        present(surface, window)
        pygame.display.flip()
