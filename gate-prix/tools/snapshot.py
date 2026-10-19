"""Render every screen of the game to PNGs, to check them by eye.

    uv run python tools/snapshot.py OUT [--seed N]

Headless (SDL's dummy driver), through the real Match and Renderer: the title (as found,
with its rows set, and over the attract race), HOW TO PLAY (1P and 2P), the countdown with
its lights, GO under the gantry, a 1P race, a drift, each item held and used (the SPLIT
clone, a MEASURE shot, a TUNNEL ghost, a DECOHERENCE cloud and its blind badge, ITEM FULL,
a box's reveal and tip), pause, the CIRCUIT CHECK panel, the LIGHT SPEED! warp, the noise
storm, the 1P result, then a 2P race (the split views and the shared minimap), its check
and its result. The players' cars are driven by the game's own AI.
"""

from __future__ import annotations

import argparse
import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from gate_prix import ai, config  # noqa: E402
from gate_prix.match import COUNTDOWN, HOWTO, RACE, RESULT, FrameInput, Match, PlayerInput  # noqa: E402
from gate_prix.race import Cloud  # noqa: E402
from gate_prix.render import Renderer  # noqa: E402

DT = 1.0 / config.FPS
ACTIVE = FrameInput(activity=True)  # someone is there (the idle timeout stays away)


def press(player: str = "p1", **kw) -> FrameInput:
    players = {p: PlayerInput() for p in ("p1", "p2")}
    players[player] = PlayerInput(held=True, button=True, **kw)
    return FrameInput(players, activity=True)


