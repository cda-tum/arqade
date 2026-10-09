"""Build the QUANTUMSPACE decal for the office stage, as pixel art.

    cd brawl-ket && uv run python tools/make_decal.py

The shapes are the MQT logo's (logo-mqt-light.svg): its Q (the ring, the inner stroke and
tail, the blue orbit) and its UANTUM, whose paths are copied here. SPACE is set in the same
geometric style (the same cap height and 10-unit strokes; its A is the logo's own A, in
blue). The layout is the wall's, measured on a photo of it (October 2026): the wall spaces
the letters wider than the logo does and sets the Q a little bigger, so every letter is
centred where it is on the wall, and the Q is scaled and placed onto the wall's ring. The
TUM logo is drawn from its blocks as they are on the wall.

Layout units are the SVG's (the cap height is 53.5), with the first U's centre at x = 0
and the top of the capitals at y = 0; the photo's 72 px capitals give 0.74 units per px.
Everything is rendered SUPER times too big, and every game pixel takes the ink that covers
most of it, so the art stays crisp and flat-coloured. Saved as
src/brawl_ket/assets/quantum_space.png.
"""

from __future__ import annotations

import io
from pathlib import Path

import pygame

SCALE = 0.5385                              # game px per unit (capitals 29 px tall)
SUPER = 4                                   # rendered this many times bigger, then reduced
COVER = 0.45                                # how much of a game pixel must be ink
CHAR, BLUE = "#383840", "#3060b0"
CHARCOAL = (56, 56, 64)
TUM_BLUE = (48, 96, 176)
OUT = Path(__file__).parent.parent / "src" / "brawl_ket" / "assets" / "quantum_space.png"

# from the MQT logo: the Q's ring, its inner stroke and tail, the orbit's two bands
RING = "M150.45 126.92c-.88-.33-1.72-.7-2.53-1.1-13.39 20.57-36.57 34.22-62.9 34.22-41.37 0-75.02-33.66-75.02-75.02S43.66 10 85.02 10c32.27 0 59.82 20.5 70.38 49.15h10.58C155 24.89 122.88 0 85.02 0 38.14 0 0 38.14 0 85.02s38.14 85.02 85.02 85.02c30.87 0 57.94-16.54 72.84-41.21-.31-.06-.61-.14-.91-.21-2.29-.36-4.46-.92-6.5-1.7"
INNER = "M185.96 152.37c-2.09.26-4.22.45-6.33.57-25.2 1.45-49.46-7.01-68.3-23.81S81.31 89.2 79.87 63.99c-1.08-18.91 3.44-37.47 13.09-53.68l-8.59-5.12C73.7 23.12 68.69 43.64 69.89 64.55c1.6 27.87 13.95 53.45 34.79 72.03 19.31 17.22 43.76 26.51 69.42 26.51 2.03 0 4.07-.06 6.11-.18 1.92-.11 3.84-.29 5.75-.5z"
ORBIT = "M132.23 60.73c-14.6-4.58-30.08-6.99-45.79-6.99-28.22 0-55.73 7.74-78.7 21.97v7.72c22.6-15 50.25-23.22 78.7-23.22 15.74 0 31.25 2.52 45.79 7.3zM132.41 102.45c-14.59 4.82-30.15 7.36-45.96 7.36-28.45 0-56.1-8.21-78.7-23.22v7.72c22.96 14.23 50.47 21.97 78.7 21.97 16.21 0 32.17-2.56 47.18-7.43-.61-2.01-1.01-4.15-1.22-6.4"
# ... and its UANTUM
LETTERS = ["M163.37 121c-3.41 0-6.5-.53-9.28-1.58s-5.16-2.54-7.12-4.46c-1.97-1.92-3.49-4.24-4.57-6.98-1.08-2.73-1.62-5.78-1.62-9.14V67.47h10.07v31.32c0 2.63.43 4.81 1.3 6.54.86 1.72 1.93 3.09 3.2 4.09 1.27 1.01 2.64 1.7 4.1 2.08s2.77.58 3.92.58 2.46-.19 3.92-.58c1.46-.38 2.83-1.08 4.1-2.08s2.34-2.37 3.2-4.09 1.3-3.9 1.3-6.54V67.47h10.07v31.37c0 3.36-.53 6.4-1.58 9.14-1.05 2.73-2.57 5.06-4.53 6.98-1.97 1.92-4.34 3.41-7.12 4.46-2.79 1.05-5.9 1.58-9.36 1.58", "M187.16 120.1l27.08-52.71h1.04l26.85 52.64h-10.96l-16.43-32.92-16.48 32.96c.01 0-11.1-.1-11.1.03", "M291.55 120.03h1.12V67.47H282.6v31.8l-34.61-31.8h-1.08v52.56h10.07V88.76z", "M315.9 76.39v43.64h10.07V76.39h15.04v-8.92h-40.22v8.92z", "M370.51 121.07c-3.41 0-6.5-.53-9.28-1.58s-5.16-2.54-7.12-4.46c-1.97-1.92-3.49-4.25-4.57-6.98s-1.62-5.78-1.62-9.14V67.54h10.07v31.32c0 2.63.43 4.81 1.3 6.54.86 1.72 1.93 3.09 3.2 4.09 1.27 1.01 2.64 1.7 4.1 2.08s2.77.57 3.92.57 2.46-.19 3.92-.57 2.83-1.08 4.1-2.08c1.27-1.01 2.34-2.37 3.2-4.09s1.3-3.9 1.3-6.54V67.54h10.07v31.37c0 3.36-.53 6.4-1.58 9.14-1.06 2.73-2.57 5.06-4.53 6.98-1.97 1.92-4.34 3.41-7.12 4.46s-5.91 1.58-9.36 1.58", "M429.66 113.3l16.47-19.79v26.52h10.08V67.54h-.65l-25.9 30.36-25.83-30.36h-.65v52.49h10.07V93.51z"]
# SPACE, in the same style: cap height 53.5 (y 67.5 to 121), strokes 10 wide
S = ("M500 80C497 75 491 72.5 485 72.5C477 72.5 471 77 471 83C471 90 478 92.5 486 94.5"
     "C494 96.5 501 99 501 106C501 112 495 116 486 116C479 116 473 113 470 108")
