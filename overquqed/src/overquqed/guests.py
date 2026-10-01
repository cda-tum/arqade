"""Guests (personified QEC codes and protocols), their orders and patience.

Pure logic, no pygame: the OrderBook spawns orders on a schedule that speeds
up during the round, runs patience timers and matches served items against
open orders. Rendering reads its state.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from overquqed import scoring
from overquqed.quantum import QState
from overquqed.recipes import RECIPES, Recipe


@dataclass(frozen=True)
class GuestType:
    key: str
    name: str
    orders: tuple[str, ...]
    patience: float  # seconds, before the level's patience scale
    tip: float  # multiplies the fidelity tip
    flavour: str  # speech bubble on their first visit of a round
    duo: bool = False  # Alice & Bob always arrive together


GUESTS: dict[str, GuestType] = {
    g.key: g
    for g in (
        GuestType("surface", "Surface Code", ("0", "+"), 38.0, 1.0,
                  "Two |0> and a |+>, I have stabilizers to measure!"),
        GuestType("steane", "Steane", ("0", "+"), 60.0, 1.6,
                  "Seven qubits, one hat. My ancillas must be spotless."),
        GuestType("grover", "Grover", ("-",), 50.0, 1.2,
                  "One |-> please. My oracle needs a kickback."),
        GuestType("dj", "Deutsch-Jozsa", ("1", "-"), 50.0, 1.2,
                  "Constant or balanced? Just one query, I promise."),
        GuestType("alicebob", "Alice & Bob", ("Phi+",), 70.0, 1.3,
                  "We share everything. Even our qubits!", duo=True),
        GuestType("knill", "Knill", ("Phi+", "Psi+", "Phi-", "Psi-"), 70.0, 1.4,
                  "Bell pairs! I teleport my errors away."),
        GuestType("shor", "Shor", ("GHZ",), 85.0, 1.5,
                  "Meow. A cat state, alive AND dead."),
    )
}


@dataclass
class Order:
    id: int
    guest: GuestType
    recipe: Recipe
    patience: float
    remaining: float
    created: float
    status: str = "open"  # open | served | refused-leave | left
    first_visit: bool = False

    @property
    def patience_frac(self) -> float:
        return max(0.0, self.remaining / self.patience)


@dataclass
class ServeResult:
    accepted: bool
    order: Order | None
    fidelity: float
    points: int
    breakdown: tuple[int, int, int] = (0, 0, 0)  # base, tip, speed
    reason: str = ""  # "no-order" | "below-threshold" | ""


@dataclass
class OrderBook:
    """Open tickets for one round."""

    recipes: tuple[str, ...]
    guests: tuple[str, ...]
    duration: float
    spawn_interval: float
    spawn_interval_end: float
    first_order_at: float = 2.0
    patience_scale: float = 1.0
    max_tickets: int = 4
    rng: random.Random = field(default_factory=random.Random)
    auto_spawn: bool = True  # the tutorial spawns its own scripted orders

    def __post_init__(self) -> None:
        self.orders: list[Order] = []  # open orders, oldest first
        self.done: list[Order] = []
        self.next_spawn = self.first_order_at
        self._next_id = 1
        self._seen_guests: set[str] = set()

    # --- spawning ---
    def interval_at(self, t: float) -> float:
        if self.duration == float("inf"):
            return self.spawn_interval
        frac = min(1.0, max(0.0, t / self.duration))
        return self.spawn_interval + (self.spawn_interval_end - self.spawn_interval) * frac

    def _eligible_guests(self) -> list[GuestType]:
        return [
            GUESTS[g] for g in self.guests
            if any(r in self.recipes for r in GUESTS[g].orders)
        ]

    def spawn(self, t: float, recipe_key: str | None = None, guest_key: str | None = None) -> Order:
        if guest_key is None:
            guest = self.rng.choice(self._eligible_guests())
        else:
            guest = GUESTS[guest_key]
        if recipe_key is None:
            recipe_key = self.rng.choice([r for r in guest.orders if r in self.recipes])
        patience = guest.patience * self.patience_scale
        order = Order(self._next_id, guest, RECIPES[recipe_key], patience, patience, t)
        order.first_visit = guest.key not in self._seen_guests
        self._seen_guests.add(guest.key)
        self._next_id += 1
        self.orders.append(order)
        return order

    def update(self, dt: float, t: float) -> tuple[list[Order], list[Order]]:
        """Advance timers. Returns (spawned, expired) this step."""
        spawned: list[Order] = []
        expired: list[Order] = []
        if self.auto_spawn and t >= self.next_spawn:
            if len(self.orders) < self.max_tickets:
                spawned.append(self.spawn(t))
            self.next_spawn = t + self.interval_at(t)
        # an empty board gets a new order quickly, so nobody stands around
        if self.auto_spawn and not self.orders and self.next_spawn - t > 3.0:
            self.next_spawn = t + 3.0
        for order in list(self.orders):
            order.remaining -= dt
            if order.remaining <= 0:
                order.status = "left"
                self.orders.remove(order)
                self.done.append(order)
                expired.append(order)
        return spawned, expired

    # --- serving ---
    def serve(self, state: QState) -> ServeResult:
        """Match an item against every open order with the same number of
        qubits: best fidelity wins, ties go to the oldest order."""
        candidates = [o for o in self.orders if o.recipe.n == state.n]
        if not candidates:
            return ServeResult(False, None, 0.0, 0, reason="no-order")
        order, fid = scoring.choose_order(candidates, lambda o: state.fidelity(o.recipe.target))
        if fid < scoring.THRESHOLD:
            return ServeResult(False, order, fid, scoring.REFUSE_PENALTY, reason="below-threshold")
        breakdown = scoring.delivery_points(order.recipe.tier, fid, order.patience_frac, order.guest.tip)
        order.status = "served"
        self.orders.remove(order)
        self.done.append(order)
        return ServeResult(True, order, fid, sum(breakdown), breakdown)