class Shooter:
    def __init__(self, out: str, seed: int) -> None:
        self.out = out
        os.makedirs(out, exist_ok=True)
        pygame.init()
        self.surface = pygame.Surface((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT))
        self.renderer = Renderer(self.surface)
        self.match = Match(random.Random(seed))
        self.n = 0
        self.saved: list[str] = []

    def shot(self, name: str, frames: int = 1) -> None:
        """Draw `frames` frames (the animations move on) and save the last."""
        for _ in range(frames):
            self.renderer.draw(self.match)
        self.n += 1
        path = os.path.join(self.out, f"{self.n:02d}-{name}.png")
        pygame.image.save(self.surface, path)
        self.saved.append(path)

    def step(self, seconds: float, inp: FrameInput = ACTIVE, draw: bool = False) -> None:
        for _ in range(round(seconds / DT)):
            self.match.update(DT, inp)
            if draw:
                self.renderer.draw(self.match)

    def until(self, done, limit: float, draw: bool = False) -> None:
        t = 0.0
        while not done():
            if t > limit:
                raise SystemExit(f"snapshot: gave up waiting after {limit:.0f} s")
            self.match.update(DT, ACTIVE)
            if draw:
                self.renderer.draw(self.match)
            t += DT

    def autopilot(self) -> None:
        """The players' cars driven by the AI (as after the line), so the race runs."""
        m = self.match
        for p in m.players:
            m.drivers[p] = ai.Driver(p, "TOUGH", 7)

    def use(self, player: str = "p1") -> None:
        """One frame of the player pressing A (the AI steering), to use the held item."""
        m = self.match
        driver = m.drivers.pop(player)
        c = driver.controls(m.race)
        players = {p: PlayerInput() for p in ("p1", "p2")}
        players[player] = PlayerInput(steer=c.steer, brake=c.brake, a=True, held=True, button=True)
        m.update(DT, FrameInput(players, activity=True))
        m.drivers[player] = driver

    def through_box(self, player: str = "p1") -> None:
        """Drive on to the player's next box line, then steer it onto a box still there
        (no jump along the track, so no row is skipped)."""
        race = self.match.race
        r = race.racer(player)
        z, k = race.box_lines[r.next_box]
        self.until(lambda: z - r.car.z < 1.5 * config.TOP_SPEED / config.FPS + 1, 30)
        offsets = race.track.boxes[k][1]
        j = next((j for j in range(len(offsets)) if race.box_present(k, j)), 0)
        r.car.x = r.car.prev_x = offsets[j]
        self.until(lambda: r.next_box > 0 and race.box_lines[r.next_box - 1][0] == z, 1)

    def to_race(self, mode: int) -> None:
        """From the title: PLAYERS set, Start, the HOW TO PLAY card, then the countdown."""
        m = self.match
        if m.mode != mode:
            m.update(DT, FrameInput({"p1": PlayerInput(nav=(1, 0)), "p2": PlayerInput()}, True))
            m.update(DT, ACTIVE)
        m.update(DT, press(start=True))
        assert m.state == HOWTO, m.state

    # --- The scenes ------------------------------------------------------------------------

    def run(self) -> None:
        m = self.match
        m.update(DT, FrameInput())
        self.shot("title")
        m.update(DT, FrameInput({"p1": PlayerInput(nav=(0, 1)), "p2": PlayerInput()}, True))
        m.update(DT, ACTIVE)
        self.shot("title-bots-row")
        self.step(config.ATTRACT_DELAY + 6.0, FrameInput())
        self.shot("title-attract")
        m.update(DT, press(a=True))  # stops the attract race
        m.update(DT, ACTIVE)
        m.title_index = 0
        self.one_player()
        self.two_players()

    def one_player(self) -> None:
        m = self.match
        self.to_race(1)
        self.shot("howto-1p", frames=80)
        self.step(config.HOWTO_GUARD + 0.1)
        m.update(DT, press(a=True))
        assert m.state == COUNTDOWN
        self.step(1.4)
        self.shot("countdown-1p")
        self.until(lambda: m.state == RACE, 3)
        self.autopilot()
        self.step(0.55)
        self.shot("go-1p")
        self.until(lambda: m.race.time > 9.0, 20)
        self.shot("race-1p", frames=3)
        self.drift()
        self.items()
        m.update(DT, press(start=True))
        self.shot("pause-1p")
        m.update(DT, press(b=True))
        p1 = m.race.racer("p1")
        self.until(lambda: m.frozen("p1"), 200)
        self.shot("check-1p")
        self.until(lambda: not m.frozen("p1"), 3, draw=True)
        self.step(0.3, draw=True)
        self.shot("warp-1p")
        line = (config.LAPS - 1) * m.race.lap_length
        self.until(lambda: p1.car.z > line + (config.STORM_START + 1.0) * config.TOP_SPEED, 20)
        self.until(lambda: any(alive and 1500 < z - p1.car.z < 9000
                               for z, _, _, alive in m.race.hazards_for("p1")), 30)
        self.shot("storm-1p", frames=2)
        self.until(lambda: m.state == RESULT, 200)
        self.step(config.RESULT_LOCK + 0.2)
        self.shot("result-1p")
        m.update(DT, press(b=True))
        m.update(DT, FrameInput())

    def drift(self) -> None:
        car = self.match.race.racer("p1").car
        saved = (car.drifting, car.drift_dir, car.drift_time, car.drift_angle)
        car.drifting, car.drift_dir, car.drift_time, car.drift_angle = True, 1, 1.6, 0.35
        self.shot("drift-1p", frames=2)
        car.turbo_level, car.turbo_flash = 2, 0.25
        self.shot("drift-turbo-1p")
        car.drifting, car.drift_dir, car.drift_time, car.drift_angle = saved
        car.turbo_flash = 0.0

    def items(self) -> None:
        m = self.match
        race = m.race
        p1 = race.racer("p1")
        m.tips_seen["p1"].clear()
        race.roll_item = lambda place, **kw: "MEASURE"
        p1.item = None
        self.through_box()  # the first MEASURE: its reveal and its tip
        self.step(0.15)
        self.shot("box-reveal-tip-1p")
        self.step(config.TIP_TIME)
        self.through_box()  # MEASURE still held: ITEM FULL
        self.step(0.1)
        self.shot("item-full-1p")
        self.step(config.FULL_TIME)
        for item in config.ITEMS:
            p1.item = item
            self.shot(f"slot-{item.lower()}-1p")
            if item == "MEASURE":  # someone just ahead to collapse
                ahead = next((r for r in race.racers if r is not p1), None)
                ahead.car.z = p1.car.z + 2500
                ahead.car.x = p1.car.x
            if item == "DECOHERENCE":  # in 1P the dropped cloud is behind: show one ahead
                race.clouds.append(Cloud(99, p1.car.z + 4000, p1.car.x, "cpu1", 5.0))
                self.shot("deco-cloud-1p")
            self.use()
            self.step({"SPLIT": 0.4, "QEC": 0.2, "MEASURE": 0.2, "TUNNEL": 0.5,
                       "DECOHERENCE": 0.2}[item])
            self.shot(f"use-{item.lower()}-1p", frames=2)
        p1.blind_time = 1.0
        self.shot("blind-1p")
        p1.blind_time = 0.0

    def two_players(self) -> None:
        m = self.match
        self.to_race(2)
        self.shot("howto-2p", frames=60)
        self.step(config.HOWTO_GUARD + 0.1)
        m.update(DT, press("p2", a=True))
        self.step(1.0)
        self.shot("countdown-2p")
        self.until(lambda: m.state == RACE, 3)
        self.autopilot()
        self.until(lambda: m.race.time > 10.0, 20)
        self.shot("race-2p", frames=3)
        p1 = m.race.racer("p1")
        p1.item, p1.split_rows = "TUNNEL", 0
        m.race.racer("p2").item = "DECOHERENCE"
        self.shot("items-2p")
        self.through_box("p2")  # P2 holds one: ITEM FULL in the narrow slot
        self.step(0.1)
        self.shot("item-full-2p")
        self.until(lambda: m.frozen("p1") or m.frozen("p2"), 200)
        self.shot("check-2p")
        self.until(lambda: m.state == RESULT, 260)
        self.step(config.RESULT_LOCK + 0.2)
        self.shot("result-2p")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out")
    parser.add_argument("--seed", type=int, default=3)
    args = parser.parse_args(argv)
    s = Shooter(args.out, args.seed)
    s.run()
    print(f"{len(s.saved)} screens in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
