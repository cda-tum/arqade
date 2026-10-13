"""Superconductor: two routers share one chip in co-op, then race in versus.

Each player draws its pair's route with the stick, one coupler at a time, at
a quick human pace. Routes are planned against the game's own occupancy
windows (the rules behind the crash and the red X): short, straight, off
miscalibrated couplers, and never into another qubit. For the show it likes
a route that cuts just behind a qubit in flight: the red X comes up, the
player waits for that qubit to go by and draws on. Now and then it starts
down a blocked route, stops on the X and backs up (X) to go round. It takes
a pair from its other end (B) when that is better, and moves to another pair
(A) when nothing is safe. Once in versus, P2 ignores the X and crashes.

Between the rounds it goes back to the title the quick way (Select twice:
a few frames of the pause screen). On the title it picks mode and chip with
the stick and starts with Start, which never quits (A on the QUIT row would),
then presses A on the HOW TO PLAY card.
"""

from superconductor.lattice import DIRECTIONS
from superconductor.rules import Occupancy

SECONDS = 85.0
SKIP = 1.0  # co-op play starts at 0.87 s, after the HOW TO PLAY card
# The same footage as before the HOW TO PLAY card: the card moved co-op
# 0.63 s and versus 1.25 s later (play starts at 0.87 s and 46.35 s).
HIGHLIGHTS = [
    73.2,  # versus: two of P2's qubits meet -- COLLISION, the chip flashes red
    58.6,  # versus: both chips busy, four gates fire, P2 drawing
    18.4,  # co-op: red X where P2's route cuts the purple qubit, a gate fires
    50.6,  # versus: crossing routes on both chips, a gate on each
    32.6,  # co-op: P1 drawing, two gates, a speed qubit turns up
    67.1,  # versus: P1 waits on the red X, P2 completes a gate
    6.1,   # co-op: P1's cursor on a fresh pair, two gates
    80.5,  # versus: late, busier chips, gates on both sides
]

# (mode, chip, seconds of play before going back to the title, and when
# (player, seconds into the round) somebody ignores the red X and crashes)
ROUNDS = (("coop", "distributed", 44.0, None), ("versus", "brick", None, (1, 22.0)))

STEP = (0.11, 0.18)  # seconds between two stick steps
THINK = ((0.15, 0.45), (0.25, 0.6))  # P1, P2: a look at a new pair before drawing
WAITS = (0.0, 0.4, 0.8, 1.2, 1.6, 2.0)  # holding the last step for a qubit to pass
WAIT_COST = 1.2  # hops a second of holding is worth
DRAMA = 2.5  # hops a near-miss is worth, at most once per DRAMA_GAP seconds
DRAMA_GAP = 3.0
MAX_X_HOLD = 2.5  # seconds to wait on a red X before drawing on anyway
TEASE_GAP = 6.0  # at most one deliberate near-miss per player this often
TEASE_SKIP = 0.3  # ... and not every time it could
MAX_ROUTES = 3000  # per search, so a wide-open chip cannot stall a frame


# ---------------------------------------------------------------- planning
def jumps(lat, route):
    """Indices of the Bell jumps in a route (links that are not couplers)."""
    return {i for i in range(len(route) - 1) if not lat.has_edge(route[i], route[i + 1])}


def hops(lat, route):
    return len(route) - 1 - len(jumps(lat, route))


def draw_time(steps):
    """Seconds until a route `steps` stick pushes away is committed (the
    last push commits it at once)."""
    return max(0, steps - 1) * sum(STEP) / 2


def shifted(occ, delay):
    return Occupancy({n: (a + delay, b + delay) for n, (a, b) in occ.nodes.items()},
                     [(x, y, a + delay, b + delay) for x, y, a, b in occ.links])


def first_crash(board, pair, route, delay, open_end=False, theirs=None):
    """(when, where) `route`, committed `delay` seconds from now, would first
    crash, or None."""
    mine = shifted(board.route_windows(route, jumps(board.lattice, route), 0.0, 1.0, open_end), delay)
    if theirs is None:
        theirs = [board.windows(o) for o in board.pairs.values() if o.id != pair.id]
    hits = [h for occ in theirs if (h := board._first_overlap(mine, occ))]
    return min(hits, key=lambda h: h[0]) if hits else None


