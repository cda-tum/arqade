"""Attract mode: bots cook a real round behind the title while nobody plays.

Cycles through the kitchens so passers-by see every level (and every kind
of dish) being made. Sound stays off; it's a shop window, not a round.
"""

from __future__ import annotations

import random

from overquqed.bot import Bot
from overquqed.dining import Dining
from overquqed.hud import Hud
from overquqed.levels import COSMIC_CAFE, SNACK_BAR, TRATTORIA
from overquqed.palette import PLAYER_COLORS
from overquqed.render import KitchenView
from overquqed.world import World

DEMO_LEVELS = (SNACK_BAR, TRATTORIA, COSMIC_CAFE)
DEMO_LENGTH = 40.0  # seconds per kitchen


class Demo:
    def __init__(self, index: int = 0) -> None:
        self.index = index
        self._start(DEMO_LEVELS[index % len(DEMO_LEVELS)])

    def _start(self, level) -> None:
        self.world = World(level, random.Random())
        if self.world.cosmic is not None:
            self.world.cosmic.next_at = 12.0  # show one off early
        self.bot = Bot(self.world)
        self.view = KitchenView(self.world)
        self.hud = Hud(self.world)
        self.dining = Dining(self.world, self.view.dining_top)
        self.t = 0.0

    def update(self, dt: float) -> None:
        self.t += dt
        if self.t > DEMO_LENGTH:
            self.index += 1
            self._start(DEMO_LEVELS[self.index % len(DEMO_LEVELS)])
        self.world.update(dt, self.bot.update(dt))
        for ev in self.world.events:
            self.dining.on_event(ev)
        self.world.events.clear()
        self.dining.update(dt)

    def draw(self, surf) -> None:
        self.view.draw(surf, self.world.t, {0, 1}, PLAYER_COLORS, hints=False)
        self.dining.draw(surf, self.t)
        self.hud.draw(surf, self.t)
