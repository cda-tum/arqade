"""TELEPORT! (boss): carry your qubit across four islands to the lab, hop by
hop, before the decoherence wave behind you catches up.

The islands are cut off from each other, so the only way across is by
teleporting: stand on a portal and press A. Portals come in entangled pairs
(the same colour, with a wavy bond across the gap), and each pair works once:
teleporting uses up the entanglement. A portal with no bond does nothing.

You arrive as a ghost: the measurement left your state flipped by up to an X
and a Z, and until the two classical bits reach you (two chips running along
the cable at the bottom, at finite speed) nobody can undo them. When the bits
land, the corrections they name are applied and you're solid again; only
then can you teleport on. That's why teleportation can't beat light. The bits
are random, as they must be, but they only choose which correction is
applied, never whether you make it.

  hop 1: one portal pair, calm.
  hop 2: noise rains while you wait for the bits. Only a ghost can be hurt
         (the uncorrected state is the fragile one); the bits follow you, so
         dodge freely. Solid again, the noise passes through you.
  hop 3: three portals, and only the one matching the far portal's colour is
         entangled with it.

Touching the wave, or noise while a ghost, fails. The wave reaches the lab just
as the time runs out, so the timer and the wave are the same thing.
"""

from __future__ import annotations

import math

import pygame

from planck_time import palette as P
from planck_time.microgames.base import H, W, Boss, PlayerInput, register_boss
from planck_time.pixel import backdrop, blit_center, card, dither, orb, outlined, result_overlay

ISLANDS = ((6, 50), (68, 112), (130, 174), (192, 236))
TOP, BOTTOM = 30, 138  # the islands' extent
CABLE_Y = 150  # the classical channel runs along here
R = 6  # the qubit
SPEED = 70.0  # px per second at level 0
BIT_SPEED = 72.0
NOISE_R = 3
HIT = 6  # a forgiving hitbox, smaller than the sprites touching (R + NOISE_R)
NOISE_EVERY = (None, None, 0.6, 0.48)  # seconds between noise particles, by the island you're a ghost on
PORTAL_R = 8
REACH = PORTAL_R + R
COLORS = (P.SKY, P.PINK, P.GOOD, P.GOLD)
WAVE_START = -14.0
WAVE_END = ISLANDS[-1][1] + 4  # where the wave is when the time runs out
BADGE_TIME = 0.6
BOT_MOVES = [(0.0, 0.0)] + [(math.cos(a * math.pi / 4), math.sin(a * math.pi / 4)) for a in range(8)]


_WAVE: list[pygame.Surface] = []


def wave_texture() -> pygame.Surface:
    """The wave's dithered body, drawn once and blitted as wide as it's grown."""
    if not _WAVE:
        tex = pygame.Surface((W, H))
        dither(tex, (0, 0, W, H), (88, 24, 72), (136, 40, 96))
        _WAVE.append(tex)
    return _WAVE[0]


