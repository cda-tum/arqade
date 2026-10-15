"""The computer drivers, at three levels: one `Driver` gives one car its controls each frame,
as a person's pad would. Pure Python, no pygame, so it is tested like the rules.

One AI drives every car that has no person in it: the bots in a race, all six cars of the
attract race behind the title (at TOUGH), a player's car once it is past the line, and the
HOW TO PLAY card's demo. It returns the same `Controls` a person's stick and A become
(steer, brake, use the item; `pace` is its handicap, see below), so the race never knows
who drives.

A level is a `Skill`, a handful of numbers (`SKILLS`, keyed by EASY / TOUGH / BRUTAL); the
code is the same for all three:

- **EASY** a first-time visitor can beat: it goes for the right arch only about half the
  time, drives a little under the top speed and brakes into the sharp curves rather than
  drift them, misses half the hazards, fumbles half its items (using them at once, wherever
  it is), looks at the traffic only every fifth of a second, and wanders off its line.
- **TOUGH** makes a decent player work: about four rows in five right, drifts most sharp
  curves for the mini-turbo, sees nearly every hazard, plays every item at its moment, and
  is rubber-banded a little (slower in front, quicker at the back) to keep races close.
- **BRUTAL** is as near perfect as the game allows: every right arch, every sharp curve
  drifted, every hazard and cloud seen (further ahead), every item played at its moment,
  knowing every rival's item too (it never MEASUREs a car that holds a TUNNEL to dodge
  with), no wandering, a look every frame, and no slowing down when it leads.

Inside a level each car gets a little seeded jitter (`field` spreads it across the bots:
aim and pace), on top of its own offset from the racing line, so a field never moves in
lockstep. What the parts do:

- **The line:** it steers for the racing line BOT_LOOK ahead, plus its own offset (up to
  BOT_OFFSET_MAX, spread across the field by `field`), and `weave` either side of that on a
  slow sway of its own (never while lined up for an arch or steering round something).
- **Gates:** BOT_ROW_LEAD seconds before each row it picks its arch, once: the right one
  with probability `aim`, otherwise a decoy (BOT_DECOY of the time, when the row has one) or
  a gap clear of every arch. While `blind` it picks at BOT_BLIND_SKILL times its aim.
- **Traffic and hazards** are what it looks at every `think` seconds (holding the spot it
  then chose in between, its reaction time). Traffic: it aims for the spot nearest its goal clear of the cars around
  it: BOT_AVOID_CLEAR beside any car ahead that it would reach within BOT_AVOID_TIME, never
  through a car alongside; it makes way for a faster car about to run into it from behind,
  when there is room. Lined up for an arch it stays inside the arch; with no room there it
  eases off behind the car in front instead of ramming it. Hazards: its own storm and every
  cloud within BOT_HAZARD_LOOK seconds (BRUTAL: BOT_HAZARD_LOOK_INFORMED): it sees each one
  with probability `sees` (once) and steers for the nearest spot clear of those it sees
  (`dodge`; lined up for an arch, only within the arch).
- **Braking:** with `brake` above 0 it brakes that hard into sharp curves; the others never
  brake. It never brakes with the stick steered past DRIFT_STEER, since that would be a
  drift: it steers instead, unless it has to ease off behind a car, when it steers less.
- **Drifting:** through each curve sharper than BOT_DRIFT_CURVE it drifts with probability
  `drift` (decided once per curve and lap): stick back, steered into the curve at least
  DRIFT_STEER, and let go as the curve eases, for the mini-turbo. Not while steering round
  a hazard, unless the curve pushes it out faster than full stick can hold (boosted into a
  sharp curve): then every level drifts, to stay on the road.
- **Items:** each item it picks up it plays smart with probability `items`, otherwise it
  fumbles it: uses it BOT_FUMBLE seconds later, wherever it is. Smart: QEC as soon as its
  circuit has a mistake; SPLIT BOT_SPLIT_LEAD seconds before a row with decoys; MEASURE as
  soon as a car (not tunnelling, and for BRUTAL holding no TUNNEL) is ahead in range;
  TUNNEL in traffic, with a MEASURE coming for it, or a hazard or cloud still in its path
  BOT_TUNNEL_LOOK seconds ahead; DECOHERENCE when a car is close behind it, in line.
- **Pace:** `Controls.pace` is its `pace` times its rubber-banding by place (`rubber`:
  the multiplier in 1st and in last, in a straight line between), within PACE_LIMITS. A
  person always drives at 1.0, so no level is ever faster than a person on the same line.
"""

