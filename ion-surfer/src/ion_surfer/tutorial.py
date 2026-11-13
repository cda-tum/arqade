"""The HOW TO PLAY card, shown each time a match is started from the main menu.

It is read in a few seconds or mashed away: the goal in plain words, the
controls with the cabinet's printed button labels, and a demo. The demo is
not a picture: it is a second, private Game running the real physics and
drawn with the real draw code, its cursor driven by a short script that
loops. The card shows a window onto that world.

Dismissal (`Tutorial.can_dismiss`) waits MIN_AGE first, so the A or Start
that picked the mode, or its bounce, can't skip the card unseen. After that
any button on either pad does, and the game then treats every button still
held as used up (Controls.consume_buttons), so the dismissing press doesn't
also act in the match.
"""

from __future__ import annotations

import math
import random

import pygame
from arqade_common.input import KEYBOARD, PAD

from ion_surfer import game as G

MIN_AGE = 0.3  # s before a press can dismiss the card
LOOP = 6.0     # s of the scripted demo before it starts over

TEXT_C = (215, 222, 245)
FACE_C = (175, 186, 220)  # the face buttons X Y B A (and their keys), which steer like the stick
ARROW_KEYS = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}
BUTTON_OFF = (30, 38, 70)
BUTTON_EDGE = (70, 90, 150)
PANEL_BG = (10, 16, 36)

GOALS = {
    1: ["Raise and lower the electrodes to bend the trap.",
        "Your ion rolls along the curve. The view scrolls:",
        "don't let the ion fall behind. Go far, grab photons."],
    2: ["Raise and lower the electrodes to bend your trap.",
        "Your ion rolls along your curve. The view scrolls:",
        "keep up. Whoever surfs furthest wins."],
    3: ["Raise and lower the electrodes to bend the trap.",
        "Both of you shape ONE curve for ONE team ion.",
        "Keep it in the scrolling view as long as you can."],
    G.SANDBOX: ["No score here: a real quantum ion to play with.",
                "Kick it with the laser, squeeze or widen the trap,",
                "cool it back down. Watch its wave packet move."],
}
MODE_NAMES = {1: "1 PLAYER", 2: "2 PLAYERS: VERSUS", 3: "2 PLAYERS: CO-OP", G.SANDBOX: "SANDBOX"}

# The demo scripts. HOLDS: (from s, to s, pad, action) held in between;
# PRESSES: (at s, pad, action), one press each. SELS: each cursor's
# electrode at the start. Times are within one LOOP.
SURF_SCRIPT = dict(
    sels=[5],
    holds=[(0.4, 0.6, 0, "down"),      # lower the electrode right of the ion ...
           (1.0, 1.5, 0, "up"),        # ... raise the one under it: it rolls off
           (1.8, 2.0, 0, "down"),      # then flatten the walls ahead, one by one
           (2.3, 2.65, 0, "down"),
           (3.0, 3.6, 0, "down")],
    presses=[(0.8, 0, "left"), (1.7, 0, "right"), (1.75, 0, "right"), (2.2, 0, "right"),
             (2.9, 0, "right")],
    photons=[(615, 50), (660, 52), (705, 50)],
)
COOP_SCRIPT = dict(
    sels=[3, 5],                       # red behind the ion, blue ahead of it
    holds=[(0.4, 0.6, 0, "down"),      # blue clears the way ...
           (1.0, 1.5, 1, "up"),        # ... red pushes from behind
           (1.8, 2.0, 0, "down"),
           (2.3, 2.65, 0, "down"),
           (2.5, 2.9, 1, "up"),
           (3.0, 3.6, 0, "down")],
    presses=[(0.8, 1, "right"), (1.7, 0, "right"), (2.2, 0, "right"), (2.0, 1, "right"),
             (2.9, 0, "right")],
    photons=[(615, 50), (660, 52), (705, 50)],
)
SANDBOX_SCRIPT = dict(
    sels=[4, 7],
    holds=[(2.4, 2.9, 0, "up"),        # tighten the trap a little: it breathes
           (4.1, 5.7, 1, "cool")],     # red holds L: back to the ground state
    presses=[(0.5, 0, "select"), (1.6, 1, "select")],
    photons=[],
)
SCRIPTS = {1: SURF_SCRIPT, 2: SURF_SCRIPT, 3: COOP_SCRIPT, G.SANDBOX: SANDBOX_SCRIPT}
# The demo's window on the card, and the left edge of the part of the demo
# world it shows (the bottom of the world's screen, electrode strip included).
WINDOW = pygame.Rect(36, 242, 640, 340)
CROP_X = {1: 150, 2: 150, 3: 150, G.SANDBOX: 280}


