"""CLIMB! (from Qlimbers): your climber clings to Qlimbers' stone tower. The
floor above holds a target ket, and your qubit's state is shown beside it.
Three gate cards from X, Y, Z and H lie below; exactly one of them turns the
state into the target in one step. The stick picks a card, A applies it,
and then you push up to climb. Pushing up on the wrong state stuns you for
a moment, as in Qlimbers; a wrong card can be undone by applying it again.

The rules are Qlimbers' own (quantum.py): states are compared exactly,
global phase included, and every ket is drawn with its phase (`-|1>`,
`i|+>`), so what's shown is what's compared. The first time, and at low
levels, every state is phase-free (|0>, |1>, |+>, |->) and no decoy lands on
the target's direction with another phase. Later the start can be any of
Qlimbers' 16 states and the target may differ only by a phase (Z on |1>
makes -|1>), which is where Y earns its place.

Doing nothing never climbs, so it runs out the clock.
"""

from __future__ import annotations

import math

import pygame

from planck_time import palette as P
from planck_time.microgames.base import IDLE, H, W, Microgame, PlayerInput, register
from planck_time.pixel import blit_center, outlined, result_overlay

# --- the qubit, as in Qlimbers' quantum.py ------------------------------------------------

R2 = 1 / math.sqrt(2)
GATES = {
    "X": lambda s: (s[1], s[0]),
    "Y": lambda s: (-1j * s[1], 1j * s[0]),
    "Z": lambda s: (s[0], -s[1]),
    "H": lambda s: (R2 * (s[0] + s[1]), R2 * (s[0] - s[1])),
}
KINDS = tuple(GATES)
DIRECTIONS = {"|0>": (1, 0), "|1>": (0, 1), "|+>": (R2, R2), "|->": (R2, -R2)}
PHASES = {"": 1, "-": -1, "i": 1j, "-i": -1j}
STATES = {pre + ket: (ph * a0, ph * a1) for ket, (a0, a1) in DIRECTIONS.items() for pre, ph in PHASES.items()}
PLAIN = tuple(DIRECTIONS)  # the four phase-free states


def same(a, b) -> bool:
    """Exact equality, global phase included (Qlimbers' states_equal)."""
    return abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) < 1e-6


def same_direction(a, b) -> bool:
    """Equal up to a global phase: the same point on the Bloch sphere."""
    return abs(abs(a[0] * b[0].conjugate() + a[1] * b[1].conjugate()) - 1) < 1e-6


def ket(s) -> str:
    """The state as Qlimbers writes it: a phase prefix and a ket."""
    for name, ref in STATES.items():
        if same(s, ref):
            return name
    raise ValueError(f"not one of Qlimbers' 16 states: {s}")


# --- tuning ---------------------------------------------------------------------------

READY = 0.6  # seconds the cards take to deal in, before any input counts (at level 0)
STUN = 0.8  # seconds a wrong push-up locks you out (at level 0): two still fit in 5 s
CLIMB_TIME = 0.45  # the win: the tower scrolls down one floor
THINK = 0.3  # the bot looks before it moves...
BOT_STEP = 0.15  # ...moves the cursor this often...
BOT_SETTLE = 0.15  # ...and waits this long before pressing A, then before pushing up
PHASED_FROM = 2  # the level from which phases come in (or the second appearance)

# --- the look: Qlimbers' sky, stone tower and climber, snapped to the GBA grid ---------

SKY_TOP, SKY_BOTTOM = (120, 168, 232), (192, 224, 248)
SUN, CLOUD = (248, 232, 160), (248, 248, 248)
GRASS, GRASS_DARK = (88, 152, 72), (72, 128, 56)
TOWER, TRIM = (128, 120, 112), (88, 80, 72)
TARGET, UNKNOWN = (232, 176, 56), (96, 88, 80)
STUN_RED, HINT = (216, 56, 56), (248, 232, 88)
CLIMBER = P.GOLD
HORIZON = 100
TOWER_RECT = pygame.Rect(8, 0, 96, 118)  # runs off the top: there are floors above
# (and never a negative y: pygame 2.5.2 fills such a rect from 0 at its full height)
BASE = TOWER_RECT.bottom  # 118, the bottom of the floor you stand on
BAND = 32
CARD = 24
CARD_Y = 116
CARD_X = (146, 180, 214)
YOU = (180, 72)  # the state's tag, level with the target floor