from __future__ import annotations

import math
import random
import weakref
from dataclasses import dataclass, replace

from gate_prix import config
from gate_prix.car import Controls, _wrapped, aim
from gate_prix.track import Arch, GateRow, Track

TOP = config.TOP_SPEED
AIM_JITTER = 0.05  # a field's aims spread this far either side of its level's
PACE_JITTER = 0.004  # and its paces (never above 1.0)


@dataclass(frozen=True)
class Skill:
    """A level: the handful of numbers the one `Driver` drives by."""

    name: str
    aim: float  # chance it lines up for a row's right arch (else a decoy or a gap)
    pace: float  # its top speed's multiplier (a person's is 1.0)
    rubber: tuple[float, float]  # the pace's multiplier in 1st place and in last
    brake: float  # how hard it brakes into sharp curves (0: never)
    drift: float  # chance it drifts each sharp curve for the mini-turbo
    sees: float  # chance it sees each hazard and cloud coming (and steers round it)
    items: float  # chance it plays an item at the right moment (else it fumbles it)
    think: float  # seconds between its looks at the traffic and the hazards (0: every frame)
    weave: float  # how far its line sways either side of its goal (road half-widths)
    informed: bool  # knows every rival's item, and looks further ahead for hazards


SKILLS = {
    "EASY": Skill("EASY", aim=0.45, pace=0.94, rubber=(0.97, 1.0), brake=0.5, drift=0.0,
                  sees=0.5, items=0.5, think=0.2, weave=0.12, informed=False),
    "TOUGH": Skill("TOUGH", aim=0.8, pace=0.995, rubber=(0.97, 1.03), brake=0.0, drift=0.75,
                   sees=0.85, items=1.0, think=0.05, weave=0.03, informed=False),
    "BRUTAL": Skill("BRUTAL", aim=1.0, pace=1.0, rubber=(1.0, 1.02), brake=0.0, drift=1.0,
                    sees=1.0, items=1.0, think=0.0, weave=0.0, informed=True),
}


def jittered(skill: Skill, j: float) -> Skill:
    """The skill nudged by j (-1 to 1): its aim by AIM_JITTER (less near 1: a perfect aim
    stays perfect) and its pace by PACE_JITTER (never above 1.0)."""
    aim_ = min(1.0, max(0.0, skill.aim + j * min(AIM_JITTER, 1.0 - skill.aim)))
    pace = min(1.0, skill.pace * (1 + j * PACE_JITTER))
    return replace(skill, aim=aim_, pace=pace)


