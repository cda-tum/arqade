"""Attract mode: a demo kitchen running behind the title (placeholder)."""

from __future__ import annotations

import random

from overquqed.dining import Dining
from overquqed.levels import SNACK_BAR
from overquqed.render import KitchenView
from overquqed.hud import Hud
from overquqed.palette import PLAYER_COLORS
from overquqed.world import IDLE, World


class Demo:
    def __init__(self) -> None:
        self.world = World(SNACK_BAR, random.Random())
        self.view = KitchenView(self.world)
        self.hud = Hud(self.world)
        self.dining = Dining(self.world, self.view.dining_top)
        self.t = 0.0

    def update(self, dt: float) -> None:
        self.t += dt
        self.world.update(dt, [IDLE, IDLE])
        for ev in self.world.events:
            self.dining.on_event(ev)
        self.world.events.clear()
        self.dining.update(dt)

    def draw(self, surf) -> None:
        self.view.draw(surf, self.world.t, set(), PLAYER_COLORS, hints=False)
        self.dining.draw(surf, self.t)
        self.hud.draw(surf, self.t)
