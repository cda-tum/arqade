"""Qurves: four light cycles that look ahead, chase gates and cut each other off.

Plays the 4-player mode (P1/P3 on the left pad's stick and buttons, P2/P4 on
the right pad's). Once per grid step each player tries the five inputs
(straight, up, down, left, right) on every copy at once, the way the game
mirrors one stick across all of them, and scores each by how much room a
flood fill finds behind the next cell. Among the safe inputs it keeps to
long straight lines with the odd turn, heads for the nearest gate (H first,
for the splits) and drives through rivals' ghost trails to measure them.
Boxed into a small pocket, it gives up rather than coil it full.

Bots this careful would duel for minutes, so each round has a script: three
of the four players are fated to slip at staggered moments. From then on
that player stops looking ahead, cuts across the path of the nearest rival,
and doesn't turn away from the next trail in its way, so a round lasts about
25 s, fills a good part of the arena, and ends one crash at a time.
"""

from collections import deque

from qurves import rules
from qurves.match import MATCH_RESULT, ROUND, TITLE

SECONDS = 90.0
SKIP = 3.1
# 2 s windows, best first: all four players split into ghost copies, with
# measurements (9.7); a full arena with a crash and a split (54.4); a split
# and two crashes in a tangle (17.5); splits in round 3 (73.5); round 1's
# full arena, a crash and a split (23.6); an X-gate jump and a crash (85.0);
# a split copy boxed in and a crash (57.1); X-gate jumps and ghost trails
# early in round 2 (38.3).
HIGHLIGHTS = [9.7, 54.4, 17.5, 73.5, 23.6, 85.0, 57.1, 38.3]

MODE = 4
INPUTS = (None, (0, -1), (0, 1), (-1, 0), (1, 0))
# Who steers with what in 4-player mode (config.CONTROLS).
SEATS = {"p1": (0, "stick"), "p2": (1, "stick"), "p3": (0, "pad"), "p4": (1, "pad")}
# The face buttons sit like W A S D: X up, Y left, B down, A right.
BUTTON = {(0, -1): "x", (-1, 0): "y", (0, 1): "b", (1, 0): "a"}
POCKET = 200  # boxed into fewer cells than this: give up and crash soon


