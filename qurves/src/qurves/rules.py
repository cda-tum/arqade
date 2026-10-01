"""The Qurves simulation: a grid of cells, bikes, superposition and collapse.

Pure Python, no pygame, so every rule is unit tested (tests/test_rules.py).
match.py drives it through two entry points:

- tick(state, inputs, rng): one grid step. Steering, moving, collisions,
  measurements and pickups, in the order the spec lays down.
- advance(state, dt, rng): the real-time part, once per frame. Meter drain,
  decoherence and pickup respawns.

Both return a list of events for the renderer and the sound.

The core idea: a branch only sees real (solid) trail and its own branch.
Your two copies are separate worlds and pass through each other; an
opponent driving through one of your ghost trails measures you. An
eliminated branch never happened, so its ghost trail dissolves, and the
surviving branch's ghost trail becomes solid.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from qurves import config

Vec = tuple[int, int]
PLAYERS = ("p1", "p2")
WALL = "wall"


def add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1])


def left_of(h: Vec) -> Vec:
    """The heading after a left turn, in screen coordinates (y grows downwards)."""
    return (h[1], -h[0])


def right_of(h: Vec) -> Vec:
    return (-h[1], h[0])


def mirror(d: Vec, axis: Vec) -> Vec:
    """Reflect direction d across a line running along heading `axis`: the
    component along the axis is kept, the perpendicular one is negated."""
    if axis[1] == 0:
        return (d[0], -d[1])
    return (-d[0], d[1])


@dataclass(frozen=True)
class Trail:
    """A trail cell. branch is None for solid trail, 0 or 1 for a copy's ghost trail."""

    player: str
    branch: int | None


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
    branch: int | None = None  # None while the player is a single, solid bike
    prev: Vec | None = None  # the cell before the last move, for interpolation
    cells: list[Vec] = field(default_factory=list)  # ghost cells, in order, from the split cell
    crashed: bool = False


@dataclass
class Player:
    name: str
    bikes: list[Bike]
    meter: float = 0.0
    split_axis: Vec | None = None  # the heading at the moment of the split
    alive: bool = True

    @property
    def is_split(self) -> bool:
        return len(self.bikes) == 2


@dataclass
class PlayerInput:
    direction: Vec | None = None  # the latest stick direction since the last tick
    split: bool = False  # A pressed since the last tick


@dataclass
class RoundState:
    arena: Arena
    players: dict[str, Player]
    pickups: list[Vec] = field(default_factory=list)
    respawns: list[float] = field(default_factory=list)  # seconds until each missing pickup returns
    over: bool = False
    winner: str | None = None  # None with over=True is a draw


# --- events ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Moved:
    player: str
    branch: int | None
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
    branch: int | None


@dataclass(frozen=True)
class Collapse:
    player: str
    reason: str  # "crash", "measurement" or "decoherence"
    at: Vec  # where the surviving bike is
    dissolved: tuple[Vec, ...]
    solidified: tuple[Vec, ...]  # the survivor's path, starting at the split cell


@dataclass(frozen=True)
class Measured:
    player: str  # who was measured
    by: str
    pos: Vec


@dataclass(frozen=True)
class PickedUp:
    player: str
    pos: Vec


@dataclass(frozen=True)
class RoundOver:
    winner: str | None


# --- a new round -------------------------------------------------------------------------


def new_round(rng) -> RoundState:
    arena = Arena()
    players = {}
    for name in PLAYERS:
        pos = config.START_CELLS[name]
        arena.set(pos, Trail(name, None))
        players[name] = Player(name, [Bike(pos, config.START_HEADINGS[name], prev=pos)])
    state = RoundState(arena, players)
    for _ in range(config.MAX_PICKUPS):
        spot = _find_pickup_spot(state, rng)
        if spot is None:
            state.respawns.append(0.0)
        else:
            state.pickups.append(spot)
    return state


def _find_pickup_spot(state: RoundState, rng) -> Vec | None:
    """A random empty cell at least PICKUP_MIN_DIST from every bike head, or
    None if a few hundred tries found nothing (the caller retries later)."""
    heads = [b.pos for pl in state.players.values() for b in pl.bikes]
    for _ in range(config.PICKUP_SPAWN_ATTEMPTS):
        c = (rng.randrange(1, state.arena.width - 1), rng.randrange(1, state.arena.height - 1))
        if state.arena.get(c) is not None or c in state.pickups:
            continue
        if all(max(abs(c[0] - h[0]), abs(c[1] - h[1])) >= config.PICKUP_MIN_DIST for h in heads):
            return c
    return None


# --- one tick ---------------------------------------------------------------------------


