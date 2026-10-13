"""Menu-side scenes: title (with attract mode), join, level select, results."""

from __future__ import annotations

import math

import pygame

from overquqed import config, hiscores, palette as P, sprites
from overquqed.config import INTERNAL_WIDTH
from overquqed.fonts import text
from overquqed.game import Scene
from overquqed.guests import GUESTS
from overquqed.hud import panel_box, receipt_surface, rich, wrap
from overquqed.input import PLAYERS, Input
from overquqed.ket import ket_surface
from overquqed.levels import LEVELS, SNACK_BAR, star_thresholds
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


_BACKDROP: list[pygame.Surface] = []


def _title_backdrop() -> pygame.Surface:
    """The Snack Bar kitchen, darkened, behind the logo."""
    if not _BACKDROP:
        from overquqed.render import build_background
        from overquqed.world import World

        bg = build_background(World(SNACK_BAR)).copy()
        shade_ = pygame.Surface(bg.get_size(), pygame.SRCALPHA)
        shade_.fill((18, 14, 28, 150))
        bg.blit(shade_, (0, 0))
        _BACKDROP.append(bg)
    return _BACKDROP[0]


TITLE_ITEMS = ("PLAY", "QUIT")


class TitleScene(Scene):
    idle_resets = False

    def __init__(self, app) -> None:
        super().__init__(app)
        self.t = 0.0
        self.idle = 0.0
        self.index = 0  # into TITLE_ITEMS
        self.demo = None  # attract-mode demo round (a bot kitchen)
        self.guest_keys = list(GUESTS)
        self.backdrop = _title_backdrop()
        self.menu_band = pygame.Surface((INTERNAL_WIDTH, 74), pygame.SRCALPHA)
        self.menu_band.fill((18, 14, 28, 200))
        app.music("title")

    def update(self, dt: float, inp: Input) -> None:
        self.t += dt
        self.idle = 0.0 if inp.activity else self.idle + dt
        if inp.select_held_time >= config.BACK_HOLD_TO_QUIT:
            self.app.running = False
            return
        # Start always plays, whatever is selected; A picks the selected row,
        # and QUIT leaves for the cabinet's menu the way Start + Select does.
        for i, p in enumerate(PLAYERS):
            start = inp.was_pressed(p, "start")
            if not (start or inp.was_pressed(p, "pick")):
                continue
            if not start and TITLE_ITEMS[self.index] == "QUIT":
                self.app.running = False
                return
            self.app.sfx("confirm")
            self.app.switch(JoinScene(self.app, first=i))
            return
        if self.demo is None:
            for d, step in (("up", -1), ("down", 1)):
                if inp.any_nav(d):
                    self.index = (self.index + step) % len(TITLE_ITEMS)
                    self.app.sfx("blip")
        if self.demo is None and self.idle > config.ATTRACT_DELAY:
            from overquqed.attract import Demo

            self.demo = Demo()
            self.index = 0  # whoever walks up and presses A gets PLAY
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
        surf.blit(self.backdrop, (0, 0))
        draw_logo(surf, 34, self.t)
        center(surf, text("the ancilla kitchen of a", 8, P.TEXT, shadow=P.INK), 76)
        center(surf, text("fault-tolerant quantum computer", 8, P.TEXT, shadow=P.INK), 88)
        # guest intros
        gi = int(self.t / 4.0) % len(self.guest_keys)
        g = GUESTS[self.guest_keys[gi]]
        card = panel_box(400, 74, fill=(255, 250, 236))
        cx = (INTERNAL_WIDTH - 400) // 2
        surf.blit(card, (cx, 112))
        key = "alice" if g.key == "alicebob" else g.key
        frame = sprites.guest_frames(key)[0]
        surf.blit(pygame.transform.scale(frame, (32, 44)), (cx + 8, 122))
        if g.duo:
            surf.blit(pygame.transform.scale(sprites.guest_frames("bob")[0], (32, 44)), (cx + 30, 122))
        tx = cx + (66 if g.duo else 48)
        surf.blit(text(g.name.upper(), 8, (170, 120, 40)), (tx, 120))
        surf.blit(rich("orders " + "  ".join(f"|{o}>" for o in g.orders), P.INK), (tx, 133))
        for i, line in enumerate(wrap('"' + g.flavour + '"', (400 - (tx - cx) - 8) // 8)):
            surf.blit(rich(line, (90, 80, 100)), (tx, 150 + i * 11))
        # two chefs walking across the floor
        for idx, col in enumerate(P.PLAYER_COLORS):
            frames = sprites.chef_frames(col)
            ph = ((self.t / 14.0) + idx * 0.5) % 1.0
            x = -20 + ph * (INTERNAL_WIDTH + 40)
            f = 1 + int(self.t * 8) % 2
            surf.blit(frames[("right", f)], (round(x), 222))
            k = ket_surface(("+",) if idx else ("0",))
            surf.blit(k, (round(x) + 2, 208))
        surf.blit(self.menu_band, (0, 248))
        for i, item in enumerate(TITLE_ITEMS):
            sel = i == self.index
            label = text(item, 16, P.GOLD if sel else P.TEXT, shadow=P.INK)
            x = (INTERNAL_WIDTH - label.get_width()) // 2
            y = 254 + i * 22
            surf.blit(label, (x, y))
            if sel:
                bob = int(self.t * 4) % 2
                surf.blit(text(">", 16, P.GOLD, shadow=P.INK), (x - 22 - bob, y))
                surf.blit(text("<", 16, P.GOLD, shadow=P.INK), (x + label.get_width() + 6 + bob, y))
        center(surf, text("STICK: CHOOSE   A: OK   START: PLAY", 8, P.TEXT_DIM, shadow=P.INK), 304)
        center(surf, text("original game for the MQSF gaming corner", 8, (150, 140, 170)), 346)


class JoinScene(Scene):
    AUTO_GO = 10.0

    def __init__(self, app, first: int) -> None:
        super().__init__(app)
        self.joined = [first]
        self.t = 0.0

    def update(self, dt: float, inp: Input) -> None:
        self.t += dt
        if inp.back():
            self.app.sfx("back")
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
        center(surf, text("B: BACK", 8, (90, 80, 110)), 340)


class LevelSelectScene(Scene):
    def __init__(self, app, players: list[int]) -> None:
        super().__init__(app)
        self.players = players
        self.index = 0 if not app.session.get("played_tutorial") else 1
        self.t = 0.0
        self._thumbs: dict[str, pygame.Surface] = {}
        app.music("title")

    def update(self, dt: float, inp: Input) -> None:
        self.t += dt
        if inp.back():
            self.app.sfx("back")
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
            from overquqed.howto import HowToPlayScene

            self.app.switch(HowToPlayScene(self.app, level, self.players))

    def _thumb(self, level) -> pygame.Surface:
        thumb = self._thumbs.get(level.key)
        if thumb is None:
            from overquqed.render import build_background
            from overquqed.world import World

            bg = build_background(World(level))
            h = level_h = len(level.map) * 24
            kitchen = bg.subsurface(pygame.Rect(0, config.KITCHEN_Y, INTERNAL_WIDTH, level_h))
            thumb = pygame.transform.scale(kitchen, (INTERNAL_WIDTH // 2, h // 2))
            self._thumbs[level.key] = thumb
        return thumb

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(P.BG)
        center(surf, text("CHOOSE A KITCHEN", 16, P.GOLD, shadow=P.INK), 12)
        data = self.app.hiscores
        for i, level in enumerate(LEVELS):
            sel = i == self.index
            y = 40 + i * 44
            box = panel_box(200, 38, fill=P.HUD_BG if not sel else (70, 50, 90), edge=P.GOLD if sel else (70, 56, 86))
            surf.blit(box, (8, y))
            surf.blit(text(level.short, 8, P.WHITE if sel else P.TEXT), (18, y + 8))
            n = hiscores.best_stars(data, level.key)
            if level.tutorial:
                tag = "NEW? START HERE!" if not self.app.session.get("played_tutorial") else "TUTORIAL"
                surf.blit(text(tag, 8, P.GOOD if sel else P.TEXT_DIM), (18, y + 22))
            else:
                for s in range(3):
                    surf.blit(sprites.star(s < n), (18 + s * 11, y + 21))
                m, sec = divmod(int(level.duration), 60)
                surf.blit(text(f"{m}:{sec:02d}", 8, P.TEXT_DIM), (160, y + 22))
            if sel:
                surf.blit(text(">", 8, P.GOLD), (1 + (int(self.t * 4) % 2), y + 15))
        # detail panel
        level = LEVELS[self.index]
        x, w = 216, 256
        panel = panel_box(w, 312, fill=P.HUD_BG, edge=(70, 56, 86))
        surf.blit(panel, (x, 36))
        surf.blit(text(level.name, 8, P.GOLD), (x + 8, 44))
        thumb = self._thumb(level)
        pygame.draw.rect(surf, P.INK, (x + 7, 55, thumb.get_width() + 2, thumb.get_height() + 2))
        surf.blit(thumb, (x + 8, 56))
        yy = 60 + thumb.get_height() + 4
        for line in _wrap_px(level.blurb, 30):
            surf.blit(text(line, 8, P.TEXT), (x + 8, yy))
            yy += 11
        yy += 4
        kx = x + 8
        for key in level.recipes:
            k = ket_surface((key,))
            if kx + k.get_width() > x + w - 8:
                kx = x + 8
                yy += 13
            surf.blit(k, (kx, yy))
            kx += k.get_width() + 4
        yy += 15
        facts = []
        if not level.noise.is_noiseless:
            facts.append((f"T1 {level.noise.t1:.0f}s  T2 {level.noise.t2:.0f}s", P.KET_0))
        if level.gate_scale != 1:
            facts.append((f"slow gates x{level.gate_scale:g}", P.TEXT_DIM))
        if level.fridge_capacity:
            facts.append((f"only {level.fridge_capacity} qubits in the fridge!", P.WARN))
        if level.two_chef_press:
            facts.append(("two-chef Waffle Iron", P.GOLD))
        if level.cosmic_rays:
            facts.append(("cosmic rays!", P.BAD))
        for line, col in facts:
            surf.blit(text(line, 8, col), (x + 8, yy))
            yy += 11
        if not level.tutorial:
            rows = hiscores.table(data, level.key)
            yy = 252
            surf.blit(text("TOP 5", 8, P.GOLD), (x + 8, yy))
            for r in range(hiscores.TOP_N):
                if r < len(rows):
                    line = f"{r + 1}. {rows[r]['name']:<3} {rows[r]['score']:>5}"
                    col = P.TEXT
                else:
                    line = f"{r + 1}. ---   ---"
                    col = (90, 80, 110)
                surf.blit(text(line, 8, col), (x + 8 + (r // 3) * 124, yy + 13 + (r % 3) * 11))
        center(surf, text("A/START: COOK   B: BACK", 8, P.TEXT_DIM), 350)


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
        self.thresholds = star_thresholds(self.level, round_scene.solo)
        self.stars = stars_for(w.score, self.thresholds) if not self.level.tutorial else 3
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
            th = "  ".join(str(v) for v in self.thresholds)
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
