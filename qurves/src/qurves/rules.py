"""The Qurves simulation: a grid of cells, bikes, superposition and collapse.

Pure Python, no pygame, so every rule is unit tested (tests/test_rules.py).
match.py drives it through two entry points:

- tick(state, directions, rng): one grid step. Steering, moving, collisions,
  measurements and gates, in the order the spec lays down.
- advance(state, dt, rng): the real-time part, once per frame. The
  superposition bar draining into decoherence, shields wearing off, gates
  respawning.

Both return a list of events for the renderer and the sound.

Gates act on the bike (the copy) that drives over them:
- H splits it into two copies, one forking each way, and adds to the bar.
- X mirrors its horizontal position across the arena and shields it.
- Z shields it.
A shield lets a bike drive through any trail and keeps it from being
measured; walls still stop it.

Superposition as a tree. Every split makes two child nodes of the copy that
split, and every ghost cell remembers the node that drew it. A copy sees
solid trail and its own history (its node and that node's ancestors) as
walls; every other copy of the same player is another world it passes
through. An opponent driving through a ghost cell measures that node: every
copy descending from it never happened. Whenever copies are eliminated,
trail shared by all the survivors becomes solid, and trail no survivor
descends from dissolves.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from qurves import config

Vec = tuple[int, int]
WALL = "wall"


def add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1])


def dist(a: Vec, b: Vec) -> int:
    """Chebyshev distance: how many king moves apart two cells are."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def left_of(h: Vec) -> Vec:
    """The heading after a left turn, in screen coordinates (y grows downwards)."""
    return (h[1], -h[0])


def right_of(h: Vec) -> Vec:
    return (-h[1], h[0])


def reflect_flip(flip: Vec, axis: Vec) -> Vec:
    """A copy's steering flip after mirroring across a line along `axis`:
    a horizontal axis flips up/down, a vertical one left/right."""
    if axis[1] == 0:
        return (flip[0], -flip[1])
    return (-flip[0], flip[1])


def steer(d: Vec, flip: Vec) -> Vec:
    """The stick direction d as a copy with steering flip `flip` sees it."""
    return (d[0] * flip[0], d[1] * flip[1])


@dataclass(frozen=True)
class Trail:
    """A trail cell. node is None for solid trail, else the copy that drew it."""

    player: str
    node: int | None


class Arena:
    """The cell grid. The outermost ring is wall; reading outside the grid is wall too."""

    def __init__(self, width: int = config.GRID_W, height: int = config.GRID_H) -> None:
        self.width, self.height = width, height
        self.cells: list[list] = [[None] * width for _ in range(height)]
        for x in range(width):
            self.cells[0][x] = self.cells[height - 1][x] = WALL
        for y in range(height):
            self.cells[y][0] = self.cells[y][width - 1] = WALL

    def get(self, c: Vec):
        x, y = c
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.cells[y][x]
        return WALL

    def set(self, c: Vec, value) -> None:
        self.cells[c[1]][c[0]] = value


@dataclass
class Bike:
    pos: Vec
    heading: Vec
    node: int | None = None  # None while the player is a single, solid bike
    flip: Vec = (1, 1)  # how this copy mirrors the stick
    prev: Vec | None = None  # the cell before the last move, for interpolation
    shield: float = 0.0  # seconds of invulnerability left
    fresh: bool = False  # just forked: ignores the stick for one tick
    crashed: bool = False


@dataclass
class Node:
    parent: int | None
    cells: list[Vec]  # in order, starting at the cell it forked from


@dataclass
class Player:
    name: str
    bikes: list[Bike]
    meter: float = 0.0  # seconds of superposition left
    alive: bool = True
    nodes: dict[int, Node] = field(default_factory=dict)  # ghost nodes still in play
    next_node: int = 1

    @property
    def is_split(self) -> bool:
        return len(self.bikes) > 1

    def lineage(self, node: int | None) -> set[int]:
        """A node and its ancestors that are still ghosts."""
        out = set()
        while node is not None and node in self.nodes:
            out.add(node)
            node = self.nodes[node].parent
        return out


