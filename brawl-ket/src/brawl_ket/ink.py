"""The drawing primitives every fighter is built from: chunky capsules, balls and blocks with
a 2 px ink outline, and a body's own frame. Shared by render.py, erwin.py and dos.py
(render.py re-exports the ones it had)."""

from __future__ import annotations

import math

import pygame

from . import palette as P


def _pt(p) -> tuple[int, int]:
    return (round(p[0]), round(p[1]))


def limb(surf: pygame.Surface, a, b, w: int, color, ink=P.INK) -> None:
    """A capsule from a to b, w px thick, with a 2 px ink outline."""
    a, b = _pt(a), _pt(b)
    for c, ww in ((ink, w + 4), (color, w)):
        pygame.draw.line(surf, c, a, b, ww)
        pygame.draw.circle(surf, c, a, ww // 2)
        pygame.draw.circle(surf, c, b, ww // 2)


def _ball(surf: pygame.Surface, p, r: int, color) -> None:
    p = _pt(p)
    pygame.draw.circle(surf, P.INK, p, r + 2)
    pygame.draw.circle(surf, color, p, r)


def _block(surf: pygame.Surface, p, half: int, color, radius: int = 3) -> None:
    """A square (a gauntlet), `half` px from its centre to each side, with a 2 px ink outline."""
    rect = pygame.Rect(0, 0, 2 * half, 2 * half)
    rect.center = _pt(p)
    pygame.draw.rect(surf, P.INK, rect.inflate(4, 4), border_radius=radius + 2)
    pygame.draw.rect(surf, color, rect, border_radius=radius)
    surf.fill(P.lighten(color, 0.5), (rect.x + 2, rect.y + 2, max(2, half - 2), 2))


def _boot(surf: pygame.Surface, foot, facing: int, w: int, color) -> None:
    """A heavy boot: a block on the foot, its toe pointing the way the fighter faces."""
    rect = pygame.Rect(0, 0, w + 10, w - 2)
    rect.midbottom = _pt((foot[0] + 3 * facing, foot[1] + w // 2 + 1))
    pygame.draw.rect(surf, P.INK, rect.inflate(4, 4), border_radius=4)
    pygame.draw.rect(surf, color, rect, border_radius=3)


def _towards(a, b, k: float) -> tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)


def _poly(surf: pygame.Surface, pts, color, ink: int = 2) -> None:
    pts = [_pt(p) for p in pts]
    pygame.draw.polygon(surf, color, pts)
    pygame.draw.polygon(surf, P.INK, pts, ink)


def frame(j, facing):
    """at(base, up, front): a point `up` px along the spine and `front` px towards the face."""
    hip, neck = j["hip"], j["neck"]
    tx, ty = neck[0] - hip[0], neck[1] - hip[1]
    n = math.hypot(tx, ty) or 1.0
    ux, uy = tx / n, ty / n
    fx, fy = -uy * facing, ux * facing

    def at(base, up, front):
        return (base[0] + ux * up + fx * front, base[1] + uy * up + fy * front)
    return at


def poly(surf, pts, color, ink=2):
    """A filled polygon, with an `ink` px outline (0: none)."""
    pts = [_pt(p) for p in pts]
    pygame.draw.polygon(surf, color, pts)
    if ink:
        pygame.draw.polygon(surf, P.INK, pts, ink)
