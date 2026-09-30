"""Tiny quantum-circuit diagrams (ticket hints, receipts, gate flashes).

Wires, boxed single-qubit gates and the CNOT's control dot / target (+)
joined by a vertical line, laid out ASAP into columns. Drawn with
primitives at 1:1 pixel scale.
"""

from __future__ import annotations

import pygame

from overquqed import palette as P
from overquqed.fonts import load_font

BOX = 11  # gate box size
COL = 13  # column pitch
WIRE_GAP = 10  # wire pitch


def layout(ops: list[tuple] | tuple[tuple, ...], n: int) -> list[list[tuple]]:
    """Greedy ASAP columns: each op goes in the first column after the last
    one that touched any of its qubits."""
    free = [0] * n
    cols: list[list[tuple]] = []
    for op in ops:
        qs = op[1:]
        col = max(free[q] for q in qs)
        if op[0] == "CNOT":
            lo, hi = min(qs), max(qs)
            col = max(free[q] for q in range(lo, hi + 1))
            for q in range(lo, hi + 1):
                free[q] = col + 1
        else:
            for q in qs:
                free[q] = col + 1
        while len(cols) <= col:
            cols.append([])
        cols[col].append(op)
    return cols


def size(ops, n: int) -> tuple[int, int]:
    return max(1, len(layout(ops, n))) * COL + 6, (n - 1) * WIRE_GAP + BOX


GATE_COLORS = {"X": P.KET_1, "Z": P.KET_MINUS, "H": P.KET_PLUS, "Y": (240, 200, 90), "S": (120, 200, 240), "T": (240, 140, 220)}


def draw_gate_box(surf: pygame.Surface, gate: str, cx: int, cy: int, box: int = BOX) -> None:
    r = pygame.Rect(cx - box // 2, cy - box // 2, box, box)
    pygame.draw.rect(surf, P.INK, r)
    pygame.draw.rect(surf, GATE_COLORS.get(gate, P.WHITE), r.inflate(-2, -2))
    pygame.draw.rect(surf, P.WHITE, r.inflate(-4, -4))
    g = load_font(8).render(gate, False, P.INK)
    gr = g.get_bounding_rect()
    surf.blit(g, (cx - gr.width // 2, cy - gr.height // 2), gr)


def draw_control(surf, cx, cy, color=P.INK) -> None:
    pygame.draw.circle(surf, color, (cx, cy), 2)
    surf.fill(color, (cx - 1, cy - 2, 3, 5))
    surf.fill(color, (cx - 2, cy - 1, 5, 3))


def draw_target(surf, cx, cy, color=P.INK, bg=P.WHITE) -> None:
    pygame.draw.circle(surf, bg, (cx, cy), 3)
    pygame.draw.circle(surf, color, (cx, cy), 4, 1)
    pygame.draw.line(surf, color, (cx - 3, cy), (cx + 3, cy))
    pygame.draw.line(surf, color, (cx, cy - 3), (cx, cy + 3))


def draw(surf: pygame.Surface, ops, n: int, x: int, y: int, wire_color=P.INK, min_width: int = 0) -> int:
    """Draw at top-left (x, y). Returns the width used."""
    cols = layout(ops, n)
    width = max(min_width, max(1, len(cols)) * COL + 6)
    wires = [y + BOX // 2 + q * WIRE_GAP for q in range(n)]
    for wy in wires:
        pygame.draw.line(surf, wire_color, (x, wy), (x + width - 1, wy))
    for ci, col in enumerate(cols):
        cx = x + 3 + ci * COL + COL // 2
        for op in col:
            if op[0] == "CNOT":
                c, t = op[1], op[2]
                pygame.draw.line(surf, wire_color, (cx, wires[c]), (cx, wires[t]))
                draw_control(surf, cx, wires[c])
                draw_target(surf, cx, wires[t])
            else:
                draw_gate_box(surf, op[0], cx, wires[op[1]])
    return width
