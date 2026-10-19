"""The CPU racers: a `Bot` gives one car its controls each frame, as a human's pad would.

Pure Python, no pygame. A bot drives any car (a CPU racer, or a player's car in the attract
race) and returns the same `Controls` a human does, so the race never knows who drives.

- **The line:** it steers for the racing line BOT_LOOK ahead, plus an offset of its own (up
  to BOT_OFFSET_MAX, spread out across the field by `field`), so a pack of bots doesn't
  drive in single file and grind together.
- **Gates:** BOT_ROW_LEAD seconds before each row it picks its arch, once: the right one with
  probability `skill`, otherwise a decoy (BOT_DECOY of the time, when the row has one) or a
  gap clear of every arch.
- **Traffic:** it aims for the spot nearest its goal that is clear of the cars around it:
  BOT_AVOID_CLEAR beside any car ahead that it would reach within BOT_AVOID_TIME, and never
  through a car alongside; it makes way for a faster car about to run into it from behind,
  when there is room. Lined up for an arch it stays inside the arch; with no room there
  it eases off behind the car in front instead of ramming it.
- **Braking:** below BOT_BRAKE_SKILL it brakes into sharp curves; better bots never brake.
  It never brakes with the stick steered past DRIFT_STEER, since that would be a drift:
  it steers instead, unless it has to ease off behind a car, when it steers less.
- **Drifting:** through each curve sharper than BOT_DRIFT_CURVE it drifts with probability
  `skill` (decided once per curve and lap): stick back, steered into the curve at least
  DRIFT_STEER, and let go as the curve eases, for the mini-turbo. Not while it is steering
  round a hazard.
- **Hazards:** its own storm and every cloud within BOT_HAZARD_LOOK seconds: it sees each one
  with probability `skill` (once), and steers for the nearest spot clear of the ones it sees
  (`dodge`; lined up for an arch, only within the arch). Picking its arch while `blind`, it
  does so at BOT_BLIND_SKILL times its skill.
- **Items:** QEC as soon as its circuit has a mistake; SPLIT BOT_SPLIT_LEAD seconds before a
  row with decoys; MEASURE as soon as a car (not tunnelling) is ahead in range; TUNNEL in
  traffic, with a MEASURE coming for it, or a hazard or cloud still in its path
  BOT_TUNNEL_LOOK seconds ahead; DECOHERENCE when a car is close behind it, in line.
- **Pace:** `Controls.pace` is its skill's pace (BOT_PACE_WORST to 1.0) times mild
  rubber-banding by place (BOT_RUBBER_FIRST in 1st to BOT_RUBBER_LAST in last).
"""

from __future__ import annotations

import math
import random
import weakref

from gate_prix import config
from gate_prix.car import Controls, _wrapped, aim
from gate_prix.track import Arch, GateRow, Track

TOP = config.TOP_SPEED


def skills(n: int) -> list[float]:
    """n skills spread evenly from the best CPU's down to the worst's."""
    best, worst = config.BOT_SKILL_BEST, config.BOT_SKILL_WORST
    if n <= 1:
        return [best] * n
    return [best + (worst - best) * i / (n - 1) for i in range(n)]


