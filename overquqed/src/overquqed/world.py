"""The kitchen simulation: map, chefs, items, stations, orders and hazards.

Pure logic (no pygame), stepped at a fixed 60 Hz by the game with one
ChefInput per chef. Everything the presentation layer needs to react to
(sounds, particles, floating text) is appended to `events` as tuples and
drained by the caller each frame.

Coordinates are map pixels: tile (tx, ty) spans [tx*TILE, (tx+1)*TILE).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from overquqed.config import TILE
from overquqed.guests import OrderBook
from overquqed.levels import Level
from overquqed.quantum import QState, cnot_merge
from overquqed.scoring import LEAVE_PENALTY
from overquqed.stations import (
    BELT_SPEED,
    HOLD_TIMES,
    JAM_TIME,
    KINDS,
    TAP_GATES,
    Item,
    ItemView,
    Station,
)

CHEF_SPEED = 92.0  # px/s, a bit under 4 tiles/s
HALF_W, HALF_H = 6, 5  # chef collision box half-size (feet)
CORNER_ASSIST = 9  # px: slide round a corner you are this close to clearing
REFRESH_INTERVAL = 0.1  # noise + labels at 10 Hz, not every frame
ANIM_TIME = 0.4  # gate rotation animation
COSMIC_WARNING = 2.0
# Seconds to the first cosmic ray, then between rays (drawn uniformly):
# about five or six hits in the Cosmic Cafe's three minutes.
COSMIC_FIRST = (18.0, 24.0)
COSMIC_EVERY = (25.0, 33.0)
WALKABLE = ".12"


@dataclass
class ChefInput:
    move: tuple[int, int] = (0, 0)
    pick: bool = False  # A pressed this frame
    use: bool = False  # B held
    use_pressed: bool = False  # B pressed this frame


IDLE = ChefInput()


def _overlap(dx: float, dy: float) -> float:
    """Penetration depth of two chef boxes whose centres are (dx, dy) apart."""
    return min(2 * HALF_W - abs(dx), 2 * HALF_H - abs(dy))


class Chef:
    def __init__(self, idx: int, x: float, y: float) -> None:
        self.idx = idx
        self.x, self.y = x, y
        self.facing = (0, 1)
        self.held: Item | None = None
        self.moving = False
        self.walk = 0.0  # walk-cycle clock
        self.working = False  # holding B on something that progresses

    @property
    def tile(self) -> tuple[int, int]:
        return int(self.x // TILE), int(self.y // TILE)

    @property
    def target(self) -> tuple[int, int]:
        tx, ty = self.tile
        return tx + self.facing[0], ty + self.facing[1]


@dataclass
class Receipt:
    ops: list[tuple]
    n: int
    tokens: tuple[str, ...]
    fidelity: float
    points: int
    guest: str
    t: float


@dataclass
class Stats:
    delivered: int = 0
    refused: int = 0
    left: int = 0
    fidelities: list[float] = field(default_factory=list)
    best: Receipt | None = None

    @property
    def avg_fidelity(self) -> float:
        return sum(self.fidelities) / len(self.fidelities) if self.fidelities else 0.0


@dataclass
class Cosmic:
    next_at: float
    center: tuple[int, int] | None = None
    hit_at: float = 0.0
    last_hit: float = -99.0
    last_center: tuple[int, int] | None = None

    def area(self, center: tuple[int, int] | None = None) -> set[tuple[int, int]]:
        cx, cy = center or self.center
        return {(cx + dx, cy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)}


class World:
    def __init__(self, level: Level, rng: random.Random | None = None, solo: bool = False) -> None:
        self.level = level
        self.rng = rng or random.Random()
        self.solo = solo
        self.noise = level.noise
        self.tiles = [row for row in level.map]
        self.h = len(self.tiles)
        self.w = len(self.tiles[0])
        self.stations: dict[tuple[int, int], Station] = {}
        spawns: dict[str, tuple[int, int]] = {}
        for y, row in enumerate(self.tiles):
            if len(row) != self.w:
                raise ValueError(f"map row {y} is {len(row)} wide, expected {self.w}")
            for x, ch in enumerate(row):
                if ch in KINDS:
                    st = Station(KINDS[ch], x, y, ch)
                    if ch in "<>":
                        st.belt_dir = 1 if ch == ">" else -1
                    self.stations[(x, y)] = st
                elif ch in "12":
                    spawns[ch] = (x, y)
        self._link_presses()
        self.chefs = [
            Chef(i, (spawns[k][0] + 0.5) * TILE, (spawns[k][1] + 0.5) * TILE)
            for i, k in enumerate("12")
        ]
        self.t = 0.0
        self.supply = level.fridge_capacity  # None = unlimited
        spawn_scale = level.solo_spawn_scale if solo else 1.0
        patience = level.patience_scale * (level.solo_patience_scale if solo else 1.0)
        self.orders = OrderBook(
            recipes=level.recipes,
            guests=level.guests,
            duration=level.duration,
            spawn_interval=level.spawn_interval * spawn_scale,
            spawn_interval_end=level.spawn_interval_end * spawn_scale,
            first_order_at=level.first_order_at,
            patience_scale=patience,
            max_tickets=level.max_tickets,
            rng=self.rng,
            auto_spawn=not level.tutorial,
        )
        self.score = 0
        self.stats = Stats()
        self.events: list[tuple] = []
        self.pending_dirty: list[tuple[float, int, tuple[int, int]]] = []
        self.cosmic = Cosmic(next_at=self.rng.uniform(*COSMIC_FIRST)) if level.cosmic_rays else None
        self._refresh_timer = 0.0
        self.press_users: dict[int, set[int]] = {}  # id(control station) -> chef idxs

    # --- map queries ------------------------------------------------------
    def _link_presses(self) -> None:
        controls = [s for s in self.stations.values() if s.kind == "control"]
        targets = [s for s in self.stations.values() if s.kind == "target"]
        for c in controls:
            best = min(targets, key=lambda t: (abs(t.y - c.y) * 100 + abs(t.x - c.x)), default=None)
            if best is not None:
                c.partner, best.partner = best, c
                targets.remove(best)

    def walkable(self, tx: int, ty: int) -> bool:
        return 0 <= tx < self.w and 0 <= ty < self.h and self.tiles[ty][tx] in WALKABLE

    def station_at(self, pos: tuple[int, int]) -> Station | None:
        return self.stations.get(pos)

    def stations_of(self, kind: str) -> list[Station]:
        return [s for s in self.stations.values() if s.kind == kind]

    def items(self) -> list[Item]:
        out = [s.item for s in self.stations.values() if s.item is not None]
        out += [c.held for c in self.chefs if c.held is not None]
        return out

    @property
    def time_left(self) -> float:
        return max(0.0, self.level.duration - self.t)

    @property
    def over(self) -> bool:
        return self.t >= self.level.duration

    # --- items -------------------------------------------------------------
    def refresh(self, item: Item) -> None:
        """Bring an item's state up to now (lazy decoherence) and rebuild its view."""
        if item.state is None:
            item.view = None
            return
        s = item.state
        s.advance(self.t, self.noise)
        tokens, prefix = s.label()
        item.view = ItemView(
            tokens, prefix, s.ideal_fidelity(), [s.bloch(q) for q in range(s.n)], s.entanglement()
        )
        item.anims = [a for a in item.anims if self.t - a[2] < ANIM_TIME]

    def new_qubit(self) -> Item:
        item = Item(QState.fresh(self.t))
        self.refresh(item)
        return item

    def _apply_gate(self, st: Station, gate: str) -> None:
        item = st.item
        self.refresh(item)
        before = item.state.bloch(0)
        item.state.apply(gate, 0, self.noise.depolarizing)
        item.anims.append((0, gate, self.t, before))
        self.refresh(item)
        st.last_used = self.t
        self.events.append(("gate", gate, st.pos))

    # --- stepping ----------------------------------------------------------
    def update(self, dt: float, inputs: list[ChefInput]) -> None:
        self.t += dt
        for chef, inp in zip(self.chefs, inputs):
            self._move(chef, inp.move, dt)
        for chef, inp in zip(self.chefs, inputs):
            if inp.pick:
                self._pick(chef)
        self._work(dt, inputs)
        self._belts(dt)
        self._dirty_returns()
        self._hazards()
        spawned, expired = self.orders.update(dt, self.t)
        for order in spawned:
            self.events.append(("order", order))
        for order in expired:
            self.score += LEAVE_PENALTY
            self.stats.left += 1
            self.events.append(("guest_left", order))
        self._refresh_timer -= dt
        if self._refresh_timer <= 0:
            self._refresh_timer += REFRESH_INTERVAL
            for item in self.items():
                self.refresh(item)

    # --- movement ----------------------------------------------------------
    def _blocked(self, chef: Chef, x: float, y: float) -> bool:
        x0, x1 = int((x - HALF_W) // TILE), int((x + HALF_W - 0.001) // TILE)
        y0, y1 = int((y - HALF_H) // TILE), int((y + HALF_H - 0.001) // TILE)
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                if not self.walkable(tx, ty):
                    return True
        for other in self.chefs:
            if other is chef:
                continue
            depth = _overlap(other.x - x, other.y - y)
            # blocked if this overlaps more than now (so two chefs that
            # somehow ended up overlapping can still walk apart)
            if depth > 0 and depth >= _overlap(other.x - chef.x, other.y - chef.y):
                return True
        return False

    def _move(self, chef: Chef, move: tuple[int, int], dt: float) -> None:
        dx, dy = move
        chef.moving = (dx, dy) != (0, 0)
        if not chef.moving:
            return
        chef.walk += dt
        if dx and dy:
            if chef.facing not in ((dx, 0), (0, dy)):
                chef.facing = (dx, 0)
        else:
            chef.facing = (dx, dy)
        step = CHEF_SPEED * dt * (math.sqrt(0.5) if dx and dy else 1.0)
        if dx:
            self._slide(chef, dx * step, 0.0, step)
        if dy:
            self._slide(chef, 0.0, dy * step, step)

    def _slide(self, chef: Chef, mx: float, my: float, step: float) -> None:
        if not self._blocked(chef, chef.x + mx, chef.y + my):
            chef.x += mx
            chef.y += my
            return
        # creep up flush to the obstacle, a pixel at a time
        ux, uy = (math.copysign(1, mx) if mx else 0.0), (math.copysign(1, my) if my else 0.0)
        crept = False
        for _ in range(int(abs(mx) + abs(my))):
            if self._blocked(chef, chef.x + ux, chef.y + uy):
                break
            chef.x += ux
            chef.y += uy
            crept = True
        if crept:
            return
        # Corner assist: if a small sideways shift would clear the obstacle,
        # nudge that way instead of stopping dead (tile-grid kitchens feel
        # sticky otherwise).
        for k in range(1, CORNER_ASSIST + 1):
            for sign in (-1, 1):
                ox, oy = (0.0, sign * k) if mx else (sign * k, 0.0)
                if not self._blocked(chef, chef.x + ox + mx, chef.y + oy + my):
                    nx = sign * min(k, step) if not mx else 0.0
                    ny = sign * min(k, step) if mx else 0.0
                    if not self._blocked(chef, chef.x + nx, chef.y + ny):
                        chef.x += nx
                        chef.y += ny
                    return

    # --- A: pick up / put down ------------------------------------------------
    def _pick(self, chef: Chef) -> None:
        st = self.station_at(chef.target)
        if st is None:
            self.events.append(("nope", chef.target))
            return
        if chef.held is None:
            if st.kind == "fridge":
                if self.supply is not None and self.supply <= 0:
                    self.events.append(("fridge_empty", st.pos))
                    return
                if self.supply is not None:
                    self.supply -= 1
                chef.held = self.new_qubit()
                self.events.append(("fridge", st.pos))
            elif st.item is not None:
                self.refresh(st.item)
                chef.held, st.item = st.item, None
                st.progress = 0.0
                st.belt_offset = 0.0
                if st.partner is not None:
                    st.partner.progress = 0.0
                    st.progress = 0.0
                self.events.append(("pick", st.pos))
            else:
                self.events.append(("nope", st.pos))
            return

        item = chef.held
        if st.kind == "pass":
            if item.is_qubit:
                self._serve(chef, st)
            else:
                self.events.append(("nope", st.pos))
        elif st.kind == "bin":
            self._bin(chef, st)
        elif st.accepts(item):
            self.refresh(item)
            if st.item is not None:  # dirty stacks merge
                st.item.dirty += item.dirty
            else:
                st.item = item
            chef.held = None
            st.progress = 0.0
            st.belt_offset = 0.0
            if st.partner is not None:
                st.partner.progress = 0.0
            self.events.append(("put", st.pos))
        else:
            self.events.append(("nope", st.pos))

    def _bin(self, chef: Chef, st: Station) -> None:
        item = chef.held
        if self.supply is None:
            chef.held = None
            self.events.append(("bin", st.pos))
        elif item.is_qubit:
            # Limited qubits: tip the contents out, keep the empty bowls.
            chef.held = Item(dirty=item.n)
            self.events.append(("bin", st.pos))
        else:
            self.events.append(("nope", st.pos))

    def _serve(self, chef: Chef, st: Station) -> None:
        item = chef.held
        self.refresh(item)
        result = self.orders.serve(item.state)
        if result.reason == "no-order":
            self.events.append(("no_order", st.pos))
            return
        chef.held = None
        self.score += result.points
        if result.accepted:
            self.stats.delivered += 1
            self.stats.fidelities.append(result.fidelity)
            receipt = Receipt(
                list(item.state.ops), item.state.n, (result.order.recipe.key,),
                result.fidelity, result.points, result.order.guest.name, self.t,
            )
            if self.stats.best is None or (receipt.points, receipt.fidelity) > (
                self.stats.best.points, self.stats.best.fidelity
            ):
                self.stats.best = receipt
            self.events.append(("serve", st.pos, result, receipt))
        else:
            self.stats.refused += 1
            self.events.append(("refuse", st.pos, result))
        if self.supply is not None:
            self.pending_dirty.append((self.t + self.level.dirty_return_delay, item.n, st.pos))

    # --- B: work stations -------------------------------------------------------
    def _work(self, dt: float, inputs: list[ChefInput]) -> None:
        scale = self.level.gate_scale
        press_users: dict[int, set[int]] = {}
        for chef, inp in zip(self.chefs, inputs):
            chef.working = False
            st = self.station_at(chef.target)
            if st is None:
                continue
            if st.jammed(self.t):
                if inp.use_pressed:
                    self.events.append(("jammed", st.pos))
                continue
            if st.kind in TAP_GATES:
                if inp.use_pressed and st.item is not None:
                    self._apply_gate(st, TAP_GATES[st.kind])
            elif st.kind in ("h", "sink") and inp.use and st.item is not None:
                chef.working = True
                st.progress += dt / (HOLD_TIMES[st.kind] * scale)
                if st.progress >= 1.0:
                    st.progress = 0.0
                    if st.kind == "h":
                        self._apply_gate(st, "H")
                    else:
                        self._reset(st)
            elif st.kind in ("control", "target") and inp.use and st.partner is not None:
                control = st if st.kind == "control" else st.partner
                press_users.setdefault(id(control), set()).add(chef.idx)
                if inp.use_pressed and (control.item is None or control.partner.item is None):
                    self.events.append(("press_needs_two", control.pos))
        self.press_users = press_users
        for control in self.stations_of("control"):
            self._press(control, press_users.get(id(control), set()), dt, scale)

    def _press(self, control: Station, users: set[int], dt: float, scale: float) -> None:
        target = control.partner
        if target is None or control.item is None or target.item is None:
            return
        if control.jammed(self.t) or target.jammed(self.t):
            return
        if not users:
            return
        speed = 1.0
        if self.level.two_chef_press:
            sides = set()
            for chef in self.chefs:
                if chef.idx in users:
                    sides.add("c" if chef.target == control.pos else "t")
            if len(users) >= 2 and sides == {"c", "t"}:
                speed = 1.0
            elif self.solo:
                speed = 0.5  # 1-player fallback: one chef, half speed
            else:
                return  # needs one chef at each end
        for chef in self.chefs:
            if chef.idx in users:
                chef.working = True
        control.progress += speed * dt / (HOLD_TIMES["press"] * scale)
        target.progress = control.progress
        if control.progress < 1.0:
            return
        control.progress = target.progress = 0.0
        a, b = control.item, target.item
        if a.n + b.n > 3:
            self.events.append(("too_big", control.pos))
            return
        self.refresh(a)
        self.refresh(b)
        merged = Item(cnot_merge(a.state, b.state, self.noise.depolarizing))
        merged.link_flash = self.t
        self.refresh(merged)
        control.item, target.item = merged, None
        control.last_used = self.t
        self.events.append(("cnot", control.pos, merged.view.entanglement > 0.1))

    def _reset(self, st: Station) -> None:
        item = st.item
        if self.supply is not None:
            self.supply += item.n
            st.item = None
            self.events.append(("sink", st.pos, item.n))
        else:
            st.item = self.new_qubit()
            self.events.append(("sink", st.pos, 1))
        st.last_used = self.t

    # --- belts, dirty bowls, hazards ----------------------------------------------
    def _belts(self, dt: float) -> None:
        moved: set[int] = set()
        for st in sorted(self.stations_of("belt"), key=lambda s: -s.x * s.belt_dir):
            item = st.item
            if item is None or item.uid in moved:
                continue
            nxt = self.station_at((st.x + st.belt_dir, st.y))
            if nxt is None or nxt.kind != "belt" or nxt.belt_dir != st.belt_dir or nxt.item is not None:
                st.belt_offset = 0.0
                continue
            st.belt_offset += dt * BELT_SPEED
            if st.belt_offset >= 1.0:
                nxt.item, st.item = item, None
                nxt.belt_offset = st.belt_offset - 1.0
                st.belt_offset = 0.0
                moved.add(item.uid)

    def _dirty_returns(self) -> None:
        still: list[tuple[float, int, tuple[int, int]]] = []
        for ready, count, pos in self.pending_dirty:
            if self.t < ready:
                still.append((ready, count, pos))
                continue
            passes = sorted(self.stations_of("pass"), key=lambda s: abs(s.x - pos[0]))
            for st in passes:
                if st.item is None:
                    st.item = Item(dirty=count)
                    self.events.append(("dirty_back", st.pos))
                    break
                if not st.item.is_qubit:
                    st.item.dirty += count
                    self.events.append(("dirty_back", st.pos))
                    break
            else:
                still.append((ready, count, pos))
        self.pending_dirty = still

    def _hazards(self) -> None:
        c = self.cosmic
        if c is None:
            return
        if c.center is None and self.t >= c.next_at:
            c.center = self._pick_impact()
            c.hit_at = self.t + COSMIC_WARNING
            self.events.append(("cosmic_warn", c.center))
        elif c.center is not None and self.t >= c.hit_at:
            area = c.area()
            for pos in area:
                st = self.station_at(pos)
                if st is not None:
                    st.jam_until = self.t + JAM_TIME
                    st.progress = 0.0
                    if st.item is not None and st.item.is_qubit:
                        self.refresh(st.item)
                        st.item.state.scramble()
                        self.refresh(st.item)
            for chef in self.chefs:
                if chef.tile in area and chef.held is not None and chef.held.is_qubit:
                    self.refresh(chef.held)
                    chef.held.state.scramble()
                    self.refresh(chef.held)
            self.events.append(("cosmic_hit", c.center))
            c.last_hit, c.last_center = self.t, c.center
            c.center = None
            c.next_at = self.t + self.rng.uniform(*COSMIC_EVERY)

    def _pick_impact(self) -> tuple[int, int]:
        """Usually near something that matters (a chef or a loaded station),
        sometimes anywhere in the kitchen."""
        interesting = [c.tile for c in self.chefs] + [
            s.pos for s in self.stations.values() if s.item is not None and s.kind != "pass"
        ]
        if interesting and self.rng.random() < 0.7:
            x, y = self.rng.choice(interesting)
        else:
            x, y = self.rng.randrange(1, self.w - 1), self.rng.randrange(1, self.h - 1)
        return min(max(x, 1), self.w - 2), min(max(y, 1), self.h - 2)