def routes(board, prefix, target, max_hops):
    """Every simple route that extends `prefix` to `target` in at most
    max_hops hops, drawn the way the stick draws it: stepping onto an open
    Bell qubit jumps to its partner."""
    lat = board.lattice
    bells = [s.nodes for s in board.specials if s.kind == "bell" and s.claimed_by is None]

    def least(n):
        d = lat.distance(n, target)
        for a, b in bells:
            d = min(d, lat.distance(n, a) + lat.distance(b, target), lat.distance(n, b) + lat.distance(a, target))
        return d

    out, path = [], list(prefix)

    def dfs(h):
        n = path[-1]
        if n == target:
            out.append(list(path))
            return
        if h + least(n) > max_hops or len(out) >= MAX_ROUTES:
            return
        for m in lat.neighbors(n):
            if m in path or not board._can_enter(n, m):
                continue
            partner = board.open_bell(m)
            if partner is not None and partner in path:
                continue
            step = [m] if partner is None else [m, partner]
            path.extend(step)
            dfs(h + 1)
            del path[-len(step):]

    dfs(hops(lat, prefix))
    return out


def cost(board, route, rng):
    """Hops, plus a little for turns (people draw straight lines) and for
    slow miscalibrated couplers, plus a random tie-break."""
    lat = board.lattice
    c = hops(lat, route) + rng.random() * 0.2
    for a, b, d in zip(route, route[1:], route[2:]):
        if lat.has_edge(a, b) and lat.has_edge(b, d) and (b[0] - a[0], b[1] - a[1]) != (d[0] - b[0], d[1] - b[1]):
            c += 0.15
    for a, b in zip(route, route[1:]):
        s = board.edge_special(frozenset((a, b)))
        if s is not None and s.kind == "miscal":
            c += 2.5
    return c


def red_x(board, pair, route, drawn, theirs):
    """Drawing `route` on from its first `drawn` nodes and waiting while the
    red X is up: (seconds the X stays up, seconds until the route is then
    committed). (0, None) if no X comes up."""
    for k in range(drawn + 1, len(route)):
        shown = draw_time(k - drawn)
        if first_crash(board, pair, route[:k], shown, open_end=True, theirs=theirs):
            up = 0.2
            while up < MAX_X_HOLD and first_crash(board, pair, route[:k], shown + up, open_end=True, theirs=theirs):
                up += 0.2
            return up, shown + up + draw_time(len(route) - k + 1)
    return 0.0, None


def best_route(board, pair, prefix, rng, extra=4, drama=False):
    """The cheapest (cost, route, wait, near_miss) that extends `prefix` and
    will not crash, holding the last step `wait` seconds if that is what it
    takes. With `drama`, a route that brings up the red X on the way (one
    that cuts just behind a qubit in flight) is worth DRAMA hops."""
    target = pair.other(prefix[0])
    lat = board.lattice
    theirs = [board.windows(o) for o in board.pairs.values() if o.id != pair.id]
    base = hops(lat, prefix) + lat.distance(prefix[-1], target)
    bonus = DRAMA if drama else 0.0
    best = None
    for slack in range(0, extra + 1, 2):
        found = routes(board, prefix, target, base + slack)
        fresh = [r for r in found if hops(lat, r) > base + slack - 2] if slack else found
        for c, r in sorted(((cost(board, r, rng), r) for r in fresh), key=lambda cr: cr[0]):
            if best is not None and c - bonus >= best[0]:
                break
            delay = draw_time(len(r) - len(prefix))
            for w in WAITS:
                if best is not None and c + w * WAIT_COST - bonus >= best[0]:
                    break
                if first_crash(board, pair, r, delay + w, theirs=theirs) is None:
                    near = False
                    if drama:
                        up, commit = red_x(board, pair, r, len(prefix), theirs)
                        near = up >= 0.8 and first_crash(board, pair, r, max(commit, delay + w), theirs=theirs) is None
                    total = c + w * WAIT_COST - (bonus if near else 0.0)
                    if best is None or total < best[0]:
                        best = (total, r, w, near)
                    break
        if best is not None and best[2] == 0 and not drama:
            break
    return best


def direction(a, b):
    step = (b[0] - a[0], b[1] - a[1])
    return next(name for name, d in DIRECTIONS.items() if d == step)


def common_prefix(a, b):
    return next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))


