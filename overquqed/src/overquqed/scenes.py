"""Menu-side scenes: title (with attract mode), join, level select, results."""

from __future__ import annotations

import math

import pygame

from overquqed import config, hiscores, palette as P, sprites
from overquqed.config import INTERNAL_WIDTH
from overquqed.fonts import text
from overquqed.game import Scene
from overquqed.guests import GUESTS
from overquqed.hud import panel_box, receipt_surface, rich
from overquqed.input import PLAYERS, Input
from overquqed.ket import ket_surface
from overquqed.levels import LEVELS
from overquqed.scoring import stars as stars_for


def center(surf: pygame.Surface, s: pygame.Surface, y: int) -> None:
    surf.blit(s, ((INTERNAL_WIDTH - s.get_width()) // 2, y))


def draw_logo(surf: pygame.Surface, y: int, t: float) -> None:
    letters = "OVERQUQED"
    font_w = 32
    x0 = (INTERNAL_WIDTH - len(letters) * font_w) // 2
    for i, ch in enumerate(letters):
        bob = round(2 * math.sin(t * 3 + i * 0.6))
        col = P.GOLD if ch == "Q" else P.WHITE
        surf.blit(text(ch, 32, P.INK), (x0 + i * font_w + 3, y + 3 + bob))
        surf.blit(text(ch, 32, col), (x0 + i * font_w, y + bob))


class TitleScene(Scene):
    idle_resets = False

    def __init__(self, app) -> None:
        super().__init__(app)
        self.t = 0.0
        self.idle = 0.0
        self.demo = None  # attract-mode demo round (a bot kitchen)
        self.guest_keys = list(GUESTS)
        app.music("title")

    def update(self, dt: float, inp: Input) -> None:
        self.t += dt
        self.idle = 0.0 if inp.activity else self.idle + dt
        if inp.select_held_time >= config.BACK_HOLD_TO_QUIT:
            self.app.running = False
            return
        for i, p in enumerate(PLAYERS):
            if inp.was_pressed(p, "start") or inp.was_pressed(p, "pick"):
                self.app.sfx("confirm")
                self.app.switch(JoinScene(self.app, first=i))
                return
        if self.demo is None and self.idle > config.ATTRACT_DELAY:
            from overquqed.attract import Demo

            self.demo = Demo()
        elif self.demo is not None and inp.activity:
            self.demo = None
        if self.demo is not None:
            self.demo.update(dt)

    def draw(self, surf: pygame.Surface) -> None:
        if self.demo is not None:
            self.demo.draw(surf)
            band = pygame.Surface((INTERNAL_WIDTH, 60), pygame.SRCALPHA)
            band.fill((18, 14, 28, 210))
            surf.blit(band, (0, 150))
            draw_logo(surf, 158, self.t)
            if int(self.t * 2) % 2 == 0:
                center(surf, text("PRESS START", 8, P.WHITE, shadow=P.INK), 196)
            return
        surf.fill(P.BG)
        # a strip of kitchen floor behind the logo
        for x in range(0, INTERNAL_WIDTH, 24):
            for y in (216, 240):
                c = P.FLOOR_A if (x // 24 + y // 24) % 2 == 0 else P.FLOOR_B
                surf.fill(c, (x, y, 24, 24))
        surf.fill(P.INK, (0, 215, INTERNAL_WIDTH, 1))
        draw_logo(surf, 60, self.t)
        center(surf, rich("the ancilla kitchen of a |0> quantum computer", P.TEXT_DIM), 104)
        # two chefs walking across the floor
        for idx, col in enumerate(P.PLAYER_COLORS):
            frames = sprites.chef_frames(col)
            period = 14.0
            ph = ((self.t / period) + idx * 0.5) % 1.0
            x = -20 + ph * (INTERNAL_WIDTH + 40)
            f = 1 + int(self.t * 8) % 2
            surf.blit(frames[("right", f)], (round(x), 220))
            # carrying a bowl
            k = ket_surface(("+",) if idx else ("0",))
            surf.blit(k, (round(x) + 2, 208))
        # guest intros
        gi = int(self.t / 3.5) % len(self.guest_keys)
        g = GUESTS[self.guest_keys[gi]]
        key = "alice" if g.key == "alicebob" else g.key
        frame = sprites.guest_frames(key)[0]
        surf.blit(pygame.transform.scale(frame, (32, 44)), (40, 128))
        if g.duo:
            surf.blit(pygame.transform.scale(sprites.guest_frames("bob")[0], (32, 44)), (62, 128))
        surf.blit(text(g.name.upper(), 8, P.GOLD), (104, 136))
        surf.blit(rich("orders " + " ".join(f"|{o}>" for o in g.orders), P.TEXT), (104, 150))
        surf.blit(rich('"' + g.flavour[:44] + ('"' if len(g.flavour) <= 44 else '..."'), P.TEXT_DIM), (104, 164))
        if int(self.t * 2) % 2 == 0:
            center(surf, text("PRESS START", 16, P.WHITE, shadow=P.INK), 282)
        center(surf, text("A or START: JOIN      HOLD SELECT: QUIT", 8, P.TEXT_DIM), 322)
        center(surf, text("MQSF gaming corner", 8, (90, 80, 110)), 344)


class JoinScene(Scene):
    AUTO_GO = 10.0

    def __init__(self, app, first: int) -> None:
        super().__init__(app)
        self.joined = [first]
        self.t = 0.0

    def update(self, dt: float, inp: Input) -> None:
        self.t += dt
        if inp.back():
            self.app.to_title()
            return
        for i, p in enumerate(PLAYERS):
            pressed = inp.was_pressed(p, "pick") or inp.was_pressed(p, "start")
            if not pressed:
                continue
            if i not in self.joined:
                self.joined.append(i)
                self.app.sfx("confirm")
                self.t = min(self.t, self.AUTO_GO - 3)
            elif self.t > 0.25:
                self._go()
                return
        if self.t >= self.AUTO_GO:
            self._go()

    def _go(self) -> None:
        self.app.sfx("confirm")
        self.app.switch(LevelSelectScene(self.app, self.joined))

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(P.BG)
        center(surf, text("WHO'S COOKING?", 16, P.GOLD, shadow=P.INK), 30)
        for i, col in enumerate(P.PLAYER_COLORS):
            x = 60 + i * 200
            box = panel_box(160, 170, fill=P.HUD_BG, edge=col if i in self.joined else (70, 56, 86))
            surf.blit(box, (x, 70))
            surf.blit(text(f"PLAYER {i + 1}", 8, col), (x + 44, 80))
            frames = sprites.chef_frames(col)
            if i in self.joined:
                f = ("down", 1 + int(self.t * 6) % 2) if int(self.t * 2) % 4 == 0 else ("down", 0)
                spr = pygame.transform.scale(frames[f], (48, 66))
                surf.blit(spr, (x + 56, 110))
                center_x = x + 80
                lbl = text("READY!", 8, P.GOOD)
                surf.blit(lbl, (center_x - lbl.get_width() // 2, 196))
            else:
                spr = pygame.transform.scale(frames[("down", 0)], (48, 66))
                spr.set_alpha(70)
                surf.blit(spr, (x + 56, 110))
                if int(self.t * 2) % 2 == 0:
                    lbl = text("PRESS A", 8, P.TEXT)
                    surf.blit(lbl, (x + 80 - lbl.get_width() // 2, 196))
                lbl = text("TO JOIN", 8, P.TEXT)
                surf.blit(lbl, (x + 80 - lbl.get_width() // 2, 208))
        if len(self.joined) == 1:
            center(surf, text("Solo? Press Y in the kitchen to swap chefs.", 8, P.TEXT_DIM), 256)
        center(surf, text("A / START again: LET'S COOK", 8, P.WHITE), 282)
        left = max(0, self.AUTO_GO - self.t)
        center(surf, text(f"starting in {int(left) + 1}", 8, P.TEXT_DIM), 300)
        center(surf, text("SELECT: BACK", 8, (90, 80, 110)), 340)


class LevelSelectScene(Scene):
    def __init__(self, app, players: list[int]) -> None:
        super().__init__(app)
        self.players = players
        self.index = 0 if not app.session.get("played_tutorial") else 1
        self.t = 0.0
        app.music("title")

    def update(self, dt: float, inp: Input) -> None:
        self.t += dt
        if inp.back():
            self.app.to_title()
            return
        if inp.any_nav("up"):
            self.index = (self.index - 1) % len(LEVELS)
            self.app.sfx("blip")
        if inp.any_nav("down"):
            self.index = (self.index + 1) % len(LEVELS)
            self.app.sfx("blip")
        if inp.confirm() and self.t > 0.2:
            level = LEVELS[self.index]
            self.app.sfx("confirm")
            if level.tutorial:
                self.app.session["played_tutorial"] = True
            from overquqed.round_scene import RoundScene

            self.app.switch(RoundScene(self.app, level, self.players))

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(P.BG)
        center(surf, text("CHOOSE A KITCHEN", 16, P.GOLD, shadow=P.INK), 14)
        data = self.app.hiscores
        for i, level in enumerate(LEVELS):
            sel = i == self.index
            y = 48 + i * 42
            box = panel_box(220, 36, fill=P.HUD_BG if not sel else (70, 50, 90), edge=P.GOLD if sel else (70, 56, 86))
            surf.blit(box, (12, y))
            surf.blit(text(level.name if len(level.name) <= 25 else level.name[:24] + ".", 8,
                           P.WHITE if sel else P.TEXT), (20, y + 7))
            n = hiscores.best_stars(data, level.key)
            if level.tutorial:
                tag = "NEW? START HERE!" if not self.app.session.get("played_tutorial") else "TUTORIAL"
                surf.blit(text(tag, 8, P.GOOD if sel else P.TEXT_DIM), (20, y + 21))
            else:
                for s in range(3):
                    surf.blit(sprites.star(s < n), (20 + s * 11, y + 20))
                m, sec = divmod(int(level.duration), 60)
                surf.blit(text(f"{m}:{sec:02d}", 8, P.TEXT_DIM), (180, y + 21))
            if sel:
                surf.blit(text(">", 8, P.GOLD), (4 + (int(self.t * 4) % 2), y + 13))
        # detail panel
        level = LEVELS[self.index]
        x = 244
        panel = panel_box(226, 300, fill=P.HUD_BG, edge=(70, 56, 86))
        surf.blit(panel, (x, 48))
        yy = 58
        for line in _wrap_px(level.blurb, 26):
            surf.blit(text(line, 8, P.TEXT), (x + 8, yy))
            yy += 11
        yy += 6
        surf.blit(text("ORDERS", 8, P.TEXT_DIM), (x + 8, yy))
        yy += 12
        kx = x + 8
        for key in level.recipes:
            k = ket_surface((key,))
            if kx + k.get_width() > x + 218:
                kx = x + 8
                yy += 14
            surf.blit(k, (kx, yy))
            kx += k.get_width() + 4
        yy += 18
        if not level.noise.is_noiseless:
            surf.blit(text(f"T1 {level.noise.t1:.0f}s  T2 {level.noise.t2:.0f}s", 8, P.KET_0), (x + 8, yy))
            yy += 12
        if level.gate_scale != 1:
            surf.blit(text(f"slow gates x{level.gate_scale:g}", 8, P.TEXT_DIM), (x + 8, yy))
            yy += 12
        if level.fridge_capacity:
            surf.blit(text(f"only {level.fridge_capacity} qubits!", 8, P.WARN), (x + 8, yy))
            yy += 12
        if level.cosmic_rays:
            surf.blit(text("cosmic rays!", 8, P.BAD), (x + 8, yy))
            yy += 12
        if not level.tutorial:
            yy = max(yy + 6, 214)
            surf.blit(text("TOP 5", 8, P.GOLD), (x + 8, yy))
            yy += 14
            rows = hiscores.table(data, level.key)
            for r in range(hiscores.TOP_N):
                if r < len(rows):
                    line = f"{r + 1}. {rows[r]['name']:<3}  {rows[r]['score']:>5}"
                    col = P.TEXT
                else:
                    line = f"{r + 1}. ---    ---"
                    col = (90, 80, 110)
                surf.blit(text(line, 8, col), (x + 8, yy))
                yy += 12
        center(surf, text("A/START: COOK   SELECT: BACK", 8, P.TEXT_DIM), 348)


def _wrap_px(s: str, chars: int) -> list[str]:
    from overquqed.hud import wrap

    return wrap(s, chars)


LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-*"


class ResultsScene(Scene):
    AUTO_LEAVE = 25.0

    def __init__(self, app, round_scene) -> None:
        super().__init__(app)
        self.rs = round_scene
        w = round_scene.world
        self.level = round_scene.level
        self.score = w.score
        self.stats = w.stats
        self.stars = stars_for(w.score, self.level.stars) if not self.level.tutorial else 3
        self.t = 0.0
        self.entering = not self.level.tutorial and hiscores.qualifies(app.hiscores, self.level.key, self.score)
        self.initials = [0, 0, 0]
        self.slot = 0
        self.rank = -1
        self.receipt = receipt_surface(w.stats.best) if w.stats.best else None
        if not self.entering:
            self._save(None)
        app.music("results")
        app.sfx("results")

    def _save(self, name: str | None) -> None:
        if name is None:
            hiscores.insert(self.app.hiscores, self.level.key, "", -1, self.stars)
        else:
            self.rank = hiscores.insert(self.app.hiscores, self.level.key, name, self.score, self.stars)
        hiscores.save(config.HISCORE_FILE, self.app.hiscores)

    def _name(self) -> str:
        return "".join(LETTERS[i] for i in self.initials)

    def update(self, dt: float, inp: Input) -> None:
        self.t += dt
        if self.entering:
            if inp.any_nav("up"):
                self.initials[self.slot] = (self.initials[self.slot] + 1) % len(LETTERS)
                self.app.sfx("blip")
            if inp.any_nav("down"):
                self.initials[self.slot] = (self.initials[self.slot] - 1) % len(LETTERS)
                self.app.sfx("blip")
            if inp.any_nav("left") and self.slot > 0:
                self.slot -= 1
            if inp.any_nav("right") and self.slot < 2:
                self.slot += 1
            if inp.confirm():
                self.app.sfx("confirm")
                if self.slot < 2:
                    self.slot += 1
                else:
                    self.entering = False
                    self._save(self._name())
            if self.t > self.AUTO_LEAVE + 20:
                self.entering = False
                self._save(self._name())
            return
        if (inp.confirm() and self.t > 1.0) or self.t > self.AUTO_LEAVE:
            self.app.sfx("confirm")
            self.app.switch(LevelSelectScene(self.app, self.rs.players))

    def on_idle(self) -> None:
        if self.entering:
            self.entering = False
            self._save(self._name())

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(P.BG)
        title = "TRAINING COMPLETE!" if self.level.tutorial else "SERVICE OVER!"
        center(surf, text(title, 16, P.GOLD, shadow=P.INK), 14)
        center(surf, text(self.level.name, 8, P.TEXT_DIM), 38)
        for s in range(3):
            shown = self.t > 0.4 + s * 0.35
            big = sprites.star(shown and s < self.stars, 3)
            x = INTERNAL_WIDTH // 2 - 45 + s * 32 - 13
            if shown:
                surf.blit(big, (x, 54 - (4 if s == 1 else 0)))
            else:
                surf.blit(sprites.star(False, 3), (x, 54 - (4 if s == 1 else 0)))
        center(surf, text(f"{self.score}", 32, P.WHITE, shadow=P.INK), 92)
        st = self.stats
        lines = [
            f"SERVED   {st.delivered}",
            f"REFUSED  {st.refused}",
            f"WALKED   {st.left}",
            f"AVG F    {st.avg_fidelity:.2f}" if st.delivered else "AVG F    -",
        ]
        for i, line in enumerate(lines):
            surf.blit(text(line, 8, P.TEXT), (40, 140 + i * 14))
        if self.receipt is not None:
            surf.blit(text("BEST DISH", 8, P.GOLD), (250, 134))
            surf.blit(self.receipt, (250, 146))
        if not self.level.tutorial:
            th = "  ".join(str(v) for v in self.level.stars)
            surf.blit(text(f"stars at {th}", 8, (110, 100, 130)), (40, 200))
        if self.entering:
            box = panel_box(260, 84, fill=P.HUD_BG, edge=P.GOLD)
            bx = (INTERNAL_WIDTH - 260) // 2
            surf.blit(box, (bx, 226))
            center(surf, text("NEW HIGH SCORE! TEAM NAME:", 8, P.GOLD), 236)
            for i in range(3):
                ch = LETTERS[self.initials[i]]
                sel = i == self.slot
                x = INTERNAL_WIDTH // 2 - 40 + i * 30
                col = P.WHITE if sel and int(self.t * 4) % 2 else P.TEXT if not sel else P.GOLD
                surf.blit(text(ch, 16, col, shadow=P.INK), (x, 254))
                if sel:
                    surf.fill(P.GOLD, (x, 274, 16, 2))
            center(surf, text("STICK: LETTER   A: NEXT", 8, P.TEXT_DIM), 290)
        else:
            if self.rank >= 0:
                center(surf, text(f"#{self.rank + 1} ON THE BOARD!", 8, P.GOOD), 250)
            if self.level.tutorial:
                center(surf, text("Now try the Superconducting Snack Bar!", 8, P.TEXT), 250)
            if int(self.t * 2) % 2 == 0:
                center(surf, text("A / START: CONTINUE", 8, P.WHITE), 300)
