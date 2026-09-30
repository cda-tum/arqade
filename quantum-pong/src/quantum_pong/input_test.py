"""Diagnostic mode: shows live joystick/keyboard state to find real button indices.

Run with `--input-test`. Not unit tested (needs real display/input); this is the
tool itself used for discovering the cabinet's actual button/axis mapping.
"""

from __future__ import annotations

import pygame

from quantum_pong import config
from quantum_pong.display import present
from quantum_pong.input import keyboard_quit_held


def _joystick_lines(font: pygame.font.Font, joy: pygame.joystick.JoystickType) -> list[pygame.Surface]:
    lines = [f"[{joy.get_id()}] {joy.get_name()}"]

    axes = [f"{joy.get_axis(i):+.2f}" for i in range(joy.get_numaxes())]
    lines.append("axes: " + (" ".join(axes) if axes else "(none)"))

    pressed = [str(i) for i in range(joy.get_numbuttons()) if joy.get_button(i)]
    lines.append("buttons down: " + (", ".join(pressed) if pressed else "(none)"))

    hats = [str(joy.get_hat(i)) for i in range(joy.get_numhats())]
    if hats:
        lines.append("hats: " + " ".join(hats))

    return [font.render(line, True, config.COLOR_TEXT) for line in lines]


def run_input_test(surface: pygame.Surface, window: pygame.Surface | None) -> None:
    internal = surface
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 16)

    joysticks = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
    for joy in joysticks:
        joy.init()

    running = True
    while running:
        clock.tick(config.FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        keys = pygame.key.get_pressed()
        if keyboard_quit_held(keys):
            running = False

        internal.fill(config.COLOR_BACKGROUND)
        y = 8
        header = font.render(
            f"INPUT TEST -- {len(joysticks)} joystick(s) found -- Esc to quit",
            True, config.COLOR_FPS,
        )
        internal.blit(header, (8, y))
        y += 18

        if not joysticks:
            msg = font.render("No joysticks detected -- keyboard fallback only.", True, config.COLOR_TEXT)
            internal.blit(msg, (8, y))
            y += 14

        for joy in joysticks:
            for line_surf in _joystick_lines(font, joy):
                internal.blit(line_surf, (8, y))
                y += 13
            y += 6

        pressed_keys = [pygame.key.name(k) for k in range(len(keys)) if keys[k]]
        key_line = "keys down: " + (", ".join(pressed_keys) if pressed_keys else "(none)")
        key_surf = font.render(key_line, True, config.COLOR_TEXT)
        internal.blit(key_surf, (8, config.INTERNAL_HEIGHT - 16))

        present(internal, window)
        pygame.display.flip()