P_BOWL = "M519 72.5H536C545 72.5 551 78.5 551 86.5C551 94.5 545 100.5 536 100.5H519"
A_SPACE = "M563.16 120.1l27.08-52.71h1.04l26.85 52.64h-10.96l-16.43-32.92-16.48 32.96c.01 0-11.1-.1-11.1.03"
C = "M666.1 78.9A21.7 21.7 0 1 0 666.1 109.6"

CAP_TOP = 67.5                              # the capitals' top in the SVG's own coordinates
# where each letter's centre is on the wall (units from the first U's centre)
CENTRES = {"U1": 0.0, "A1": 55.9, "N": 115.1, "T": 170.2, "U2": 222.7, "M": 285.6,
           "S": 349.7, "P": 402.6, "A2": 449.2, "C": 505.4, "E": 561.7}
Q_CENTRE = (-84.4, 14.8)                    # the ring's centre on the wall
Q_SCALE = 1.068                             # the wall's ring (radius 90.8) over the logo's (85.02)
LOGO_RING = (85.02, 85.02)                  # the ring's centre in the logo's SVG
# the TUM logo on the wall, in photo px from its top left (156 x 81): the T's bar runs into
# the U's left stem; the U's right stem is the M's first, under the M's bar
TUM_AT = (5.9, -80.7)
TUM_PER_PX = 0.74
TUM = [(0, 0, 56, 10), (14, 0, 11, 81), (46, 0, 11, 81), (46, 70, 44, 11),
       (80, 0, 76, 10), (80, 0, 11, 81), (111, 0, 11, 81), (145, 0, 11, 81)]