@dataclass
class Gate:
    kind: str  # "H", "X" or "Z"
    pos: Vec  # the centre of its 5x5 pickup area


@dataclass
class RoundState:
    arena: Arena
    players: dict[str, Player]
    gates: list[Gate] = field(default_factory=list)
    respawns: list[float] = field(default_factory=list)  # seconds until each missing gate returns
    over: bool = False
    winner: str | None = None  # None with over=True is a draw


# --- events ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Moved:
    player: str
    node: int | None
    frm: Vec
    to: Vec


@dataclass(frozen=True)
class Split:
    player: str
    pos: Vec


@dataclass(frozen=True)
class Crash:
    player: str
    pos: Vec
    node: int | None


@dataclass(frozen=True)
class Collapse:
    player: str
    reason: str  # "crash", "measurement", "decoherence" or "lost"
    at: tuple[Vec, ...]  # where the surviving copies are
    dissolved: tuple[Vec, ...]
    solidified: tuple[tuple[Vec, ...], ...]  # paths that turned solid, each in order


@dataclass(frozen=True)
class Measured:
    player: str  # who was measured
    by: str
    pos: Vec


@dataclass(frozen=True)
class PickedUp:
    player: str
    kind: str
    pos: Vec


@dataclass(frozen=True)
class Teleported:
    player: str
    frm: Vec
    to: Vec


@dataclass(frozen=True)
class RoundOver:
    winner: str | None


# --- a new round -------------------------------------------------------------------------


def new_round(rng, players: tuple[str, ...] = ("p1", "p2")) -> RoundState:
    arena = Arena()
    built = {}
    for name in players:
        pos, heading = config.START[len(players)][name]
        arena.set(pos, Trail(name, None))
        built[name] = Player(name, [Bike(pos, heading, prev=pos)])
    state = RoundState(arena, built)
    for _ in range(config.MAX_GATES[len(players)]):
        gate = _spawn_gate(state, rng)
        if gate is None:
            state.respawns.append(0.0)
        else:
            state.gates.append(gate)
    return state


def _spawn_gate(state: RoundState, rng) -> Gate | None:
    """A random gate on an empty cell clear of every head and every other gate,
    or None if a few hundred tries found nothing (the caller retries later)."""
    heads = [b.pos for pl in state.players.values() for b in pl.bikes]
    margin = 1 + config.GATE_REACH
    for _ in range(config.GATE_SPAWN_ATTEMPTS):
        c = (rng.randrange(margin, state.arena.width - margin),
             rng.randrange(margin, state.arena.height - margin))
        if state.arena.get(c) is not None:
            continue
        if any(dist(c, h) < config.GATE_MIN_DIST for h in heads):
            continue
        if any(dist(c, g.pos) < config.GATE_GAP for g in state.gates):
            continue
        kinds = list(config.GATE_WEIGHTS)
        return Gate(rng.choices(kinds, [config.GATE_WEIGHTS[k] for k in kinds])[0], c)
    return None


# --- one tick ---------------------------------------------------------------------------