# ---------------------------------------------------------------- one player
class Router:
    def __init__(self, pads, index, rng):
        self.pads, self.index, self.rng = pads, index, rng
        self.player = ("p1", "p2")[index]
        self.stick_off = 0.0
        self.last_tease = -TEASE_GAP / 2 - index * 3.0
        self.blunder_at = None  # board time from which to commit a route that crashes
        self.last_drama = -DRAMA_GAP
        self.reset()

    def reset(self):
        self.plan, self.pair_id, self.ready = None, None, 0.0
        self.commit_at = 0.0  # don't make the last push before this
        self.x_since = None  # when the red X came up on the route being drawn
        self.tease = self.blunder = False

    def wait(self, t, lo, hi):
        self.ready = t + self.rng.uniform(lo, hi)

    def push(self, t, d):
        dx, dy = DIRECTIONS[d][1], DIRECTIONS[d][0]
        self.pads.stick(self.index, float(dx), float(dy))
        self.stick_off = t + 0.05
        self.wait(t, *STEP)

    def press(self, t, button):
        self.pads.tap(self.index, button, 3)
        self.wait(t, 0.12, 0.2)

    def update(self, board, t):
        if t >= self.stick_off:
            self.pads.stick(self.index, 0.0, 0.0)
        if t < self.ready or board.over:
            return
        cur = board.cursors[self.player]
        if cur.pair_id != self.pair_id:
            self.reset()
            self.pair_id = cur.pair_id
            self.wait(t, *THINK[self.index])
            return
        if cur.pair_id is None:
            return
        pair = board.pairs[cur.pair_id]
        drawn = cur.path

        if self.tease:
            # drawing a blocked route on purpose: stop once the X shows
            if board.predict_collision(self.player) is not None:
                self.tease, self.plan = False, None
                self.wait(t, 0.5, 0.8)
                return
            if self.plan[:len(drawn)] != drawn or len(drawn) >= len(self.plan) - 2:
                self.tease, self.plan = False, None
            else:
                self.push(t, direction(drawn[-1], self.plan[len(drawn)]))
                return

        if not self.still_good(board, pair, drawn, t) and not self.choose(board, cur, pair, t):
            return
        plan = self.plan
        x = board.predict_collision(self.player) is not None
        self.x_since = (self.x_since or t) if x else None
        if plan[:len(drawn)] != drawn:
            self.press(t, "x")  # back up to where the new route leaves the old
        elif x and not self.blunder and t - self.x_since < MAX_X_HOLD:
            self.ready = t + 0.1  # the red X: wait for that qubit to go by
        elif len(drawn) == len(plan) - 1 and t < self.commit_at:
            self.ready = min(self.commit_at, t + 0.1)  # let the other qubit pass
        else:
            self.push(t, direction(drawn[-1], plan[len(drawn)]))

    def still_good(self, board, pair, drawn, t):
        plan = self.plan
        if plan is None or plan[0] != drawn[0] or plan[-1] != pair.other(drawn[0]):
            return False
        if not all(board._link_ok(a, b) for a, b in zip(plan, plan[1:])):
            return False
        if self.blunder:
            return True
        common = common_prefix(plan, drawn)
        delay = max(draw_time(len(drawn) - common + len(plan) - common), self.commit_at - t)
        return first_crash(board, pair, plan, delay) is None

    def choose(self, board, cur, pair, t):
        """Pick the next route. False if that took a button press or a wait."""
        drawn = cur.path
        rng = self.rng
        if self.blunder_at is not None and board.time >= self.blunder_at and len(drawn) == 1:
            if self.find_blunder(board, pair, drawn[0]):
                return True
            if self.find_blunder(board, pair, pair.other(drawn[0])):
                self.press(t, "b")
                return False
        options = []
        drama = t - self.last_drama >= DRAMA_GAP
        if len(drawn) > 1:
            best = best_route(board, pair, drawn, rng, extra=2, drama=drama)
            if best is not None:
                options.append((best[0], "keep", *best[1:]))
        for start, penalty in ((drawn[0], 0.3 * (len(drawn) - 1)), (pair.other(drawn[0]), 1.0)):
            best = best_route(board, pair, [start], rng, drama=drama)
            if best is not None:
                options.append((best[0] + penalty, "same" if start == drawn[0] else "other", *best[1:]))
        if not options:
            return self.switch_pair(board, cur, t)
        _, how, route, hold, near = min(options, key=lambda o: o[0])
        if near:
            self.last_drama = t
        steps = len(drawn) - common_prefix(route, drawn) + len(route) - common_prefix(route, drawn)
        self.plan, self.commit_at = route, t + draw_time(steps) + hold
        if how == "other":
            self.press(t, "b")
            return False
        if how == "same" and len(drawn) == 1 and (hold > 0 or hops(board.lattice, route) > board.lattice.distance(route[0], route[-1])):
            self.maybe_tease(board, pair, t)
        return True

    def maybe_tease(self, board, pair, t):
        """The direct route is blocked: sometimes start down it anyway, far
        enough for the red X to show."""
        lat = board.lattice
        start = self.plan[0]
        target = pair.other(start)
        if t - self.last_tease < TEASE_GAP or self.rng.random() < TEASE_SKIP:
            return
        for direct in routes(board, [start], target, lat.distance(start, target))[:200]:
            for k in range(2, len(direct) - 2):
                if first_crash(board, pair, direct[:k], draw_time(k - 1), open_end=True):
                    self.plan, self.tease, self.last_tease = direct, True, t
                    return

    def find_blunder(self, board, pair, start):
        """A short route that crashes a second or so after it sets off,
        where everybody can see it coming."""
        lat = board.lattice
        target = pair.other(start)
        for r in routes(board, [start], target, lat.distance(start, target) + 4)[:1000]:
            delay = draw_time(len(r) - 1)
            hit = first_crash(board, pair, r, delay)
            if hit is not None and 0.8 <= hit[0] - delay <= 4.0:
                self.plan, self.blunder, self.blunder_at = r, True, None
                return True
        return False

    def switch_pair(self, board, cur, t):
        """Nothing safe for this pair right now: move to one that has a route."""
        stations = board.stations(self.player)
        here = stations.index((cur.pair_id, cur.path[0])) if (cur.pair_id, cur.path[0]) in stations else 0
        for k in range(2, len(stations), 2):
            pid, node = stations[(here + k) % len(stations)]
            if best_route(board, board.pairs[pid], [node], self.rng, extra=2) is not None:
                self.plan = None
                self.press(t, "a")
                return False
        self.wait(t, 0.2, 0.3)
        return False


