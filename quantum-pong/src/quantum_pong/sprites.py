"""Drawing the field's pieces: paddles, balls, gates (live and announced) and
the catch/score flash. Shared by the match (main.py) and the HOW TO PLAY demo
(tutorial.py), so the demo is drawn with exactly the game's own sprites.

pygame-drawing glue, not unit tested (same convention as screens.py).
"""

from __future__ import annotations

import itertools

import pygame

from quantum_pong import config
from quantum_pong.gates import Gate
from quantum_pong.pong import Ball, Paddle

# The announced gate's dashed outline: dash and gap length in px, and how fast
# the dashes march round it (px/sec) -- a moving outline is hard to miss.
DASH = 6
DASH_GAP = 4
DASH_SPEED = 24.0


def draw_paddle(surface: pygame.Surface, x: float, paddle: Paddle) -> None:
    pygame.draw.rect(
        surface, config.COLOR_PADDLE, (x, paddle.y, config.PADDLE_WIDTH, paddle.height),
        border_radius=2,
    )


def draw_ball(surface: pygame.Surface, ball: Ball) -> None:
    pos = (round(ball.x), round(ball.y))
    pygame.draw.circle(surface, config.COLOR_BALL, pos, config.BALL_RADIUS)
    pygame.draw.circle(surface, config.COLOR_BACKGROUND, pos, config.BALL_RADIUS, 1)


def make_gate_label_surfaces(font: pygame.font.Font) -> dict[str, pygame.Surface]:
    """Pre-render each gate letter once -- there are only 4 possible labels,
    no need to re-rasterize text every frame for every gate on screen."""
    return {kind: font.render(kind, False, config.COLOR_BACKGROUND) for kind in config.GATE_COLORS}


def make_gate_warning_labels(font: pygame.font.Font) -> dict[str, pygame.Surface]:
    """The same letters in white, for the announced (not yet solid) gate."""
    return {kind: font.render(kind, False, config.COLOR_TEXT) for kind in config.GATE_COLORS}


def _gate_rect(gate: Gate) -> pygame.Rect:
    size = config.GATE_RADIUS * 2
    rect = pygame.Rect(0, 0, size, size)
    rect.center = (round(gate.x), round(gate.y))
    return rect


def draw_gate(
    surface: pygame.Surface,
    label_surfaces: dict[str, pygame.Surface],
    gate: Gate,
) -> None:
    color = config.GATE_COLORS[gate.kind]
    rect = _gate_rect(gate)

    pygame.draw.rect(surface, color, rect, border_radius=6)
    pygame.draw.rect(surface, config.COLOR_TEXT, rect, width=2, border_radius=6)

    label = label_surfaces[gate.kind]
    surface.blit(label, label.get_rect(center=rect.center))


def _perimeter_point(rect: pygame.Rect, d: float) -> tuple[float, float]:
    """The point `d` px clockwise round `rect`'s outline from its top-left."""
    w, h = rect.width - 1, rect.height - 1
    d %= 2 * (w + h)
    if d < w:
        return rect.left + d, rect.top
    d -= w
    if d < h:
        return rect.left + w, rect.top + d
    d -= h
    if d < w:
        return rect.left + w - d, rect.top + h
    return rect.left, rect.top + h - (d - w)


def draw_gate_warning(
    surface: pygame.Surface,
    label_surfaces: dict[str, pygame.Surface],
    gate: Gate,
    t: float,
) -> None:
    """An announced gate: a white dashed outline, marching round, with the
    white letter inside, exactly where the solid gate will appear."""
    rect = _gate_rect(gate)
    pygame.draw.rect(surface, config.COLOR_BACKGROUND, rect)  # hides the midline, like a real gate
    w, h = rect.width - 1, rect.height - 1
    corners = (w, w + h, 2 * w + h)  # perimeter distances of the turns
    perimeter = 2 * (w + h)
    period = DASH + DASH_GAP
    start = (t * DASH_SPEED) % period - period
    while start < perimeter:
        a, b = max(0.0, start), min(perimeter, start + DASH)
        if b > a:
            # Split the dash at any corner it wraps round, so it bends with the outline.
            stops = [a, *(c for c in corners if a < c < b), b]
            for p, q in itertools.pairwise(stops):
                pygame.draw.line(
                    surface, config.COLOR_TEXT,
                    _perimeter_point(rect, p), _perimeter_point(rect, q), 2,
                )
        start += period

    label = label_surfaces[gate.kind]
    surface.blit(label, label.get_rect(center=rect.center))


def draw_flash(surface: pygame.Surface, flash: tuple[float, float, float], game_time: float) -> None:
    """Draw a brief expanding ring at a paddle catch/score point. Caller is
    responsible for dropping flashes older than FLASH_DURATION."""
    x, y, started_at = flash
    age = game_time - started_at
    t = min(1.0, age / config.FLASH_DURATION)
    radius = config.BALL_RADIUS + round(t * config.FLASH_MAX_GROWTH)
    pygame.draw.circle(surface, config.COLOR_FLASH, (round(x), round(y)), radius, 2)
