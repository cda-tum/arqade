"""The race: racers on wires, boost pads, kickers, gates that come and go,
item gates, error bugs and Zeno traps. Pure (no pygame), so it is unit
tested; match.py drives it one frame at a time, decides who has fallen off
the screen (camera.py) and puts them back in with reset().

A racer drives like a slot car: gas, brake, or neither (it coasts down),
and left/right change to the neighbouring wire on its own left or right.
Corners have a speed limit per wire (inner wires are shorter but tighter):
over it the racer drifts and scrubs speed, further over it flashes red
while its spin meter fills, and a full meter spins it out: it stalls,
nearly stopped, and the pack streams past.

Each player's racer has its own CarStats (racers.py): heavier racers give
less in bumps and shove lighter ones aside. A boost pad puts a racer over
its top speed; a kicker throws a fast one into the air, where it can't
change wires or drift and flies over everything on the track.

Close behind another racer on the same wire, the slipstream builds; once
full it lasts DRAFT_HOLD after you pull out (like DRS), long enough to
pass.

Gates come and go (GATE_LIFE): a SWAP trades wires, a CNOT copies a racer
onto its target wire. A copy is an extra life: falling off the screen
costs the player nothing while another copy is still on it. Copies
collapse onto the leading one after COPY_TIME. Item gates are taken by the
first racer through them: ERR puts a Pauli-error bug in front of you that
hovers for ERR_HOLD (change wires to aim it) and then shoots off along the
wire (X knocks the racer it hits onto another wire, Z takes its speed);
ZENO drops a trap behind you that slows whoever drives into it.

Progress p is units along the centre line past the track's start; it keeps
counting up, lap after lap. A race can start anywhere (start_p).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from qircuit import config
from qircuit.track import Track


@dataclass
class Controls:
    throttle: bool = False
    brake: bool = False
    left: bool = False  # pressed this frame: change to the wire on the racer's left
    right: bool = False


@dataclass(frozen=True)
class Cue:
    """Something that happened, for the renderer and the sound."""

    kind: str
    player: str | None = None
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass(eq=False)
class Body:
    id: int
    player: str
    p: float
    lane: int  # the wire it is on, or changing to
    u: float  # where it is across the wires
    v: float = 0.0
    reach: float = 0.0  # furthest progress so far: things fire only on new ground
    load: float = 0.0  # lateral acceleration over grip
    curve: float = 0.0  # signed curvature under it (for drawing the drift)
    slip: float = 0.0  # the spin meter, 0..1
    draft: float = 0.0  # 0..1
    drs: float = 0.0  # seconds the full slipstream still lasts, out of it
    wiggle: float = 0.0
    measured: float = 0.0  # seconds left glowing from a Zeno trap
    ghost: float = 0.0  # seconds left passing through everything, just put back in
    spin: float = 0.0  # seconds left spun out
    z: float = 0.0  # height: the track's, or higher in the air
    vz: float = 0.0
    air: bool = False  # off a kicker, flying
    boost: float = 0.0  # seconds of boost flames left
    drifted: float = -9.0  # race time of its last drift cue, so the squeal doesn't chatter
    skip: object | None = None  # a gate to ignore once (after being swapped onto its other wire)


@dataclass(eq=False)
class LiveGate:
    """A SWAP or CNOT on the track for its life, then gone."""

    id: int
    kind: str  # "SWAP" or "CNOT"
    s: float
    lanes: tuple[int, ...]  # the CNOT's (control, target)
    life: float = math.inf
    age: float = 0.0


@dataclass(eq=False)
class Item:
    """An item gate, ERR or ZENO, taken by the first racer through it on its wire."""

    id: int
    kind: str
    s: float
    lane: int
    age: float = 0.0


@dataclass(eq=False)
class Bug:
    """A Pauli error running along a wire, like a shell along a slot, at the
    speed its racer launched it with plus a little. A new one first hovers
    in front of its racer (hold), following it from wire to wire."""

    id: int
    kind: str  # "X" or "Z"
    lane: int
    p: float
    owner: str | None
    life: float
    v: float = 250.0
    hold: float = 0.0  # seconds left hovering in front of its racer
    carrier: int | None = None  # that racer's body id
    u: float | None = None  # where it is across the wires (its lane, once it flies)

    def __post_init__(self) -> None:
        if self.u is None:
            self.u = float(self.lane)


@dataclass(eq=False)
class Trap:
    """A Zeno trap: it blinks behind its racer for ZENO_ARM, then stays on the
    wire. Whatever drives into it is measured so often it can barely move
    on: it loses much of its speed."""

    id: int
    owner: str
    lane: int
    p: float
    arm: float
    body_id: int | None
    life: float = config.ZENO_LIFE
    grace: float = 0.0


@dataclass
class Racer:
    player: str
    stats: config.CarStats
    copy_time: float = 0.0


def approach(value: float, target: float, step: float) -> float:
    if value < target:
        return min(target, value + step)
    return max(target, value - step)


def grid(players: tuple[str, ...], humans: tuple[str, ...], start_p: float = 0.0) -> dict[str, tuple[float, int]]:
    """(progress, wire) on the starting grid for each player: people in the
    front row on their own side (config.GRID_LANES), then everyone else in
    the free places, front row first."""
    slots = [(start_p - config.GRID_BEHIND - row * config.GRID_ROW, lane)
             for row in range(math.ceil(len(players) / config.LANES) + 1) for lane in range(config.LANES)]
    out = {}
    if humans:
        for p, lane in config.GRID_LANES[len(humans)].items():
            out[p] = slots[lane]
    free = [s for s in slots if s not in out.values()]
    for p in players:
        if p not in out:
            out[p] = free.pop(0)
    return out


class Race:
    def __init__(self, track: Track, players: tuple[str, ...], rng: random.Random | None = None,
                 humans: tuple[str, ...] = (), stats: dict[str, config.CarStats] | None = None,
                 start_p: float = 0.0) -> None:
        self.track = track
        self.players = players
        self.humans = tuple(p for p in players if p in humans)
        self.rng = rng or random.Random()
        stats = stats or {}
        self.racers = {p: Racer(p, stats.get(p, config.CAR)) for p in players}
        self.racer_keys: dict[str, str] = {}  # which racer (racers.py) each player drives, for drawing
        self._ids = 0
        self.bodies: list[Body] = []
        for p, (start, lane) in grid(players, self.humans, start_p).items():
            self.bodies.append(self._body(p, start, lane))
        self.bugs: list[Bug] = []
        self.traps: list[Trap] = []
        self.gates: list[LiveGate] = [LiveGate(self._id(), g.kind, g.s, g.lanes) for g in track.gates]
        self.items: list[Item] = []
        self.gate_due: list[float] = []
        for _ in range(track.d.dynamic_gates):
            if not self._spawn_gate():
                self.gate_due.append(config.GATE_RESPAWN)
        self.item_due: list[float] = []
        for _ in range(track.d.items):
            if not self._spawn_item():
                self.item_due.append(config.ITEM_RESPAWN)
        self.time = 0.0
        self._new_bodies: list[Body] = []

    # --- helpers --------------------------------------------------------------------

    def _id(self) -> int:
        self._ids += 1
        return self._ids

    def _body(self, player: str, p: float, lane: int, v: float = 0.0, u: float | None = None) -> Body:
        b = Body(self._id(), player, p, lane, float(lane) if u is None else u, v=v, reach=p)
        b.z = self.track.height(self.s_of(p))
        return b

    def s_of(self, p: float) -> float:
        return (self.track.d.start_s + p) % self.track.length

    def p_of(self, s: float) -> float:
        return (s - self.track.d.start_s) % self.track.length

    def gap(self, a: float, b: float) -> float:
        """Signed distance from b ahead to a along the track (a lap wraps round)."""
        L = self.track.length
        return (a - b + L / 2) % L - L / 2

    def _passes(self, p: float, mark: float) -> int:
        return math.floor((p - mark) / self.track.length)

    def _crossed(self, p_from: float, p_to: float, s: float) -> bool:
        mark = self.p_of(s)
        return self._passes(p_to, mark) > self._passes(p_from, mark)

    def pose(self, body: Body) -> tuple[float, float, float]:
        return self.track.pose(body.u, self.s_of(body.p))

    def lane_point(self, lane: float, p: float) -> tuple[float, float]:
        x, y, _ = self.track.pose(lane, self.s_of(p))
        return x, y

    def bodies_of(self, player: str) -> list[Body]:
        return [b for b in self.bodies if b.player == player]

    def front(self, player: str) -> Body:
        """A player's furthest copy."""
        return max(self.bodies_of(player), key=lambda b: b.p)

    def body(self, body_id: int | None) -> Body | None:
        return next((b for b in self.bodies if b.id == body_id), None)

    def mass(self, b: Body) -> float:
        return self.racers[b.player].stats.mass

    def _cue(self, kind: str, body: Body | None = None, player: str | None = None) -> Cue:
        if body is None:
            return Cue(kind, player)
        x, y, _ = self.pose(body)
        return Cue(kind, body.player, x, y, body.z)

    def _side_by_side(self, lane: int, p: float, exclude: Body) -> Body | None:
        for o in self.bodies:
            if o is not exclude and o.lane == lane and abs(self.gap(o.p, p)) < config.CAR_LEN:
                return o
        return None

    def standings(self) -> list[str]:
        """Who is ahead now, by their furthest copy."""
        return sorted(self.players, key=lambda p: -self.front(p).p)

    def leader(self) -> Body:
        """The furthest body of anyone."""
        return max(self.bodies, key=lambda b: b.p)

    def safe_speed(self, lane: int, p: float, stats: config.CarStats, look: float = 200.0) -> float:
        """The fastest a racer at p on this wire can go and still brake down to
        the drift limit of every corner within look."""
        s0, brake = self.s_of(p), 0.8 * stats.brake
        best, d = math.inf, 0.0
        while d <= look:
            k = abs(self.track.curvature(lane, s0 + d))
            if k > 1e-6:
                v_corner = math.sqrt(config.DRIFT_LOAD * stats.grip / k)
                best = min(best, math.sqrt(v_corner * v_corner + 2 * brake * d))
            d += 4.0
        return best

    def reset(self, player: str, p: float, v: float, events: list) -> Body:
        """Off the screen: back in at progress p (its copies gone), on the
        emptiest wire there, already doing v (or less, if a corner is coming),
        and passing through everything for RESET_GHOST."""
        b = self.front(player)
        for other in self.bodies_of(player):
            if other is not b:
                self.bodies.remove(other)

        def crowd(lane: int) -> tuple:
            near = sum(1 for o in self.bodies if o is not b and o.lane == lane
                       and abs(self.gap(o.p, p)) < 2 * config.CAR_LEN)
            return near, abs(lane - b.lane)

        lane = min(range(config.LANES), key=crowd)
        stats = self.racers[player].stats
        b.p, b.reach = p, max(b.reach, p)
        b.lane, b.u = lane, float(lane)
        b.v = min(v, self.safe_speed(lane, p, stats))
        b.z, b.vz, b.air = self.track.height(self.s_of(p)), 0.0, False
        b.load = b.slip = b.spin = b.measured = b.wiggle = b.boost = b.draft = b.drs = 0.0
        b.ghost = config.RESET_GHOST
        b.skip = None
        events.append(self._cue("reset", b))
        return b

    def drop_copy(self, b: Body, events: list) -> None:
        """One copy off the screen while another is still on it: just that copy goes."""
        if b in self.bodies:
            events.append(self._cue("copy_lost", b))
            self.bodies.remove(b)

    # --- spawning gates and items -------------------------------------------------------

    def _spot_clear(self, s: float, gate_room: float, item_room: float) -> bool:
        """Can something appear at station s: clear of gates, items, boost pads
        and kickers, and not right in front of a racer?"""
        d = self.track.d
        features = [g.s for g in self.gates] + [b[0] for b in d.boosts] + list(d.kickers)
        if any(abs(self.gap(s, f)) < gate_room for f in features):
            return False
        if any(abs(self.gap(s, it.s)) < item_room for it in self.items):
            return False
        p = self.p_of(s)
        return not any(0 <= self.gap(p, b.p) < config.ITEM_AHEAD_CLEAR for b in self.bodies)

    def _spawn_item(self) -> bool:
        kinds = list(config.ITEM_KINDS)
        weights = list(config.ITEM_KINDS.values())
        for _ in range(40):
            s = self.rng.uniform(0, self.track.length)
            if self._spot_clear(s, config.ITEM_GATE_CLEAR, config.ITEM_SPACING):
                kind = self.rng.choices(kinds, weights)[0]
                self.items.append(Item(self._id(), kind, s, self.rng.randrange(config.LANES)))
                return True
        return False

    def _spawn_gate(self) -> bool:
        """A SWAP or CNOT on two neighbouring wires (never across a split's
        gap), for GATE_LIFE; a CNOT's control on either one."""
        kinds = list(config.GATE_KINDS)
        weights = list(config.GATE_KINDS.values())
        for _ in range(40):
            s = self.rng.uniform(0, self.track.length)
            if not self._spot_clear(s, config.GATE_SPACING, config.ITEM_GATE_CLEAR):
                continue
            kind = self.rng.choices(kinds, weights)[0]
            pairs = [(i, i + 1) for i in range(config.LANES - 1) if self.track.can_switch(s, i, i + 1)]
            lanes = self.rng.choice(pairs)
            if kind == "CNOT" and self.rng.random() < 0.5:
                lanes = (lanes[1], lanes[0])
            self.gates.append(LiveGate(self._id(), kind, s, lanes, self.rng.uniform(*config.GATE_LIFE)))
            return True
        return False

    @staticmethod
    def _respawn(waits: list[float], dt: float, spawn) -> list[float]:
        """Count down each wait; spawn when one is up, or try again in half a second."""
        due = []
        for wait in waits:
            wait -= dt
            if wait > 0:
                due.append(wait)
            elif not spawn():
                due.append(0.5)
        return due

    # --- the frame ----------------------------------------------------------------------

    def update(self, dt: float, controls: dict[str, Controls]) -> list[Cue]:
        events: list[Cue] = []
        self.time += dt
        for thing in (*self.items, *self.gates):
            thing.age += dt
        for g in [g for g in self.gates if g.age >= g.life]:
            self.gates.remove(g)
            self.gate_due.append(config.GATE_RESPAWN)
        self.gate_due = self._respawn(self.gate_due, dt, self._spawn_gate)
        self.item_due = self._respawn(self.item_due, dt, self._spawn_item)
        for b in self.bodies:
            b.wiggle = max(0.0, b.wiggle - dt)
        for player in self.players:
            self._steer(player, controls.get(player, Controls()), events)
        for b in list(self.bodies):
            if b in self.bodies:  # not collapsed away earlier this frame
                self._drive(b, controls.get(b.player, Controls()), dt, events)
        self.bodies += self._new_bodies
        self._new_bodies = []
        self._contacts(dt, events)
        self._move_bugs(dt, events)
        self._update_traps(dt, events)
        self._copies(dt, events)
        return events

    # --- steering -------------------------------------------------------------------------

    def _steer(self, player: str, c: Controls, events: list) -> None:
        if c.left == c.right:
            return
        d = 1 if c.right else -1
        movable = [b for b in self.bodies_of(player) if b.spin <= 0 and not b.air]
        for b in sorted(movable, key=lambda b: -b.lane * d):  # copies side by side shift together
            self.switch(b, b.lane + d, events)

    def switch(self, b: Body, target: int, events: list) -> bool:
        """Change b to the neighbouring wire target. Into another racer, it is
        a push: both wiggle and lose speed (BUMP_SIDE_SLOW between equals, the
        lighter one more), and the other moves a wire further over if it can
        and isn't much heavier (otherwise b stays where it was)."""
        s = self.s_of(b.p)
        if not self.track.can_switch(s, b.lane, target):
            return False
        other = self._side_by_side(target, b.p, b)
        if other is None or other.air or other.ghost > 0 or b.ghost > 0:
            b.lane = target
            return True
        if other.player == b.player:
            return False
        mb, mo = self.mass(b), self.mass(other)
        b.wiggle = other.wiggle = config.WIGGLE_TIME
        b.v *= 1 - config.BUMP_SIDE_SLOW * 2 * mo / (mb + mo)
        other.v *= 1 - config.BUMP_SIDE_SLOW * 2 * mb / (mb + mo)
        beyond = target + (target - b.lane)
        if (mb >= 0.8 * mo and self.track.can_switch(s, target, beyond)
                and self._side_by_side(beyond, other.p, other) is None):
            other.lane = beyond
            b.lane = target
            events.append(self._cue("push", b))
            return True
        events.append(self._cue("bump", b))
        return False

    # --- driving ----------------------------------------------------------------------------

    def _drive(self, b: Body, c: Controls, dt: float, events: list) -> None:
        stats = self.racers[b.player].stats
        gas, brake = c.throttle, c.brake
        b.measured = max(0.0, b.measured - dt)
        b.ghost = max(0.0, b.ghost - dt)
        if b.spin > 0:  # spun out: nothing works for a moment
            b.spin = max(0.0, b.spin - dt)
            gas = brake = False
            b.v = max(0.0, b.v - 2 * stats.brake * dt)
        if b.air:  # wheels off the ground: nothing to push or brake against
            gas = brake = False
        top = stats.max_speed * (1 + config.DRAFT_TOP * b.draft)
        if gas and not brake:
            if b.v < top:
                b.v = min(top, b.v + stats.accel * (1 + config.DRAFT_ACCEL * b.draft) * dt)
            else:
                b.v = max(top, b.v - stats.coast * dt)
        elif brake:
            b.v = max(0.0, b.v - stats.brake * dt)
        elif not b.air:
            b.v = max(0.0, b.v - stats.coast * dt)

        b.u = approach(b.u, float(b.lane), stats.switch_rate * dt)
        p_was = b.p
        b.p += b.v * dt / self.track.factor(b.u, self.s_of(b.p))
        s = self.s_of(b.p)
        b.curve = self.track.curvature(b.u, s)
        b.boost = max(0.0, b.boost - dt)
        if b.air:
            self._in_air(b, s, dt, events)
            return
        z_was, b.z = b.z, self.track.height(s)
        if any(self._crossed(p_was, b.p, lip) for lip in self.track.d.kickers) and b.v >= config.JUMP_MIN_SPEED:
            b.air, b.z, b.vz = True, z_was, b.v * config.JUMP_LIFT  # off the top of the lip
            b.load = b.slip = 0.0
            events.append(self._cue("jump", b))
            return
        self._corner(b, stats, dt, events)
        if b.p > b.reach:
            self._cross(b, b.reach, b.p, events)
            b.reach = b.p

    def _corner(self, b: Body, stats: config.CarStats, dt: float, events: list) -> None:
        was = b.load
        b.load = b.v * b.v * abs(b.curve) / stats.grip
        if b.load > config.DRIFT_LOAD:
            b.v *= max(0.0, 1 - config.DRIFT_SCRUB * (b.load - config.DRIFT_LOAD) * dt)
            if was <= config.DRIFT_LOAD and self.time - b.drifted > 1.0:
                b.drifted = self.time
                events.append(Cue("drift", b.player))
        if b.load > config.WARN_LOAD:
            if b.slip == 0:
                events.append(Cue("warn", b.player))
            b.slip += (config.SLIP_BASE + config.SLIP_GAIN * (b.load - config.WARN_LOAD)) * dt
        else:
            b.slip = max(0.0, b.slip - config.SLIP_RECOVER * dt)
        if b.slip >= 1.0:  # spun out: nearly stopped, for a moment
            b.slip = b.load = 0.0
            b.v *= config.SPIN_KEEP
            b.spin = config.SPIN_TIME
            b.wiggle = config.WIGGLE_TIME
            events.append(self._cue("spin", b))

    def _in_air(self, b: Body, s: float, dt: float, events: list) -> None:
        """Flying: no grip, no drift, over everything on the track, until it
        comes down to the track's height again."""
        b.z += b.vz * dt
        b.vz -= config.GRAVITY * dt
        b.load = 0.0
        b.reach = max(b.reach, b.p)  # whatever it flew over, it didn't touch
        ground = self.track.height(s)
        if b.z <= ground and b.vz < 0:
            b.z, b.vz, b.air = ground, 0.0, False
            b.v *= config.LAND_KEEP
            events.append(self._cue("land", b))

    # --- what a racer drives over -----------------------------------------------------------

    def _cross(self, b: Body, p_from: float, p_to: float, events: list) -> None:
        lane = round(b.u)
        stats = self.racers[b.player].stats
        for s, lanes in self.track.d.boosts:
            if lane in lanes and self._crossed(p_from, p_to, s):
                b.v = max(b.v, stats.max_speed * (1 + config.BOOST))
                b.boost = 0.8
                events.append(self._cue("boost", b))
        for g in list(self.gates):
            if not self._crossed(p_from, p_to, g.s):
                continue
            if b.skip is g:
                b.skip = None
                continue
            if lane not in g.lanes:
                continue
            if g.kind == "SWAP":
                self._swap(b, g, lane, events)
            elif g.kind == "CNOT" and lane == g.lanes[0]:
                self._copy(b, g.lanes[1], events)
        for it in list(self.items):
            if it.lane != lane or not self._crossed(p_from, p_to, it.s):
                continue
            if it.kind == "ERR":
                self.bugs.append(Bug(self._id(), self.rng.choice(("X", "Z")), lane, b.p + config.CAR_LEN, b.player,
                                     config.BUG_LIFE, 0.0, hold=config.ERR_HOLD, carrier=b.id, u=b.u))
                events.append(self._cue("err_armed", b))
            elif any(t.owner == b.player and t.arm > 0 for t in self.traps):
                continue  # one Zeno trap at a time: this one stays for someone else
            else:
                self.traps.append(Trap(self._id(), b.player, lane, b.p - config.CAR_LEN, config.ZENO_ARM, b.id))
                events.append(self._cue("zeno_armed", b))
            self.items.remove(it)
            self.item_due.append(config.ITEM_RESPAWN)

    def _swap(self, b: Body, g: LiveGate, lane: int, events: list) -> None:
        """A SWAP: b goes to the other wire, and a racer right beside it there
        comes over to b's wire: they trade places."""
        other_lane = g.lanes[1] if lane == g.lanes[0] else g.lanes[0]
        other = self._side_by_side(other_lane, b.p, b)
        b.lane = other_lane
        if other is not None and other.player != b.player and not other.air:
            other.lane = lane
            if self._passes(other.reach, self.p_of(g.s)) < self._passes(b.p, self.p_of(g.s)):
                other.skip = g  # it hasn't reached the gate yet: don't swap it back
        events.append(self._cue("swap", b))

    def _copy(self, b: Body, target: int, events: list) -> None:
        """A CNOT with this racer on its control wire copies it onto the target
        wire: an extra life for COPY_TIME."""
        mine = self.bodies_of(b.player) + [n for n in self._new_bodies if n.player == b.player]
        if len(mine) >= config.MAX_BODIES:
            return
        if any(o.lane == target and abs(self.gap(o.p, b.p)) < config.CAR_LEN for o in mine):
            return
        self._new_bodies.append(self._body(b.player, b.p, target, v=b.v, u=b.u))
        self.racers[b.player].copy_time = config.COPY_TIME
        events.append(self._cue("copy", b))

    # --- contact ------------------------------------------------------------------------

    def _contacts(self, dt: float, events: list) -> None:
        """Rear-end bumps and slipstream between racers on the same wire. Two
        copies of one racer on the same spot of the same wire merge into one.
        A racer just put back in passes through the others."""
        ground = [b for b in self.bodies if not b.air and b.ghost <= 0]
        drafting = set()
        removed = set()
        for i, a in enumerate(ground):
            for c in ground[i + 1:]:
                if a.id in removed or c.id in removed or a.lane != c.lane or abs(a.u - c.u) >= 0.5:
                    continue
                g = self.gap(a.p, c.p)
                front, rear = (a, c) if g > 0 else (c, a)
                d = abs(g)
                if a.player == c.player:
                    if d < config.CAR_LEN:
                        self.bodies.remove(rear)
                        removed.add(rear.id)
                    continue
                if d < config.CAR_LEN:
                    rear.p -= config.CAR_LEN - d
                    mr, mf = self.mass(rear), self.mass(front)
                    slowed = front.v * (1 - config.BUMP_REAR_SLOW * 2 * mf / (mr + mf))
                    if rear.v > slowed:
                        if mr > mf:  # a heavier racer shoves the one in front along
                            front.v += (rear.v - front.v) * 0.5 * (mr - mf) / (mr + mf)
                        rear.v = slowed
                        if rear.wiggle <= 0:
                            rear.wiggle = front.wiggle = config.WIGGLE_TIME * 0.6
                            events.append(self._cue("bump", rear))
                elif d < config.DRAFT_RANGE:
                    drafting.add(rear.id)
        for b in self.bodies:
            if b.id in drafting:
                b.draft = approach(b.draft, 1.0, config.DRAFT_RISE * dt)
                if b.draft >= 1.0:
                    b.drs = config.DRAFT_HOLD
            elif b.drs > 0:  # pulled out with a full slipstream: it lasts a moment yet
                b.drs = max(0.0, b.drs - dt)
            else:
                b.draft = approach(b.draft, 0.0, config.DRAFT_RISE * dt)

    # --- errors and traps -------------------------------------------------------------------

    def _move_bugs(self, dt: float, events: list) -> None:
        gone: set[int] = set()
        for bug in self.bugs:
            if bug.hold > 0:
                self._hover(bug, dt, events)
            else:
                bug.life -= dt
                if bug.life <= 0:
                    gone.add(bug.id)
                    continue
                bug.p += bug.v * dt / self.track.factor(bug.lane, self.s_of(bug.p))
            for b in self.bodies:
                if b.air or b.ghost > 0 or b.player == bug.owner or round(b.u) != bug.lane:
                    continue
                if abs(self.gap(b.p, bug.p)) < config.CAR_LEN / 2 + 4:
                    gone.add(bug.id)
                    self._hit(b, bug.kind, events)
                    break
        self.bugs = [bug for bug in self.bugs if bug.id not in gone]

    def _hover(self, bug: Bug, dt: float, events: list) -> None:
        """A new bug in front of its racer, on whatever wire the racer is on;
        when its time is up, off it goes along the wire it is on, a little
        faster than its racer."""
        carrier = self.body(bug.carrier)
        bug.hold = 0.0 if carrier is None else max(0.0, bug.hold - dt)
        if carrier is None:
            bug.u, bug.v = float(bug.lane), max(bug.v, config.BUG_MIN_SPEED) + config.BUG_EXTRA[bug.kind]
            return
        bug.p = carrier.p + config.CAR_LEN
        bug.u, bug.lane = carrier.u, round(carrier.u)
        bug.v = carrier.v
        if bug.hold <= 0:
            bug.lane = carrier.lane
            bug.u = float(bug.lane)
            bug.v = max(carrier.v, config.BUG_MIN_SPEED) + config.BUG_EXTRA[bug.kind]
            bug.carrier = None
            events.append(self._cue("launch", carrier))

    def _hit(self, b: Body, kind: str, events: list) -> None:
        """X is a bit flip: the racer is knocked onto a neighbouring wire. Z is
        a phase flip: it loses its timing, most of its speed."""
        b.v *= config.BUG_HIT_KEEP[kind]
        b.wiggle = config.WIGGLE_TIME
        if kind == "X":
            s = self.s_of(b.p)
            sides = [d for d in (-1, 1) if self.track.can_switch(s, b.lane, b.lane + d)]
            if sides:
                self.switch(b, b.lane + self.rng.choice(sides), events)
            events.append(self._cue("bitflip", b))
        else:
            events.append(self._cue("phaseflip", b))

    def _update_traps(self, dt: float, events: list) -> None:
        gone: set[int] = set()
        for t in self.traps:
            if t.arm > 0:
                body = next((b for b in self.bodies if b.id == t.body_id), None)
                if body is not None:
                    t.lane = round(body.u)
                    t.p = body.p - config.CAR_LEN * 1.1
                t.arm -= dt
                if t.arm <= 0:
                    t.body_id = None
                    t.grace = config.ZENO_GRACE
                continue
            t.life -= dt
            t.grace -= dt
            if t.life <= 0:
                gone.add(t.id)
                continue
            for b in self.bodies:
                if b.air or b.ghost > 0 or round(b.u) != t.lane or (b.player == t.owner and t.grace > 0):
                    continue
                if abs(self.gap(b.p, t.p)) < config.CAR_LEN / 2 + 3:
                    b.v *= config.ZENO_KEEP  # measured so often it can barely move on
                    b.measured = config.ZENO_GLOW
                    b.wiggle = config.WIGGLE_TIME
                    gone.add(t.id)
                    events.append(self._cue("zeno", b))
                    break
        self.traps = [t for t in self.traps if t.id not in gone]

    def _copies(self, dt: float, events: list) -> None:
        """After COPY_TIME a player's copies collapse onto the leading one."""
        for player, racer in self.racers.items():
            mine = self.bodies_of(player)
            if len(mine) < 2:
                continue
            racer.copy_time -= dt
            if racer.copy_time > 0:
                continue
            keep = max(mine, key=lambda b: b.p)
            for b in mine:
                if b is not keep:
                    self.bodies.remove(b)
            events.append(self._cue("decohered", keep))
