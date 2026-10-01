"""Game rules: qubit pairs appearing, routes being drawn, qubits travelling.

Pure Python, no pygame, so the whole game logic is unit tested. game.py only
feeds player actions in and draws the state (plus `events`) back out.

The model:

- A **pair** is a two-qubit gate waiting to happen: two endpoint qubits in the
  same color ("stations"). While it waits, its coherence timer runs down; at
  zero it decoheres and costs a life.
- Each player has a **cursor**. It always starts on a station and draws a
  route from there, one coupler at a time. A player can only ever start from
  stations, never roam the chip freely.
- When the route reaches the partner station it is **committed** and the
  qubit from the starting end travels along it at QUBIT_SPEED. Its couplers
  are reserved (no other route may use them) and released one by one as soon
  as the qubit has passed them.
- **Qubits are shared, couplers are not.** Routes may cross each other at a
  qubit, and may even run through other stations. Each qubit has a finite
  extent (NODE_RADIUS, in coupler lengths): two qubits inside the same one at
  the same time crash, both gates are lost and it costs a life. A station
  counts as occupied while its qubit is still sitting there: both ends of a
  waiting pair, the start of a route until its qubit has left, and the end of
  a route until the gate has fired. So running through a station is only
  safe if that pair gets routed away in time -- the player is free to plan
  for that. Live collisions and the lookahead (`predict_collision`,
  `predicted_crashes`) use the same occupancy windows, so a warning on screen
  means exactly what will happen if nothing changes.
- Arrival executes the gate: points for a short route (fidelity) and for the
  coherence that was left.

On top of that, **specials** appear on the chip for a while:

- `miscal`: a miscalibrated coupler, MISCAL_SLOWDOWN times slower and with
  lower fidelity, until it is recalibrated.
- `defect`: a broken coupler nothing can use, until it is restored.
- `speed`: a qubit that doubles the speed of every qubit travelling over it.
- `bell`: two linked qubits. A route that enters one continues from the
  other, once; the link is used up when the qubit teleports through it.

Specials never appear on anything a route (committed or half-drawn) still
needs, and never share a qubit with a station.

Pairs come from a seeded, endless spawn schedule. In VERSUS both chips use the
same seed, so both players get the identical sequence of pairs.
"""

from __future__ import annotations

import random
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass, field

from superconductor import config
from superconductor.lattice import Edge, Lattice, Node, edge

PALETTE_SIZE = 8  # number of distinct pair colors game.py provides
SPECIAL_KINDS = ("miscal", "defect", "speed", "bell")


@dataclass(frozen=True)
class Spawn:
    t: float  # schedule time at which the pair becomes due
    a: Node
    b: Node
    coherence: float


def ramp(start: float, end: float, t: float) -> float:
    """Linear from start (t=0) to end (t=RAMP_SECONDS), constant afterwards."""
    frac = min(1.0, max(0.0, t / config.RAMP_SECONDS))
    return start + (end - start) * frac


def spawn_schedule(lattice: Lattice, seed: int) -> Iterator[Spawn]:
    rng = random.Random(seed)
    t = 0.5
    count = 0
    while True:
        a = rng.choice(lattice.nodes)
        far = [n for n in lattice.nodes if lattice.distance(a, n) >= config.MIN_PAIR_DISTANCE]
        b = rng.choice(far)
        yield Spawn(t, a, b, ramp(config.COHERENCE_START, config.COHERENCE_MIN, t))
        count += 1
        if count >= config.INITIAL_PAIRS:  # the first few all arrive at once
            t += ramp(config.SPAWN_INTERVAL_START, config.SPAWN_INTERVAL_MIN, t)


