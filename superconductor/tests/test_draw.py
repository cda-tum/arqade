import math

import pygame

from superconductor.game import dashed_path


def test_dashed_path_terminates_on_curves():
    # A bowed polyline like the Bell link once looped forever on float residue.
    surf = pygame.Surface((200, 200))
    pts = [(10 + 180 * f, 100 + 60 * math.sin(math.pi * f)) for f in (i / 20 for i in range(21))]
    for phase in (0.0, 0.1, 7.3, 1234.567):
        dashed_path(surf, (255, 255, 255), pts, 2, 6, 10, phase)
    assert any(surf.get_at((x, y))[0] for x in range(200) for y in range(200))


def test_dashed_path_ignores_degenerate_input():
    surf = pygame.Surface((10, 10))
    dashed_path(surf, (255, 255, 255), [(5, 5), (5, 5)], 2)
    dashed_path(surf, (255, 255, 255), [(5, 5)], 2)
