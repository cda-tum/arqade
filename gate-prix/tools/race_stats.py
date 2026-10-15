"""Race the AI over many seeds and print how it does.

    uv run python tools/race_stats.py [--seeds N] [--level EASY|TOUGH|BRUTAL] [--bots N]
                                      [--player perfect|mediocre|ai|park] [--naive]
    uv run python tools/race_stats.py --ladder [--seeds N]

For each seed it runs a whole 1P race to the end (every car finishes), the bots at --level.
P1 is the scripted perfect driver (every right arch, every hazard seen, no drifting, no
items), the scripted mediocre one (a first-time visitor: the right arch on 60% of the rows,
60% of the hazards seen, no drifting, no items; --right sets the 60%), the AI at --level, or parked off the road.
It prints each car's right-gate rate (gates driven through right, a SPLIT clone's included)
and its share of right slots at the end (after QEC repairs), its finish time, the bump cues
per race, the gap from 1st to last, how often P1 won and by how much, and per race the items
used by kind, the mini-turbos by level and the hits. --naive drives the bots on the exact
racing line with no avoidance (offset 0), the "before" of the traffic numbers.

--ladder instead runs each level alone on the track (one bot, no rivals) and prints its
finish times, gate outcomes, storm hits, off-road frames and mini-turbos.
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys

from gate_prix import ai, config
from gate_prix.car import Controls, aim
from gate_prix.race import Race

DT = 1 / config.FPS


class Scripted:
    """A scripted player: the right arch of a row with probability `right` (decided per
    row, from 1.5 s out; otherwise a decoy or a gap, as a bot would), steering round the
    hazards it sees (each with probability `sees`). It never drifts and never uses items."""

    def __init__(self, seed: int, right: float = 1.0, sees: float = 1.0) -> None:
        self.rng = random.Random(f"{seed}:scripted")
        self.right, self.sees = right, sees
        self.picks: dict[int, object] = {}
        self.seen: dict[tuple, bool] = {}

    def _sees(self, key: tuple) -> bool:
        if key not in self.seen:
            self.seen[key] = self.rng.random() < self.sees
        return self.seen[key]

    def __call__(self, race, racer) -> Controls:
        car = racer.car
        goal = race.track.segment_at(car.z + 600.0).line
        arch = None
        if racer.next_row < len(race.rows):
            row = race.rows[racer.next_row]
            if row.z - car.z < 1.5 * config.TOP_SPEED:
                if racer.next_row not in self.picks:
                    if self.rng.random() < self.right:
                        pick = next(a for a in row.arches if a.right)
                    else:
                        decoys = [a for a in row.arches if not a.right]
                        pick = self.rng.choice(decoys) if decoys and self.rng.random() < 0.5 else None
                    self.picks[racer.next_row] = (pick, ai._gap(row, goal))
                arch, gap = self.picks[racer.next_row]
                goal = arch.offset if arch is not None else gap
        goal = ai.dodge(race, racer, goal, arch, self._sees)
        return Controls(*aim(car, goal, race.track.segment_at(car.z)))


def park(race, racer):
    car = racer.car
    return Controls(*aim(car, -2.1, race.track.segment_at(car.z)))


def one(seed: int, player: str, naive: bool, level: str = config.DEFAULT_LEVEL,
        bots: int | None = None, right: float = 0.6):
    race = Race(seed=seed, players=1, finish_all=True, bots=bots)
    drivers = ai.field(race, seed, level, players=level if player == "ai" else None)
    if naive:
        drivers = {k: ai.Driver(k, d.skill, seed, traffic=False) for k, d in drivers.items()}
    p1 = {"perfect": Scripted(seed), "mediocre": Scripted(seed, right, right),
          "park": park}.get(player)
    events = []
    while not race.over and race.time < 400.0:
        controls = ai.drive(race, drivers)
        if p1 is not None:
            controls["p1"] = p1(race, race.racer("p1"))
        events += race.update(DT, controls)
    return race, drivers, events


def time_trial(seed: int, level: str | ai.Skill):
    """One bot alone on the track, the whole race: (time, rights, wrongs, misses, the rows
    it meant to miss, storm hits, the hazards it chose not to see, off-road frames, turbos)."""
    race = Race(seed=seed, players=0, bots=1, finish_all=True)
    d = ai.Driver("cpu1", level, seed)
    me = race.racer("cpu1")
    counts = {"right": 0, "wrong": 0, "miss": 0, "hazard": 0, "turbo": 0}
    offroad = 0
    while not race.over and race.time < 400.0:
        for e in race.update(DT, {"cpu1": d.controls(race)}):
            if e.kind in counts:
                counts[e.kind] += 1
        offroad += me.car.offroad
    meant = sum(1 for _, arch in d._aims.values() if arch is None or not arch.right)
    unseen = sum(1 for k, seen in d._seen.items() if not seen and k[0] == "hazard")
    return (me.finish_time, counts["right"], counts["wrong"], counts["miss"], meant,
            counts["hazard"], unseen, offroad, counts["turbo"])


def ladder(seeds: int) -> None:
    print(f"{'level':7} {'time':>7} {'min':>7} {'max':>7} {'right':>6} {'wrong':>6} {'miss':>5}"
          f" {'meant':>6} {'hits':>5} {'unseen':>7} {'offrd':>6} {'turbos':>7}")
    for level in config.LEVELS:
        rows = [time_trial(seed, level) for seed in range(seeds)]
        t = [r[0] for r in rows]
        sums = [sum(r[i] for r in rows) / seeds for i in range(1, 9)]
        print(f"{level:7} {statistics.median(t):7.2f} {min(t):7.2f} {max(t):7.2f} "
              + " ".join(f"{v:{w}.2f}" for v, w in zip(sums, (6, 6, 5, 6, 5, 7, 6, 7))))


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--player", choices=("perfect", "mediocre", "ai", "park"),
                        default="perfect")
    parser.add_argument("--level", choices=config.LEVELS, default=config.DEFAULT_LEVEL)
    parser.add_argument("--bots", type=int, default=None)
    parser.add_argument("--right", type=float, default=0.6,
                        help="the mediocre player's share of right arches and hazards seen")
    parser.add_argument("--naive", action="store_true")
    parser.add_argument("--ladder", action="store_true")
    args = parser.parse_args(argv)
    if args.ladder:
        ladder(args.seeds)
        return
    rights: dict[str, list[float]] = {}  # right gates driven (a SPLIT clone's count)
    fixed: dict[str, list[float]] = {}  # right slots at the end, after QEC repairs
    times: dict[str, list[float]] = {}
    bumps, gaps, wins, used, got = [], [], 0, 0, 0
    margins: list[float] = []  # P1's lead over the next car at the line (negative: behind)
    kinds: dict[str, int] = {}  # the other cues per race: drifts, hits, items by kind
    for seed in range(args.seeds):
        race, drivers, events = one(seed, args.player, args.naive, args.level, args.bots,
                                    args.right)
        for r in race.racers:
            right = sum(e.kind == "right" and e.car == r.car.id for e in events)
            rights.setdefault(r.car.id, []).append(right / config.SLOTS)
            fixed.setdefault(r.car.id, []).append(sum(r.circuit.results) / config.SLOTS)
            times.setdefault(r.car.id, []).append(r.finish_time or float("nan"))
        bumps.append(sum(e.kind == "bump" for e in events))
        done = sorted(r.finish_time for r in race.racers if r.finish_time is not None)
        gaps.append(done[-1] - done[0])
        wins += race.results()[0] == "p1"
        others = [r.finish_time for r in race.racers if r.car.id != "p1" and r.finish_time]
        if race.racer("p1").finish_time and others:
            margins.append(min(others) - race.racer("p1").finish_time)
        used += sum(e.kind == "item" and e.car != "p1" for e in events)
        got += sum(e.kind == "box" and e.value is not None and e.car != "p1" for e in events)
        for e in events:
            name = {"item": f"item {e.value}", "turbo": f"turbo {e.value}",
                    "hazard": f"hit {e.value}", "collapse": "collapse", "fizzle": "fizzle",
                    "decohered": "decohered", "immune": "immune"}.get(e.kind)
            if name:
                kinds[name] = kinds.get(name, 0) + 1
    aims = {k: d.skill.aim for k, d in drivers.items()}
    print(f"{'car':7} {'aim':>5} {'right':>6} {'w/ QEC':>6} {'time':>7} {'min':>6} {'max':>6}")
    for car_id in rights:
        t = times[car_id]
        s = f"{aims[car_id]:5.2f}" if car_id in aims else "    -"
        print(f"{car_id:7} {s} {statistics.mean(rights[car_id]):6.1%} "
              f"{statistics.mean(fixed[car_id]):6.1%} {statistics.median(t):7.2f}"
              f" {min(t):6.2f} {max(t):6.2f}")
    print(f"bump cues per race: median {statistics.median(bumps)}, mean {statistics.mean(bumps):.1f}"
          f" (each bump cues both cars)")
    print(f"1st to last: median {statistics.median(gaps):.2f} s, min {min(gaps):.2f}, max {max(gaps):.2f}")
    print(f"P1 won {wins}/{args.seeds}; the bots' items got {got}, used {used}")
    if margins:
        print(f"P1's margin over the next car: median {statistics.median(margins):.2f} s, "
              f"min {min(margins):.2f}, max {max(margins):.2f}")
    print("per race: " + ", ".join(f"{k} {v / args.seeds:.1f}" for k, v in sorted(kinds.items())))


if __name__ == "__main__":
    main(sys.argv[1:])