def manhattan(a, b) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class Bot:
    def __init__(self, pads, rng):
        self.pads, self.rng = pads, rng
        self.last_press = -10.0
        self.seen = None  # the grid state last decided on
        self.round = None
        self.sight = {}  # flood-fill limit per player
        self.fate = {}  # round time at which each player slips
        self.whim = {}  # a turn just because, per player, and until when
        self.straight = {}  # grid steps since each player last turned

    # --- menus --------------------------------------------------------------------

    def update(self, t):
        match = self.pads.loop.get("match")
        if match is None:
            return
        if match.state == ROUND and not match.paused:
            self.play(match, t)
            return
        self.hands_off()
        if match.paused:  # never meant to happen; B resumes
            self.press("b", t)
        elif match.state == TITLE:
            if match.mode != MODE:
                self.pads.stick(0, 1.0 if self.pads.frame % 2 else 0.0, 0.0)
            else:
                self.press("a", t)
        elif match.state == MATCH_RESULT:
            self.press("a", t)

    def press(self, button, t):
        if t - self.last_press > 0.5:
            self.pads.tap(0, button)
            self.last_press = t

    def hands_off(self):
        for player in (0, 1):
            self.pads.stick(player, 0.0, 0.0)
            for button in BUTTON.values():
                self.pads.release(player, button)

    def steer(self, name, d):
        pad, kind = SEATS[name]
        if kind == "stick":
            self.pads.stick(pad, *(d or (0, 0)))
            return
        for vec, button in BUTTON.items():
            self.pads.hold(pad, button, vec == d)

    # --- driving --------------------------------------------------------------------

    def play(self, match, t):
        rs = match.round
        if rs is not self.round:
            self.new_round(rs)
        state = tuple((b.pos, b.heading) for pl in rs.players.values() for b in pl.bikes)
        if state == self.seen:
            return  # no grid step since the last decision: keep holding it
        self.seen = state
        for name, pl in rs.players.items():
            if not pl.alive:
                continue
            slipped = match.round_time - self.fate[name]
            d = self.choose(rs, pl, t, slipped)
            turned = d is not None and d != pl.bikes[0].heading
            self.straight[name] = 0 if turned else self.straight[name] + 1
            self.steer(name, d)

    def new_round(self, rs):
        self.round = rs
        names = list(rs.players)
        self.rng.shuffle(names)
        when = self.rng.uniform(15.0, 19.0)
        self.fate = {}
        for name in names[:-1]:
            self.fate[name] = when
            when += self.rng.uniform(4.0, 6.0)
        self.fate[names[-1]] = 1e9  # this round's winner, if all goes to plan
        self.sight = {p: self.rng.choice((400, 500, 600)) for p in names}
        self.whim = {}
        self.straight = {p: 9 for p in names}

    def choose(self, rs, pl, t, slipped):
        heads = [b for other in rs.players.values() if other is not pl and other.alive
                 for b in other.bikes]
        limit = self.sight[pl.name] if slipped < 0 else 15
        whim, until = self.whim.get(pl.name, (None, 0.0))
        if t >= until:  # now and then, a turn just because
            whim = self.rng.choice(INPUTS[1:]) if self.rng.random() < 0.5 else None
            self.whim[pl.name] = (whim, t + (self.rng.uniform(0.3, 0.6) if whim else self.rng.uniform(0.8, 2.5)))

        options = {}  # input -> [(bike, target, heading, room or None if it crashes)]
        rooms = {}
        for d in INPUTS:
            moves = []
            for bike in pl.bikes:
                heading = bike.heading
                if d is not None and not bike.fresh:
                    want = rules.steer(d, bike.flip)
                    if want != (-heading[0], -heading[1]):
                        heading = want
                target = rules.add(bike.pos, heading)
                room = None
                if rules._effect(pl, bike, rs.arena.get(target)) != "crash":
                    key = (id(bike), target)
                    if key not in rooms:
                        rooms[key] = self.room(rs, pl, bike, target, limit)
                    room = rooms[key]
                moves.append((bike, target, heading, room))
            options[d] = moves

        if slipped >= 0:
            # This player's moment has come: the next trail dead ahead is the
            # one it doesn't turn away from (anything at all, once it has
            # dodged for a few seconds too many).
            ahead = [(target, room) for _, target, _, room in options[None]]
            if any(room is None and (slipped > 4.0 or isinstance(rs.arena.get(target), rules.Trail))
                   for target, room in ahead):
                return None
        else:
            best_room = max((m[3] for moves in options.values() for m in moves if m[3] is not None), default=0)
            if best_room < POCKET:
                # Boxed in. Rather than coil up the pocket for ages, flail:
                # keep going while it's safe and crash soon, the way people do.
                safe = [d for d, moves in options.items() if any(m[3] is not None for m in moves)]
                if None in safe and self.rng.random() < 0.8:
                    return None
                return self.rng.choice(safe) if safe else None

        danger = set() if slipped >= 0 else {rules.add(b.pos, step) for b in heads for step in INPUTS[1:]}
        hunt = 0 if slipped < 0 else 1000
        best, best_score = None, None
        for d, moves in options.items():
            scores = []
            for bike, target, heading, room in moves:
                if room is None:
                    scores.append(-10_000.0)
                    continue
                # Room counts in coarse steps: chasing every last cell is
                # what makes a bot coil up a pocket in tight zig-zags.
                score = 10.0 * (room if room >= limit else room - room % 40)
                score += self.taste(rs, pl, bike, target, heading, heads, hunt)
                if target in danger:
                    score -= 300.0
                scores.append(score)
            score = max(scores) + 0.4 * sum(scores) / len(scores)
            if d is None:
                # Lines, not staircases: turn only for a reason, and not
                # again straight after a turn.
                score += 25.0 + (150.0 if self.straight[pl.name] < 3 else 0.0)
            elif d == whim:
                score += 40.0
            if best_score is None or score > best_score:
                best, best_score = d, score
        return best

    def taste(self, rs, pl, bike, target, heading, heads, hunt):
        """What a skilled player likes: open road, gates, cutting across a
        rival's path, measuring a rival's ghost trail."""
        arena = rs.arena
        run, c = 0, target
        while run < 12:
            c = rules.add(c, heading)
            if rules._effect(pl, bike, arena.get(c)) == "crash":
                break
            run += 1
        score = 3.0 * run
        gates = [g for g in rs.gates if manhattan(g.pos, bike.pos) < (60 if g.kind == "H" else 30)]
        if gates:
            gate = min(gates, key=lambda g: manhattan(g.pos, bike.pos) * (0.5 if g.kind == "H" else 1.0))
            weight = 40.0 if gate.kind == "H" and len(pl.bikes) < 6 else 15.0
            score += weight * (manhattan(gate.pos, bike.pos) - manhattan(gate.pos, target))
        near = [b for b in heads if manhattan(b.pos, bike.pos) < hunt]
        if near:
            rival = min(near, key=lambda b: manhattan(b.pos, bike.pos))
            ahead = (rival.pos[0] + 8 * rival.heading[0], rival.pos[1] + 8 * rival.heading[1])
            score += 30.0 * (manhattan(ahead, bike.pos) - manhattan(ahead, target))
        cell = arena.get(target)
        if isinstance(cell, rules.Trail) and cell.player != pl.name and cell.node is not None:
            score += 80.0  # a rival's ghost trail: measure it
        # A trail along the edge is a wasted trail.
        x, y = target
        if min(x, y, arena.width - 1 - x, arena.height - 1 - y) <= 2:
            score -= 20.0
        return score

    @staticmethod
    def room(rs, pl, bike, start, limit):
        """How many cells this copy can reach from `start`, up to `limit`."""
        seen = {start, bike.pos}
        queue = deque([start])
        arena = rs.arena
        count = 0
        while queue and count < limit:
            c = queue.popleft()
            count += 1
            for step in INPUTS[1:]:
                n = (c[0] + step[0], c[1] + step[1])
                if n in seen:
                    continue
                seen.add(n)
                if rules._effect(pl, bike, arena.get(n)) != "crash":
                    queue.append(n)
        return count
