"""Quantum Pong app icon: classic Pong, white on black, with a ball splitting in two.

The look is stark 1972 Pong: the game's near-black field, plain chunky
white pixel lettering with no outline, gradient or glow, a dashed midline,
and two white paddles. The title sits at the top, where the score sits in
the game. Below it, a ball off P1's paddle on the left runs into an H gate
on the midline, and two balls leave the gate: one carries on towards P2's
paddle on the right, one turns back towards P1. Motion is shown with faded
copies of the ball. The marquee is the same white lettering between two
paddles.

Only colours the game itself uses: COLOR_BACKGROUND, COLOR_MIDLINE,
COLOR_PADDLE/BALL/TEXT and the H gate's GATE_COLORS entry. The gate and the
balls are drawn by main._draw_gate / main._draw_ball, the paddles the way
run_game draws them, all at native size and upscaled by one shared
nearest-neighbour factor, so they keep their in-game proportions. The two
outgoing directions come from gates.apply_h.
"""

from __future__ import annotations

import math
import sys

import kit
import pygame

sys.path.insert(0, str(kit.ROOT / "quantum-pong/src"))

from quantum_pong import config, fonts  # noqa: E402
from quantum_pong import main as qp  # noqa: E402
from quantum_pong.gates import Gate, apply_h  # noqa: E402
from quantum_pong.pong import Ball  # noqa: E402

ROM = "quantum_pong"

# Only colours the game itself draws with (config.py).
BG = config.COLOR_BACKGROUND
WHITE = config.COLOR_PADDLE
# One pixel scale for every game sprite, so gate, ball and paddles keep
# their in-game proportions (gate 48 px, ball 8 px, paddle 8x40).
K = 5


# --- game sprites, drawn the way the game draws them ---------------------------


def gate_sprite(kind: str, k: int) -> pygame.Surface:
    """One gate exactly as main._draw_gate draws it, upscaled k times."""
    label_surfaces = qp._make_gate_label_surfaces(fonts.load_font(10))
    n = config.GATE_RADIUS * 2 + 2
    surf = pygame.Surface((n, n), pygame.SRCALPHA)
    qp._draw_gate(surf, label_surfaces, Gate(kind=kind, x=n / 2, y=n / 2, spawned_at=0.0))
    return kit.nearest(surf, k)


def ball_sprite(k: int) -> pygame.Surface:
    """The ball as main._draw_ball draws it (white with a dark 1px rim)."""
    n = config.BALL_RADIUS * 2 + 2
    surf = pygame.Surface((n, n), pygame.SRCALPHA)
    qp._draw_ball(surf, Ball(x=n / 2, y=n / 2, vx=0, vy=0))
    return kit.nearest(surf, k)


def paddle_sprite(k: int) -> pygame.Surface:
    """A paddle as run_game draws it: PADDLE_WIDTH x PADDLE_HEIGHT, radius 2."""
    surf = pygame.Surface((config.PADDLE_WIDTH, config.PADDLE_HEIGHT), pygame.SRCALPHA)
    pygame.draw.rect(surf, WHITE, surf.get_rect(), border_radius=2)
    return kit.nearest(surf, k)


def ghost(k: int, alpha: int) -> pygame.Surface:
    """A motion copy of the ball: COLOR_BALL faded to `alpha` (it reads as
    grey on the field), without the rim, so it is no bigger than the ball."""
    n = config.BALL_RADIUS * 2 + 2
    surf = pygame.Surface((n, n), pygame.SRCALPHA)
    pygame.draw.circle(surf, (*config.COLOR_BALL, alpha), (n // 2, n // 2), config.BALL_RADIUS - 1)
    return kit.nearest(surf, k)


# --- the icon -------------------------------------------------------------------


def title(k: int) -> pygame.Surface:
    """QUANTUM over a bigger PONG, in plain white Press Start 2P."""
    top = kit.tint(kit.text_shape("QUANTUM", kit.PIXEL_FONT, 8 * k), config.COLOR_TEXT)
    big = kit.tint(kit.text_shape("PONG", kit.PIXEL_FONT, 16 * k), config.COLOR_TEXT)
    gap = 3 * k
    out = pygame.Surface((max(top.get_width(), big.get_width()), top.get_height() + gap + big.get_height()),
                         pygame.SRCALPHA)
    out.blit(top, ((out.get_width() - top.get_width()) // 2, 0))
    out.blit(big, ((out.get_width() - big.get_width()) // 2, top.get_height() + gap))
    return kit.trim(out)


def art(size: int) -> pygame.Surface:
    s = size / 1024
    k = max(1, round(K * s))
    surf = pygame.Surface((size, size))
    surf.fill(BG)

    # the score area: the title
    kit.blit_center(surf, title(max(1, round(11 * s))), (size / 2, 230 * s))

    # dashed midline below it, in COLOR_MIDLINE
    dash, step = round(32 * s), round(56 * s)
    for y in range(round(430 * s), round(960 * s), step):
        pygame.draw.rect(surf, config.COLOR_MIDLINE, (size // 2 - round(5 * s), y, round(10 * s), dash))

    # paddles framing the field: P1 left, P2 right
    p1 = (130 * s, 590 * s)
    p2 = (size - 130 * s, 790 * s)
    kit.blit_center(surf, paddle_sprite(k), p1)
    kit.blit_center(surf, paddle_sprite(k), p2)

    # one ball, off P1's paddle, into the H gate on the midline
    split = (size / 2, 680 * s)
    start = (p1[0] + (config.PADDLE_WIDTH / 2 + config.BALL_RADIUS) * k, 560 * s)
    vx, vy = split[0] - start[0], split[1] - start[1]
    norm = math.hypot(vx, vy)
    incoming = Ball(x=split[0], y=split[1], vx=vx / norm, vy=vy / norm)
    spacing = 56 * s
    # its faded copies, brightest where it touched the gate's edge
    edge = (config.GATE_RADIUS + config.BALL_RADIUS) * k
    n_in = int((norm - edge) // spacing) + 1
    for j in range(n_in):
        d = edge + j * spacing
        kit.blit_center(surf, ghost(k, round(200 * (1 - j / n_in))),
                        (split[0] - incoming.vx * d, split[1] - incoming.vy * d))

    kit.blit_center(surf, gate_sprite("H", k), split)

    # apply_h: one half carries on towards P2, one turns back towards P1
    far = 330 * s
    for out in apply_h(incoming):
        for i in range(3, 0, -1):
            d = far - i * spacing
            kit.blit_center(surf, ghost(k, round(200 * (1 - i / 4))),
                            (split[0] + out.vx * d, split[1] + out.vy * d))
        kit.blit_center(surf, ball_sprite(k), (split[0] + out.vx * far, split[1] + out.vy * far))
    return surf


def marquee() -> pygame.Surface:
    """QUANTUM PONG on one line in plain white, between two paddles."""
    line = kit.tint(kit.text_shape("QUANTUM PONG", kit.PIXEL_FONT, 96), config.COLOR_TEXT)
    paddle = paddle_sprite(3)
    gap = 48
    out = pygame.Surface((line.get_width() + 2 * (paddle.get_width() + gap), paddle.get_height()),
                         pygame.SRCALPHA)
    out.blit(paddle, (0, 0))
    out.blit(paddle, (out.get_width() - paddle.get_width(), 0))
    kit.blit_center(out, line, (out.get_width() / 2, out.get_height() / 2))
    return kit.trim(out)
