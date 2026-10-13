"""Balance check for the roster: each racer's solo pace on every track
(BRUTAL, no gates or items: seconds for two laps), and its share of the
lead over many 8-racer BRUTAL races of RACE_TIME with everything on and the
camera putting racers back in. Run from qircuit/ after changing racers.py
or the STAT_* steps in config.py: `uv run python tools/balance.py [races
per track]`. The field is balanced when the paces sit within a couple of
percent and every racer leads near an eighth of the time, none far off."""

import dataclasses
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from qircuit import racers, tracks  # noqa: E402
from qircuit.ai import Driver  # noqa: E402
from qircuit.match import Pack  # noqa: E402
from qircuit.race import Race  # noqa: E402
from qircuit.track import Track  # noqa: E402

DT = 1 / 30
RACE_TIME = 90.0


def solo(track: Track, racer) -> float:
    race = Race(track, ("cpu1",), random.Random(0), stats={"cpu1": racer.stats()})
    driver = Driver("cpu1", "BRUTAL", random.Random(1))
    body = race.bodies[0]
    goal = body.p + 2 * track.length
    while body.p < goal and race.time < 200:
        race.update(DT, {"cpu1": driver.controls(race, DT)})
    return race.time


def main(races: int) -> None:
    print("solo pace (two laps, BRUTAL, no gates or items):")
    for d in tracks.ALL:
        t = Track(dataclasses.replace(d, dynamic_gates=0, items=0))
        row = {r.key: solo(t, r) for r in racers.ROSTER}
        m = statistics.mean(row.values())
        print(f"  {d.name:9}", " ".join(f"{k[:5]}:{v / m * 100 - 100:+.1f}%" for k, v in row.items()))
    shares = {r.key: [] for r in racers.ROSTER}
    for d in tracks.ALL:
        t = Track(d)
        for seed in range(races):
            rng = random.Random(seed)
            field = rng.sample(racers.ROSTER, 8)
            players = tuple(f"cpu{i + 1}" for i in range(8))
            race = Race(t, players, rng, stats={p: r.stats() for p, r in zip(players, field)},
                        start_p=rng.uniform(0, t.length))
            pack = Pack(race)
            drivers = [Driver(p, "BRUTAL", random.Random(seed * 10 + i)) for i, p in enumerate(players)]
            while race.time < RACE_TIME:
                pack.update(DT, {dr.player: dr.controls(race, DT) for dr in drivers})
            for p, r in zip(players, field):
                shares[r.key].append(pack.lead_time[p] / race.time)
    print(f"share of the lead in 8-racer BRUTAL races (an even field gives {1 / 8:.0%}), "
          f"over {races * len(tracks.ALL)} races:")
    for k, v in sorted(shares.items(), key=lambda kv: -statistics.mean(kv[1])):
        print(f"  {k:10} {statistics.mean(v):5.1%}  in {len(v)} races")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