def tick(state: RoundState, directions: dict, rng) -> list:
    """One grid step. `directions` maps a player to the stick direction to
    apply this tick, or None to keep going straight."""
    if state.over:
        return []
    events: list = []
    alive = [pl for pl in state.players.values() if pl.alive]

    # 1. Steer. A copy that just forked keeps its fork heading for one tick.
    for pl in alive:
        d = directions.get(pl.name)
        for bike in pl.bikes:
            if bike.fresh:
                bike.fresh = False
                continue
            if d is None:
                continue
            want = steer(d, bike.flip)
            if want != (-bike.heading[0], -bike.heading[1]):
                bike.heading = want

    # 2. Every bike's target cell.
    moving = [(pl, bike, add(bike.pos, bike.heading)) for pl in alive for bike in pl.bikes]

    # 3. Classify every target against the grid as it was before this tick.
    #    A bike entering the same cell counts as trail of its own kind.
    crashed: set[int] = set()
    touches: list[tuple[str, int, str, Vec]] = []  # (measured, node, by, cell)
    for pl, bike, target in moving:
        obstacles = [state.arena.get(target)]
        obstacles += [
            Trail(other_pl.name, other.node)
            for other_pl, other, other_target in moving
            if other is not bike and other_target == target
        ]
        for ob in obstacles:
            effect = _effect(pl, bike, ob)
            if effect == "crash":
                crashed.add(id(bike))
            elif effect == "measure":
                touches.append((ob.player, ob.node, pl.name, target))

    # 4. Crashes. A crashed copy is eliminated; losing every copy loses the round.
    for pl in alive:
        hit = [b for b in pl.bikes if id(b) in crashed]
        if not hit:
            continue
        for bike in hit:
            bike.crashed = True
            events.append(Crash(pl.name, bike.pos, bike.node))
        pl.bikes = [b for b in pl.bikes if id(b) not in crashed]
        if not pl.bikes:
            pl.alive = False
            if pl.nodes:
                events.append(_resolve(state, pl, "lost"))
        else:
            events.append(_resolve(state, pl, "crash"))

    # 5. Measurements. Every copy descending from a touched node never happened,
    #    unless it is shielded. If that would be every copy, one survives at random.
    for name in dict.fromkeys(t[0] for t in touches):
        pl = state.players[name]
        if not pl.alive or not pl.is_split:
            continue
        mine = [t for t in touches if t[0] == name]
        nodes = {t[1] for t in mine}
        doomed = [b for b in pl.bikes if b.shield <= 0 and pl.lineage(b.node) & nodes]
        if not doomed:
            continue
        for _, _, by, cell in dict.fromkeys(mine):
            events.append(Measured(name, by, cell))
        if len(doomed) == len(pl.bikes):
            doomed.remove(rng.choice(doomed))
        pl.bikes = [b for b in pl.bikes if b not in doomed]
        events.append(_resolve(state, pl, "measurement"))

    # 6. Write each surviving bike's new cell.
    for pl, bike, target in moving:
        if not pl.alive or bike.crashed or not any(b is bike for b in pl.bikes):
            continue
        bike.prev, bike.pos = bike.pos, target
        _paint(state, pl, bike)
        events.append(Moved(pl.name, bike.node, bike.prev, target))

    # 7. Gates.
    for pl in alive:
        if not pl.alive:
            continue
        for bike in list(pl.bikes):
            gate = next((g for g in state.gates if dist(g.pos, bike.pos) <= config.GATE_REACH), None)
            if gate is None:
                continue
            state.gates.remove(gate)
            state.respawns.append(config.GATE_RESPAWN)
            events.append(PickedUp(pl.name, gate.kind, gate.pos))
            events += _take(state, pl, bike, gate.kind)

    # 8. Is the round over?
    events += _check_over(state)
    return events


def _effect(pl: Player, bike: Bike, ob) -> str | None:
    """What entering a cell holding `ob` does to `bike` (owned by `pl`)."""
    if ob is None:
        return None
    if ob == WALL:
        return "crash"
    if ob.player == pl.name and ob.node is not None and ob.node not in pl.lineage(bike.node):
        return None  # another copy's world: pass through
    if ob.player != pl.name and ob.node is not None:
        return "measure"
    return None if bike.shield > 0 else "crash"


def _paint(state: RoundState, pl: Player, bike: Bike) -> None:
    state.arena.set(bike.pos, Trail(pl.name, bike.node))
    if bike.node is not None:
        pl.nodes[bike.node].cells.append(bike.pos)


