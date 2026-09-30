"""A simple kitchen AI: plans recipes as station steps and drives the chefs.

Used by the attract-mode demo and by the headless playthrough tests (which
also make it a rough balancing tool). It plays through the same ChefInput
interface as a human, so everything it does is something a player can do.

A Job turns one order into steps (take / put / tap / hold / press / wait),
each done by the chef that can reach that station. Kitchens split by walls
(the Ion Trap Trattoria) are handled by passing items over the belts.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from overquqed.config import TILE
from overquqed.guests import Order
from overquqed.stations import Station
from overquqed.world import IDLE, ChefInput, World

STEP_TIMEOUT = 14.0
ARRIVE = 2.0  # px from a tile centre counts as there
DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


@dataclass
class Step:
    kind: str  # take | put | tap | hold | press | wait
    station: Station
    chef: int
    helper: int | None = None  # the second chef on a two-chef press
    t: float = 0.0
    mark: int = -1  # item op-count / uid snapshot for completion checks


@dataclass
class Job:
    order_id: int | None
    steps: list[Step]
    chefs: set[int]
    stations: set[tuple[int, int]] = field(default_factory=set)
    i: int = 0

    @property
    def step(self) -> Step | None:
        return self.steps[self.i] if self.i < len(self.steps) else None


class Bot:
    def __init__(self, world: World, chefs: tuple[int, ...] = (0, 1)) -> None:
        self.w = world
        self.chefs = chefs
        self.jobs: list[Job] = []
        self.regions = self._regions()
        self._paths: dict[int, list[tuple[int, int]]] = {}
        self._repath: dict[int, float] = {}
        self.inputs = [IDLE, IDLE]

    # --- geometry -------------------------------------------------------------------------
    def _regions(self) -> dict[tuple[int, int], int]:
        w = self.w
        region: dict[tuple[int, int], int] = {}
        rid = 0
        for y in range(w.h):
            for x in range(w.w):
                if w.walkable(x, y) and (x, y) not in region:
                    q = deque([(x, y)])
                    region[(x, y)] = rid
                    while q:
                        cx, cy = q.popleft()
                        for dx, dy in DIRS:
                            n = (cx + dx, cy + dy)
                            if w.walkable(*n) and n not in region:
                                region[n] = rid
                                q.append(n)
                    rid += 1
        return region

    def region_of_chef(self, idx: int) -> int:
        return self.regions.get(self.w.chefs[idx].tile, -1)

    def approach_tiles(self, st: Station, region: int) -> list[tuple[int, int]]:
        return [
            (st.x + dx, st.y + dy) for dx, dy in DIRS
            if self.regions.get((st.x + dx, st.y + dy)) == region
        ]

    def reachable(self, st: Station, chef: int) -> bool:
        return bool(self.approach_tiles(st, self.region_of_chef(chef)))

    def _bfs(self, start, goals: set, blocked: set) -> list[tuple[int, int]] | None:
        if start in goals:
            return [start]
        prev = {start: None}
        q = deque([start])
        while q:
            cur = q.popleft()
            for dx, dy in DIRS:
                n = (cur[0] + dx, cur[1] + dy)
                if n in prev or not self.w.walkable(*n) or (n in blocked and n not in goals):
                    continue
                prev[n] = cur
                if n in goals:
                    path = [n]
                    while prev[path[-1]] is not None:
                        path.append(prev[path[-1]])
                    return path[::-1]
                q.append(n)
        return None

    # --- planning --------------------------------------------------------------------------
    def _nearest(self, kind: str, chef: int, free_only: bool = False) -> Station | None:
        region = self.region_of_chef(chef)
        c = self.w.chefs[chef]
        best = None
        for st in self.w.stations_of(kind):
            if not self.approach_tiles(st, region):
                continue
            if free_only and (st.item is not None or st.pos in self._reserved()):
                continue
            d = abs(st.x - c.tile[0]) + abs(st.y - c.tile[1])
            if best is None or d < best[0]:
                best = (d, st)
        return best[1] if best else None

    def _reserved(self) -> set[tuple[int, int]]:
        out: set[tuple[int, int]] = set()
        for j in self.jobs:
            out |= j.stations
        return out

    def _chef_for(self, kind: str, prefer: int | None, allowed: set[int]) -> int | None:
        order = ([prefer] if prefer is not None else []) + [c for c in self.chefs if c != prefer]
        for c in order:
            if c in allowed and self._nearest(kind, c) is not None:
                return c
        return None

    def _belt_ends(self, from_region: int, to_region: int) -> tuple[Station, Station] | None:
        belts = self.w.stations_of("belt")
        for start in belts:
            if not self.approach_tiles(start, from_region):
                continue
            # follow the belt
            cur = start
            seen = {cur.pos}
            while True:
                nxt = self.w.station_at((cur.x + cur.belt_dir, cur.y))
                if nxt is None or nxt.kind != "belt" or nxt.pos in seen:
                    break
                seen.add(nxt.pos)
                cur = nxt
            if cur is not start and self.approach_tiles(cur, to_region):
                return start, cur
        return None

    def plan(self, order: Order, free: set[int]) -> Job | None:
        """Steps that make and serve this order, or None if we can't now."""
        steps: list[Step] = []
        chefs_used: set[int] = set()
        stations: set[tuple[int, int]] = set()
        w = self.w

        def need(kind: str, holder: int) -> tuple[Station, int] | None:
            """A station of `kind` for an item currently held by `holder`;
            if only the other region has one, hand the item over a belt."""
            st = self._nearest(kind, holder, free_only=kind not in ("pass", "bin"))
            if st is not None:
                return st, holder
            for other in self.chefs:
                if other == holder or other not in free:
                    continue
                st = self._nearest(kind, other, free_only=kind not in ("pass", "bin"))
                if st is None:
                    continue
                ends = self._belt_ends(self.region_of_chef(holder), self.region_of_chef(other))
                if ends is None:
                    continue
                start, end = ends
                steps.append(Step("put", start, holder))
                steps.append(Step("wait", end, other))
                steps.append(Step("take", end, other))
                chefs_used.add(other)
                return st, other
            return None

        def fetch(prefer: int | None) -> int | None:
            chef = self._chef_for("fridge", prefer, free)
            if chef is None:
                return None
            if w.supply is not None and w.supply <= 0:
                return None
            steps.append(Step("take", self._nearest("fridge", chef), chef))
            chefs_used.add(chef)
            return chef

        def gate(kind: str, holder: int, action: str) -> int | None:
            got = need(kind, holder)
            if got is None:
                return None
            st, holder = got
            stations.add(st.pos)
            steps.extend([Step("put", st, holder), Step(action, st, holder), Step("take", st, holder)])
            return holder

        recipe = order.recipe
        prefer = next(iter(sorted(free)))
        key = recipe.key
        single = {"0": [], "1": ["x"], "+": ["h"], "-": ["x", "h"]}
        if key in single:
            if w.supply is not None and w.supply < 1:
                return None
            holder = fetch(prefer)
            if holder is None:
                return None
            for kind in single[key]:
                holder = gate(kind, holder, "tap" if kind == "x" else "hold")
                if holder is None:
                    return None
        else:
            if w.supply is not None and w.supply < recipe.n:
                return None
            if not w.stations_of("control"):
                return None
            holder = fetch(prefer)
            if holder is None:
                return None
            holder = gate("h", holder, "hold")
            if holder is None:
                return None
            got = need("control", holder)
            if got is None:
                return None
            control, holder = got
            target = control.partner
            if target is None or target.item is not None or control.item is not None:
                return None
            stations.update({control.pos, target.pos})
            steps.append(Step("put", control, holder))
            presser = holder
            extra = 2 if key == "GHZ" else 1
            for _ in range(extra):
                # (for GHZ the Bell tray the first press left in the control
                # slot is the control of the second press)
                f = fetch(presser)
                if f is None:
                    return None
                if f != presser:
                    return None  # keep the entangling in one region
                steps.append(Step("put", target, presser))
                helper = None
                if w.level.two_chef_press and not w.solo:
                    helper = next((c for c in self.chefs if c != presser and c in free), None)
                    if helper is None:
                        return None
                    chefs_used.add(helper)
                steps.append(Step("press", control, presser, helper=helper))
            steps.append(Step("take", control, presser))
            holder = presser
            post = {"Phi-": ["z"], "Psi+": ["x"], "Psi-": ["x", "z"]}.get(key, [])
            for kind in post:
                holder = gate(kind, holder, "tap")
                if holder is None:
                    return None
        got = need("pass", holder)
        if got is None:
            return None
        pas, holder = got
        steps.append(Step("put", pas, holder))
        chefs_used.add(holder)
        return Job(order.id, steps, chefs_used, stations)

    def plan_cleanup(self, free: set[int]) -> Job | None:
        """Limited fridge: bring dirty bowls from the pass to the sink."""
        w = self.w
        dirty = [s for s in w.stations_of("pass") if s.item is not None and not s.item.is_qubit]
        if not dirty or w.supply is None:
            return None
        for chef in sorted(free):
            if not self.reachable(dirty[0], chef):
                continue
            steps: list[Step] = [Step("take", dirty[0], chef)]
            sink = self._nearest("sink", chef, free_only=True)
            holder = chef
            used = {chef}
            if sink is None:
                other = next((c for c in self.chefs if c != chef and c in free), None)
                if other is None:
                    return None
                sink = self._nearest("sink", other, free_only=True)
                ends = self._belt_ends(self.region_of_chef(chef), self.region_of_chef(other))
                if sink is None or ends is None:
                    return None
                steps += [Step("put", ends[0], chef), Step("wait", ends[1], other), Step("take", ends[1], other)]
                holder = other
                used.add(other)
            steps += [Step("put", sink, holder), Step("hold", sink, holder)]
            return Job(None, steps, used, {sink.pos})
        return None

    # --- execution --------------------------------------------------------------------------
    def update(self, dt: float) -> list[ChefInput]:
        w = self.w
        busy = set().union(*(j.chefs for j in self.jobs)) if self.jobs else set()
        free = {c for c in self.chefs if c not in busy and w.chefs[c].held is None}
        taken = {j.order_id for j in self.jobs}
        if free:
            if w.supply is not None and w.supply < 2 and not any(j.order_id is None for j in self.jobs):
                job = self.plan_cleanup(free)
                if job is not None:
                    self.jobs.append(job)
                    free -= job.chefs
            for order in sorted(w.orders.orders, key=lambda o: o.remaining):
                if not free or order.id in taken:
                    continue
                job = self.plan(order, set(free))
                if job is not None:
                    self.jobs.append(job)
                    free -= job.chefs
        inputs = [IDLE, IDLE]
        for job in list(self.jobs):
            self._run(job, dt, inputs)
            if job.step is None:
                self.jobs.remove(job)
        # anyone left holding something with no job: bin it
        for c in self.chefs:
            chef = w.chefs[c]
            if chef.held is not None and not any(c in j.chefs for j in self.jobs):
                b = self._nearest("bin", c) or self._nearest("sink", c)
                if b is not None:
                    self.jobs.append(Job(None, [Step("put", b, c)] if b.kind == "bin" else
                                         [Step("put", b, c), Step("hold", b, c)], {c}, set()))
        self.inputs = inputs
        return inputs

    def _goto(self, idx: int, st: Station, dt: float) -> ChefInput | None:
        """Walk next to `st` and face it. None once facing it."""
        chef = self.w.chefs[idx]
        if chef.target == st.pos:
            return None
        region = self.region_of_chef(idx)
        goals = set(self.approach_tiles(st, region))
        if not goals:
            return IDLE
        if chef.tile in goals:
            cx, cy = (chef.tile[0] + 0.5) * TILE, (chef.tile[1] + 0.5) * TILE
            if abs(chef.x - cx) > ARRIVE or abs(chef.y - cy) > ARRIVE:
                return ChefInput(move=(_sgn(cx - chef.x, ARRIVE), _sgn(cy - chef.y, ARRIVE)))
            return ChefInput(move=(st.x - chef.tile[0], st.y - chef.tile[1]))
        self._repath[idx] = self._repath.get(idx, 0.0) - dt
        path = self._paths.get(idx)
        if not path or self._repath[idx] <= 0 or path[-1] not in goals or chef.tile not in path:
            others = {c.tile for c in self.w.chefs if c.idx != idx}
            path = self._bfs(chef.tile, goals, others) or self._bfs(chef.tile, goals, set())
            self._paths[idx] = path or []
            self._repath[idx] = 0.5
        path = self._paths[idx]
        if not path:
            return IDLE
        i = path.index(chef.tile) if chef.tile in path else 0
        nxt = path[min(i + 1, len(path) - 1)]
        tx, ty = (nxt[0] + 0.5) * TILE, (nxt[1] + 0.5) * TILE
        # keep centred on the lane we're leaving, so corners don't snag
        cx, cy = (chef.tile[0] + 0.5) * TILE, (chef.tile[1] + 0.5) * TILE
        mx = _sgn(tx - chef.x, ARRIVE) if nxt[0] != chef.tile[0] else _sgn(cx - chef.x, ARRIVE)
        my = _sgn(ty - chef.y, ARRIVE) if nxt[1] != chef.tile[1] else _sgn(cy - chef.y, ARRIVE)
        return ChefInput(move=(mx, my))

    def _run(self, job: Job, dt: float, inputs: list[ChefInput]) -> None:
        step = job.step
        if step is None:
            return
        w = self.w
        step.t += dt
        if step.t > STEP_TIMEOUT:
            job.i = len(job.steps)  # give up; stray items get binned
            return
        chef = w.chefs[step.chef]
        st = step.station
        if step.kind == "press":
            done = step.mark >= 0 and (st.item is None or st.item.n > step.mark) and st.partner.item is None
            if done:
                job.i += 1
                return
            if step.mark < 0 and st.item is not None:
                step.mark = st.item.n
            for idx, side in ((step.chef, st), (step.helper, st.partner)):
                if idx is None:
                    continue
                mv = self._goto(idx, side, dt)
                inputs[idx] = mv if mv is not None else ChefInput(use=True, use_pressed=step.t < 0.1)
            return
        mv = self._goto(step.chef, st, dt)
        if mv is not None:
            inputs[step.chef] = mv
            return
        if step.kind == "wait":
            if st.item is not None and st.belt_offset == 0.0:
                job.i += 1
            return
        if step.kind == "take":
            if chef.held is not None:
                job.i += 1
            elif st.kind == "fridge" or st.item is not None:
                inputs[step.chef] = ChefInput(pick=True)
            return
        if step.kind == "put":
            if chef.held is None:
                job.i += 1
                return
            if st.kind in ("pass", "bin") or st.accepts(chef.held):
                inputs[step.chef] = ChefInput(pick=True)
                if st.kind == "pass" and step.mark == 1:
                    # the pass refused ("nobody ordered that"): bin it instead
                    job.i = len(job.steps)
                step.mark = 1
            return
        if step.kind in ("tap", "hold"):
            item = st.item
            if item is None:
                job.i += 1  # sink finished (item went back to the fridge)
                return
            ops = len(item.state.ops) if item.is_qubit else -item.uid
            if step.mark == -1:
                step.mark = ops
            if ops != step.mark or (st.kind == "sink" and item.is_qubit and item.state.n == 1
                                    and not item.state.ops and step.t > 0.2 and st.progress == 0):
                job.i += 1
                return
            if step.kind == "tap":
                inputs[step.chef] = ChefInput(use=True, use_pressed=int(step.t * 10) % 3 == 0)
            else:
                inputs[step.chef] = ChefInput(use=True, use_pressed=step.t < 0.05)


def _sgn(v: float, dead: float) -> int:
    return 0 if abs(v) <= dead else (1 if v > 0 else -1)