# ---------------------------------------------------------------- the game
class Bot:
    def __init__(self, pads, rng):
        self.pads, self.rng = pads, rng
        self.round = 0
        self.leaving = False
        self.started = False
        self.routers = [Router(pads, i, rng) for i in (0, 1)]
        self.next_menu = 0.0

    def update(self, t):
        game = self.pads.loop["self"]
        if game.state == "play":
            mode, chip, length, blunder = ROUNDS[min(self.round, len(ROUNDS) - 1)]
            if not self.started:
                self.started = True
                if blunder is not None:
                    self.routers[blunder[0]].blunder_at = blunder[1]
            if length is not None and game.views[0].board.time >= length:
                self.pads.release_all()
                self.pads.tap(0, "select", 3)
                self.leaving = True
                self.round += 1
                self.next_menu = t + 0.15
                return
            for router in self.routers:
                view = game.player_view.get(router.player)
                if view is not None:
                    router.update(view.board, t)
            return
        self.started = False
        for router in self.routers:
            router.reset()
        if t < self.next_menu:
            return
        self.pads.release_all()
        self.next_menu = t + 0.06
        if game.state == "paused":
            self.pads.tap(0, "select" if self.leaving else "a", 2)
            self.next_menu = t + 0.15
        elif game.state == "tutorial":
            if game.state_t > 0.6:  # a glimpse of the card, then any button
                self.pads.tap(0, "a", 2)
                self.next_menu = t + 0.15
        elif game.state == "over":
            if game.state_t > 1.6:
                self.pads.tap(0, "a", 2)
        elif game.state == "title":
            self.leaving = False
            mode, chip = ROUNDS[min(self.round, len(ROUNDS) - 1)][:2]
            modes = ("single", "coop", "versus")
            chips = ("square", "brick", "bottleneck", "distributed")
            # rows: 0 MODE, 1 CHIP, 2 QUIT -- the stick only ever aims at 0 or 1
            if game.mode != mode:
                row, options, now, want = 0, modes, game.mode, mode
            elif game.lattice_kind != chip:
                row, options, now, want = 1, chips, game.lattice_kind, chip
            else:
                self.pads.tap(0, "start", 2)  # Start plays from any row, never quits
                self.next_menu = t + 0.15
                return
            if game.menu_row != row:
                self.pads.stick(0, 0.0, 1.0 if game.menu_row < row else -1.0)
            else:
                self.pads.stick(0, self.lean(options, now, want), 0.0)

    @staticmethod
    def lean(options, now, want):
        """Stick x towards `want`, whichever way round is shorter."""
        right = (options.index(want) - options.index(now)) % len(options)
        return 1.0 if right <= len(options) // 2 else -1.0