@dataclass
class Pair:
    id: int
    a: Node
    b: Node
    color: int
    coherence: float  # full coherence time
    life: float  # coherence left
    route: list[Node] | None = None  # set once committed, route[0] = moving qubit
    teleports: set[int] = field(default_factory=set)  # link indices that are Bell jumps
    progress: float = 0.0  # links travelled along route
    boost: float = 1.0  # speed multiplier picked up from speed qubits
    fidelity: float = 1.0  # lowered by miscalibrated couplers on the way
    routed_by: str | None = None

    @property
    def waiting(self) -> bool:
        return self.route is None

    def other(self, end: Node) -> Node:
        return self.b if end == self.a else self.a

    def segment(self) -> tuple[Node, Node, float, bool]:
        """Where the travelling qubit is: (from, to, fraction, is_bell_jump)."""
        assert self.route is not None
        last = len(self.route) - 1
        i = min(int(self.progress), last - 1)
        f = min(1.0, self.progress - i)
        return self.route[i], self.route[i + 1], f, i in self.teleports


@dataclass
class Special:
    kind: str  # one of SPECIAL_KINDS
    life: float
    duration: float
    edge: Edge | None = None  # miscal / defect
    nodes: tuple[Node, ...] = ()  # speed: 1 node, bell: 2 nodes
    claimed_by: int | None = None  # bell: pair whose committed route uses it

    def anchor(self) -> tuple[Node, ...]:
        """Where to show a label for it: the coupler's two ends, or its first qubit."""
        return tuple(self.edge) if self.edge is not None else self.nodes[:1]


@dataclass
class Cursor:
    player: str
    pair_id: int | None = None
    path: list[Node] = field(default_factory=list)  # path[0] = chosen station

    def clear(self) -> None:
        self.pair_id = None
        self.path = []


@dataclass
class Event:
    # spawn | select | step | back | blocked | routed | teleport | boost | gate
    # | decohere | crash | special_on | special_off
    kind: str
    pair: Pair | None = None
    player: str | None = None
    node: Node | None = None
    points: int = 0
    fidelity: float = 1.0
    special: Special | None = None
    pairs: tuple[Pair, ...] = ()