def glyphs() -> dict[str, str]:
    """Each letter as SVG, in the logo's own coordinates."""
    stroke = f'fill="none" stroke="{BLUE}" stroke-width="10"'
    out = {k: f'<path d="{d}" fill="{CHAR}"/>' for k, d in zip(("U1", "A1", "N", "T", "U2", "M"), LETTERS)}
    out["S"] = f'<path d="{S}" {stroke}/>'
    out["P"] = f'<rect x="514" y="67.5" width="10.07" height="53.5" fill="{BLUE}"/><path d="{P_BOWL}" {stroke}/>'
    out["A2"] = f'<path d="{A_SPACE}" fill="{BLUE}"/>'
    out["C"] = f'<path d="{C}" {stroke}/>'
    out["E"] = "".join(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{BLUE}"/>'
                       for x, y, w, h in ((684, 67.5, 10.07, 53.5), (684, 67.5, 36, 10),
                                          (684, 89.2, 32, 9.6), (684, 111, 36, 10)))
    return out


def render(body: str, view: tuple[float, float, float, float], per_unit: float) -> pygame.Surface:
    x, y, w, h = view
    return pygame.image.load(io.BytesIO(
        (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x} {y} {w} {h}" '
         f'width="{round(w * per_unit)}" height="{round(h * per_unit)}">{body}</svg>').encode()), "x.svg")


def bounds(body: str, view: tuple[float, float, float, float], per_unit: float = 4) -> tuple[float, ...]:
    """The inked box of some SVG, in units: (left, top, right, bottom)."""
    rects = pygame.mask.from_surface(render(body, view, per_unit)).get_bounding_rects()
    box = rects[0].unionall(rects[1:])
    return (view[0] + box.left / per_unit, view[1] + box.top / per_unit,
            view[0] + box.right / per_unit, view[1] + box.bottom / per_unit)


def composition() -> str:
    parts = []
    for name, svg in glyphs().items():
        left, _, right, _ = bounds(svg, (0, 0, 800, 200))
        dx = CENTRES[name] - (left + right) / 2
        parts.append(f'<g transform="translate({dx:.2f} {-CAP_TOP})">{svg}</g>')
    q = f'<path d="{RING}" fill="{CHAR}"/><path d="{INNER}" fill="{CHAR}"/><path d="{ORBIT}" fill="{BLUE}"/>'
    parts.append(f'<g transform="translate({Q_CENTRE[0]} {Q_CENTRE[1]}) scale({Q_SCALE}) '
                 f'translate({-LOGO_RING[0]} {-LOGO_RING[1]})">{q}</g>')
    tx, ty = TUM_AT
    k = TUM_PER_PX
    parts += [f'<rect x="{tx + x * k:.2f}" y="{ty + y * k:.2f}" width="{w * k:.2f}" height="{h * k:.2f}" '
              f'fill="{BLUE}"/>' for x, y, w, h in TUM]
    return "".join(parts)


def main() -> None:
    pygame.init()
    body = composition()
    left, top, right, bottom = bounds(body, (-250, -150, 1000, 400), per_unit=2)
    pad = 1 / SCALE                         # a game pixel of margin all round
    view = (left - pad, top - pad, right - left + 2 * pad, bottom - top + 2 * pad)
    w, h = round(view[2] * SCALE), round(view[3] * SCALE)
    view = (view[0], view[1], w / SCALE, h / SCALE)  # whole game pixels
    big = render(body, view, SCALE * SUPER)
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    out.fill((0, 0, 0, 0))
    bw, bh = big.get_size()
    for y in range(h):
        for x in range(w):
            ink = {"charcoal": 0.0, "blue": 0.0}
            for sy in range(SUPER):
                for sx in range(SUPER):
                    px, py = min(bw - 1, x * SUPER + sx), min(bh - 1, y * SUPER + sy)
                    r, g, b, a = big.get_at((px, py))
                    ink["blue" if b - r > 40 else "charcoal"] += a / 255
            if ink["charcoal"] + ink["blue"] >= COVER * SUPER * SUPER:
                out.set_at((x, y), TUM_BLUE if ink["blue"] > ink["charcoal"] else CHARCOAL)
    pygame.image.save(out, OUT)
    u1 = (round(-view[0] * SCALE), round(-view[1] * SCALE))
    print(f"saved {OUT} ({w}x{h}); the first U's centre, at the capitals' top, is at {u1}")


if __name__ == "__main__":
    main()
