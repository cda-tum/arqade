"""Diagnostic mode: live joystick and keyboard state, for finding the real button and axis
numbers on the cabinet. Run with --input-test. Leave with Esc, or Start + Select on one pad.

Not unit tested beyond starting and leaving (it needs real devices): it is itself the test
tool. It lists every joystick, also the ones the game skips (see input.is_pad).
"""

from __future__ import annotations

import pygame
from arqade_common.input import ENCODER

from gate_prix import config
from gate_prix.display import present
from gate_prix.input import is_pad
from gate_prix.sprites import font


def _joystick_lines(joy) -> list[str]:
    try:
        lines = [f"[{joy.get_instance_id()}] {joy.get_name()}"
                 + ("" if is_pad(joy) else "   (skipped: not a pad)")]
        axes = [f"{joy.get_axis(i):+.2f}" for i in range(joy.get_numaxes())]
        lines.append("axes: " + (" ".join(axes) if axes else "(none)"))
        down = [str(i) for i in range(joy.get_numbuttons()) if joy.get_button(i)]
        lines.append("buttons down: " + (", ".join(down) if down else "(none)"))
        hats = [str(joy.get_hat(i)) for i in range(joy.get_numhats())]
        if hats:
            lines.append("hats: " + " ".join(hats))
    except pygame.error as e:
        lines = [f"(error reading a joystick: {e})"]
    return lines


def run_input_test(surface: pygame.Surface, window: pygame.Surface | None) -> None:
    clock = pygame.time.Clock()
    face = font(16)
    combo = (ENCODER.buttons["start"], ENCODER.buttons["select"])
    joysticks = []

    def rescan():
        joysticks.clear()
        for i in range(pygame.joystick.get_count()):
            joy = pygame.joystick.Joystick(i)
            joy.init()
            joysticks.append(joy)

    rescan()
    while True:
        clock.tick(config.FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return
            if event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                rescan()
        for joy in joysticks:
            try:
                if joy.get_numbuttons() > max(combo) and all(joy.get_button(b) for b in combo):
                    return
            except pygame.error:
                pass
        keys = pygame.key.get_pressed()
        surface.fill((10, 14, 34))
        lines = [f"INPUT TEST - {len(joysticks)} joystick(s) - Esc or Start+Select to leave", ""]
        if not joysticks:
            lines.append("No joysticks detected.")
        for joy in joysticks:
            lines += _joystick_lines(joy) + [""]
        pressed = [pygame.key.name(k) for k in range(len(keys)) if keys[k]]
        lines.append("keys down: " + (", ".join(pressed) if pressed else "(none)"))
        lines += ["", "Cabinet: A = 1, B = 2, Select = 8, Start = 9; axis 0 steers, "
                      "axis 1 pulled back (+) brakes"]
        y = 16
        for i, line in enumerate(lines):
            colour = (255, 230, 120) if i == 0 else (230, 235, 255)
            surface.blit(face.render(line, True, colour), (16, y))
            y += 22
        present(surface, window)
        pygame.display.flip()
