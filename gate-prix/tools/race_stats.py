"""Race the CPU racers over many seeds and print how they do.

    uv run python tools/race_stats.py [--seeds N] [--player perfect|bot|park] [--naive]

For each seed it runs a whole 1P race to the end (every car finishes). P1 is the scripted
perfect driver (every right arch), a bot of the field's middle skill, or parked off the
road. It prints each car's right-gate rate (gates driven through right, a SPLIT clone's
included) and its share of right slots at the end (after QEC repairs), its finish time, the
bump cues per race, the gap from 1st to 6th, how often P1 won and by how much, and per race
the items used by kind, the mini-turbos by level and the hits. --naive drives the bots on the exact racing line
with no avoidance (offset 0), the "before" of the traffic numbers.
"""

from __future__ import annotations

import argparse
import statistics
import sys

from gate_prix import bot, config
from gate_prix.car import Controls, aim
from gate_prix.race import Race

DT = 1 / config.FPS


def perfect(race, racer):
    """Every right arch, and clear of every hazard and cloud (it sees them all)."""
    car = racer.car
    goal = race.track.segment_at(car.z + 600.0).line
    arch = None
    if racer.next_row < len(race.rows):
        row = race.rows[racer.next_row]
        if row.z - car.z < 1.5 * config.TOP_SPEED:
            arch = next(a for a in row.arches if a.right)
            goal = arch.offset
    goal = bot.dodge(race, racer, goal, arch)
    return Controls(*aim(car, goal, race.track.segment_at(car.z)))


def park(race, racer):
    car = racer.car
    return Controls(*aim(car, -2.1, race.track.segment_at(car.z)))


def one(seed: int, player: str, naive: bool):
    race = Race(seed=seed, players=1, finish_all=True)
    middle = statistics.median(bot.skills(config.CPU_CARS_1P))
    bots = bot.field(race, seed, players=middle if player == "bot" else None)
    if naive:
        bots = {k: bot.Bot(k, b.skill, seed, traffic=False) for k, b in bots.items()}
    events = []
    while not race.over and race.time < 400.0:
        controls = bot.drive(race, bots)
        if player != "bot":
            controls["p1"] = (perfect if player == "perfect" else park)(race, race.racer("p1"))
        events += race.update(DT, controls)
    return race, bots, events


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--player", choices=("perfect", "bot", "park"), default="perfect")
    parser.add_argument("--naive", action="store_true")
    args = parser.parse_args(argv)
    rights: dict[str, list[float]] = {}  # right gates driven (a SPLIT clone's count)
    fixed: dict[str, list[float]] = {}  # right slots at the end, after QEC repairs
    times: dict[str, list[float]] = {}
    bumps, gaps, wins, used, got = [], [], 0, 0, 0
    margins: list[float] = []  # P1's lead over the next car at the line
    kinds: dict[str, int] = {}  # the other cues per race: drifts, hits, items by kind
    for seed in range(args.seeds):
        race, bots, events = one(seed, args.player, args.naive)
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
    skill = {k: b.skill for k, b in bots.items()}
    print(f"{'car':7} {'skill':>5} {'right':>6} {'w/ QEC':>6} {'time':>7} {'min':>6} {'max':>6}")
    for car_id in rights:
        t = times[car_id]
        s = f"{skill[car_id]:5.2f}" if car_id in skill else "    -"
        print(f"{car_id:7} {s} {statistics.mean(rights[car_id]):6.1%} "
              f"{statistics.mean(fixed[car_id]):6.1%} {statistics.median(t):7.2f}"
              f" {min(t):6.2f} {max(t):6.2f}")
    print(f"bump cues per race: median {statistics.median(bumps)}, mean {statistics.mean(bumps):.1f}"
          f" (each bump cues both cars)")
    print(f"1st to 6th: median {statistics.median(gaps):.2f} s, min {min(gaps):.2f}, max {max(gaps):.2f}")
    print(f"P1 won {wins}/{args.seeds}; the CPUs' items got {got}, used {used}")
    if margins:
        print(f"P1's margin over the next car: median {statistics.median(margins):.2f} s, "
              f"min {min(margins):.2f}, max {max(margins):.2f}")
    print("per race: " + ", ".join(f"{k} {v / args.seeds:.1f}" for k, v in sorted(kinds.items())))


if __name__ == "__main__":
    main(sys.argv[1:])