def tick(state: RoundState, inputs: dict[str, PlayerInput], rng) -> list:
    if state.over:
        return []
    events: list = []
    alive = [pl for pl in state.players.values() if pl.alive]

    # 1. Split, or steer. The fork is the steering on the tick of a split.
    for pl in alive:
        inp = inputs.get(pl.name) or PlayerInput()
        if inp.split and not pl.is_split and pl.meter >= config.SPLIT_MIN_METER:
            _split(pl)
            events.append(Split(pl.name, pl.bikes[0].pos))
            continue
        if inp.direction is None:
            continue
        for bike in pl.bikes:
            d = inp.direction if bike.branch != 1 else mirror(inp.direction, pl.split_axis)
            if d != (-bike.heading[0], -bike.heading[1]):
                bike.heading = d

    # 2. Every bike's target cell.
    moving = [(pl, bike, add(bike.pos, bike.heading)) for pl in alive for bike in pl.bikes]

    # 3. Classify every target against the grid as it was before this tick.
    #    A bike entering the same cell counts as trail of its own kind.
    crashed: set[int] = set()
    touched: dict[str, set[int]] = {}
    for pl, bike, target in moving:
        obstacles = [state.arena.get(target)]
        obstacles += [
            Trail(other_pl.name, other.branch)
            for other_pl, other, other_target in moving
            if other is not bike and other_target == target
        ]
        for ob in obstacles:
            effect = _effect(pl.name, bike, ob)
            if effect == "crash":
                crashed.add(id(bike))
            elif effect == "measure":
                if ob.branch not in touched.setdefault(ob.player, set()):
                    events.append(Measured(ob.player, pl.name, target))
                touched[ob.player].add(ob.branch)

    # 4. Crashes. Losing one copy collapses onto the other; losing all of them loses.
    for pl in alive:
        hit = [b for b in pl.bikes if id(b) in crashed]
        if not hit:
            continue
        for bike in hit:
            bike.crashed = True
            events.append(Crash(pl.name, bike.pos, bike.branch))
        if len(hit) == len(pl.bikes):
            pl.alive = False
        else:
            survivor = next(b for b in pl.bikes if id(b) not in crashed)
            events.append(_collapse(state, pl, survivor.branch, "crash"))

    # 5. Measurements, on players who are still split.
    for name, branches in touched.items():
        pl = state.players[name]
        if not pl.alive or not pl.is_split:
            continue
        survivor = 1 - next(iter(branches)) if len(branches) == 1 else rng.choice((0, 1))
        events.append(_collapse(state, pl, survivor, "measurement"))

    # 6. Write each surviving bike's new cell.
    for pl, bike, target in moving:
        if not pl.alive or bike.crashed or not any(b is bike for b in pl.bikes):
            continue
        bike.prev, bike.pos = bike.pos, target
        state.arena.set(target, Trail(pl.name, bike.branch))
        if bike.branch is not None:
            bike.cells.append(target)
        events.append(Moved(pl.name, bike.branch, bike.prev, target))

    # 7. Pickups. A copy's pickup counts at once, even if that copy is later eliminated.
    for pl in alive:
        if not pl.alive:
            continue
        for bike in pl.bikes:
            if bike.pos in state.pickups:
                state.pickups.remove(bike.pos)
                state.respawns.append(config.PICKUP_RESPAWN)
                pl.meter = min(config.METER_MAX, pl.meter + config.METER_PER_PICKUP)
                events.append(PickedUp(pl.name, bike.pos))

    # 8. Is the round over?
    events += _check_over(state)
    return events


def _effect(owner: str, bike: Bike, ob) -> str | None:
    """What entering a cell holding `ob` does to `bike` (owned by `owner`)."""
    if ob is None:
        return None
    if ob == WALL or ob.branch is None:
        return "crash"
    if ob.player == owner:
        # The other branch of your own player is another world: pass through.
        return None if bike.branch is not None and ob.branch != bike.branch else "crash"
    return "measure"


def _split(pl: Player) -> None:
    bike = pl.bikes[0]
    h = bike.heading
    pl.split_axis = h
    pl.bikes = [
        Bike(bike.pos, left_of(h), 0, prev=bike.pos, cells=[bike.pos]),
        Bike(bike.pos, right_of(h), 1, prev=bike.pos, cells=[bike.pos]),
    ]


def _collapse(state: RoundState, pl: Player, survivor_branch: int, reason: str) -> Collapse:
    """End pl's superposition on survivor_branch: the other branch never
    happened, so its ghost trail dissolves; the survivor's becomes solid.
    Cells someone else has since driven over are left alone."""
    survivor = next(b for b in pl.bikes if b.branch == survivor_branch)
    loser = next(b for b in pl.bikes if b.branch != survivor_branch)
    dissolved = []
    for c in loser.cells:
        if state.arena.get(c) == Trail(pl.name, loser.branch):
            state.arena.set(c, None)
            dissolved.append(c)
    for c in survivor.cells:
        if state.arena.get(c) == Trail(pl.name, survivor_branch):
            state.arena.set(c, Trail(pl.name, None))
    solidified = tuple(survivor.cells)
    survivor.branch = None
    survivor.cells = []
    pl.bikes = [survivor]
    pl.split_axis = None
    return Collapse(pl.name, reason, survivor.pos, tuple(dissolved), solidified)


def _check_over(state: RoundState) -> list:
    alive = [name for name, pl in state.players.items() if pl.alive]
    if len(alive) == len(state.players):
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
        if pl.alive and pl.is_split:
            pl.meter = max(0.0, pl.meter - config.METER_DRAIN_PER_S * dt)
            if pl.meter == 0.0:
                events.append(_collapse(state, pl, rng.choice((0, 1)), "decoherence"))
    pending = []
    for remaining in state.respawns:
        remaining -= dt
        if remaining <= 0:
            spot = _find_pickup_spot(state, rng)
            if spot is not None:
                state.pickups.append(spot)
                continue
            remaining = 0.0
        pending.append(remaining)
    state.respawns = pending
    return events
