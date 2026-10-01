"""HUD strip (tickets, score, timer), receipts, speech bubbles, rich text."""

from __future__ import annotations

import re

import pygame

from overquqed import circuit, palette as P, sprites
from overquqed.config import HUD_HEIGHT, INTERNAL_WIDTH
from overquqed.fonts import text
from overquqed.guests import Order
from overquqed.ket import ket_surface
from overquqed.world import Receipt, World

TICKET_W, TICKET_H = 84, 66
TICKET_PITCH = 88
PANEL_X = 4 + 4 * TICKET_PITCH

_KET_RE = re.compile(r"\|([^|>]+)>")
_KET_TOKENS = {"0": ("0",), "1": ("1",), "+": ("+",), "-": ("-",), "Phi+": ("Phi+",), "Phi-": ("Phi-",),
               "Psi+": ("Psi+",), "Psi-": ("Psi-",), "GHZ": ("GHZ",)}


def rich(s: str, color=P.INK, outline=None) -> pygame.Surface:
    """One line of 8 px text where |0>, |Phi+> etc. become proper kets."""
    parts: list[pygame.Surface] = []
    pos = 0
    for m in _KET_RE.finditer(s):
        if m.start() > pos:
            parts.append(text(s[pos:m.start()], 8, color))
        tokens = _KET_TOKENS.get(m.group(1), (m.group(1),))
        parts.append(ket_surface(tokens, outline=outline))
        pos = m.end()
    if pos < len(s):
        parts.append(text(s[pos:], 8, color))
    w = sum(p.get_width() for p in parts) or 1
    h = max((p.get_height() for p in parts), default=8)
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    x = 0
    for p in parts:
        out.blit(p, (x, (h - p.get_height()) // 2))
        x += p.get_width()
    return out


def wrap(s: str, width_chars: int) -> list[str]:
    words, lines, cur = s.split(), [], ""
    for word in words:
        cand = (cur + " " + word).strip()
        if len(cand) > width_chars and cur:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def speech_bubble(s: str, width_chars: int = 20, tail_top: bool = False) -> pygame.Surface:
    lines = [rich(line, P.INK, outline=None) for line in wrap(s, width_chars)]
    w = max(line.get_width() for line in lines) + 8
    h = len(lines) * 10 + 6
    out = pygame.Surface((w, h + 4), pygame.SRCALPHA)
    oy = 4 if tail_top else 0
    pygame.draw.rect(out, P.INK, (0, oy, w, h))
    pygame.draw.rect(out, P.WHITE, (1, oy + 1, w - 2, h - 2))
    if tail_top:
        pygame.draw.polygon(out, P.INK, [(6, 5), (12, 5), (6, 0)])
        pygame.draw.polygon(out, P.WHITE, [(7, 6), (11, 6), (7, 2)])
    else:
        pygame.draw.polygon(out, P.INK, [(6, h - 1), (12, h - 1), (6, h + 4)])
        pygame.draw.polygon(out, P.WHITE, [(7, h - 2), (11, h - 2), (7, h + 2)])
    for i, line in enumerate(lines):
        out.blit(line, (4, oy + 4 + i * 10))
    return out


def panel_box(w: int, h: int, fill=P.TICKET, edge=P.INK) -> pygame.Surface:
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(s, edge, (1, 0, w - 2, h))
    pygame.draw.rect(s, edge, (0, 1, w, h - 2))
    pygame.draw.rect(s, fill, (1, 1, w - 2, h - 2))
    return s


class Hud:
    def __init__(self, world: World, show_hints: bool = True) -> None:
        self.world = world
        self.show_hints = show_hints
        self._tickets: dict[int, pygame.Surface] = {}

    def _ticket(self, order: Order) -> pygame.Surface:
        surf = self._tickets.get(order.id)
        if surf is not None:
            return surf
        surf = panel_box(TICKET_W, TICKET_H)
        # torn top edge in the guest's colour
        pygame.draw.rect(surf, P.TICKET_EDGE, (2, 1, TICKET_W - 4, 2))
        k = ket_surface((order.recipe.key,), scale=2)
        if k.get_width() > TICKET_W - 6:
            k = ket_surface((order.recipe.key,), scale=1)
            surf.blit(k, ((TICKET_W - k.get_width()) // 2, 8))
        else:
            surf.blit(k, ((TICKET_W - k.get_width()) // 2, 3))
        key = "alice" if order.guest.key == "alicebob" else order.guest.key
        surf.blit(sprites.portrait(key), (3, 27))
        if order.guest.duo:
            surf.blit(sprites.portrait("bob"), (3, 40))
        if self.show_hints:
            hint = order.recipe.hint
            n = order.recipe.n
            cw, ch = circuit.size(hint, n)
            x0 = 22 + max(0, (TICKET_W - 24 - cw) // 2)
            y0 = 26 + max(0, (28 - ch) // 2)
            if hint:
                circuit.draw(surf, hint, n, x0, y0, wire_color=(120, 100, 90))
            else:
                pygame.draw.line(surf, (120, 100, 90), (24, 38), (TICKET_W - 4, 38))
                lbl = text("FRESH", 8, (120, 100, 90))
                surf.blit(lbl, (26 + (TICKET_W - 28 - lbl.get_width()) // 2, 42))
        self._tickets[order.id] = surf
        return surf

    def draw(self, surf: pygame.Surface, t: float, score_flash: float = 0.0) -> None:
        w = self.world
        surf.fill(P.HUD_BG, (0, 0, INTERNAL_WIDTH, HUD_HEIGHT))
        surf.fill(P.INK, (0, HUD_HEIGHT - 1, INTERNAL_WIDTH, 1))
        for i in range(w.level.max_tickets):
            x = 4 + i * TICKET_PITCH
            pygame.draw.rect(surf, shade_bg(), (x, 3, TICKET_W, TICKET_H), 1)
        for i, order in enumerate(w.orders.orders[: w.level.max_tickets]):
            x = 4 + i * TICKET_PITCH
            age = w.t - order.created
            y = 3 - max(0, round((1 - age / 0.25) * 60)) if age < 0.25 else 3
            tk = self._ticket(order)
            shake = 0
            frac = order.patience_frac
            if frac < 0.25 and int(t * 8) % 2:
                shake = 1
            surf.blit(tk, (x + shake, y))
            # patience bar
            bw = TICKET_W - 8
            col = P.GOOD if frac > 0.5 else P.WARN if frac > 0.25 else P.BAD
            pygame.draw.rect(surf, P.INK, (x + 3 + shake, y + TICKET_H - 7, bw + 2, 5))
            pygame.draw.rect(surf, (80, 70, 80), (x + 4 + shake, y + TICKET_H - 6, bw, 3))
            pygame.draw.rect(surf, col, (x + 4 + shake, y + TICKET_H - 6, round(bw * frac), 3))
        self._panel(surf, t, score_flash)

    def _panel(self, surf, t: float, score_flash: float) -> None:
        w = self.world
        x = PANEL_X
        surf.blit(text("SCORE", 8, P.TEXT_DIM), (x, 6))
        col = P.GOLD if score_flash > 0 and int(t * 12) % 2 else P.TEXT
        surf.blit(text(f"{w.score}", 16, col, shadow=P.INK), (x, 16))
        if w.level.duration != float("inf"):
            left = w.time_left
            m, s = divmod(int(left + 0.999), 60)
            tcol = P.BAD if left < 30 and int(t * 4) % 2 else P.TEXT
            surf.blit(text("TIME", 8, P.TEXT_DIM), (x, 38))
            surf.blit(text(f"{m}:{s:02d}", 16, tcol, shadow=P.INK), (x, 48))
        if w.supply is not None:
            surf.blit(text(f"Q {w.supply}", 8, P.KET_0, shadow=P.INK), (x + 88, 6))


def shade_bg():
    return (70, 56, 86)


def receipt_surface(r: Receipt) -> pygame.Surface:
    cw, ch = circuit.size(r.ops, r.n)
    w = max(96, cw + 14)
    h = 34 + ch
    surf = panel_box(w, h, fill=(255, 252, 240))
    surf.blit(text("RECEIPT", 8, (150, 130, 110)), (5, 4))
    for x in range(3, w - 3, 4):
        surf.set_at((x, 13), (200, 190, 170))
    circuit.draw(surf, r.ops, r.n, 7, 17, wire_color=(120, 100, 90), min_width=cw)
    k = ket_surface(r.tokens)
    y = 20 + ch
    surf.blit(text("=", 8, P.INK), (5, y + 1))
    surf.blit(k, (15, y))
    f = text(f"F{r.fidelity:.2f}", 8, P.GOOD if r.fidelity >= 0.9 else (190, 140, 20))
    surf.blit(f, (w - f.get_width() - 4, y + 1))
    pts = text(f"+{r.points}", 8, (40, 150, 70))
    surf.blit(pts, (w - pts.get_width() - 4, 4))
    return surf