class Bot:
    """One car's CPU driver. `skill` is 0 to 1; the CPU racers' run from 0.6 to 0.85."""

    def __init__(self, car_id: str, skill: float, seed: int, offset: float | None = None,
                 traffic: bool = True) -> None:
        """`offset` is its own offset from the racing line (random when None; `field` spreads
        them out). `traffic=False` drives on the exact racing line with no avoidance: only
        for measuring what the offsets and the avoidance are worth (tools/race_stats.py)."""
        self.car_id = car_id
        self.skill = skill
        self.traffic = traffic
        self.rng = random.Random(f"{seed}:bot:{car_id}")
        drawn = self.rng.uniform(-config.BOT_OFFSET_MAX, config.BOT_OFFSET_MAX)
        self.offset = (drawn if offset is None else offset) if traffic else 0.0
        self._aims: dict[int, tuple[float, Arch | None]] = {}  # row index -> (x, its arch)
        # the final lap's and the curves' decisions, a stream of their own (so that adding
        # them left every arch pick as it was)
        self.choices = random.Random(f"{seed}:bot:{car_id}:storm")
        self._seen: dict[tuple, bool] = {}  # an obstacle's key -> whether it saw it coming
        self._drifts: dict[tuple[int, int], bool] = {}  # (lap, curve) -> drift through it

    # --- The parts ----------------------------------------------------------------------------

    def pace(self, race) -> float:
        """Its skill's pace times the rubber-banding for its place now."""
        place = race.racer(self.car_id).place
        span = (config.BOT_SKILL_BEST - config.BOT_SKILL_WORST) or 1.0
        f = min(1.0, max(0.0, (self.skill - config.BOT_SKILL_WORST) / span))
        skill = config.BOT_PACE_WORST + (1.0 - config.BOT_PACE_WORST) * f
        g = (max(1, min(config.CARS, place)) - 1) / (config.CARS - 1)
        rubber = config.BOT_RUBBER_FIRST + (config.BOT_RUBBER_LAST - config.BOT_RUBBER_FIRST) * g
        lo, hi = config.PACE_LIMITS
        return min(hi, max(lo, skill * rubber))

    def _row_aim(self, row_index: int, row: GateRow, line: float,
                 me=None) -> tuple[float, Arch | None]:
        """Where it goes through this row, and the arch it means to take (None for a gap):
        picked once, the first time it is asked (at half its skill while blind)."""
        if row_index not in self._aims:
            arch: Arch | None
            skill = self.skill * (config.BOT_BLIND_SKILL if me is not None and me.blind else 1)
            if self.rng.random() < skill:
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
        if arch is None:
            lo, hi = -config.BOT_GOAL_MAX, config.BOT_GOAL_MAX
            clear = config.BOT_AVOID_CLEAR
        else:
            reach = arch.half_width - 0.01
            lo, hi = arch.offset - reach, arch.offset + reach
            clear = config.CAR_WIDTH + 0.005
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
        dodged = dodge(race, me, goal, arch, self._sees) if self.traffic else goal
        dodging = dodged != goal
        goal, queue = self._avoid(race, me, dodged, arch) if self.traffic else (goal, 0.0)
        goal = max(-config.BOT_GOAL_MAX, min(config.BOT_GOAL_MAX, goal))
        segment = race.track.segment_at(car.z)
        careful = self.skill < config.BOT_BRAKE_SKILL
        steer, brake = aim(car, goal, segment, brake_at=0.95 if careful else float("inf"))
        if careful and car.speed > 0.8 * TOP:
            ahead = race.track.segment_at(car.z + config.BOT_BRAKE_LOOK).curve
            if abs(ahead) > config.SHARP_CURVE:
                brake = max(brake, config.BOT_BRAKE)
        brake = max(brake, queue)
        side = 0 if dodging else self._drift(race, me)
        if side:  # stick back, steered into the curve
            steer, brake = side * max(config.DRIFT_STEER, side * steer), 1.0
        elif brake > 0 and abs(steer) >= config.DRIFT_STEER:
            if queue > 0:  # it must ease off behind a car: a brake, so the steer stays under
                steer = math.copysign(config.DRIFT_STEER - 0.01, steer)
            else:
                brake = 0.0  # that would be a drift: it steers instead
        return Controls(steer, brake, self._use(race, me, row), self.pace(race))

    def _sees(self, key: tuple) -> bool:
        """Whether it saw this obstacle coming: decided once, with its skill."""
        if key not in self._seen:
            self._seen[key] = self.choices.random() < self.skill
        return self._seen[key]

    def _drift(self, race, me) -> int:
        """The direction to drift in now (1 right, -1 left), or 0: in a curve sharper than
        BOT_DRIFT_CURVE that it chose (with its skill) to drift through."""
        car = me.car
        seg = race.track.segment_at(car.z)
        if abs(seg.curve) <= config.BOT_DRIFT_CURVE or car.spinning:
            return 0
        if not car.drifting and car.speed < config.DRIFT_MIN_SPEED * TOP:
            return 0
        curve = _curves(race.track).get(seg.index)
        key = (int(car.z // race.lap_length), curve)
        if key not in self._drifts:
            self._drifts[key] = self.choices.random() < self.skill
        return (1 if seg.curve > 0 else -1) if self._drifts[key] else 0

    def _use(self, race, me, row: GateRow | None) -> bool:
        item, car = me.item, me.car
        if item == "QEC":
            return any(r is False for r in me.circuit.results)
        if item == "SPLIT" and not me.split and row is not None and len(row.arches) > 1:
            lead = config.BOT_SPLIT_LEAD * max(car.speed, 0.5 * TOP)
            return row.z - car.z < lead
        if item == "MEASURE":
            target = race.measure_target(me.car.id)
            return target is not None and not target.car.tunnelling
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


def dodge(race, me, goal: float, arch: Arch | None = None, sees=None) -> float:
    """`goal` moved to a spot (nearest the car, then the goal) clear of the hazards and
    clouds within BOT_HAZARD_LOOK seconds ahead that `sees` (key -> bool; None: all of
    them): the first one in its way (on its goal, or between the car and it), and any others
    with it (within BOT_HAZARD_WAVE). Lined up for an arch it only moves within the arch,
    and keeps its goal when nothing there is clear. For the bots and scripted drivers."""
    car = me.car
    look = config.BOT_HAZARD_LOOK * max(car.speed, 0.5 * TOP)
    seen = [o for o in race.obstacles(me.car.id, look) if sees is None or sees(o[0])]
    clear = config.BOT_HAZARD_CLEAR
    lo_path, hi_path = min(car.x, goal), max(car.x, goal)  # the way across to its goal
    first = next((o for o in seen
                  if o[2] + o[3] + clear > lo_path and o[2] - o[3] - clear < hi_path), None)
    if first is None:
        return goal
    wave = [o for o in seen if abs(o[1] - first[1]) < config.BOT_HAZARD_WAVE]
    if arch is None:
        lo, hi = -config.BOT_GOAL_MAX, config.BOT_GOAL_MAX
    else:
        reach = arch.half_width - 0.01
        lo, hi = arch.offset - reach, arch.offset + reach
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


def offsets(n: int, seed: int) -> list[float]:
    """n offsets from the racing line spread evenly across +-BOT_OFFSET_MAX, shuffled."""
    m = config.BOT_OFFSET_MAX
    spread = [-m + 2 * m * i / (n - 1) for i in range(n)] if n > 1 else [0.0] * n
    random.Random(f"{seed}:offsets").shuffle(spread)
    return spread


def field(race, seed: int, players: float | None = None) -> dict[str, Bot]:
    """Bots for the race's CPU racers, in grid order with the best at the front, and with
    `players` a skill, bots of that skill for the players' cars too (the attract race).
    Their offsets from the line are spread out, so that no two drive in each other's
    tracks."""
    cpus = [r.car.id for r in race.racers if not r.player]
    pairs = list(zip(cpus, skills(len(cpus))))
    if players is not None:
        pairs = [(r.car.id, players) for r in race.racers if r.player] + pairs
    spots = offsets(len(pairs), seed)
    return {car_id: Bot(car_id, s, seed, offset=x) for (car_id, s), x in zip(pairs, spots)}


def cpu_bots(race, seed: int) -> dict[str, Bot]:
    """A bot for each of the race's CPU racers (`field` without the players)."""
    return field(race, seed)


def drive(race, bots: dict[str, Bot]) -> dict[str, Controls]:
    """Every bot's controls for this frame, by car id."""
    return {car_id: b.controls(race) for car_id, b in bots.items()}
