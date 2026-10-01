"""The dining room: guests walk in, queue under the pass, cheer or storm off.

Presentation only -- it mirrors the OrderBook through world events.
"""

from __future__ import annotations

import pygame

from overquqed import palette as P, sprites
from overquqed.config import INTERNAL_WIDTH, TILE
from overquqed.guests import Order
from overquqed.hud import speech_bubble
from overquqed.world import World

WALK_SPEED = 70.0
SLOT_PITCH = 30


class Actor:
    def __init__(self, order: Order, x: float) -> None:
        self.order = order
        self.x = x
        self.target = x
        self.state = "enter"  # enter | wait | leave
        self.mood = ""  # "" | happy | angry
        self.t = 0.0
        self.bubble: pygame.Surface | None = None
        self.bubble_until = 0.0
        self.bang_until = 0.0

    @property
    def looks(self) -> list[tuple[str, int]]:
        if self.order.guest.duo:
            return [("alice", -7), ("bob", 7)]
        return [(self.order.guest.key, 0)]


class Dining:
    def __init__(self, world: World, top: int) -> None:
        self.world = world
        self.top = top
        self.floor_y = top + 34  # feet line
        passes = [s.x for s in world.stations_of("pass")]
        self.center = ((min(passes) + max(passes) + 1) / 2) * TILE if passes else INTERNAL_WIDTH / 2
        self.actors: dict[int, Actor] = {}
        self.leaving: list[Actor] = []
        self.clock = 0.0

    def slot_x(self, i: int, n: int) -> float:
        return self.center + (i - (n - 1) / 2) * SLOT_PITCH

    def on_event(self, ev: tuple) -> None:
        kind = ev[0]
        if kind == "order":
            order = ev[1]
            a = Actor(order, -20.0)
            a.bang_until = self.clock + 1.2
            if order.first_visit:
                a.bubble = speech_bubble(order.guest.flavour, 24, tail_top=True)
                a.bubble_until = self.clock + 4.5
            self.actors[order.id] = a
        elif kind == "serve":
            order = ev[2].order
            a = self.actors.pop(order.id, None)
            if a:
                a.state, a.mood, a.t = "leave", "happy", 0.0
                a.bubble = None
                self.leaving.append(a)
        elif kind == "refuse":
            order = ev[2].order
            a = self.actors.get(order.id) if order else None
            if a:
                a.bubble = speech_bubble("Below threshold!", 18, tail_top=True)
                a.bubble_until = self.clock + 1.6
        elif kind == "guest_left":
            order = ev[1]
            a = self.actors.pop(order.id, None)
            if a:
                a.state, a.mood, a.t = "leave", "angry", 0.0
                a.bubble = None
                self.leaving.append(a)

    def update(self, dt: float) -> None:
        self.clock += dt
        open_ids = [o.id for o in self.world.orders.orders]
        n = len(open_ids)
        for i, oid in enumerate(open_ids):
            a = self.actors.get(oid)
            if a:
                a.target = self.slot_x(i, n)
        for a in list(self.actors.values()) + self.leaving:
            a.t += dt
            if a.state == "leave":
                a.target = INTERNAL_WIDTH + 30
                if a.t < 0.6:
                    continue  # cheer / fume on the spot first
            step = WALK_SPEED * dt
            if abs(a.target - a.x) <= step:
                a.x = a.target
                if a.state == "enter":
                    a.state = "wait"
            else:
                a.x += step if a.target > a.x else -step
        self.leaving = [a for a in self.leaving if a.x < INTERNAL_WIDTH + 25]

    def draw(self, surf: pygame.Surface, t: float) -> None:
        for a in sorted(list(self.actors.values()) + self.leaving, key=lambda a: a.x):
            moving = abs(a.target - a.x) > 0.5 and not (a.state == "leave" and a.t < 0.6)
            hop = 0
            if a.mood == "happy" and a.t < 0.6:
                hop = -2 if int(a.t * 10) % 2 else 0
            if a.order.guest.key == "surface" and moving:
                hop = -1 if int(t * 12) % 2 else 0  # always rushing
            for key, dx in a.looks:
                idle, step = sprites.guest_frames(key)
                spr = step if moving and int(t * 8) % 2 else idle
                if moving and a.target < a.x:
                    spr = pygame.transform.flip(spr, True, False)
                x = round(a.x) + dx - 8
                y = self.floor_y - 22 + hop
                pygame.draw.ellipse(surf, (70, 40, 34), (x + 2, self.floor_y - 3, 12, 4))
                surf.blit(spr, (x, y))
            x, y = round(a.x), self.floor_y - 22
            if a.mood == "happy" and a.t < 1.2:
                h = sprites.heart()
                surf.blit(h, (x - 3, y - 8 - round(a.t * 10)))
            elif a.mood == "angry" and a.t < 1.2:
                surf.blit(sprites.angry(), (x + 4, y - 4))
            elif a.bang_until > self.clock and a.state != "leave":
                surf.blit(sprites.bubble_bang(), (x - 3, y - 8))
            # patience pip over waiting guests
            if a.state == "wait" and a.mood == "":
                frac = a.order.patience_frac
                col = P.GOOD if frac > 0.5 else P.WARN if frac > 0.25 else P.BAD
                pygame.draw.rect(surf, P.INK, (x - 7, self.floor_y + 2, 14, 3))
                pygame.draw.rect(surf, col, (x - 6, self.floor_y + 3, round(12 * frac), 1))

    def draw_bubbles(self, surf: pygame.Surface) -> None:
        for a in self.actors.values():
            if a.bubble is not None and a.bubble_until > self.clock and a.state != "enter":
                b = a.bubble
                x = min(max(4, round(a.x) - 6), INTERNAL_WIDTH - b.get_width() - 4)
                y = self.floor_y + 8
                surf.blit(b, (x, y))
