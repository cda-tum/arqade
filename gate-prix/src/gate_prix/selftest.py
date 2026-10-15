"""`--selftest SECONDS`: a scripted session through the real loop, renderer and match.

It plays, as a visitor would, and checks the match at every turn:
1. the title, untouched until the attract race starts, then a while of it; the menu: BOTS
   stepped down and back up with left and right (clamped at 5), a held stick down onto
   QUIT (it stays there), a held diagonal up a row (and no value changed), back on QUIT;
2. Start on QUIT: a 1 player, 5 TOUGH bots match (Start never quits), its HOW TO PLAY card
   (a press in its first 0.3 s ignored, then X goes on), the countdown, a race steered by
   the AI with the stick mashed on top (A
   pressed at random, Select tapped, Start to pause, the pause menu moved and B to
   resume), through the CIRCUIT CHECK (all 16 gates before it, a freeze of about a
   second while the car drives on, no gate after it), to the finish and the result; a
   mashed A in the result's lock is ignored, then A rematches; in the rematch, pause and
   QUIT TO TITLE with A held on: the title must wait for it to be let go;
3. PLAYERS 2, BOTS 2, LEVEL BRUTAL (picked with the stick): the card, then a race of four
   with both pads driven the same way, to the result, B to the title;
4. a race left untouched: 60 s later it is back on the title, its rows reset (1 player,
   5 bots, TOUGH);
5. QUIT, with A: the game exits (the script fails if it is still running a frame later).

It stops after SECONDS of game time (exit 0 if every check held until then) or at the
end of the script. With --shots DIR it saves a screenshot of every screen on the way.
Game time runs as fast as the machine renders.
"""

from __future__ import annotations

import os
import random
import time

import pygame

from gate_prix import ai, config
from gate_prix.match import (COUNTDOWN, HOWTO, PAUSED, RACE, RESULT, TITLE, FrameInput,
                             PlayerInput)

DT = 1.0 / config.FPS


class SelftestError(AssertionError):
    pass


def check(ok: bool, what: str) -> None:
    if not ok:
        raise SelftestError(what)


