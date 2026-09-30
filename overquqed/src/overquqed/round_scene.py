"""One round in a kitchen: input -> chefs, world events -> sound/fx/guests."""

from __future__ import annotations

import random

import pygame

from overquqed import palette as P
from overquqed.config import INTERNAL_HEIGHT, INTERNAL_WIDTH, TILE
from overquqed.dining import Dining
from overquqed.fonts import text
from overquqed.game import Scene
from overquqed.hud import Hud, panel_box, receipt_surface
from overquqed.input import PLAYERS, Input
from overquqed.levels import Level
from overquqed.render import KitchenView, tile_px
from overquqed.world import IDLE, ChefInput, World

RECEIPT_TIME = 2.8
PAUSE_ITEMS = ("RESUME", "RESTART", "QUIT TO MENU")


class Floater:
    def __init__(self, surf: pygame.Surface, x: int, y: int, dur: float = 1.1) -> None:
        self.surf, self.x, self.y, self.t, self.dur = surf, x, y, 0.0, dur


class RoundScene(Scene):
    def __init__(self, app, level: Level, players: list[int], seed: int | None = None) -> None:
        super().__init__(app)
        self.level = level
        self.players = sorted(players)
        self.solo = len(self.players) == 1
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        self.world = World(level, random.Random(self.seed), solo=self.solo)
        self.view = KitchenView(self.world)
        self.hud = Hud(self.world, level.show_hints)
        self.dining = Dining(self.world, self.view.dining_top)
        self.active_chef = 0  # solo mode: the chef player 1 controls
        self.floaters: list[Floater] = []
        self.receipts: list[tuple[pygame.Surface, float]] = []
        self.score_flash = 0.0
        self.shake = 0.0
        self.paused = False
        app.music(level.key)
        self.pause_index = 0
        self.ending = 0.0  # "TIME UP" banner countdown
        self.clock = 0.0
        self._whirr = 0.0
        self.tutorial = None
        self.idle_resets = True
        if level.tutorial:
            from overquqed.tutorial import Tutorial

            self.tutorial = Tutorial(self)

    # --- control mapping ------------------------------------------------------
    def colors(self):
        return P.PLAYER_COLORS

    def active_chefs(self) -> set[int]:
        if self.solo:
            return {self.active_chef}
        return {0, 1}

    def chef_inputs(self, inp: Input) -> list[ChefInput]:
        out = [IDLE, IDLE]
        if self.solo:
            p = PLAYERS[self.players[0]]
            if inp.was_pressed(p, "swap"):
                self.active_chef = 1 - self.active_chef
                self.app.sfx("swap")
            out[self.active_chef] = self._read(inp, p)
        else:
            for chef_idx, p in enumerate(PLAYERS):
                out[chef_idx] = self._read(inp, p)
        return out

    @staticmethod
    def _read(inp: Input, p: str) -> ChefInput:
        return ChefInput(
            move=inp.move(p),
            pick=inp.was_pressed(p, "pick"),
            use=inp.is_held(p, "use"),
            use_pressed=inp.was_pressed(p, "use"),
        )

    # --- update -----------------------------------------------------------------
    def update(self, dt: float, inp: Input) -> None:
        self.clock += dt
        if self.paused:
            self._pause_menu(inp)
            return
        if inp.any_pressed("start") and not (self.tutorial and self.tutorial.wants_start):
            self.paused = True
            self.pause_index = 0
            self.app.sfx("blip")
            return
        if self.ending > 0:
            self.ending -= dt
            self.world.events.clear()
            self.dining.update(dt)
            if self.ending <= 0:
                from overquqed.scenes import ResultsScene

                self.app.switch(ResultsScene(self.app, self))
            return
        inputs = self.chef_inputs(inp)
        if self.tutorial is not None:
            inputs = self.tutorial.filter_inputs(inputs, inp)
        self.world.update(dt, inputs)
        self._whirr -= dt
        if self._whirr <= 0 and any(
            c.working and (st := self.world.station_at(c.target)) is not None and st.kind == "h"
            for c in self.world.chefs
        ):
            self.app.sfx("whirr")
            self._whirr = 0.12
        for ev in self.world.events:
            self._on_event(ev)
            if self.tutorial is not None:
                self.tutorial.on_event(ev)
        self.world.events.clear()
        if self.tutorial is not None:
            self.tutorial.update(dt, inp)
        self.dining.update(dt)
        for f in self.floaters:
            f.t += dt
        self.floaters = [f for f in self.floaters if f.t < f.dur]
        self.receipts = [(s, t0) for s, t0 in self.receipts if self.clock - t0 < RECEIPT_TIME]
        self.score_flash = max(0.0, self.score_flash - dt)
        self.shake = max(0.0, self.shake - dt)
        self.app.music_tempo(fast=self.world.time_left < 30)
        if self.world.over:
            self.ending = 1.6
            self.app.sfx("timeup")

    def _pause_menu(self, inp: Input) -> None:
        if inp.any_nav("up"):
            self.pause_index = (self.pause_index - 1) % len(PAUSE_ITEMS)
            self.app.sfx("blip")
        if inp.any_nav("down"):
            self.pause_index = (self.pause_index + 1) % len(PAUSE_ITEMS)
            self.app.sfx("blip")
        if inp.back():
            self.paused = False
            return
        if inp.confirm():
            choice = PAUSE_ITEMS[self.pause_index]
            self.app.sfx("confirm")
            if choice == "RESUME":
                self.paused = False
            elif choice == "RESTART":
                self.app.switch(RoundScene(self.app, self.level, self.players))
            else:
                from overquqed.scenes import LevelSelectScene

                self.app.switch(LevelSelectScene(self.app, self.players))

    def _float(self, s: str, pos: tuple[int, int], color, dur: float = 1.1) -> None:
        px, py = tile_px(*pos)
        surf = text(s, 8, color, shadow=P.INK)
        x = min(max(2, px + TILE // 2 - surf.get_width() // 2), INTERNAL_WIDTH - surf.get_width() - 2)
        self.floaters.append(Floater(surf, x, py - 4, dur))

    def _on_event(self, ev: tuple) -> None:
        kind = ev[0]
        self.dining.on_event(ev)
        sfx = {
            "pick": "pick", "put": "put", "fridge": "fridge", "bin": "bin", "nope": "nope",
            "fridge_empty": "nope", "no_order": "nope", "jammed": "nope", "too_big": "nope",
            "dirty_back": "put", "order": "order", "sink": "sink",
        }.get(kind)
        if sfx:
            self.app.sfx(sfx)
        if kind == "gate":
            self.app.sfx({"X": "flip", "Z": "stir", "H": "blend_done"}[ev[1]])
        elif kind == "cnot":
            self.app.sfx("cnot_sparkle" if ev[2] else "cnot")
            if ev[2]:
                self._float("ENTANGLED!", ev[1], P.GOLD)
        elif kind == "serve":
            result, receipt = ev[2], ev[3]
            self._float(f"+{result.points}", ev[1], P.GOOD)
            self.receipts.append((receipt_surface(receipt), self.clock))
            self.score_flash = 0.8
            self.app.sfx("serve")
        elif kind == "refuse":
            self._float(f"F={ev[2].fidelity:.2f} < 0.8", ev[1], P.BAD, 1.6)
            self.app.sfx("refuse")
        elif kind == "no_order":
            self._float("NOBODY ORDERED THAT", ev[1], P.WARN)
        elif kind == "fridge_empty":
            self._float("OUT OF QUBITS!", ev[1], P.BAD)
        elif kind == "too_big":
            self._float("MAX 3 QUBITS", ev[1], P.WARN)
        elif kind == "guest_left":
            self.app.sfx("leave")
        elif kind == "cosmic_warn":
            self.app.sfx("siren")
        elif kind == "cosmic_hit":
            self.app.sfx("cosmic")
            self.shake = 0.35

    # --- draw -------------------------------------------------------------------
    def draw(self, surf: pygame.Surface) -> None:
        t = self.clock
        self.view.draw(surf, self.world.t, self.active_chefs(), self.colors(),
                       hints=self.tutorial is None or self.tutorial.show_hints)
        self.dining.draw(surf, t)
        for f in self.floaters:
            y = f.y - round(f.t * 18)
            surf.blit(f.surf, (f.x, y))
        for i, (rs, t0) in enumerate(self.receipts[-2:]):
            age = self.clock - t0
            slide = min(1.0, age / 0.2)
            x = INTERNAL_WIDTH - rs.get_width() - 4
            y = INTERNAL_HEIGHT - round(rs.get_height() * slide) - 2 - i * 6
            surf.blit(rs, (x, y))
        self.dining.draw_bubbles(surf)
        self.hud.draw(surf, t, self.score_flash)
        if self.solo:
            lbl = text("Y: SWAP CHEF", 8, P.TEXT_DIM, shadow=P.INK)
            surf.blit(lbl, (4, INTERNAL_HEIGHT - 11))
        if self.tutorial is not None:
            self.tutorial.draw(surf, t)
        if self.ending > 0:
            banner = text("TIME UP!", 32, P.GOLD, shadow=P.INK)
            surf.blit(banner, ((INTERNAL_WIDTH - banner.get_width()) // 2, 150))
        if self.paused:
            self._draw_pause(surf)
        if self.shake > 0:
            dx = 2 if int(self.shake * 40) % 2 else -2
            surf.scroll(dx, 0)

    def _draw_pause(self, surf: pygame.Surface) -> None:
        dim = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT), pygame.SRCALPHA)
        dim.fill((10, 8, 20, 170))
        surf.blit(dim, (0, 0))
        box = panel_box(180, 96, fill=P.HUD_BG, edge=P.GOLD)
        bx, by = (INTERNAL_WIDTH - 180) // 2, 120
        surf.blit(box, (bx, by))
        title = text("PAUSED", 16, P.GOLD, shadow=P.INK)
        surf.blit(title, ((INTERNAL_WIDTH - title.get_width()) // 2, by + 8))
        for i, item in enumerate(PAUSE_ITEMS):
            sel = i == self.pause_index
            s = text(("> " if sel else "  ") + item, 8, P.WHITE if sel else P.TEXT_DIM)
            surf.blit(s, (bx + 24, by + 38 + i * 16))
