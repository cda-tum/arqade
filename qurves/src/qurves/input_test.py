"""Diagnostic mode: live joystick and keyboard state, for finding the real
button and axis numbers on the cabinet. Run with --input-test. Leave with
Esc, or Start + Select on one pad.

Not unit tested (it needs real devices); it is itself the test tool.
"""

from __future__ import annotations

import pygame

from qurves import config
from qurves.display import present
from qurves.fonts import load_font


def _joystick_lines(joy) -> list[str]:
    lines = [f"[{joy.get_instance_id()}] {joy.get_name()}"]
    axes = [f"{joy.get_axis(i):+.2f}" for i in range(joy.get_numaxes())]
    lines.append("axes: " + (" ".join(axes) if axes else "(none)"))
    down = [str(i) for i in range(joy.get_numbuttons()) if joy.get_button(i)]
    lines.append("buttons down: " + (", ".join(down) if down else "(none)"))
    hats = [str(joy.get_hat(i)) for i in range(joy.get_numhats())]
    if hats:
        lines.append("hats: " + " ".join(hats))
    return lines


def run_input_test(surface: pygame.Surface, window: pygame.Surface | None) -> None:
    clock = pygame.time.Clock()
    font = load_font(16)
    system = config.INPUT_CONFIG["system"]
    joysticks = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
    for joy in joysticks:
        joy.init()

    while True:
        clock.tick(config.FPS)
        if any(event.type == pygame.QUIT for event in pygame.event.get()):
            return
        keys = pygame.key.get_pressed()
        if keys[pygame.K_ESCAPE]:
            return
        combo = (system["start_button"], system["select_button"])
        for joy in joysticks:
            if joy.get_numbuttons() > max(combo) and all(joy.get_button(b) for b in combo):
                return

        surface.fill(config.COLOR_BACKGROUND)
        y = 12
        lines = [f"INPUT TEST - {len(joysticks)} joystick(s) - Esc or Start+Select to leave", ""]
        if not joysticks:
            lines.append("No joysticks detected.")
        for joy in joysticks:
            lines += _joystick_lines(joy) + [""]
        pressed = [pygame.key.name(k) for k in range(len(keys)) if keys[k]]
        lines.append("keys down: " + (", ".join(pressed) if pressed else "(none)"))
        for i, line in enumerate(lines):
            color = config.COLOR_FPS if i == 0 else config.COLOR_TEXT
            surface.blit(font.render(line, False, color), (12, y))
            y += 24
        present(surface, window)
        pygame.display.flip()
