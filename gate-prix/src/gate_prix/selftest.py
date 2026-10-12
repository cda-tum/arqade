"""`--selftest SECONDS`: a scripted session through the real loop, renderer and match.

It plays, as a visitor would, and checks the match at every turn:
1. the title, untouched until the attract race starts, then a while of it;
2. 1 PLAYER: the countdown, a race steered by a bot with the stick mashed on top (A
   pressed at random, Select tapped, Start to pause, the pause menu moved and B to
   resume), through the CIRCUIT CHECK (all 16 gates before it, a freeze of about a
   second while the car drives on, no gate after it), to the finish and the result; a
   mashed A in the result's lock is ignored, then A rematches; in the rematch, pause and
   QUIT TO TITLE with A held on: the title must wait for it to be let go;
3. 2 PLAYERS (picked with the stick, held: it must not flicker): a race with both pads driven the same way, to the result, B to the title;
4. a race left untouched: 60 s later it is back on the title, at 1 PLAYER.

It stops after SECONDS of game time (exit 0 if every check held until then) or at the
end of the script. With --shots DIR it saves a screenshot of every screen on the way.
Game time runs as fast as the machine renders.
"""

from __future__ import annotations

import os
import random
import time

import pygame

from gate_prix import bot, config
from gate_prix.match import COUNTDOWN, PAUSED, RACE, RESULT, TITLE, FrameInput, PlayerInput

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
        self._drivers: dict[str, bot.Bot] = {}
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
            self._drivers = {p: bot.Bot(p, 0.8, self.rng.randrange(1000)) for p in m.players}
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
        check(m.state == TITLE and m.mode == 1 and not m.attract, "the title at 1 PLAYER")
        yield from self.snap("title")
        yield from self.idle(config.ATTRACT_DELAY)
        check(m.attract and m.race is not None and m.race.players == 2, "the attract race")
        yield from self.idle(8.0)
        yield from self.snap("attract")
        yield from self.idle(DT)
        check(m.race.time > 7.0, "the attract race drives")

        # 1 PLAYER: down and up again, then Start
        yield from self.tap(nav=(0, 1))
        check(m.mode == 1 and not m.attract, "the stick stops the demo, and only that")
        for k in range(40):  # the stick held down, auto-repeating: 2 PLAYERS, no flicker
            yield self._press(nav=(0, 1) if k == 0 or self.rng.random() < 0.2 else (0, 0))
            check(m.mode == 2, "a held stick stays on 2 PLAYERS")
        for k in range(60):  # held up-right, the y axis two frames late: 1 PLAYER, steady
            yield self._press(nav=(1 if k % 9 == 0 else 0, -1 if k == 2 else 0),
                              stick=(1, -1 if k >= 2 else 0))
            check(m.mode == (2 if k < 2 else 1), "a held diagonal picks one mode")
        yield from self.idle(0.1)
        check(m.mode == 1, "up: back to 1 PLAYER")
        yield from self.tap("p2", start=True)
        check(m.state == COUNTDOWN and m.race.players == 1, "Start begins a 1P countdown")
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

        # 2 PLAYERS
        yield from self.tap("p2", nav=(0, 1))
        check(m.mode == 2, "2 PLAYERS")
        yield from self.tap(a=True)
        check(m.state == COUNTDOWN and m.race.players == 2, "A begins a 2P countdown")
        yield from self.idle(config.COUNTDOWN + 0.1)
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

        # a race left alone: back to the title at 1 PLAYER
        yield from self.tap(start=True)
        yield from self.idle(config.IDLE_TIMEOUT + 0.5)
        check(m.state == TITLE and m.mode == 1, "60 s untouched: the title, 1 PLAYER")
        yield from self.snap("idle-title")
        yield from self.idle(0.5)