class Script:
    def __init__(self, match, seed: int, shots: str | None) -> None:
        self.match = match
        self.rng = random.Random(f"{seed}:selftest")
        self.shots = shots
        self.time = 0.0
        self.done = False
        self.error: str | None = None
        self.pending: str | None = None
        self.taken: list[str] = []
        self._drivers: dict[str, ai.Driver] = {}
        self._race_id = None
        self._gen = self._script()
        self._wall = time.perf_counter()
        if shots:
            os.makedirs(shots, exist_ok=True)

    # --- The loop's side ---------------------------------------------------------------------

    def next(self) -> FrameInput:
        self.time += DT
        try:
            return next(self._gen)
        except StopIteration:
            self.done = True
        except SelftestError as e:
            self.error = f"{e} (at {self.time:.1f} s, state {self.match.state})"
            self.done = True
        return FrameInput()

    def after_draw(self, surface: pygame.Surface) -> None:
        if self.pending and self.shots:
            path = os.path.join(self.shots, f"{len(self.taken) + 1:02d}-{self.pending}.png")
            pygame.image.save(surface, path)
            self.taken.append(path)
        self.pending = None

    def finish(self) -> int:
        if self.error:
            print("SELFTEST FAILED:", self.error)
            return 1
        frames = round(self.time / DT)
        ms = (time.perf_counter() - self._wall) * 1000 / max(1, frames)
        print(f"selftest ok: {self.time:.1f} s of game time, {frames} frames, {ms:.1f} ms a frame"
              + (f", {len(self.taken)} screenshots in {self.shots}" if self.shots else ""))
        return 0

    def shot(self, name: str) -> None:
        """Screenshot the frame after the next one drawn (in drive_until: while driving)."""
        self.pending = name

    def snap(self, name: str):
        """Screenshot the screen as it is now: one untouched frame, then saved."""
        self.pending = name
        yield FrameInput()

    # --- Input -------------------------------------------------------------------------------

    def _drive(self, mash: float = 0.0) -> FrameInput:
        """Both players' pads, steered by bots (one per player car) with mashing on top."""
        m = self.match
        race = m.race
        if race is None or m.attract:
            return FrameInput()
        if id(race) != self._race_id:
            self._race_id = id(race)
            self._drivers = {p: ai.Driver(p, "TOUGH", self.rng.randrange(1000)) for p in m.players}
        players = {}
        for p in ("p1", "p2"):
            if p not in self._drivers or m.state != RACE:
                players[p] = PlayerInput()
                continue
            c = self._drivers[p].controls(race)
            steer = max(-1.0, min(1.0, c.steer + self.rng.uniform(-mash, mash)))
            a = self.rng.random() < 0.04 * (mash > 0) or c.item
            players[p] = PlayerInput(steer=steer, brake=c.brake, a=a, held=a)
        return FrameInput(players, activity=True)

    def _press(self, player="p1", **kw) -> FrameInput:
        held = any(kw.get(k) for k in ("a", "b", "start"))
        kw.setdefault("button", held)
        players = {p: PlayerInput() for p in ("p1", "p2")}
        players[player] = PlayerInput(held=held, **kw)
        return FrameInput(players, activity=True)

    def idle(self, seconds: float):
        for _ in range(round(seconds / DT)):
            yield FrameInput()

    def tap(self, player="p1", **kw):
        yield self._press(player, **kw)
        yield FrameInput()  # let go

    def drive_until(self, done, limit: float, mash: float = 0.3, shots=()):
        """Drive both pads until done() or `limit` seconds; `shots` are (race time, name)."""
        todo = sorted(shots)
        t = 0.0
        while not done():
            check(t < limit, f"still racing after {limit:.0f} s")
            if todo and self.match.race is not None and self.match.race.time >= todo[0][0]:
                self.shot(todo.pop(0)[1])
            frame = self._drive(mash)
            if self.rng.random() < 0.01:  # a Select tap, alone: never quits or pauses
                frame.players["p1"] = PlayerInput(steer=frame.players["p1"].steer, held=True)
            yield frame
            t += DT

    # --- The script --------------------------------------------------------------------------

    def _script(self):
        m = self.match
        yield from self.idle(0.5)
        check(m.state == TITLE and (m.mode, m.bot_count, m.level) == (1, 5, "TOUGH")
              and not m.attract, "the title at 1 player, 5 bots, TOUGH")
        yield from self.snap("title")
        yield from self.idle(config.ATTRACT_DELAY)
        check(m.attract and m.race is not None and m.race.players == 2, "the attract race")
        yield from self.idle(8.0)
        yield from self.snap("attract")
        yield from self.idle(DT)
        check(m.race.time > 7.0, "the attract race drives")

        # the menu: BOTS down and up, down onto QUIT and back up, then Start on QUIT
        yield from self.tap(nav=(0, 1))
        check(m.title_index == 0 and not m.attract, "the stick stops the demo, and only that")
        yield from self.tap(nav=(0, 1))
        check(m.title_index == 1, "down: BOTS")
        yield from self.tap(nav=(-1, 0), stick=(-1, 0))
        check(m.bot_count == 4 and m.title_index == 1, "left: one bot fewer")
        for _ in range(2):
            yield from self.tap(nav=(1, 0), stick=(1, 0))
        check(m.bot_count == 5, "right: back to 5, and no further")
        yield from self.snap("title-bots")
        for k in range(40):  # the stick held down, auto-repeating: QUIT, and it stays there
            yield self._press(nav=(0, 1) if k == 0 or self.rng.random() < 0.2 else (0, 0),
                              stick=(0, 1))
            check(m.title_index == 2, "a held stick steps once per push: LEVEL")
        yield from self.idle(DT)  # let go
        yield from self.tap(nav=(0, 1))
        check(m.title_index == 3, "QUIT, the last row")
        for _ in range(3):
            yield from self.tap(nav=(0, 1), stick=(0, 1))
        check(m.title_index == 3, "the stick stops on QUIT")
        yield from self.snap("title-quit")
        for k in range(60):  # held up-right, the y axis two frames late: one step up
            yield self._press(nav=(1 if k % 9 == 0 else 0, -1 if k == 2 else 0),
                              stick=(1, -1 if k >= 2 else 0))
            check(m.title_index == (3 if k < 2 else 2), "a held diagonal steps once")
        check(m.level == "TOUGH", "a diagonal never changes a value")
        yield from self.tap(nav=(0, 1))
        check(m.title_index == 3, "back on QUIT")
        yield from self.tap("p2", start=True)
        check(m.state == HOWTO and (m.mode, m.bot_count, m.level) == (1, 5, "TOUGH")
              and not m.quit_requested, "Start on QUIT begins the race, with the card")
        yield from self.idle(0.1)
        yield from self.tap(a=True)
        check(m.state == HOWTO, "the card ignores a press in its first 0.3 s")
        yield from self.idle(0.6)
        yield from self.snap("howto-1p")
        yield from self.tap("p2", button=True)  # X: any button goes on
        check(m.state == COUNTDOWN and m.race.players == 1 and len(m.race.racers) == 6
              and {d.level for d in m.drivers.values()} == {"TOUGH"},
              "any button: the 1P countdown, 5 TOUGH bots")
        yield from self.idle(1.4)
        yield from self.snap("countdown")
        yield from self.idle(config.COUNTDOWN - 1.4 + 0.1)
        check(m.state == RACE, "GO")
        yield from self.drive_until(lambda: m.race.time > 12.0, 20, shots=((6.0, "race-1p"),))
        yield from self.tap(start=True)
        check(m.state == PAUSED, "Start pauses")
        t = m.race.time
        yield from self.tap(nav=(0, 1))
        yield from self.snap("pause")
        yield from self.idle(1.0)
        check(m.race.time == t and m.pause_index == 1, "paused: frozen, the menu moves")
        yield from self.tap(nav=(0, -1))
        yield from self.tap(b=True)
        check(m.state == RACE, "B resumes")
        p1 = m.race.racer("p1")
        yield from self.drive_until(lambda: m.frozen("p1"), 200)
        check(p1.circuit.filled == config.SLOTS, "all 16 gates before the final lap")
        z, t = p1.car.z, m.race.time
        yield from self.snap("check-1p")
        yield from self.drive_until(lambda: not m.frozen("p1"), 2)  # the pad is mashed on
        check(m.race.time - t > 0.9 * config.CHECK_FREEZE, "the freeze lasts about a second")
        check(p1.car.z - z > 0.8 * config.TOP_SPEED * (m.race.time - t),
              "the car drove on through the freeze")
        rows = p1.next_row
        yield from self.drive_until(lambda: m.state == RESULT, 200,
                                    shots=((m.race.time + 0.4, "warp-1p"),
                                           (m.race.time + 12.0, "final-lap-1p")))
        check(p1.next_row == rows and p1.circuit.filled == config.SLOTS,
              "no gates on the final lap")
        check(m.results[0].car in {r.car.id for r in m.race.racers}, "the results")
        yield from self.tap(a=True)
        check(m.state == RESULT, "a mashed A in the result's lock is ignored")
        yield from self.idle(config.RESULT_LOCK + 0.5)
        yield from self.snap("result-1p")
        yield from self.tap(a=True)
        check(m.state == COUNTDOWN and m.race.players == 1, "A rematches")
        yield from self.idle(config.COUNTDOWN + 0.1)
        yield from self.drive_until(lambda: m.race.time > 5.0, 10)
        yield from self.tap(start=True)
        yield from self.tap(nav=(0, 1))
        held_a = self._press(a=True)
        yield held_a
        check(m.state == TITLE and m.title_wait, "QUIT TO TITLE")
        for _ in range(30):  # A still held (mashed) on the title: it must not start
            yield FrameInput({"p1": PlayerInput(a=self.rng.random() < 0.3, held=True),
                              "p2": PlayerInput()}, activity=True)
        check(m.state == TITLE, "the title waits for the buttons to be let go")
        yield from self.idle(0.2)

        # PLAYERS 2, BOTS 2, LEVEL BRUTAL
        check(m.title_index == 0, "back on PLAYERS")
        yield from self.tap("p2", nav=(1, 0), stick=(1, 0))
        check(m.mode == 2 and m.bot_count == 4, "PLAYERS 2: the field stays full, 4 bots")
        yield from self.tap(nav=(0, 1))
        for _ in range(2):
            yield from self.tap(nav=(-1, 0), stick=(-1, 0))
        yield from self.tap(nav=(0, 1))
        for _ in range(2):
            yield from self.tap(nav=(1, 0), stick=(1, 0))
        check((m.mode, m.bot_count, m.level) == (2, 2, "BRUTAL"), "2 players, 2 bots, BRUTAL")
        yield from self.snap("title-2p")
        yield from self.tap(a=True)
        check(m.state == HOWTO, "A: the HOW TO PLAY card")
        yield from self.idle(0.5)
        yield from self.snap("howto-2p")
        yield from self.tap("p2", b=True)
        check(m.state == COUNTDOWN and m.race.players == 2 and len(m.race.racers) == 4
              and {d.level for d in m.drivers.values()} == {"BRUTAL"},
              "B on the card: a 2P countdown, 2 BRUTAL bots")
        yield from self.idle(0.5)
        yield from self.snap("countdown-2p")
        yield from self.idle(config.COUNTDOWN - 0.4)
        yield from self.drive_until(lambda: m.frozen("p1") or m.frozen("p2"), 200,
                                    shots=((8.0, "race-2p"),))
        yield from self.idle(DT)
        yield from self.snap("check-2p")
        yield from self.drive_until(lambda: any(m.banner(p, "finish") for p in m.players), 200)
        yield from self.snap("finish-2p")
        yield from self.drive_until(lambda: m.state == RESULT, 200)
        yield from self.idle(config.RESULT_LOCK + 0.5)
        yield from self.snap("result-2p")
        check(len([r for r in m.results if r.player]) == 2, "both players in the results")
        yield from self.tap("p2", b=True)
        check(m.state == TITLE and m.mode == 2, "B goes to the title")
        yield from self.idle(0.2)

        # a race left alone: back to the title, its rows reset
        yield from self.tap(start=True)
        yield from self.idle(0.4)
        yield from self.tap(start=True)
        check(m.state == COUNTDOWN, "Start on the card goes on, never pauses it")
        yield from self.idle(config.IDLE_TIMEOUT + 0.5)
        check(m.state == TITLE and (m.mode, m.bot_count, m.level) == (1, 5, "TOUGH"),
              "60 s untouched: the title, its rows reset")
        yield from self.snap("idle-title")
        yield from self.idle(0.5)

        # QUIT: down three times, then A
        for _ in range(3):
            yield from self.tap(nav=(0, 1))
        check(m.title_index == 3, "QUIT")
        yield self._press(a=True)
        check(False, "A on QUIT quits the game")