class Driver:
    """One car's computer driver at a level (a name of SKILLS, or a Skill of its own)."""

    def __init__(self, car_id: str, level: str | Skill = config.DEFAULT_LEVEL, seed: int = 0,
                 offset: float | None = None, traffic: bool = True) -> None:
        """`offset` is its own offset from the racing line (random when None; `field` spreads
        them out). `traffic=False` drives on the exact racing line with no avoidance: only
        for measuring what the offsets and the avoidance are worth (tools/race_stats.py)."""
        self.car_id = car_id
        self.skill = SKILLS[level] if isinstance(level, str) else level
        self.traffic = traffic
        self.rng = random.Random(f"{seed}:bot:{car_id}")
        drawn = self.rng.uniform(-config.BOT_OFFSET_MAX, config.BOT_OFFSET_MAX)
        self.offset = (drawn if offset is None else offset) if traffic else 0.0
        self._aims: dict[int, tuple[float, Arch | None]] = {}  # row index -> (x, its arch)
        # the curves', hazards' and items' decisions, a stream of their own
        self.choices = random.Random(f"{seed}:bot:{car_id}:storm")
        self._seen: dict[tuple, bool] = {}  # an obstacle's key -> whether it saw it coming
        self._drifts: dict[tuple[int, int], bool] = {}  # (lap, curve) -> drift through it
        self._sway = self.choices.uniform(0.0, 2 * math.pi)  # its weave's phase
        self._look_at = self.choices.uniform(0.0, self.skill.think)  # its next look ...
        self._look: tuple[Arch | None, float, float, bool] | None = None  # ... the last
        self._plan: tuple[str, bool, float] | None = None  # (item, smart, fumble time)

    @property
    def level(self) -> str:
        return self.skill.name

    # --- The parts ----------------------------------------------------------------------------

    def pace(self, race) -> float:
        """Its pace times the rubber-banding for its place now."""
        place = race.racer(self.car_id).place
        n = len(race.racers)
        g = (max(1, min(n, place)) - 1) / (n - 1) if n > 1 else 0.0
        first, last = self.skill.rubber
        lo, hi = config.PACE_LIMITS
        return min(hi, max(lo, self.skill.pace * (first + (last - first) * g)))

    def _row_aim(self, row_index: int, row: GateRow, line: float,
                 me=None) -> tuple[float, Arch | None]:
        """Where it goes through this row, and the arch it means to take (None for a gap):
        picked once, the first time it is asked (at BOT_BLIND_SKILL of its aim while blind)."""
        if row_index not in self._aims:
            arch: Arch | None
            blind = me is not None and me.blind
            if self.rng.random() < self.skill.aim * (config.BOT_BLIND_SKILL if blind else 1):
                arch = next(a for a in row.arches if a.right)
            else:
                decoys = [a for a in row.arches if not a.right]
                arch = (self.rng.choice(decoys)
                        if decoys and self.rng.random() < config.BOT_DECOY else None)
            self._aims[row_index] = (_gap(row, line) if arch is None else arch.offset, arch)
        return self._aims[row_index]

    def _avoid(self, race, me, goal: float, arch: Arch | None) -> tuple[float, float]:
        """(goal, brake): its goal moved to the spot nearest it that is clear of the traffic.

        Cars alongside are never driven through: it stays on its own side of each. Cars ahead
        that it will reach within BOT_AVOID_TIME are passed BOT_AVOID_CLEAR to either side, and
        it makes way for a faster car that would run into it within BOT_YIELD_TIME when it
        can do both. When a car alongside stands between it and its arch, the car further
        back brakes to drop behind it and cross.
        Lined up for an arch it only moves within the arch (two cars fit side by side), and
        when nothing there is clear it stays in line and eases off rather than ram."""
        car = me.car
        lo, hi = _bounds(arch)
        clear = config.BOT_AVOID_CLEAR if arch is None else config.CAR_WIDTH + 0.005
        ahead, behind = [], []
        beside_ahead = False  # a car alongside, its nose ahead of ours
        for other in race.racers:
            if other is me:
                continue
            o = other.car
            dz = _wrapped(o.z - car.z, race.lap_length)
            if dz <= -config.CAR_LENGTH:
                faster = o.speed - car.speed
                if faster > 0 and -dz - config.CAR_LENGTH < faster * config.BOT_YIELD_TIME:
                    behind.append(o.x)  # about to run into us: make way if there is room
                continue
            if dz < config.CAR_LENGTH:  # alongside: never cross it
                beside_ahead = beside_ahead or dz > 0
                if o.x >= car.x:
                    hi = min(hi, o.x - config.CAR_WIDTH - 0.04)
                else:
                    lo = max(lo, o.x + config.CAR_WIDTH + 0.04)
                continue
            closing = car.speed - o.speed
            gap = dz - config.CAR_LENGTH
            if gap > 2 * config.CAR_LENGTH and (
                    closing <= 0 or gap > closing * config.BOT_AVOID_TIME):
                continue  # not going to reach it soon: not in the way yet
            ahead.append((dz, o.x, closing))
        if lo > hi:  # a car alongside is between it and where it must go
            if arch is not None and beside_ahead:
                return car.x, 1.0  # the one behind drops back to cross behind it
            return car.x, 0.0
        goal = min(hi, max(lo, goal))
        if not ahead and not behind:
            return goal, 0.0
        cars = [ox for _, ox, _ in ahead]
        spots = [goal] + [min(hi, max(lo, ox + side * (clear + 1e-3)))
                          for ox in cars + behind for side in (-1.0, 1.0)]
        for avoid in (cars + behind, cars):  # make way if it can, but pass first
            free = [x for x in spots if all(abs(x - ox) >= clear for ox in avoid)]
            if free:
                return min(free, key=lambda x: abs(x - goal)), 0.0
        # no room to pass: stay in line, easing off as it closes on the car in front
        blocking = [(dz, c) for dz, ox, c in ahead
                    if abs(car.x - ox) < config.CAR_WIDTH + 0.02 and dz < 3 * config.CAR_LENGTH]
        if blocking:
            closing = min(blocking)[1]
            if closing > 0:
                return goal, min(1.0, closing / (0.2 * config.BRAKE))
        return goal, 0.0

    def _looked(self, race, me, goal: float, arch: Arch | None) -> tuple[float, float, bool]:
        """(goal, brake, dodging): its goal moved past the hazards and the traffic, from a
        fresh look every `think` seconds (and whenever it lines up for a new arch); in
        between, the spot the last look chose (kept within the arch), and its brake."""
        if not self.traffic:
            return goal, 0.0, False
        last = self._look
        if last is None or last[0] is not arch or race.time >= self._look_at:
            look = (config.BOT_HAZARD_LOOK_INFORMED if self.skill.informed
                    else config.BOT_HAZARD_LOOK)
            dodged = dodge(race, me, goal, arch, self._sees, look)
            moved, queue = self._avoid(race, me, dodged, arch)
            self._look = last = (arch, moved, queue, dodged != goal)
            think = self.skill.think
            self._look_at = race.time + (think * self.choices.uniform(0.8, 1.2) if think else 0)
        return last[1], last[2], last[3]

    # --- A frame ------------------------------------------------------------------------------

    def controls(self, race) -> Controls:
        """Its controls for this frame."""
        me = race.racer(self.car_id)
        car = me.car
        line = race.track.segment_at(car.z + config.BOT_LOOK).line + self.offset
        goal, arch = line, None
        row = None
        if me.next_row < len(race.rows):
            row = race.rows[me.next_row]
            if row.z - car.z < config.BOT_ROW_LEAD * max(car.speed, 0.5 * TOP):
                goal, arch = self._row_aim(me.next_row, row, line, me)
        if arch is None and self.skill.weave:
            goal += self.skill.weave * math.sin(self._sway + race.time * config.BOT_WEAVE_RATE)
        goal, queue, dodging = self._looked(race, me, goal, arch)
        goal = max(-config.BOT_GOAL_MAX, min(config.BOT_GOAL_MAX, goal))
        segment = race.track.segment_at(car.z)
        careful = self.skill.brake > 0
        steer, brake = aim(car, goal, segment, brake_at=0.95 if careful else float("inf"))
        if careful and car.speed > 0.8 * TOP:
            ahead = race.track.segment_at(car.z + config.BOT_BRAKE_LOOK).curve
            if abs(ahead) > config.SHARP_CURVE:
                brake = max(brake, self.skill.brake)
        brake = max(brake, queue)
        side = 0 if dodging else self._drift(race, me)
        if not side and _overpowered(car, segment):  # it can't hold the road otherwise
            side = 1 if segment.curve > 0 else -1
        if side:  # stick back, steered into the curve
            steer, brake = side * max(config.DRIFT_STEER, side * steer), 1.0
        elif brake > 0 and abs(steer) >= config.DRIFT_STEER:
            if queue > 0:  # it must ease off behind a car: a brake, so the steer stays under
                steer = math.copysign(config.DRIFT_STEER - 0.01, steer)
            else:
                brake = 0.0  # that would be a drift: it steers instead
        return Controls(steer, brake, self._use(race, me, row), self.pace(race))

    def _sees(self, key: tuple) -> bool:
        """Whether it saw this obstacle coming: decided once, with `sees`."""
        if key not in self._seen:
            self._seen[key] = self.choices.random() < self.skill.sees
        return self._seen[key]

    def _drift(self, race, me) -> int:
        """The direction to drift in now (1 right, -1 left), or 0: in a curve sharper than
        BOT_DRIFT_CURVE that it chose (with `drift`) to drift through."""
        car = me.car
        seg = race.track.segment_at(car.z)
        if abs(seg.curve) <= config.BOT_DRIFT_CURVE or car.spinning:
            return 0
        if not car.drifting and car.speed < config.DRIFT_MIN_SPEED * TOP:
            return 0
        curve = _curves(race.track).get(seg.index)
        key = (int(car.z // race.lap_length), curve)
        if key not in self._drifts:
            self._drifts[key] = self.choices.random() < self.skill.drift
        return (1 if seg.curve > 0 else -1) if self._drifts[key] else 0

    def _use(self, race, me, row: GateRow | None) -> bool:
        """Whether to use the held item now: at its moment (smart), or fumbled."""
        item = me.item
        if item is None:
            self._plan = None
            return False
        if self._plan is None or self._plan[0] != item:
            smart = self.choices.random() < self.skill.items
            self._plan = (item, smart, race.time + config.BOT_FUMBLE)
        if not self._plan[1]:
            return race.time >= self._plan[2]
        return self._smart(race, me, row)

    def _smart(self, race, me, row: GateRow | None) -> bool:
        item, car = me.item, me.car
        if item == "QEC":  # with a mistake to fix, or none left to make (it frees the slot)
            return any(r is False for r in me.circuit.results) or me.next_row >= len(race.rows)
        if item == "SPLIT" and not me.split and row is not None and len(row.arches) > 1:
            lead = config.BOT_SPLIT_LEAD * max(car.speed, 0.5 * TOP)
            return row.z - car.z < lead
        if item == "MEASURE":
            target = race.measure_target(me.car.id)
            if target is None or target.car.tunnelling:
                return False
            return not (self.skill.informed and target.item == "TUNNEL")
        if item == "TUNNEL":
            return not car.tunnelling and self._wants_tunnel(race, me)
        if item == "DECOHERENCE":
            for other in race.racers:
                o = other.car
                dz = o.z - car.z
                if (other is not me and not other.finished
                        and -config.BOT_DECO_BEHIND < dz < -config.DECO_BEHIND - config.CAR_LENGTH
                        and abs(o.x - car.x) < config.BOT_DECO_LINE):
                    return True
        return False

    def _wants_tunnel(self, race, me) -> bool:
        """In traffic, a MEASURE on its way to it, or a hazard still in its path just ahead."""
        car = me.car
        if any(s.target == me.car.id for s in race.shots):
            return True
        for other in race.racers:
            if other is me:
                continue
            o = other.car
            dz = _wrapped(o.z - car.z, race.lap_length)
            near_x = abs(o.x - car.x) < 2 * config.CAR_WIDTH
            if -config.CAR_LENGTH < dz < config.BOT_TRAFFIC and near_x:
                return True
        near = config.BOT_TUNNEL_LOOK * max(car.speed, 0.5 * TOP)
        return any(abs(car.x - x) < reach for _, _, x, reach in race.obstacles(me.car.id, near))


def _overpowered(car, segment) -> bool:
    """Whether the curve pushes the car out faster than full stick can hold it (a boost
    into a sharp curve): then only a drift, which halves the push, keeps it on the road."""
    return (not car.spinning and car.speed >= config.DRIFT_MIN_SPEED * TOP
            and abs(car.push(segment.curve, drift=False)) > 0.95 * car.steer_rate())


def _bounds(arch: Arch | None) -> tuple[float, float]:
    """Where its goal may lie: within the arch it is lined up for, else on the road."""
    if arch is None:
        return -config.BOT_GOAL_MAX, config.BOT_GOAL_MAX
    reach = arch.half_width - 0.01
    return arch.offset - reach, arch.offset + reach


def dodge(race, me, goal: float, arch: Arch | None = None, sees=None,
          look: float = config.BOT_HAZARD_LOOK) -> float:
    """`goal` moved to a spot (nearest the car, then the goal) clear of the hazards and
    clouds within `look` seconds ahead that `sees` (key -> bool; None: all of them): the
    first one in its way (on its goal, or between the car and it), and any others with it
    (within BOT_HAZARD_WAVE). Lined up for an arch it only moves within the arch, and keeps
    its goal when nothing there is clear. For the drivers and scripted drivers."""
    car = me.car
    ahead = look * max(car.speed, 0.5 * TOP)
    seen = [o for o in race.obstacles(me.car.id, ahead) if sees is None or sees(o[0])]
    clear = config.BOT_HAZARD_CLEAR
    lo_path, hi_path = min(car.x, goal), max(car.x, goal)  # the way across to its goal
    first = next((o for o in seen
                  if o[2] + o[3] + clear > lo_path and o[2] - o[3] - clear < hi_path), None)
    if first is None:
        return goal
    wave = [o for o in seen if abs(o[1] - first[1]) < config.BOT_HAZARD_WAVE]
    lo, hi = _bounds(arch)
    spots = [lo + i * 0.02 for i in range(round((hi - lo) / 0.02) + 1)]
    free = [x for x in spots if all(abs(x - ox) >= r + clear for _, _, ox, r in wave)]
    # the clear spot nearest the car (it keeps to its side), then nearest its goal
    return min(free, key=lambda x: abs(x - car.x) + 0.25 * abs(x - goal)) if free else goal


# per Track object, held weakly (an id could be reused by a later track)
_CURVES: weakref.WeakKeyDictionary[Track, dict[int, int]] = weakref.WeakKeyDictionary()


def _curves(course: Track) -> dict[int, int]:
    """Segment index -> which of the lap's curves sharper than BOT_DRIFT_CURVE it is in."""
    key = course
    if key not in _CURVES:
        out, n, inside = {}, -1, False
        for seg in course.segments:
            sharp = abs(seg.curve) > config.BOT_DRIFT_CURVE
            if sharp and not inside:
                n += 1
            inside = sharp
            if sharp:
                out[seg.index] = n
        _CURVES[key] = out
    return _CURVES[key]


def _gap(row: GateRow, near: float) -> float:
    """The x nearest `near` that is clear of every arch of the row by BOT_GAP_CLEAR."""
    clear = config.ARCH_HALF_WIDTH + config.BOT_GAP_CLEAR
    reach = config.BOT_GOAL_MAX
    spots = [-reach + i * 0.02 for i in range(round(2 * reach / 0.02) + 1)]
    free = [x for x in spots if all(abs(x - a.offset) > clear for a in row.arches)]
    return min(free, key=lambda x: abs(x - near)) if free else reach


def spread(n: int, seed: int, salt: str = "offsets") -> list[float]:
    """n values spread evenly across -1 to 1, shuffled by the seed (one 0.0 for n = 1)."""
    out = [-1 + 2 * i / (n - 1) for i in range(n)] if n > 1 else [0.0] * n
    random.Random(f"{seed}:{salt}").shuffle(out)
    return out


def offsets(n: int, seed: int) -> list[float]:
    """n offsets from the racing line spread evenly across +-BOT_OFFSET_MAX, shuffled."""
    return [config.BOT_OFFSET_MAX * v for v in spread(n, seed)]


def field(race, seed: int, level: str = config.DEFAULT_LEVEL,
          players: str | None = None) -> dict[str, Driver]:
    """Drivers at `level` for the race's bots and, with `players` a level, drivers at that
    level for the people's cars too (the attract race). Their offsets from the line are
    spread out, so that no two drive in each other's tracks, and the bots' jitter is spread
    across them, the best at the front of the grid."""
    bots = [r.car.id for r in race.racers if not r.player]
    jitter = sorted(spread(len(bots), seed, "jitter"), reverse=True)  # the grid's order
    pairs = [(car_id, jittered(SKILLS[level], j)) for car_id, j in zip(bots, jitter)]
    if players is not None:
        pairs = [(r.car.id, SKILLS[players]) for r in race.racers if r.player] + pairs
    spots = offsets(len(pairs), seed)
    return {car_id: Driver(car_id, s, seed, offset=x) for (car_id, s), x in zip(pairs, spots)}


def drive(race, drivers: dict[str, Driver]) -> dict[str, Controls]:
    """Every driver's controls for this frame, by car id."""
    return {car_id: d.controls(race) for car_id, d in drivers.items()}