def lerp(a, b, k):
    return tuple(round((x + (y - x) * k) / 8) * 8 for x, y in zip(a, b))


_SCENE: dict = {}


def scene() -> pygame.Surface:
    """Qlimbers' backdrop (a sky gradient, the sun, two clouds, grass), drawn once."""
    if "bg" not in _SCENE:
        s = pygame.Surface((W, H))
        bands = 10
        for i in range(bands):
            y0, y1 = HORIZON * i // bands, HORIZON * (i + 1) // bands
            s.fill(lerp(SKY_TOP, SKY_BOTTOM, i / (bands - 1)), (0, y0, W, y1 - y0))
        pygame.draw.circle(s, SUN, (222, 18), 11)
        for cx, cy in ((132, 18), (196, 42)):
            for dx, dy, r in ((-8, 2, 5), (0, -2, 7), (8, 2, 5), (14, 2, 4)):
                pygame.draw.circle(s, CLOUD, (cx + dx, cy + dy), r)
        s.fill(GRASS, (0, HORIZON, W, H - HORIZON))
        s.fill(GRASS_DARK, (0, HORIZON, W, 3))
        for x in range(4, W, 11):
            pygame.draw.line(s, GRASS_DARK, (x, HORIZON + 2), (x, HORIZON + 4 + (x % 3) * 2), 1)
        _SCENE["bg"] = s
    return _SCENE["bg"]


def smooth(k: float) -> float:
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