class Demo:
    """A scripted few seconds of the real game, in a world of its own.

    It has its own random state: the burst particles use the random module,
    and the real match's footage must not depend on how long the card was up.
    """

    def __init__(self, mode):
        # versus is one surfer: the card shows what each player does
        self.mode = 3 if mode == 3 else G.SANDBOX if mode == G.SANDBOX else 1
        self.script = SCRIPTS[mode]
        self.crop = pygame.Rect(CROP_X[mode], G.H - WINDOW.h, WINDOW.w, WINDOW.h)
        self._rng = random.Random(7).getstate()
        self.world = self._isolated(lambda: G.Game(pygame.Surface((G.W, G.H))))
        self.reset()

    def _isolated(self, fn):
        outer = random.getstate()
        random.setstate(self._rng)
        try:
            return fn()
        finally:
            self._rng = random.getstate()
            random.setstate(outer)

    def reset(self):
        self.t = 0.0
        self._isolated(self._reset)

    def _reset(self):
        w = self.world
        w.start(self.mode, "SURFDEMO")
        w.next_spawn = math.inf  # no level: only what the script places
        for cu, sel in zip(w.cursors, self.script["sels"]):
            cu.sel = sel
        for x, y in self.script["photons"]:
            w.ents.append(G.Ent(type="photon", x=x, y=y, ph=x * 0.1))
        for p in w.controls.pads:
            p.src = {a: set() for a in p.src}

    def update(self, dt):
        t0, t1 = self.t, self.t + dt
        if t1 >= LOOP:
            self.reset()
            return
        self.t = t1
        w = self.world
        c = w.controls
        c.begin_frame()
        held = {(pad, act): False for _, _, pad, act in self.script["holds"]}
        for a, b, pad, act in self.script["holds"]:
            held[pad, act] |= a <= t1 < b
        for (pad, act), on in held.items():
            c.pads[pad].set(act, "demo", on)
        for at, pad, act in self.script["presses"]:
            if t0 < at <= t1:
                c.pads[pad].pressed.add(act)
        self._isolated(lambda: w.update(dt))
        if w.state != "play":  # the ion fell out for good: start over
            self.reset()

    def draw(self, surf, dest):
        w = self.world
        w.draw_world()
        if w.mode == G.SANDBOX:
            if w.sandbox.crystal:
                w.sandbox.draw_ions(w.screen, G.sy)
            else:
                w.sandbox.draw_packet(w.screen, G.sy)
        surf.blit(w.screen, dest, self.crop)