class Board:
    """One chip and everything happening on it (one per chip, so two in VERSUS)."""

    def __init__(self, lattice: Lattice, seed: int, players: tuple[str, ...],
                 lives: int = config.LIVES, specials: bool = True):
        self.lattice = lattice
        self.players = players
        self.cursors = {p: Cursor(p) for p in players}
        self.pairs: dict[int, Pair] = {}  # insertion order = age, oldest first
        self.endpoint_owner: dict[Node, int] = {}  # stations, exclusive
        self.edge_owner: dict[Edge, int] = {}  # couplers on committed routes, exclusive
        self.specials: list[Special] = []
        self.queue: list[Spawn] = []
        self._schedule = spawn_schedule(lattice, seed)
        self._next = next(self._schedule)
        self._next_id = 0
        self._special_rng = random.Random(seed * 7919 + 1)
        self._next_special = config.SPECIAL_FIRST if specials else float("inf")
        self.time = 0.0  # real play time on this board
        self.clock = 0.0  # schedule time (runs ahead when the board is idle)
        self.score = 0
        self.lives = lives
        self.gates = 0
        self.events: list[Event] = []

    # ------------------------------------------------------------------ queries
    @property
    def over(self) -> bool:
        return self.lives <= 0

    def waiting_pairs(self) -> list[Pair]:
        return [p for p in self.pairs.values() if p.waiting]

    def travelling_pairs(self) -> list[Pair]:
        return [p for p in self.pairs.values() if not p.waiting]

    def claimed_by_other(self, pair_id: int, player: str) -> bool:
        return any(c.pair_id == pair_id for p, c in self.cursors.items() if p != player)

    def stations(self, player: str) -> list[tuple[int, Node]]:
        """Endpoints the player may start from, oldest pair first."""
        out = []
        for pair in self.waiting_pairs():
            if not self.claimed_by_other(pair.id, player):
                out += [(pair.id, pair.a), (pair.id, pair.b)]
        return out

    def target(self, player: str) -> Node | None:
        cur = self.cursors[player]
        if cur.pair_id is None:
            return None
        return self.pairs[cur.pair_id].other(cur.path[0])

    def edge_special(self, e: Edge) -> Special | None:
        return next((s for s in self.specials if s.edge == e), None)

    def node_special(self, n: Node) -> Special | None:
        return next((s for s in self.specials if n in s.nodes), None)

    def bell_partner(self, n: Node) -> Node | None:
        s = self.node_special(n)
        if s is None or s.kind != "bell":
            return None
        return s.nodes[1] if s.nodes[0] == n else s.nodes[0]

    def busy_nodes(self) -> set[Node]:
        """Qubits that stations and specials must not appear on."""
        busy = set(self.endpoint_owner)
        for pair in self.travelling_pairs():
            busy.update(pair.route[int(pair.progress):])
        for cur in self.cursors.values():
            busy.update(cur.path)
        for s in self.specials:
            busy.update(s.nodes)
        return busy

    def busy_edges(self) -> set[Edge]:
        """Couplers that specials must not appear on."""
        busy = set(self.edge_owner)
        for cur in self.cursors.values():
            busy.update(edge(a, b) for a, b in zip(cur.path, cur.path[1:]))
        busy.update(s.edge for s in self.specials if s.edge is not None)
        return busy

    def _can_enter(self, pair: Pair, frm: Node, to: Node, target: Node) -> bool:
        """May `pair`'s route step over the coupler frm -> to?

        Other stations are deliberately allowed (see the module docstring).
        """
        e = edge(frm, to)
        if e in self.edge_owner:
            return False
        s = self.edge_special(e)
        if s is not None and s.kind == "defect":
            return False
        s = self.node_special(to)
        if s is not None and s.kind == "bell" and s.claimed_by is not None:
            return False
        return True

    def _link_ok(self, pair: Pair, a: Node, b: Node, target: Node) -> bool:
        if self.lattice.has_edge(a, b):
            return self._can_enter(pair, a, b, target)
        s = self.node_special(a)  # a Bell jump
        return (s is not None and s.kind == "bell" and s.claimed_by is None
                and self.bell_partner(a) == b)

    def free_route(self, pair: Pair, start: Node) -> list[Node] | None:
        """Shortest route from `start` to its partner over usable couplers.

        Used by the title screen's demo bot; it keeps clear of Bell qubits and
        other stations.
        """
        target = pair.other(start)
        came_from: dict[Node, Node | None] = {start: None}
        queue = deque([start])
        while queue:
            n = queue.popleft()
            if n == target:
                path = [n]
                while came_from[path[-1]] is not None:
                    path.append(came_from[path[-1]])
                return path[::-1]
            for m in self.lattice.neighbors(n):
                if (m not in came_from and self.bell_partner(m) is None
                        and (m == target or m not in self.endpoint_owner)
                        and self._can_enter(pair, n, m, target)):
                    came_from[m] = n
                    queue.append(m)
        return None

    # ------------------------------------------------------------------ timing
    def _link_time(self, route: list[Node], teleports: set[int], i: int, boost: float) -> float:
        """Seconds to travel link i of a route at the given boost."""
        if i in teleports:
            return config.TELEPORT_TIME
        s = self.edge_special(edge(route[i], route[i + 1]))
        slow = config.MISCAL_SLOWDOWN if s is not None and s.kind == "miscal" else 1.0
        return slow / (config.QUBIT_SPEED * boost)

    def _boosted(self, node: Node, boost: float) -> float:
        s = self.node_special(node)
        if s is not None and s.kind == "speed":
            return min(config.MAX_BOOST, boost * config.SPEED_BOOST)
        return boost

    def route_windows(self, route: list[Node], teleports: set[int], progress: float,
                      boost: float, open_end: bool = False) -> dict[Node, tuple[float, float]]:
        """When (seconds from now) a qubit on `route` occupies each qubit it still visits.

        The start counts as occupied from forever until the qubit has left
        it, the end from forever until the gate fires on arrival (the partner
        qubit sits there all along). With `open_end` (a half-drawn route) the
        last node is just passed through, assuming normal speed from there.
        """
        inf = float("inf")
        last = len(route) - 1
        i0 = int(progress)
        if i0 >= last:
            return {}
        durs: dict[int, float] = {}
        times: dict[int, float] = {}
        b = boost
        durs[i0] = self._link_time(route, teleports, i0, b)
        times[i0] = -(progress - i0) * durs[i0]
        for k in range(i0 + 1, last + 1):
            times[k] = times[k - 1] + durs[k - 1]
            b = self._boosted(route[k], b)
            durs[k] = (self._link_time(route, teleports, k, b) if k < last
                       else 1.0 / (config.QUBIT_SPEED * b))
        r = config.NODE_RADIUS
        out = {}
        for k in range(i0, last + 1):
            if k == 0:
                out[route[k]] = (-inf, times[0] + r * durs[0])
            elif k == last and not open_end:
                out[route[k]] = (-inf, times[k])
            else:
                before = durs.get(k - 1, durs[k])
                out[route[k]] = (times[k] - r * before, times[k] + r * durs[k])
        return out

    def windows(self, pair: Pair) -> dict[Node, tuple[float, float]]:
        """Occupancy windows of a committed or waiting pair."""
        if pair.waiting:
            inf = float("inf")
            return {pair.a: (-inf, inf), pair.b: (-inf, inf)}
        return self.route_windows(pair.route, pair.teleports, pair.progress, pair.boost)

    @staticmethod
    def _first_overlap(mine: dict, theirs: dict) -> tuple[float, Node] | None:
        best = None
        for n, (a0, a1) in mine.items():
            if n in theirs:
                b0, b1 = theirs[n]
                start, end = max(a0, b0), min(a1, b1)
                if start < end and end > 0:
                    start = max(start, 0.0)
                    if best is None or start < best[0]:
                        best = (start, n)
        return best

    def predict_collision(self, player: str) -> Node | None:
        """Where the half-drawn route would crash if committed right now."""
        cur = self.cursors[player]
        if len(cur.path) < 2:
            return None
        pair = self.pairs[cur.pair_id]
        teleports = {i for i in range(len(cur.path) - 1)
                     if not self.lattice.has_edge(cur.path[i], cur.path[i + 1])}
        mine = self.route_windows(cur.path, teleports, 0.0, 1.0, open_end=True)
        inf = float("inf")
        mine[pair.other(cur.path[0])] = (-inf, inf)  # the partner keeps waiting
        hits = [h for other in self.pairs.values() if other.id != pair.id
                if (h := self._first_overlap(mine, self.windows(other)))]
        return min(hits)[1] if hits else None

    def predicted_crashes(self) -> set[Node]:
        """Qubits where committed routes will crash if nothing changes."""
        pairs = list(self.pairs.values())
        wins = {p.id: self.windows(p) for p in pairs}
        out = set()
        for i, p in enumerate(pairs):
            for q in pairs[i + 1:]:
                if p.waiting and q.waiting:
                    continue  # two stations never share a qubit
                hit = self._first_overlap(wins[p.id], wins[q.id])
                if hit:
                    out.add(hit[1])
        return out

    # ------------------------------------------------------------------ actions
    def select(self, player: str, step: int) -> None:
        """Jump to the next (step=1) or previous (step=-1) station."""
        stations = self.stations(player)
        if not stations:
            return
        cur = self.cursors[player]
        current = (cur.pair_id, cur.path[0]) if cur.pair_id is not None else None
        idx = stations.index(current) if current in stations else (-1 if step > 0 else 0)
        pair_id, node = stations[(idx + step) % len(stations)]
        self._set_station(player, pair_id, node)

    def other_end(self, player: str) -> None:
        cur = self.cursors[player]
        if cur.pair_id is not None:
            self._set_station(player, cur.pair_id, self.pairs[cur.pair_id].other(cur.path[0]))

    def undo(self, player: str) -> None:
        """Take back the last step (a Bell jump is undone as a whole)."""
        cur = self.cursors[player]
        if len(cur.path) < 2:
            return
        cur.path.pop()
        head = cur.path[-1]
        # standing on a Bell entry without having jumped is not a valid state
        if len(cur.path) > 1 and self.bell_partner(head) is not None \
                and self.bell_partner(head) != cur.path[-2]:
            cur.path.pop()
        self.events.append(Event("back", player=player, node=cur.path[-1]))

    def clear(self, player: str) -> None:
        cur = self.cursors[player]
        if len(cur.path) > 1:
            cur.path = cur.path[:1]
            self.events.append(Event("back", player=player, node=cur.path[0]))

    def move(self, player: str, direction: str) -> None:
        """Extend the route one coupler, or step back if that's where it came from."""
        if self.over:
            return
        cur = self.cursors[player]
        if cur.pair_id is None:
            return
        pair = self.pairs[cur.pair_id]
        head = cur.path[-1]
        nxt = self.lattice.neighbor(head, direction)
        target = pair.other(cur.path[0])
        if nxt is None:
            self.events.append(Event("blocked", pair, player, head))
        elif len(cur.path) >= 2 and nxt == cur.path[-2]:
            self.undo(player)
        elif nxt in cur.path or not self._can_enter(pair, head, nxt, target):
            self.events.append(Event("blocked", pair, player, nxt))
        else:
            cur.path.append(nxt)
            partner = self.bell_partner(nxt)
            if partner is not None:
                if partner in cur.path:
                    cur.path.pop()
                    self.events.append(Event("blocked", pair, player, nxt))
                    return
                cur.path.append(partner)
                self.events.append(Event("teleport", pair, player, partner))
            if cur.path[-1] == target:
                self._commit(player)
            elif partner is None:
                self.events.append(Event("step", pair, player, nxt))

    def commit_route(self, pair_id: int, route: list[Node]) -> None:
        """Commit a whole route at once (the title screen's demo bot)."""
        self._commit_route(self.pairs[pair_id], route, None)

    def place_special(self, kind: str, *, edge_: Edge | None = None,
                      nodes: tuple[Node, ...] | None = None) -> Special | None:
        """Put a special on the chip, at a random free spot unless one is given."""
        rng = self._special_rng
        if kind in ("miscal", "defect"):
            if edge_ is None:
                busy = self.busy_edges()
                free = sorted((e for e in self.lattice.edges if e not in busy), key=sorted)
                if not free:
                    return None
                edge_ = rng.choice(free)
            nodes = ()
        elif nodes is None:
            free = sorted(set(self.lattice.nodes) - self.busy_nodes())
            if kind == "speed":
                if not free:
                    return None
                nodes = (rng.choice(free),)
            else:
                # Bell ends never sit side by side on the grid, so a jump is
                # always visibly a jump.
                options = [(a, b) for a in free for b in free
                           if a < b and abs(a[0] - b[0]) + abs(a[1] - b[1]) >= config.BELL_MIN_DISTANCE]
                if not options:
                    return None
                nodes = rng.choice(options)
        duration = config.SPECIAL_DURATION[kind]
        special = Special(kind, duration, duration, edge_, tuple(nodes))
        self.specials.append(special)
        self.events.append(Event("special_on", special=special))
        self._prune_drafts()
        return special

    # ------------------------------------------------------------------ time
    def update(self, dt: float) -> None:
        if self.over:
            return
        self.time += dt
        self.clock += dt
        # Never leave the player with nothing to do. (A spawn at t=inf, as
        # scripted test schedules end with, never arrives.)
        if not self.waiting_pairs() and not self.queue and self._next.t != float("inf"):
            self.clock = max(self.clock, self._next.t - config.IDLE_SPAWN_DELAY)
        while self._next.t <= self.clock:
            self.queue.append(self._next)
            self._next = next(self._schedule)
        self._spawn_queued()
        self._update_specials(dt)

        for pair in list(self.pairs.values()):
            if pair.waiting:
                pair.life -= dt
                if pair.life <= 0:
                    self._decohere(pair)
            else:
                self._advance(pair, dt)
            if self.over:
                break
        if not self.over:
            self._check_collisions()
        self._prune_drafts()  # also drops cursors whose pair just vanished
        if not self.over:
            self._autoselect()

    # ------------------------------------------------------------------ internals
    def _set_station(self, player: str, pair_id: int, node: Node) -> None:
        cur = self.cursors[player]
        cur.pair_id = pair_id
        cur.path = [node]
        self.events.append(Event("select", self.pairs[pair_id], player, node))

    def _spawn_queued(self) -> None:
        busy = self.busy_nodes()
        for spawn in list(self.queue):
            if len(self.pairs) >= config.MAX_ACTIVE_PAIRS:
                break
            if spawn.a in busy or spawn.b in busy:
                continue  # that spot is in use; the pair comes once it clears
            used = {p.color for p in self.pairs.values()}
            color = next(c for c in range(PALETTE_SIZE) if c not in used)
            pair = Pair(self._next_id, spawn.a, spawn.b, color, spawn.coherence, spawn.coherence)
            self._next_id += 1
            self.pairs[pair.id] = pair
            self.endpoint_owner[pair.a] = self.endpoint_owner[pair.b] = pair.id
            busy.update((pair.a, pair.b))
            self.queue.remove(spawn)
            self.events.append(Event("spawn", pair))

    def _update_specials(self, dt: float) -> None:
        for s in list(self.specials):
            if s.kind == "bell" and s.claimed_by is not None:
                continue  # a route is on its way to use it
            s.life -= dt
            if s.life <= 0:
                self.specials.remove(s)
                self.events.append(Event("special_off", special=s))
        if self.time >= self._next_special:
            placed = None
            if len(self.specials) < config.MAX_SPECIALS:
                unlocked = [k for k in SPECIAL_KINDS if self.time >= config.SPECIAL_UNLOCK[k]]
                placed = self.place_special(self._special_rng.choice(unlocked))
            if placed is not None:
                self._next_special = self.time + self._special_rng.uniform(*config.SPECIAL_INTERVAL)
            else:
                self._next_special = self.time + 2.0  # no room right now, try again soon

    def _commit(self, player: str) -> None:
        cur = self.cursors[player]
        pair = self.pairs[cur.pair_id]
        route = cur.path
        cur.clear()
        self._commit_route(pair, route, player)

    def _commit_route(self, pair: Pair, route: list[Node], player: str | None) -> None:
        pair.route = list(route)
        pair.routed_by = player
        for i, (n0, n1) in enumerate(zip(route, route[1:])):
            if self.lattice.has_edge(n0, n1):
                self.edge_owner[edge(n0, n1)] = pair.id
            else:
                pair.teleports.add(i)
                self.node_special(n0).claimed_by = pair.id
        self.events.append(Event("routed", pair, player, pair.route[-1]))
        self._enter_link(pair, 0)
        self._prune_drafts()
        self._autoselect()

    def _release(self, pair: Pair, nodes: list[Node], edges: list[Edge]) -> None:
        for n in nodes:
            if self.endpoint_owner.get(n) == pair.id:
                del self.endpoint_owner[n]
        for e in edges:
            if self.edge_owner.get(e) == pair.id:
                del self.edge_owner[e]

    def _route_edges(self, pair: Pair, upto: int | None = None) -> list[Edge]:
        route = pair.route
        n = len(route) - 1 if upto is None else upto
        return [edge(route[i], route[i + 1]) for i in range(n) if i not in pair.teleports]

    def _enter_link(self, pair: Pair, i: int) -> None:
        """The travelling qubit starts on link i of its route."""
        if i in pair.teleports:
            s = self.node_special(pair.route[i])
            if s is not None:
                self.specials.remove(s)
            self.events.append(Event("teleport", pair, pair.routed_by, pair.route[i + 1]))
            return
        s = self.edge_special(edge(pair.route[i], pair.route[i + 1]))
        if s is not None and s.kind == "miscal":
            pair.fidelity *= config.MISCAL_FIDELITY

    def _reach_node(self, pair: Pair, k: int) -> None:
        boosted = self._boosted(pair.route[k], pair.boost)
        if boosted != pair.boost:
            pair.boost = boosted
            self.events.append(Event("boost", pair, pair.routed_by, pair.route[k]))

    def _advance(self, pair: Pair, dt: float) -> None:
        route = pair.route
        last = len(route) - 1
        remaining = dt
        while remaining > 0 and pair.progress < last:
            i = int(pair.progress)
            dur = self._link_time(route, pair.teleports, i, pair.boost)
            left = (i + 1 - pair.progress) * dur
            if left > remaining:
                pair.progress += remaining / dur
                remaining = 0.0
            else:
                remaining -= left
                pair.progress = float(i + 1)
                if i + 1 < last:
                    self._reach_node(pair, i + 1)
                    self._enter_link(pair, i + 1)
        passed = int(pair.progress)
        self._release(pair, route[:min(passed, 1)], self._route_edges(pair, passed))
        if pair.progress >= last:
            self._complete(pair)

    def _complete(self, pair: Pair) -> None:
        hops = len(pair.route) - 1 - len(pair.teleports)
        extra = max(0, hops - self.lattice.distance(pair.a, pair.b))
        fidelity = config.DETOUR_FIDELITY ** extra * pair.fidelity
        points = round(config.GATE_BASE_POINTS * fidelity
                       + config.TIME_BONUS * max(0.0, pair.life) / pair.coherence)
        self.score += points
        self.gates += 1
        self._release(pair, [pair.a, pair.b], self._route_edges(pair))
        del self.pairs[pair.id]
        self.events.append(Event("gate", pair, pair.routed_by, pair.route[-1], points, fidelity))

    def _decohere(self, pair: Pair) -> None:
        self._release(pair, [pair.a, pair.b], [])
        del self.pairs[pair.id]
        self.lives -= 1
        self.events.append(Event("decohere", pair))

    def _check_collisions(self) -> None:
        if not self.travelling_pairs():
            return
        inside: dict[Node, list[Pair]] = {}
        for pair in self.pairs.values():
            for n, (t0, t1) in self.windows(pair).items():
                if t0 <= 0 < t1:
                    inside.setdefault(n, []).append(pair)
        for n, pairs in inside.items():
            pairs = [p for p in pairs if p.id in self.pairs]
            if len(pairs) < 2:
                continue
            for p in pairs:
                self._release(p, [p.a, p.b], self._route_edges(p) if not p.waiting else [])
                for s in self.specials:
                    if s.claimed_by == p.id:
                        s.claimed_by = None
                del self.pairs[p.id]
            self.lives -= config.CRASH_LIFE_COST
            self.events.append(Event("crash", node=n, pairs=tuple(pairs)))
            if self.over:
                return

    def _prune_drafts(self) -> None:
        """Cut every drawn route back to before anything it may no longer use."""
        for cur in self.cursors.values():
            if cur.pair_id is None:
                continue
            pair = self.pairs.get(cur.pair_id)
            if pair is None or not pair.waiting:
                cur.clear()
                continue
            target = pair.other(cur.path[0])
            for i in range(1, len(cur.path)):
                if not self._link_ok(pair, cur.path[i - 1], cur.path[i], target):
                    cut = i
                    # don't leave the route standing on a Bell entry
                    if i >= 2 and not self.lattice.has_edge(cur.path[i - 1], cur.path[i]):
                        cut = i - 1
                    cur.path = cur.path[:cut]
                    break

    def _autoselect(self) -> None:
        """A cursor without a pair grabs the oldest free one."""
        for player, cur in self.cursors.items():
            if cur.pair_id is None:
                stations = self.stations(player)
                if stations:
                    self._set_station(player, *stations[0])
