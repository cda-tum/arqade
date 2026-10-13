"""Computer drivers, at three levels. Pure (no pygame), so it is tested.

One AI drives every car that has no person in it: the opponents in a race,
the bots racing behind the title menu, and the attract-reel bot
(../../../batocera/attract/bots/qircuit.py), which turns the same Controls
into pad presses. It returns exactly what a person's input becomes (up or
down on the cruise speed, a wire change), and the race's cruise control
(race.py) turns that into speed for bots and people alike, so it plays by
the same rules and can do nothing a person can't.

A level is a Skill, a handful of numbers; the code is the same for all three.

- EASY takes corners well under the drift limit, never quite flat out, and
  brakes early. It thinks about its wire now and then, and not always well.
- TOUGH takes corners into a light drift with good braking, overtakes slower
  cars (pulling out of their slipstream to pass), and lines up for boost
  pads.
- BRUTAL drives right up to the red, brakes at the last moment, and knows the
  whole race: it picks up the gates that help it (a CNOT copy, an error
  launcher with a rival ahead on that wire), aims its error bugs at a rival
  while they hover, and dodges bugs about to catch it and Zeno traps.

Speed: each frame it works out the speed it wants (its pace, or less for
the tightest corner within braking distance, for every one of its copies:
they share one input). Too fast for a corner, or set higher than it wants,
it pushes down, which brakes; set lower, it pushes up until the setting
gets there; otherwise it lets the cruise control hold. Wire: every
`think` seconds it estimates the time each reachable wire costs over the
next stretch (shorter inner wires against their lower corner speeds, slower
cars in the way, slipstreams, and for BRUTAL the gates and hazards) and
changes to the cheapest.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from qircuit import config
from qircuit.race import Body, Controls, Race

LOOK_STEP = 4.0
WINDOW = 240.0  # how far ahead a wire choice looks
WINDOW_STEP = 8.0
SWITCH_COST = 0.02  # seconds a wire change is worth only if it gains more than this
TRAFFIC_RANGE = 120.0
HAZARD_HORIZON = 2.0  # seconds: a bug it would meet sooner than this is in the way


@dataclass(frozen=True)
class Skill:
    name: str
    corner_load: float  # the load it takes corners at (1.0 is the drift limit)
    pace: float  # fraction of top speed it drives at
    brake_plan: float  # fraction of its real braking it plans with: less brakes earlier
    think: float  # seconds between wire choices
    sense: float  # chance a wire choice is the best it can see (else it keeps its wire)
    wander: float  # chance a wire choice is a random one instead
    informed: bool  # sees gates, items, bugs and traps, and uses them


SKILLS = {
    "EASY": Skill("EASY", corner_load=0.8, pace=0.86, brake_plan=0.6, think=1.0, sense=0.35,
                  wander=0.15, informed=False),
    "TOUGH": Skill("TOUGH", corner_load=1.15, pace=1.0, brake_plan=0.8, think=0.5, sense=0.8,
                   wander=0.0, informed=False),
    "BRUTAL": Skill("BRUTAL", corner_load=0.96 * config.WARN_LOAD, pace=1.0, brake_plan=0.95, think=0.15,
                    sense=1.0, wander=0.0, informed=True),
}


def allowed_speed(race: Race, body: Body, skill: Skill) -> float:
    """The fastest this body may go now and still brake in time for every
    corner within its braking distance, at this skill's corner load (inf
    with no corner in reach)."""
    stats = race.racers[body.player].stats
    brake = stats.brake * skill.brake_plan
    s = race.s_of(body.p)
    allowed = math.inf
    look = body.v * body.v / (2 * brake) + 40
    d = 0.0
    while d <= look:
        k = abs(race.track.curvature(body.lane, s + d))
        if k > 1e-6:
            v_corner = math.sqrt(skill.corner_load * stats.grip / k)
            allowed = min(allowed, math.sqrt(v_corner * v_corner + 2 * brake * d))
        d += LOOK_STEP
    return allowed


class Driver:
    def __init__(self, player: str, level: str, rng: random.Random | None = None) -> None:
        self.player = player
        self.skill = SKILLS[level]
        self.rng = rng or random.Random()
        self.wait = self.rng.uniform(0.3, 0.3 + self.skill.think)

    def controls(self, race: Race, dt: float) -> Controls:
        bodies = race.bodies_of(self.player)
        if not bodies:
            return Controls()
        stats = race.racers[self.player].stats
        corner = [allowed_speed(race, b, self.skill) for b in bodies]
        # the speed it wants: its pace, or less for a corner
        want = [min(a, stats.max_speed * (1 + config.DRAFT_TOP * b.draft) * self.skill.pace)
                for a, b in zip(corner, bodies)]
        setting = [race.cruise_speed(b, stats) for b in bodies]
        if any(b.v > a + 3 for a, b in zip(corner, bodies)):
            c = Controls(brake=True)  # too fast for a corner: down brakes, and the setting comes down with it
        elif any(s > w + 3 and b.v <= w + 3 for s, w, b in zip(setting, want, bodies)):
            c = Controls(brake=True)  # set too high: down brings it to what it does now (over its pace, off a
            # boost pad, it waits until it has eased down to it)
        elif min(w - max(s, b.v) for w, s, b in zip(want, setting, bodies)) > 3:
            c = Controls(throttle=True)  # the setting can go up (up starts from the speed it does now, if higher)
        else:
            c = Controls()  # the cruise control holds it
        self.wait -= dt
        if self.wait <= 0:
            self.wait = self.skill.think * self.rng.uniform(0.7, 1.3)
            d = self.choose_wire(race, max(bodies, key=lambda b: b.p))
            c.left, c.right = d < 0, d > 0
        return c

    # --- the wire ---------------------------------------------------------------------

    def choose_wire(self, race: Race, body: Body) -> int:
        """-1 (the car's left), 0 (stay) or +1 (its right)."""
        if body.air or body.u != body.lane:
            return 0
        s = race.s_of(body.p)
        options = [0] + [d for d in (-1, 1) if race.track.can_switch(s, body.lane, body.lane + d)]
        if self.rng.random() < self.skill.wander:
            return self.rng.choice(options)
        if self.rng.random() > self.skill.sense:
            return 0
        cost = {d: self.wire_cost(race, body, body.lane + d) + (SWITCH_COST if d else 0.0) for d in options}
        return min(options, key=lambda d: (cost[d], d != 0))

    def wire_cost(self, race: Race, body: Body, lane: int) -> float:
        """Roughly the seconds the next WINDOW of track costs on `lane`."""
        stats = race.racers[body.player].stats
        skill = self.skill
        top = stats.max_speed * skill.pace
        free = top * (1 + config.DRAFT_TOP * body.draft)  # what it could do, out of a slipstream
        s0 = race.s_of(body.p)
        t = 0.0
        steps = int(WINDOW / WINDOW_STEP)
        for i in range(steps):
            s = s0 + i * WINDOW_STEP
            k = abs(race.track.curvature(lane, s))
            v = top if k < 1e-6 else min(top, math.sqrt(skill.corner_load * stats.grip / k))
            t += WINDOW_STEP * race.track.factor(lane, s) / v
        start, L = race.track.d.start_s, race.track.length
        for s, lanes in race.track.d.boosts:  # a boost pad on this wire, coming up
            if lane in lanes and 0 < race.gap((s - start) % L, body.p) < WINDOW:
                t -= 0.25
        for o in race.bodies:
            if o.player == body.player or o.air or o.lane != lane:
                continue
            g = race.gap(o.p, body.p)
            if abs(g) < config.CAR_LEN + 2:
                t += 0.25  # right beside us there: a push, and both of us lose speed
            elif 0 < g < TRAFFIC_RANGE and o.v < (max(body.v, free) if g < config.DRAFT_RANGE else body.v) - 5:
                t += 0.1 + 0.4 * (1 - g / TRAFFIC_RANGE)  # a slower car in the way: pull out and pass
            elif config.CAR_LEN < g < config.DRAFT_RANGE:
                t -= 0.05  # its slipstream
        if skill.informed:
            t += self.gate_cost(race, body, lane)
        return t

    def gate_cost(self, race: Race, body: Body, lane: int) -> float:
        """What BRUTAL knows: hazards on the wire cost time, useful gates save it."""
        t = 0.0
        for bug in race.bugs:
            if bug.lane != lane or bug.owner == body.player:
                continue
            g = race.gap(bug.p, body.p)
            closing = body.v - bug.v if g > 0 else bug.v - body.v
            if closing > 0 and abs(g) / closing < HAZARD_HORIZON:
                t += 0.7  # we would meet it: from behind if it is faster, ahead if slower
        for trap in race.traps:
            if trap.arm > 0 or trap.lane != lane or (trap.owner == body.player and trap.grace > 0):
                continue
            if 0 < race.gap(trap.p, body.p) < WINDOW:
                t += 0.4
        if any(bug.carrier == body.id for bug in race.bugs) and self._rival_on(race, body, lane, 0, 300):
            t -= 0.5  # our bug is hovering, about to go: aim it at someone
        copies = len(race.bodies_of(body.player))
        for gate in race.gates:
            if lane not in gate.lanes or not 0 < race.gap(race.p_of(gate.s), body.p) < WINDOW:
                continue
            if gate.kind == "CNOT" and lane == gate.lanes[0] and copies < config.MAX_BODIES:
                t -= 0.3  # a copy: an extra life
        arming = any(tr.owner == body.player and tr.arm > 0 for tr in race.traps)
        for item in race.items:
            if item.lane != lane or not 0 < race.gap(race.p_of(item.s), body.p) < WINDOW:
                continue
            if item.kind == "ERR":
                t -= 0.35 if self._rival_on(race, body, lane, 0, 400) else 0.1
            elif not arming:
                t -= 0.3 if self._rival_on(race, body, lane, -150, 0) else 0.15
        return t

    @staticmethod
    def _rival_on(race: Race, body: Body, lane: int, lo: float, hi: float) -> bool:
        return any(o.player != body.player and o.lane == lane and lo < race.gap(o.p, body.p) < hi
                   for o in race.bodies)