class Tutorial:
    def __init__(self, mode, game):
        self.mode = mode
        self.age = 0.0
        self.demo = Demo(mode)
        self.name = game.name  # names a control for the players' keys or pads
        self.devices = game.controls.devices
        self.bg = game.bg
        self.f_title = game.f_title
        self.f_label = G.load_font("Bungee-Regular.ttf", 22)
        self.f_key = G.load_font("Bungee-Regular.ttf", 15)
        self.f_prompt = G.load_font("Bungee-Regular.ttf", 28)
        self.f_body = G.load_font("Rubik-Medium.ttf", 22)
        self.f_ctrl = G.load_font("Rubik-Medium.ttf", 20)
        self.f_small = G.load_font("Rubik-Medium.ttf", 17)

    def can_dismiss(self):
        return self.age >= MIN_AGE

    def update(self, dt):
        self.age += dt
        self.demo.update(dt)

    # ---------- drawing ----------
    def draw(self, s):
        s.blit(self.bg, (0, 0))
        G.text(s, "HOW TO PLAY", self.f_title, G.GOLD, (G.W / 2, 46))
        G.text(s, MODE_NAMES[self.mode], self.f_small, G.TEXT_DIM, (G.W / 2, 88))

        left = pygame.Rect(36, 112, 640, 470)
        G.text(s, "GOAL", self.f_label, G.GOLD, (left.x, left.y + 4), "topleft")
        for i, ln in enumerate(GOALS[self.mode]):
            G.text(s, ln, self.f_body, TEXT_C, (left.x, left.y + 38 + i * 28), "topleft")
        self.demo.draw(s, WINDOW.topleft)
        pygame.draw.rect(s, BUTTON_EDGE, WINDOW.inflate(4, 4), 2, border_radius=4)

        right = pygame.Rect(712, 112, 452, 470)
        G.text(s, "CONTROLS", self.f_label, G.GOLD, (right.x, right.y + 4), "topleft")
        if self.mode == G.SANDBOX:
            self._sandbox_controls(s, right)
        else:
            self._game_controls(s, right)

        if self.age % 0.9 < 0.6:
            any_button = "ANY KEY" if self.devices.everyone_on(KEYBOARD) else "ANY BUTTON"
            G.text(s, f"PRESS {any_button} TO START", self.f_prompt, (255, 255, 255), (G.W / 2, 612))

    def _stick(self, s, center, color):
        x, y = center
        pygame.draw.circle(s, BUTTON_OFF, center, 26)
        pygame.draw.circle(s, BUTTON_EDGE, center, 26, 2)
        pygame.draw.line(s, (150, 160, 190), center, (x, y - 4), 6)
        pygame.draw.circle(s, color, (x, y - 6), 12)
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            tx, ty = x + dx * 38, y + dy * 38
            px, py = -dy, dx
            pygame.draw.polygon(s, color, [(tx + dx * 7, ty + dy * 7), (tx + px * 6, ty + py * 6),
                                           (tx - px * 6, ty - py * 6)])

    def _cluster(self, s, topleft, lit):
        """The cabinet's 2x3 buttons as printed: L X R over Y B A. `lit`
        maps a label to its colour; the rest are drawn dark."""
        x0, y0 = topleft
        for row, labels in enumerate(("LXR", "YBA")):
            for col, lab in enumerate(labels):
                c = (x0 + 20 + col * 46, y0 + 20 + row * 44)
                color = lit.get(lab)
                pygame.draw.circle(s, color or BUTTON_OFF, c, 18)
                pygame.draw.circle(s, BUTTON_EDGE if color is None else (255, 255, 255), c, 18, 2)
                G.text(s, lab, self.f_key, (8, 12, 28) if color else (90, 104, 150), (c[0], c[1] + 1))

    def _keycap(self, s, center, size, label, color=None):
        """One keyboard key: a rounded cap with the key's name (an arrow for
        the arrow keys), filled with `color` when the key is used."""
        rect = pygame.Rect(0, 0, size, size)
        rect.center = center
        pygame.draw.rect(s, color or BUTTON_OFF, rect, border_radius=6)
        pygame.draw.rect(s, BUTTON_EDGE if color is None else (255, 255, 255), rect, 2, border_radius=6)
        ink = (8, 12, 28) if color else (90, 104, 150)
        if label in ARROW_KEYS:
            (dx, dy), (x, y), k = ARROW_KEYS[label], center, size // 5
            pygame.draw.polygon(s, ink, [(x + dx * k, y + dy * k), (x - dx * k - dy * k, y - dy * k - dx * k),
                                         (x - dx * k + dy * k, y - dy * k + dx * k)])
        else:
            G.text(s, label, self.f_key, ink, (center[0], center[1] + 1))

    def _dir_keys(self, s, center, player, size=26, color=G.GOLD):
        """A keyboard player's four direction keys (W over A S D, or the
        arrows), centred on `center`, standing in for the stick."""
        x, y, step = center[0], center[1], size + 4
        for name, dx, dy in (("up", 0, -0.5), ("left", -1, 0.5), ("down", 0, 0.5), ("right", 1, 0.5)):
            self._keycap(s, (round(x + dx * step), round(y + dy * step)), size,
                         self.devices.label(name, player), color)

    def _key_block(self, s, topleft, player, lit, size=36, pitch=46):
        """A keyboard player's six keys laid out like the pad's 2x3 cluster
        (L X R over Y B A: F G H over C V B for P1); `lit` maps a pad label to
        the colour of the key in its place."""
        x0, y0 = topleft
        for row, labels in enumerate(("LXR", "YBA")):
            for col, lab in enumerate(labels):
                c = (x0 + size // 2 + 2 + col * pitch, y0 + size // 2 + 2 + row * (pitch - 2))
                self._keycap(s, c, size, self.devices.label(lab.lower(), player), lit.get(lab))

    def _on_keys(self, players):
        return any(self.devices[p] == KEYBOARD for p in players)

    def _row(self, s, x, y, key, what, key_color=TEXT_C, width=86):
        """A printed button name, then what it does, lined up at x + width
        (further right if the name is longer, e.g. a key's)."""
        width = max(width, self.f_key.size(key)[0] + 12)
        G.text(s, key, self.f_key, key_color, (x, y), "midleft")
        G.text(s, what, self.f_ctrl, TEXT_C, (x + width, y), "midleft")

    def _faces(self, player=None):
        """What X B Y A are called for a player's device: on the keyboard, the
        keys in their place ("G V C B"), for both players when player is None."""
        if player is None:
            if not (self.devices.everyone_on(PAD) or self.devices.everyone_on(KEYBOARD)):
                return ", ".join(f"{p.upper()}: {self._faces(p)}" for p in ("p1", "p2"))  # keys and buttons
            return " / ".join(dict.fromkeys(self._faces(p) for p in ("p1", "p2")))
        return " ".join(self.name(b, player) for b in ("x", "b", "y", "a"))

    def _game_controls(self, s, r):
        players = (self.devices.latest,) if self.mode == 1 else ("p1", "p2")
        if self._on_keys(players):
            if self.mode == 1:
                self._solo_key_controls(s, r, players[0])
            else:
                self._duo_key_controls(s, r)
            return
        who = {1: "Either pad works.", 2: "Each pad has its own curve.",
               3: "Each pad has its own cursor."}[self.mode]
        G.text(s, who, self.f_small, G.TEXT_DIM, (r.x, r.y + 38), "topleft")
        self._stick(s, (r.x + 40, r.y + 118), G.GOLD)
        G.text(s, "LEFT/RIGHT", self.f_key, TEXT_C, (r.x + 104, r.y + 100), "midleft")
        G.text(s, "pick an electrode", self.f_ctrl, TEXT_C, (r.x + 104, r.y + 112), "topleft")
        G.text(s, "UP/DOWN", self.f_key, TEXT_C, (r.x + 104, r.y + 156), "midleft")
        G.text(s, "raise / lower it", self.f_ctrl, TEXT_C, (r.x + 104, r.y + 168), "topleft")
        face = (175, 186, 220)
        self._cluster(s, (r.x + 2, r.y + 222), {"X": face, "Y": face, "B": face, "A": face})
        who = self.devices.latest if self.mode == 1 else None  # 1 player: either pad works
        G.text(s, f"{self._faces(who)} work", self.f_ctrl, TEXT_C, (r.x + 164, r.y + 236), "topleft")
        G.text(s, "like the stick:", self.f_ctrl, TEXT_C, (r.x + 164, r.y + 262), "topleft")
        G.text(s, "up, down, left, right", self.f_small, G.TEXT_DIM, (r.x + 164, r.y + 290), "topleft")
        self._row(s, r.x, r.y + 362, self.name("start", who), "pause")

    def _solo_key_controls(self, s, r, p):
        """1 PLAYER on the keyboard: the direction keys where the stick was,
        the six keys where the buttons were, each named."""
        G.text(s, "Either player's keys work.", self.f_small, G.TEXT_DIM, (r.x, r.y + 38), "topleft")
        self._dir_keys(s, (r.x + 40, r.y + 118), p)
        n = lambda k: self.name(k, p)  # noqa: E731
        G.text(s, f"{n('left')}/{n('right')}", self.f_key, TEXT_C, (r.x + 104, r.y + 100), "midleft")
        G.text(s, "pick an electrode", self.f_ctrl, TEXT_C, (r.x + 104, r.y + 112), "topleft")
        G.text(s, f"{n('up')}/{n('down')}", self.f_key, TEXT_C, (r.x + 104, r.y + 156), "midleft")
        G.text(s, "raise / lower it", self.f_ctrl, TEXT_C, (r.x + 104, r.y + 168), "topleft")
        self._key_block(s, (r.x + 2, r.y + 222), p, {"X": FACE_C, "Y": FACE_C, "B": FACE_C, "A": FACE_C})
        G.text(s, f"{self._faces(p)} work", self.f_ctrl, TEXT_C, (r.x + 164, r.y + 236), "topleft")
        G.text(s, "like the direction keys:", self.f_ctrl, TEXT_C, (r.x + 164, r.y + 262), "topleft")
        G.text(s, "up, down, left, right", self.f_small, G.TEXT_DIM, (r.x + 164, r.y + 290), "topleft")
        self._row(s, r.x, r.y + 362, n("start"), "pause")

    def _duo_key_controls(self, s, r):
        """VERSUS / CO-OP with someone on the keyboard: each player's keys (or
        pad) under their name, then a table with a column per player."""
        who = {2: "Each player has their own curve.", 3: "Each player has their own cursor."}[self.mode]
        G.text(s, who, self.f_small, G.TEXT_DIM, (r.x, r.y + 38), "topleft")
        heads, cols = [], []
        for i, p in enumerate(("p1", "p2")):
            x, keys = r.x + i * 236, self.devices[p] == KEYBOARD
            heads.append(f"{p.upper()} {'KEYS' if keys else 'PAD'}")
            G.text(s, heads[-1], self.f_key, G.TEXT_DIM, (x, r.y + 68), "midleft")
            face = {"X": FACE_C, "Y": FACE_C, "B": FACE_C, "A": FACE_C}
            if keys:
                self._dir_keys(s, (x + 36, r.y + 126), p, 22)
                self._key_block(s, (x + 86, r.y + 96), p, face, 26, 32)
                n = lambda k, p=p: self.name(k, p)  # noqa: E731
                cols.append([f"{n('left')}/{n('right')}", f"{n('up')}/{n('down')}", self._faces(p), n("start")])
            else:
                self._stick(s, (x + 36, r.y + 128), G.GOLD)
                self._cluster(s, (x + 84, r.y + 92), face)
                cols.append(["LEFT/RIGHT", "UP/DOWN", self._faces(p), self.name("start", p)])
        whats = ["pick an electrode", "raise / lower it", "like the stick", "pause"]
        widths = [max(self.f_key.size(k)[0] for k in col + [h]) + 16 for col, h in zip(cols, heads)]
        x = r.x
        for col, h, w in zip(cols, heads, widths):
            G.text(s, h, self.f_key, G.TEXT_DIM, (x, r.y + 206), "midleft")
            for i, k in enumerate(col):
                G.text(s, k, self.f_key, TEXT_C, (x, r.y + 242 + i * 36), "midleft")
            x += w
        for i, what in enumerate(whats):
            G.text(s, what, self.f_ctrl, TEXT_C, (x, r.y + 242 + i * 36), "midleft")

    def _sandbox_controls(self, s, r):
        face = (175, 186, 220)
        players = (("P1", G.BLUE, "remove ion", "add ion"),
                   ("P2", G.RED, "hold: cool", "slow cooling"))
        for col, (name, color, l_what, r_what) in enumerate(players):
            x = r.x + col * 236
            G.text(s, name, self.f_label, color, (x, r.y + 44), "topleft")
            player = name.lower()
            lit = {"L": color, "R": color, "X": face, "Y": face, "B": face, "A": face}
            if self.devices[player] == KEYBOARD:  # the keys in the buttons' places
                self._key_block(s, (x + 52, r.y + 40), player, lit)
            else:
                self._cluster(s, (x + 52, r.y + 40), lit)
            self._row(s, x, r.y + 146, self.name("l", player), l_what, color, 30)
            self._row(s, x, r.y + 176, self.name("r", player), r_what, color, 30)
        self._row(s, r.x, r.y + 230, self.name("stick"), "electrode / voltage")
        G.text(s, f"({self._faces()} work like the stick)", self.f_small, G.TEXT_DIM, (r.x, r.y + 252), "topleft")
        self._row(s, r.x, r.y + 300, self.name("select"), "laser kick")
        self._row(s, r.x, r.y + 336, self.name("start"), "pause")
