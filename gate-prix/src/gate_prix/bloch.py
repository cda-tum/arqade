"""The qubit on show: the car's Bloch orb and the result screen's Bloch spheres.

From |0>, a circuit of H, X, Y and Z only ever reaches four states, up to a global phase:
|0> and |1> (the sphere's top and bottom) and |+> and |-> (towards you and away). H swaps
the z and x axes and the Paulis flip signs, so the y axis is never reached (a test checks
it by trying every circuit). `state_of(slots)` simulates a car's circuit exactly
(circuit.run) and names its state; each state has its colour, shared by the orb and the
spheres, and its picture is drawn once per size, so per frame the qubit is a blit.

The picture's projection: z up, y to the right, x towards the viewer (down and to the left,
foreshortened, its tip drawn a little bigger in front and smaller behind).
"""

from __future__ import annotations

from functools import lru_cache

import pygame

from gate_prix import circuit

WHITE = (255, 255, 255)
INK = (8, 8, 20)
# name: (Bloch vector, ket, colour). No player blue or red: every car carries one.
STATES = {
    "+z": ((0, 0, 1), "|0⟩", (200, 240, 255)),
    "-z": ((0, 0, -1), "|1⟩", (255, 200, 70)),
    "+x": ((1, 0, 0), "|+⟩", (90, 230, 140)),
    "-x": ((-1, 0, 0), "|−⟩", (240, 120, 225)),
}
NAMES = tuple(STATES)


def mix(a, b, k):
    return tuple(round(x + (y - x) * k) for x, y in zip(a, b))


def nearest(vector: tuple[float, float, float]) -> str:
    """The state whose axis is nearest to a Bloch vector."""
    return max(NAMES, key=lambda n: sum(a * b for a, b in zip(STATES[n][0], vector)))


@lru_cache(maxsize=512)
def state_of(slots: tuple) -> str:
    """The state a circuit's slots so far put |0> in (None, an empty slot, does nothing)."""
    return nearest(circuit.bloch(circuit.run(list(slots))))


def project(vector, r: float) -> tuple[float, float]:
    """A Bloch vector's tip on the picture, from the centre, for a sphere of radius r."""
    x, y, z = vector
    return r * (0.86 * y - 0.42 * x), r * (-0.86 * z + 0.36 * x)


def draw_arrow(surf, cx: float, cy: float, r: float, name: str, width: float) -> None:
    """The state's arrow from the centre, its tip a bright dot in the state's colour."""
    vector, _, col = STATES[name]
    dx, dy = project(vector, r)
    tip = (cx + dx, cy + dy)
    pygame.draw.line(surf, WHITE, (round(cx), round(cy)), (round(tip[0]), round(tip[1])),
                     max(1, round(width)))
    k = 1.25 if vector[0] > 0 else (0.8 if vector[0] < 0 else 1.0)  # in front, or behind
    pygame.draw.circle(surf, mix(col, WHITE, 0.3), (round(tip[0]), round(tip[1])),
                       max(1, round(1.7 * width * k)))
    pygame.draw.circle(surf, WHITE, (round(tip[0]), round(tip[1])), max(1, round(0.7 * width * k)))


def sphere(name: str, size: int, label_font=None) -> pygame.Surface:
    """A Bloch sphere `size` px across showing a state: glass, its equator, the z axis
    with |0> and |1> at its ends, and the state's arrow. Drawn at 3x, smoothed down."""
    ss = 3
    n = size * ss
    s = pygame.Surface((n, n), pygame.SRCALPHA)
    c = n / 2
    r = n * 0.36
    col = STATES[name][2]
    pygame.draw.circle(s, (20, 26, 48), (round(c), round(c)), round(r))
    glow = pygame.Surface((n, n), pygame.SRCALPHA)
    for k in range(10):
        pygame.draw.circle(glow, (*col, 10), (round(c), round(c)), round(r * (1 - k * 0.07)))
    s.blit(glow, (0, 0))
    eq = pygame.Rect(0, 0, round(2 * r), round(0.72 * r))
    eq.center = (round(c), round(c))
    back = pygame.Surface((n, n), pygame.SRCALPHA)
    pygame.draw.ellipse(back, (150, 170, 220, 90), eq, max(1, ss))
    s.blit(back, (0, 0))
    pygame.draw.line(s, (120, 130, 170), (round(c), round(c - r)), (round(c), round(c + r)),
                     max(1, ss // 2 + 1))
    pygame.draw.line(s, (90, 100, 140), (round(c - r), round(c)), (round(c + r), round(c)), 1)
    pygame.draw.circle(s, mix(col, WHITE, 0.45), (round(c), round(c)), round(r), max(2, ss))
    shine = pygame.Surface((n, n), pygame.SRCALPHA)
    pygame.draw.circle(shine, (255, 255, 255, 36), (round(c - r * 0.42), round(c - r * 0.46)),
                       round(r * 0.2))
    s.blit(shine, (0, 0))
    draw_arrow(s, c, c, r * 0.92, name, 2.0 * ss)
    if label_font is not None:
        for text, y in (("|0⟩", c - r - 0.09 * n), ("|1⟩", c + r + 0.09 * n)):
            img = label_font(round(0.13 * n)).render(text, True, (170, 180, 210))
            s.blit(img, img.get_rect(center=(round(c), round(y))))
    return pygame.transform.smoothscale(s, (size, size))