@register
class Climb(Microgame):
    VERB = "CLIMB!"
    INPUT = "stick+a"
    CAPTION = "Gates turn one state into another"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        self.phased = level >= PHASED_FROM or self.appearance >= 1
        start, gate, decoys = self._round()
        self.state = self.start = STATES[start]
        self.target = GATES[gate](self.state)
        self.right = gate
        self.cards = self.rng.sample([gate, *decoys], 3)
        self.cursor = 1
        self.moved_at = 0.0
        self.applied_at = -9.0  # when, and which card, A last applied
        self.applied = -1
        self.stunned_until = 0.0
        self.stun_at = -9.0
        self.up_was_held = False
        self.ready = READY / self.speed
        self.stun_len = STUN / self.speed

    def _round(self) -> tuple[str, str, list[str]]:
        """(start ket, the right gate, two decoys): the right gate maps the start
        onto a different state, and neither decoy maps it onto the target."""
        rng = self.rng
        while True:
            start = rng.choice(tuple(STATES) if self.phased else PLAIN)
            s = STATES[start]
            gate = rng.choice(KINDS)
            target = GATES[gate](s)
            if same(target, s) or (not self.phased and ket(target) not in PLAIN):
                continue
            # first time round, no decoy lands on the target's direction with another phase
            decoys = [k for k in KINDS if k != gate
                      and (self.phased or not same_direction(GATES[k](s), target))]
            if len(decoys) >= 2:
                return start, gate, rng.sample(decoys, 2)

    # --- the rules -----------------------------------------------------------------------

    @property
    def matched(self) -> bool:
        return same(self.state, self.target)

    @property
    def stunned(self) -> bool:
        return self.t < self.stunned_until

    def step(self, dt: float, inp: PlayerInput) -> None:
        up = inp.step[1] < 0 or inp.stick[1] <= -0.5
        pushed = up and not self.up_was_held
        self.up_was_held = up
        if self.t < self.ready or self.stunned:
            return
        if inp.step[0]:
            self.cursor = max(0, min(2, self.cursor + inp.step[0]))
            self.moved_at = self.t
        if inp.a:
            self.state = GATES[self.cards[self.cursor]](self.state)
            self.applied, self.applied_at = self.cursor, self.t
        if pushed:
            if self.matched:
                self.win()
            else:
                self.stunned_until = self.t + self.stun_len
                self.stun_at = self.t

    def bot(self) -> PlayerInput:
        if self.t < self.ready + THINK or self.stunned:
            return IDLE
        if self.matched:
            if self.t - self.applied_at < BOT_SETTLE:
                return IDLE
            return PlayerInput(stick=(0.0, -1.0), step=(0, -1))
        goal = self.cards.index(self.right)
        since = self.t - self.moved_at
        if goal != self.cursor:
            return PlayerInput(step=(1 if goal > self.cursor else -1, 0)) if since >= BOT_STEP else IDLE
        return PlayerInput(a=True, a_held=True) if since >= BOT_SETTLE else IDLE

    # --- drawing ---------------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        surf.blit(scene(), (0, 0))
        won = self.result is True
        climb = smooth(self.since_end / CLIMB_TIME) if won else 0.0
        self._tower(surf, climb)
        self._climber(surf, climb)
        self._you(surf)
        self._cards(surf)
        if self.result is None and self.matched and self.t >= self.ready and int(self.t * 4) % 2 == 0:
            blit_center(surf, outlined("PUSH UP!", 8, HINT), (YOU[0], YOU[1] - 26))
        if self.stunned and self.result is None:
            self._stun_flash(surf)
        if self.matched and self.result is None:
            hint = "PUSH UP TO CLIMB!"
        else:
            hint = "MATCH THE FLOOR, PUSH UP"
        blit_center(surf, outlined(hint, 8, P.WHITE), (W // 2, H - 9))
        result_overlay(surf, self.result, self.since_end, seed=7)

    def _tower(self, surf: pygame.Surface, climb: float) -> None:
        body = TOWER_RECT
        surf.fill(P.shade(TOWER, 0.55), body.move(3, 4))
        surf.fill(TOWER, body)
        floor = 1 if self.result is True else 0
        surf.set_clip(body)
        for f in range(0, 5):
            bottom = round(BASE - (f - climb) * BAND)
            band = pygame.Rect(body.x, bottom - BAND, body.w, BAND)
            if band.bottom < 0 or band.top > BASE:
                continue
            pygame.draw.line(surf, TRIM, (band.left + 5, band.bottom), (band.right - 5, band.bottom), 2)
            if f == 0:  # the floor you started on: just a window
                window = pygame.Rect(0, 0, 10, 16)
                window.center = band.center
                pygame.draw.rect(surf, P.shade(TOWER, 0.4), window, border_radius=2)
                continue
            # the target floor (green once climbed), then the unknown floors above
            fill = (P.GOOD_DARK if floor else TARGET) if f == 1 else UNKNOWN
            label = ket(self.target) if f == 1 else "?"
            panel = band.inflate(-12, -12)
            pygame.draw.rect(surf, P.shade(TOWER, 0.35), panel.inflate(6, 6), border_radius=3)
            pygame.draw.rect(surf, fill, panel, border_radius=3)
            size = 16 if len(label) <= 5 else 8
            blit_center(surf, outlined(label, size, P.WHITE, shadow=False), panel.center)
        surf.set_clip(None)
        # the stone edges, and the ground the tower stands on
        for x in (body.left + 1, body.left + 4, body.right - 2, body.right - 5):
            pygame.draw.line(surf, TRIM, (x, 0), (x, BASE), 3)
        surf.fill(GRASS_DARK, (body.x - 4, BASE - 1, body.w + 10, 3))

    def _climber(self, surf: pygame.Surface, climb: float) -> None:
        """Qlimbers' climber on the tower's right wall, feet on the target
        floor's ledge: reaching and pulling on a climb, jittering when stunned."""
        wall_x, y = TOWER_RECT.right, BASE - BAND
        if self.result is True:
            reach = math.sin(climb * math.pi)
            y -= round(reach * 5)
        else:
            reach = math.sin(self.t * 5.0) * 0.5 + 0.5
        jitter = round(math.sin((self.t - self.stun_at) * 50.0) * 3) if self.stunned else 0
        if self.result is False:
            reach = 0.0
        body_x = wall_x + 9 + jitter
        hip = (body_x, y - 9)
        shoulder = (body_x - 4, hip[1] - 14)
        head = (shoulder[0] - 2, shoulder[1] - 8)
        limbs = [
            (hip, (wall_x, y), 3), (hip, (wall_x, y - 10 - round(reach * 6)), 3),
            (shoulder, (wall_x, shoulder[1] - 10 - round(reach * 10)), 3),
            (shoulder, (wall_x, shoulder[1] + 2 - round((1 - reach) * 8)), 3),
            (hip, shoulder, 4),
        ]
        for a, b, w in limbs:  # an ink outline first, so it reads on stone and sky
            pygame.draw.line(surf, P.INK, a, b, w + 2)
        pygame.draw.circle(surf, P.INK, head, 7)
        for a, b, w in limbs:
            pygame.draw.line(surf, CLIMBER, a, b, w)
        pygame.draw.circle(surf, CLIMBER, head, 6)
        surf.fill(P.INK, (head[0] - 3, head[1] - 1, 2, 2))

    def _you(self, surf: pygame.Surface) -> None:
        """Your state, as Qlimbers' "YOU:" readout, level with the target floor."""
        box = pygame.Rect(0, 0, 100, 34)
        box.center = YOU
        pop = self.t - self.applied_at < 0.15
        pygame.draw.rect(surf, P.INK, box.inflate(4, 4), border_radius=5)
        pygame.draw.rect(surf, P.NIGHT, box, border_radius=4)
        edge = {True: P.GOOD, False: STUN_RED}.get(self.result, P.GOOD if self.matched else P.SLATE)
        pygame.draw.rect(surf, P.WHITE if pop else edge, box, 2, border_radius=4)
        surf.blit(outlined("YOU:", 8, P.MIST, shadow=False), (box.x + 4, box.y + 3))
        label = ket(self.state)
        color = P.GOOD if self.matched else P.WHITE
        blit_center(surf, outlined(label, 16 if len(label) <= 5 else 8, color), (box.centerx + 4, box.centery + 5))

    def _cards(self, surf: pygame.Surface) -> None:
        """The gate cards as Qlimbers' stone buttons, dealt up from below."""
        deal = smooth(self.t / self.ready) if self.ready else 1.0
        for i, kind in enumerate(self.cards):
            r = pygame.Rect(0, 0, CARD, CARD)
            r.center = (CARD_X[i], round(CARD_Y + (1 - deal) * 60 + 12 * (1 - deal) * i))
            flash = i == self.applied and self.t - self.applied_at < 0.2
            fill = P.WHITE if flash else TOWER
            if i == self.cursor and self.result is None:
                pygame.draw.rect(surf, P.WHITE, r.inflate(8, 8), border_radius=6)
            pygame.draw.rect(surf, P.INK, r.inflate(2, 2), border_radius=4)
            pygame.draw.rect(surf, fill, r, border_radius=3)
            pygame.draw.rect(surf, TRIM, r, 2, border_radius=3)
            blit_center(surf, outlined(kind, 16, P.INK if flash else P.WHITE, shadow=False), (r.centerx + 1, r.centery + 1))
        if self.result is None and deal >= 1:
            x, y = CARD_X[self.cursor], CARD_Y - CARD // 2 - 6 + round(2 * math.sin(self.t * 9))
            pygame.draw.polygon(surf, P.INK, ((x - 8, y - 9), (x + 8, y - 9), (x, y + 1)))
            pygame.draw.polygon(surf, P.GOLD, ((x - 5, y - 7), (x + 5, y - 7), (x, y - 2)))

    def _stun_flash(self, surf: pygame.Surface) -> None:
        """Qlimbers' stun: red ticks bursting round the climber, and WRONG!"""
        k = (self.t - self.stun_at) / self.stun_len
        cx, cy = TOWER_RECT.right + 8, BASE - BAND - 22
        for i in range(8):
            a = i * math.pi / 4
            r0 = 10 + 6 * k
            p0 = (cx + math.cos(a) * r0, cy + math.sin(a) * r0)
            p1 = (cx + math.cos(a) * (r0 + 5), cy + math.sin(a) * (r0 + 5))
            pygame.draw.line(surf, STUN_RED, p0, p1, 2)
        blit_center(surf, outlined("WRONG!", 8, STUN_RED), (cx + 14, cy - 22))