@register_boss
class Teleport(Boss):
    VERB = "TELEPORT!"
    INPUT = "stick+a"
    CAPTION = "Teleporting uses up entanglement and needs 2 classical bits"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        rng = self.rng
        self.x, self.y = 22.0, rng.uniform(56.0, 112.0)
        self.island = 0
        self.ghost = False
        self.state = rng.uniform(-0.6, 0.6)  # the qubit: an arrow's angle in the x-z plane, from |0>
        self.shown = self.state  # what the arrow shows (flipped while a ghost)
        self.bits: list[list] = []  # chips in flight: [x, y, value, gate, stage, delay]
        self.badges: list[tuple[str, float]] = []  # corrections just applied, and when
        self.buzz_at = -1.0  # pressed A on a portal with no partner
        self.hops = []
        colors = list(COLORS)
        rng.shuffle(colors)
        for k in range(3):
            send_x, recv_x = ISLANDS[k][1] - 8, ISLANDS[k + 1][0] + 8
            recv_y = rng.uniform(TOP + 14, BOTTOM - 14)
            if k < 2:
                sends = [(send_x, rng.uniform(TOP + 14, BOTTOM - 14), colors[k])]
                match = 0
            else:  # three portals, one entangled with the far one
                ys = [TOP + 18, (TOP + BOTTOM) / 2, BOTTOM - 18]
                picks = rng.sample(colors, 3)
                sends = [(send_x, y + rng.uniform(-4, 4), c) for y, c in zip(ys, picks)]
                match = rng.randrange(3)
            self.hops.append({"sends": sends, "match": match, "recv": (recv_x, recv_y), "used": False})
        self.noise: list[list[float]] = []  # [x, y, vx, vy]
        self.next_noise = 0.0
        self.aim = False
        self.wave = WAVE_START
        self.wave_speed = (WAVE_END - WAVE_START) / duration
        self.backdrop = ((24, 16, 48), (32, 24, 64))

    # --- the rules ----------------------------------------------------------------------

    @property
    def hop(self) -> dict | None:
        return self.hops[self.island] if self.island < len(self.hops) else None

    def portal_near(self) -> int | None:
        hop = self.hop
        if hop is None or hop["used"]:
            return None
        for i, (px, py, _c) in enumerate(hop["sends"]):
            if math.hypot(px - self.x, py - self.y) <= REACH:
                return i
        return None

    def step(self, dt: float, inp: PlayerInput) -> None:
        speed = SPEED * self.speed
        sx, sy = inp.stick
        lo, hi = ISLANDS[self.island]
        self.x = max(lo + R, min(hi - R, self.x + sx * speed * dt))
        self.y = max(TOP + R, min(BOTTOM - R, self.y + sy * speed * dt))
        if inp.a and not self.ghost:
            i = self.portal_near()
            if i is not None:
                if i == self.hop["match"]:
                    self._teleport()
                else:
                    self.buzz_at = self.t
        self._move_bits(dt)
        self._move_noise(dt)
        self.wave += self.wave_speed * dt
        if self.x - R <= self.wave:
            self.fail()
        elif self.ghost and any(math.hypot(nx - self.x, ny - self.y) < HIT for nx, ny, _vx, _vy in self.noise):
            self.fail()  # only the fragile, uncorrected ghost can be hurt
        elif self.island == len(ISLANDS) - 1 and not self.ghost:
            self.win()

    def _teleport(self) -> None:
        hop = self.hop
        hop["used"] = True
        px, py, _c = hop["sends"][hop["match"]]
        self.x, self.y = hop["recv"]
        self.island += 1
        self.ghost = True
        m_z, m_x = self.rng.randrange(2), self.rng.randrange(2)
        # what arrives is X^m_x Z^m_z |psi>: Z mirrors the arrow left-right, X up-down
        shown = self.state
        if m_z:
            shown = -shown
        if m_x:
            shown = math.pi - shown
        self.shown = shown
        self.bits = [[px, py, m_z, "Z", 0, 0.0], [px, py, m_x, "X", 0, 0.18]]

    def _move_bits(self, dt: float) -> None:
        """The two bits run down to the cable, along it, then up to wherever the
        qubit is now; when both have arrived, their corrections are applied."""
        if not self.bits:
            return
        for b in self.bits:
            if b[5] > 0:
                b[5] -= dt
                continue
            left = BIT_SPEED * self.speed * dt
            while left > 0 and b[4] < 3:
                tx, ty = ((b[0], CABLE_Y), (self.x, CABLE_Y), (self.x, self.y))[b[4]]
                d = math.hypot(tx - b[0], ty - b[1])
                if d <= left:
                    b[0], b[1] = tx, ty
                    b[4] += 1
                    left -= d
                else:
                    b[0] += (tx - b[0]) / d * left
                    b[1] += (ty - b[1]) / d * left
                    left = 0
        if all(b[4] >= 3 for b in self.bits):
            for _x, _y, value, gate, _stage, _delay in self.bits:
                if value:
                    self.badges.append((gate, self.t))
            self.bits = []
            self.ghost = False
            self.shown = self.state

    def _move_noise(self, dt: float) -> None:
        every = NOISE_EVERY[min(self.island, len(NOISE_EVERY) - 1)]
        if every is not None and self.ghost:  # it rains while you wait for the bits
            self.next_noise -= dt
            if self.next_noise <= 0:
                self.next_noise = every / self.speed
                # straight down; every other drop aims at where the ghost is now (so
                # freezing gets you hit), the rest land anywhere but right on you
                lo, hi = ISLANDS[self.island]
                self.aim = not self.aim
                if self.aim:
                    x = self.x
                else:
                    x = self.rng.uniform(lo + 4, hi - 4)
                    for _ in range(6):
                        if abs(x - self.x) >= 14:
                            break
                        x = self.rng.uniform(lo + 4, hi - 4)
                vy = self.rng.uniform(50, 70) * self.speed
                self.noise.append([x, -4.0, 0.0, vy])
        for n in self.noise:
            n[0] += n[2] * dt
            n[1] += n[3] * dt
        self.noise = [n for n in self.noise if n[1] < H + 6]

    # --- the bot --------------------------------------------------------------------------

    def bot(self) -> PlayerInput:
        """Look 0.5 s ahead along each of nine moves and take the safest one
        that still makes progress towards the portal (or the lab)."""
        hop = self.hop
        if hop is not None:
            tx, ty, _c = hop["sends"][hop["match"]]
        else:
            tx, ty = ISLANDS[-1][1] - R - 2, self.y
        if not self.ghost and math.hypot(tx - self.x, ty - self.y) <= REACH - 2:
            return PlayerInput(a=True, a_held=True)
        speed = SPEED * self.speed
        lo, hi = ISLANDS[self.island]
        best, best_score = (0.0, 0.0), -math.inf
        for cx, cy in BOT_MOVES:
            safety = closest = math.inf
            x, y = self.x, self.y
            for k in range(1, 13):
                dt = 0.04 * k
                x = max(lo + R, min(hi - R, self.x + cx * speed * dt))
                y = max(TOP + R, min(BOTTOM - R, self.y + cy * speed * dt))
                if self.ghost:
                    for nx, ny, nvx, nvy in self.noise:
                        safety = min(safety, math.hypot(nx + nvx * dt - x, ny + nvy * dt - y))
                safety = min(safety, (x - self.wave - self.wave_speed * dt) * 2)
                closest = min(closest, math.hypot(tx - x, ty - y) + k * 0.5)
            score = -closest
            if safety < HIT + 7:  # unsafe: then only safety counts
                score = -1e6 + safety * 1000
            if score > best_score:
                best, best_score = (cx, cy), score
        return PlayerInput(stick=best)

    # --- drawing ----------------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        backdrop(surf, self.backdrop, self.t, speed=4)
        t = self.t
        # the classical channel
        for x in range(0, W, 6):
            surf.fill(P.SLATE, (x, CABLE_Y, 3, 1))
        # islands; the last one is the lab
        for k, (lo, hi) in enumerate(ISLANDS):
            rect = pygame.Rect(lo, TOP, hi - lo, BOTTOM - TOP)
            pygame.draw.rect(surf, P.INK, rect.inflate(4, 4), border_radius=6)
            pygame.draw.rect(surf, (48, 56, 104), rect, border_radius=5)
            surf.fill((64, 72, 128), (rect.x + 3, rect.y + 2, rect.w - 6, 2))
            for gy in range(rect.y + 12, rect.bottom - 4, 12):  # chip-like floor tracks
                surf.fill((56, 64, 116), (rect.x + 5, gy, rect.w - 10, 1))
            surf.fill(P.INK, (rect.centerx - 1, rect.bottom + 2, 3, CABLE_Y - rect.bottom - 2))
            if k == len(ISLANDS) - 1:
                blit_center(surf, outlined("LAB", 8, P.GOLD), (rect.centerx, rect.y + 9))
        # portals and their entanglement bonds
        for hop in self.hops:
            rx, ry = hop["recv"]
            for i, (px, py, color) in enumerate(hop["sends"]):
                live = not hop["used"]
                c = color if live else P.SLATE
                if i == hop["match"]:
                    if live:
                        self._bond(surf, (px, py), (rx, ry), color)
                    self._portal(surf, (rx, ry), c, live)
                self._portal(surf, (px, py), c, live)
        if self.buzz_at >= 0 and t - self.buzz_at < 0.5:
            blit_center(surf, outlined("NO PAIR!", 8, P.BAD), (self.x, self.y - 16))
        # the bits on their way
        for bx, by, value, gate, stage, delay in self.bits:
            if delay > 0:
                continue
            r = pygame.Rect(0, 0, 11, 11)
            r.center = (round(bx), round(by))
            card(surf, r, P.GATE[gate] if value else P.SLATE)
            blit_center(surf, outlined(str(value), 8, P.WHITE, shadow=False), (r.centerx + 1, r.centery))
        # noise
        for nx, ny, _vx, _vy in self.noise:
            x, y = round(nx), round(ny)
            for ddx, ddy in ((-5, 0), (5, 0), (0, -5), (0, 5)):
                pygame.draw.line(surf, P.INK, (x, y), (x + ddx, y + ddy), 3)
                pygame.draw.line(surf, P.BAD, (x, y), (x + ddx, y + ddy), 1)
            orb(surf, (x, y), NOISE_R, P.BAD)
        # the decoherence wave
        if self.wave > 0:
            w = min(W, round(self.wave))
            surf.blit(wave_texture(), (0, 0), (0, 0, w, H))
            for y in range(0, H, 6):
                jag = round(3 * math.sin(y * 0.7 + t * 9))
                surf.fill(P.PINK, (w + jag - 2, y, 3, 4))
        self._qubit(surf)
        for gate, at in self.badges:
            k = t - at
            if k < BADGE_TIME:
                r = pygame.Rect(0, 0, 16, 16)
                off = -10 if gate == "Z" else 10
                r.center = (round(self.x + off), round(self.y - 16 - k * 12))
                card(surf, r, P.GATE[gate])
                blit_center(surf, outlined(gate, 8, P.WHITE, shadow=False), (r.centerx + 1, r.centery))
        hint = ("WAIT FOR THE 2 BITS" if self.ghost
                else "PICK THE ENTANGLED ONE" if self.island == 2
                else "A ON THE PORTAL" if self.island < 3 else "DELIVERED!")
        blit_center(surf, outlined(hint, 8, P.WHITE), (W // 2, 12))
        for k in range(3):  # hops done, top left (the hint is centred)
            x = 8 + k * 9
            pygame.draw.circle(surf, P.INK, (x, 12), 4)
            pygame.draw.circle(surf, P.GOLD if self.island > k else P.SLATE, (x, 12), 3)
        result_overlay(surf, self.result, self.since_end, seed=21)

    def _portal(self, surf, center, color, live: bool) -> None:
        x, y = round(center[0]), round(center[1])
        ring = pygame.Rect(0, 0, PORTAL_R * 2 + 2, PORTAL_R + 6)
        ring.center = (x, y)
        pygame.draw.ellipse(surf, P.INK, ring.inflate(4, 4))
        pygame.draw.ellipse(surf, P.shade(color, 0.6), ring)
        pygame.draw.ellipse(surf, color, ring, 2)
        if live:
            a = self.t * 6
            for k in range(3):
                ang = a + k * 2.1
                surf.fill(P.WHITE, (round(x + math.cos(ang) * 5), round(y + math.sin(ang) * 2), 1, 1))

    def _bond(self, surf, a, b, color) -> None:
        """A wavy line between an entangled pair of portals."""
        (ax, ay), (bx, by) = a, b
        steps = max(2, round(math.hypot(bx - ax, by - ay) / 4))
        ln = math.hypot(bx - ax, by - ay) or 1
        nx, ny = (ay - by) / ln, (bx - ax) / ln
        pts = []
        for s in range(steps + 1):
            k = s / steps
            wave = 3 * math.sin(s * 1.3 + self.t * 10)
            pts.append((round(ax + (bx - ax) * k + nx * wave), round(ay + (by - ay) * k + ny * wave)))
        pygame.draw.lines(surf, P.INK, False, pts, 3)
        pygame.draw.lines(surf, color, False, pts, 1)

    def _qubit(self, surf) -> None:
        x, y = round(self.x), round(self.y)
        if self.ghost and int(self.t * 12) % 2:
            pygame.draw.circle(surf, P.MIST, (x, y), R, 1)
        else:
            orb(surf, (x, y), R, P.MIST if self.ghost else P.TEAL, glow=not self.ghost)
        a = self.shown
        tip = (x + math.sin(a) * (R + 4), y - math.cos(a) * (R + 4))
        pygame.draw.line(surf, P.INK, (x, y), tip, 3)
        pygame.draw.line(surf, P.CREAM if self.ghost else P.WHITE, (x, y), tip, 1)
