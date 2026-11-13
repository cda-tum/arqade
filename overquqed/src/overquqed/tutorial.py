"""Training Day: Chef Ket walks new cooks through three orders in < 60 s.

A tiny script over a normal, noise-free round: each step shows one or two
lines in the text box, highlights the stations involved and waits for a
world event (or A). Start skips the whole thing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from overquqed import palette as P, sprites
from overquqed.config import INTERNAL_HEIGHT, INTERNAL_WIDTH
from overquqed.fonts import text
from overquqed.hud import panel_box, rich
from overquqed.input import PLAYERS
from overquqed.render import tile_px

TYPE_SPEED = 45.0  # characters per second


@dataclass(frozen=True)
class Beat:
    lines: tuple[str, ...]
    wait: str  # "A" | an event kind ("fridge", "serve", "gate:X", ...)
    highlight: tuple[str, ...] = ()
    order: str | None = None  # spawn this order when the beat starts
    # The lines for keyboard players, if `lines` names pad buttons: {a} and
    # {b} become their keys (a pad's letters would name the wrong keys).
    keys: tuple[str, ...] = ()


SCRIPT = (
    Beat(("Welcome to the ancilla kitchen! I'm Chef Ket.",
          "Guests order quantum states. Let's cook!"), "A"),
    Beat(("Surface Code wants a |0>. Fresh qubits come",
          "out of the Dilution Fridge in |0>. Face it, press A."), "fridge", ("fridge",), "0",
         ("Surface Code wants a |0>, fresh from the Dilution",
          "Fridge. Face the Fridge and take one: {a}.")),
    Beat(("The arrow points up: that's |0>. Now put it on",
          "the PASS with A to serve it."), "serve", ("pass",), None,
         ("The arrow points up: that's |0>. Now put it on",
          "the PASS to serve it: {a}.")),
    Beat(("Next up: |1>. Put a fresh qubit on the Pauli-X",
          "Flipper (A), then tap B to flip it."), "gate:X", ("fridge", "x"), "1",
         ("Next up: |1>. Put a fresh qubit on the Pauli-X",
          "Flipper: {a}. Then flip it: tap {b}.")),
    Beat(("Flipped! X turns |0> into |1>.",
          "Pick it up (A) and serve it."), "serve", ("x", "pass"), None,
         ("Flipped! X turns |0> into |1>.",
          "Pick it up ({a}) and serve it.")),
    Beat(("Now |+>, a superposition! Put a |0> in the",
          "Hadamard Blender and HOLD B."), "gate:H", ("fridge", "h"), "+",
         ("Now |+>, a superposition! Put a |0> in the",
          "Hadamard Blender and HOLD {b}.")),
    Beat(("See the arrow swing onto the equator?",
          "Blend it again and it un-blends! Serve it now."), "serve", ("h", "pass")),
    Beat(("Guests only accept fidelity F >= 0.8. Below that",
          "threshold, error correction can't keep up!"), "A"),
    Beat(("Out there qubits decohere: serve them fresh.",
          "Training done. Good luck, chefs!"), "A"),
)


class Tutorial:
    wants_start = True  # Start skips instead of pausing
    show_hints = True

    def __init__(self, scene) -> None:
        self.scene = scene
        self.world = scene.world
        self.i = -1
        self.shown = 0.0
        self.t = 0.0
        self.done = False
        self.oops = 0.0
        self._next()

    @property
    def beat(self) -> Beat:
        return SCRIPT[self.i]

    def _who(self) -> str | None:
        """The one player in training, or None for both."""
        players = self.scene.players
        return PLAYERS[players[0]] if len(players) == 1 else None

    @property
    def lines(self) -> tuple[str, ...]:
        """The beat's lines, naming the keys for keyboard players."""
        beat, inp = self.beat, self.scene.app.inp
        who = self._who()
        if not beat.keys or inp.on_pads(who):
            return beat.lines
        return tuple(line.format(a=inp.name("a", who), b=inp.name("b", who)) for line in beat.keys)

    def _next(self) -> None:
        self.i += 1
        self.shown = 0.0
        self.t = 0.0
        if self.i >= len(SCRIPT):
            self._finish()
            return
        if self.beat.order:
            order = self.world.orders.spawn(self.world.t, self.beat.order, "surface")
            order.patience = order.remaining = 9999.0
            self.scene._on_event(("order", order))

    def _finish(self) -> None:
        if self.done:
            return
        self.done = True
        from overquqed.scenes import ResultsScene

        self.scene.app.switch(ResultsScene(self.scene.app, self.scene))

    def filter_inputs(self, inputs, inp):
        return inputs

    def on_event(self, ev: tuple) -> None:
        if self.done or self.i >= len(SCRIPT):
            return
        kind = ev[0]
        if kind == "refuse":
            self.oops = 3.0
        want = self.beat.wait
        if want == kind or (want.startswith("gate:") and kind == "gate" and ev[1] == want[5:]):
            self._next()

    def update(self, dt: float, inp) -> None:
        if self.done:
            return
        self.t += dt
        self.oops = max(0.0, self.oops - dt)
        full = sum(len(line) for line in self.lines)
        self.shown = min(full, self.shown + dt * TYPE_SPEED)
        if inp.any_pressed("start"):
            self._finish()
            return
        if self.beat.wait == "A" and inp.any_pressed("pick"):
            if self.shown < full:
                self.shown = full
            elif self.t > 0.3:
                self.scene.app.sfx("blip")
                self._next()

    def draw(self, surf: pygame.Surface, t: float) -> None:
        if self.done or self.i >= len(SCRIPT):
            return
        beat = self.beat
        # pulsing highlight round the stations this step is about
        pulse = int(t * 4) % 2 == 0
        for st in self.world.stations.values():
            if st.kind in beat.highlight:
                px, py = tile_px(st.x, st.y)
                col = P.GOLD if pulse else P.WHITE
                pygame.draw.rect(surf, P.INK, (px - 2, py - 2, 28, 28), 1)
                pygame.draw.rect(surf, col, (px - 1, py - 1, 26, 26), 2)
        # the text box
        h = 52
        y = INTERNAL_HEIGHT - h - 4
        box = panel_box(INTERNAL_WIDTH - 8, h, fill=(255, 250, 236))
        surf.blit(box, (4, y))
        portrait = pygame.transform.scale(sprites.portrait("chefket"), (32, 32))
        pygame.draw.rect(surf, P.INK, (9, y + 9, 36, 36))
        pygame.draw.rect(surf, (255, 226, 170), (10, y + 10, 34, 34))
        surf.blit(portrait, (11, y + 11))
        surf.blit(text("CHEF KET", 8, (170, 120, 40)), (52, y + 6))
        remaining = int(self.shown)
        lines = self.lines
        for li, line in enumerate(lines):
            part = line[:max(0, remaining)]
            remaining -= len(line)
            if part:
                surf.blit(rich(part, P.INK), (52, y + 19 + li * 12))
        full = sum(len(line) for line in lines)
        if self.shown >= full and beat.wait == "A" and int(t * 3) % 2 == 0:
            inp, who = self.scene.app.inp, self._who()
            a = text(f"{inp.name('a')} >" if inp.on_pads(who) else f"{inp.name('a', who)}: NEXT", 8, (200, 60, 60))
            surf.blit(a, (INTERNAL_WIDTH - 12 - a.get_width(), y + h - 12))
        skip = text(f"{self.scene.app.inp.name('start')}: SKIP", 8, P.TEXT_DIM, shadow=P.INK)
        surf.blit(skip, (INTERNAL_WIDTH - skip.get_width() - 4, y - 11))
        if self.oops > 0:
            msg = rich("Not quite! Check the recipe on the ticket.", P.BAD, outline=P.INK)
            surf.blit(msg, ((INTERNAL_WIDTH - msg.get_width()) // 2, y - 12 - round(2 * math.sin(t * 8))))