def _take(state: RoundState, pl: Player, bike: Bike, kind: str) -> list:
    if kind == "H":
        if len(pl.bikes) < config.MAX_COPIES:
            _split(pl, bike)
            pl.meter = min(config.SUPERPOSITION_MAX, pl.meter + config.H_TIME)
            return [Split(pl.name, bike.pos)]
        if pl.is_split:
            pl.meter = min(config.SUPERPOSITION_MAX, pl.meter + config.H_TIME)
        return []
    if kind == "X":
        frm = bike.pos
        bike.pos = bike.prev = (state.arena.width - 1 - frm[0], frm[1])
        bike.shield = max(bike.shield, config.SHIELD_X)
        _paint(state, pl, bike)
        return [Teleported(pl.name, frm, bike.pos)]
    if kind == "Z":
        bike.shield = max(bike.shield, config.SHIELD_Z)
    return []


def _split(pl: Player, bike: Bike) -> None:
    """Fork `bike` in place: it turns left, and a mirrored twin turns right."""
    h = bike.heading
    a, b = pl.next_node, pl.next_node + 1
    pl.next_node += 2
    pl.nodes[a] = Node(bike.node, [bike.pos])
    pl.nodes[b] = Node(bike.node, [bike.pos])
    twin = Bike(bike.pos, right_of(h), b, reflect_flip(bike.flip, h), prev=bike.pos,
                shield=bike.shield, fresh=True)
    bike.node, bike.heading, bike.fresh = a, left_of(h), True
    pl.bikes.insert(pl.bikes.index(bike) + 1, twin)


def _resolve(state: RoundState, pl: Player, reason: str) -> Collapse:
    """After copies were eliminated: trail no survivor descends from dissolves,
    trail every survivor descends from becomes solid. Cells someone else has
    since driven over are left alone."""
    lineages = [pl.lineage(b.node) for b in pl.bikes]
    live = set().union(*lineages)
    shared = set.intersection(*lineages) if lineages else set()
    dissolved: list[Vec] = []
    solidified: list[tuple[Vec, ...]] = []
    for nid in sorted(pl.nodes):
        node = pl.nodes[nid]
        mine = Trail(pl.name, nid)
        if nid not in live:
            for c in node.cells:
                if state.arena.get(c) == mine:
                    state.arena.set(c, None)
                    dissolved.append(c)
            del pl.nodes[nid]
        elif nid in shared:
            for c in node.cells:
                if state.arena.get(c) == mine:
                    state.arena.set(c, Trail(pl.name, None))
            solidified.append(tuple(node.cells))
            del pl.nodes[nid]
    for bike in pl.bikes:
        if bike.node is not None and bike.node not in pl.nodes:
            bike.node = None
    if len(pl.bikes) == 1:
        pl.bikes[0].flip = (1, 1)
        pl.meter = 0.0
    return Collapse(pl.name, reason, tuple(b.pos for b in pl.bikes), tuple(dissolved), tuple(solidified))


def _check_over(state: RoundState) -> list:
    alive = [name for name, pl in state.players.items() if pl.alive]
    if len(alive) > 1:
        return []
    state.over = True
    state.winner = alive[0] if alive else None
    return [RoundOver(state.winner)]


# --- real time --------------------------------------------------------------------------


def advance(state: RoundState, dt: float, rng) -> list:
    if state.over:
        return []
    events: list = []
    for pl in state.players.values():
        if not pl.alive:
            continue
        for bike in pl.bikes:
            bike.shield = max(0.0, bike.shield - dt)
        if pl.is_split:
            pl.meter = max(0.0, pl.meter - dt)
            if pl.meter == 0.0:
                pl.bikes = [rng.choice(pl.bikes)]
                events.append(_resolve(state, pl, "decoherence"))
    pending = []
    for remaining in state.respawns:
        remaining -= dt
        if remaining <= 0:
            gate = _spawn_gate(state, rng)
            if gate is not None:
                state.gates.append(gate)
                continue
            remaining = 0.0
        pending.append(remaining)
    state.respawns = pending
    return events
