"""Pauli Invaders: two ships that read each invader's colour and fire to match.

Plays 2-player EASY. The bot steps the formation's march, the boss and the
shots already in flight forward frame by frame, so it knows what each shot
will hit and which invaders are as good as gone. Each ship then picks the
front invader it can reach soonest (distance, colour switches, the
partner's half of the field), switches to that invader's colour with B and
fires with A whenever a shot from where it stands would land on something
its colour corrects. The ships dodge incoming fire, shoot the Cosmic Ray
through a cleared column, catch the capsules and now and then merge for
lattice surgery. The bosses (wave 3's LOGICAL ERROR chain, wave 6's WAVE
PACKET) are played the same way.
"""

import math

from error_invaders import bosses as B
from error_invaders import game as G

SECONDS = 85.0
SKIP = 0.7
HIGHLIGHTS = [
    37.5,  # wave 4: a full formation cleared colour by colour, MAGIC STATE x9 blast
    29.0,  # boss: the LOGICAL ERROR chain split apart segment by segment
    2.0,   # wave 1 opens: matching shots tear into the formation
    48.5,  # wave 5: lattice surgery, the merged ship's every-colour shots
    18.3,  # wave 2: noise bias chains popped in one hit (BUBBLE POP)
    13.6,  # wave 2 arrives, the Cosmic Ray is shot down
    31.5,  # the chain's last segments, boss beaten: LOGICAL ERROR CORRECTED!
    72.4,  # boss: the WAVE PACKET, measured and hit while it darts about
]

# The game would otherwise read and write the real high-score file in ~.
G.load_hiscores = lambda: None
G.save_hiscores = lambda: None

DT = 1 / 60
HORIZON = 64  # frames: a shot crosses the whole field in under that
SHOT = 640    # px/s, a ship's plain shot


class Target:
    """Something a shot can hit: where it will be k frames from now, how
    close a shot has to come, and its colour as far as the bot knows."""

    def __init__(self, obj, col, pos, hit, front=True):
        self.obj, self.col, self.pos, self.hit, self.front = obj, col, pos, hit, front


def box(w, h):
    return lambda dx, dy: abs(dx) < w and abs(dy) < h


def disc(r):
    return lambda dx, dy: dx * dx + dy * dy < r * r


class Field:
    """Everything a shot can hit over the next HORIZON frames."""

    def __init__(self, g):
        self.g = g
        F = g.F
        alive = [e for e in F.en if e.alive]
        self.grid = {(e.c, e.r): e for e in alive}
        self.march = self.plan_march(g, alive)
        self.targets = []
        if g.boss and g.boss.intro <= 0:
            self.targets += self.boss_targets(g.boss)
        for m in g.minions:
            self.targets.append(Target(m, m.col, lambda k, m=m: (
                G.clamp(m.x0 + math.sin((m.t + k * DT) * 1.4) * m.amp, 20, G.W - 20),
                m.y + m.vy * k * DT), box(G.EW / 2 + 2, G.EH / 2 + 4)))
        if g.ufo:
            u = g.ufo
            self.ufo = Target(u, "any", lambda k: (u.x + u.vx * k * DT, u.y), box(32, 18), front=False)
            self.targets.append(self.ufo)
        else:
            self.ufo = None
        self.col = {id(e): e.col for e in alive}
        self.col.update((id(t.obj), t.col) for t in self.targets)
        self.gone = set()
        self.play_out(g.pb)
        # the invaders and boss parts that are still worth a shot
        self.live = [t for t in self.targets if id(t.obj) not in self.gone]
        for t in self.live:
            t.col = self.col[id(t.obj)]
        fronts = {}
        for e in alive:
            if id(e) not in self.gone and (e.c not in fronts or e.r > fronts[e.c].r):
                fronts[e.c] = e
        for e in fronts.values():
            self.live.append(Target(e, self.col[id(e)], lambda k, e=e: (
                self.march[min(k, HORIZON)][0] + e.c * G.SX,
                self.march[min(k, HORIZON)][1] + e.r * G.SY), None))

    @staticmethod
    def plan_march(g, alive):
        """(ox, oy) of the formation for each of the next HORIZON frames."""
        F = g.F
        ox, oy, d, st = F.ox, F.oy, F.dir, F.stepT
        out = [(ox, oy)]
        if not alive:
            return out * (HORIZON + 1)
        period = max(0.016, (0.02 + 0.6 * (len(alive) / F.total) ** 1.4) * 0.88 ** (g.wave - 1))
        lo = min(e.c for e in alive) * G.SX - G.EW / 2
        hi = max(e.c for e in alive) * G.SX + G.EW / 2
        for _ in range(HORIZON):
            st -= DT
            if st <= 0:
                st = period
                if ox + hi + 10 * d > G.W - 20 or ox + lo + 10 * d < 20:
                    oy += 18
                    d = -d
                else:
                    ox += 10 * d
            out.append((ox, oy))
        return out

    @staticmethod
    def boss_targets(boss):
        if boss.kind == "centipede":
            # segment i will be where the one ahead of it is now; the head
            # follows the chain's own rule: along the row, down one at a wall
            out = []
            sp = boss.speed()
            ahead = int(sp * HORIZON * DT / B.STEP) + 1
            for ch in boss.chains:
                x, y = ch.path[0]
                d, down = ch.dir, ch.down
                head = []
                for _ in range(ahead):
                    if down <= 0 and not B.MARGIN <= x + d * B.STEP <= G.W - B.MARGIN:
                        down = B.ROW_H
                    if down > 0:
                        y += B.STEP
                        down -= B.STEP
                        if down <= 0:
                            down, d = 0.0, -d
                    else:
                        x += d * B.STEP
                    head.append((x, y))
                for i, s in enumerate(ch.segs):
                    def pos(k, ch=ch, i=i, head=head):
                        n = i * B.K - int(sp * k * DT / B.STEP)
                        return ch.path[min(n, len(ch.path) - 1)] if n >= 0 else head[min(-n, ahead) - 1]
                    out.append(Target(s, s.col, pos, disc(B.SEG_R + 4)))
            return out
        if boss.kind == "packet" and boss.hittable:
            return [Target(boss, boss.col, lambda k: (boss.x + boss.vx * k * DT, boss.y + boss.vy * k * DT),
                           box(max(1.6 * boss.sigma, 24), 45))]
        if boss.kind == "syndrome":
            return [Target(e, e.col, lambda k, e=e: (e.q[0], e.q[1]), box(14, 16)) for e in boss.errors]
        if boss.kind == "bell":
            return [Target(h, boss.col, lambda k, h=h: (h.x, h.y), disc(28)) for h in boss.halves]
        return []

    def first_hit(self, x, y, vx, vy, skip=None):
        """(frames, thing) a shot now at (x, y) hits first, or None."""
        gone = self.gone if skip is None else skip
        for k in range(1, HORIZON + 1):
            bx, by = x + vx * k * DT, y + vy * k * DT
            if by < 30 or not -10 < bx < G.W + 10:
                return None
            for t in self.targets:
                if id(t.obj) not in gone:
                    tx, ty = t.pos(k)
                    if t.hit(bx - tx, by - ty):
                        return k, t.obj
            ox, oy = self.march[k]
            c, r = round((bx - ox) / G.SX), round((by - oy) / G.SY)
            e = self.grid.get((c, r))
            if e is not None and id(e) not in gone and abs(bx - ox - c * G.SX) < G.EW / 2 + 2 \
                    and abs(by - oy - r * G.SY) < G.EH / 2 + 4:
                return k, e
        return None

    def play_out(self, shots):
        """Land the shots in flight, in order: who dies, who changes colour."""
        hits = []
        for n, b in enumerate(shots):
            if b.kind == "bomb":
                continue
            h = self.first_hit(b.x, b.y, b.vx, b.vy)
            if h:
                hits.append((h[0], n, b, h[1]))
        hits.sort(key=lambda h: h[:2])  # never by id(): that differs from run to run
        for _, _, b, obj in hits:
            if id(obj) in self.gone:
                h = self.first_hit(b.x, b.y, b.vx, b.vy)
                if not h:
                    continue
                obj = h[1]
            col = self.col.get(id(obj))
            if b.kind == "all" or col == "any" or b.col == col:
                self.gone.add(id(obj))
                if getattr(obj, "chain", 0):
                    self.gone |= {id(o) for o in self.grid.values() if o.chain == obj.chain}
            elif col == "Y":
                self.col[id(obj)] = "Z" if b.col == "X" else "X"


class Bot:
    def __init__(self, pads, rng):
        self.pads, self.rng = pads, rng
        self.next_menu = 0.0
        self.swap_ready = [0, 0]
        self.target = [None, None]
        self.dodge = [(0, -1.0), (0, -1.0)]  # (direction, until)
        self.last_merge = -100.0

    def update(self, t):
        pads = self.pads
        if G.state == "play":
            self.play(t)
            return
        pads.release_all()
        if t < self.next_menu:
            return
        self.next_menu = t + 0.3
        if G.state == "title":
            if G.menu["step"] == 0 and not G.menu["two"]:
                pads.stick(0, 0.0, 1.0)  # 1 PLAYER -> 2 PLAYERS
            else:
                pads.tap(0, "a", 3)      # 2 PLAYERS, then EASY
        elif G.state == "over" and G.over_t > 1.6:
            pads.tap(0, "a", 3)

    # ------------------------------------------------------------ one ship
    @staticmethod
    def need(p, col):
        """The colour p must fire at a target of colour col (None: any will do)."""
        if col in ("any", "all") or (col == "Y" and col not in p.colors):
            return None
        return col

    def choose(self, i, p, field, other):
        best, best_cost = None, 1e9
        for tgt in field.live:
            _, y0 = tgt.pos(0)
            k = max(1, round((p.y - 20 - y0) / (SHOT * DT)))
            x, y = tgt.pos(min(k, HORIZON))
            k = max(1, round((p.y - 20 - y) / (SHOT * DT)))
            x, y = tgt.pos(min(k, HORIZON))
            if not 25 <= x <= G.W - 25:
                continue
            cost = abs(x - p.x) / p.speed - 0.0015 * y
            n = self.need(p, tgt.col)
            if n is not None:
                cost += 0.12 * ((p.colors.index(n) - p.ci) % len(p.colors))
            elif tgt.col == "Y":
                cost += 0.15  # two shots for the surface patch
            if other is not None:
                # P1 keeps to the left of P2, like their pads, and neither
                # crowds the other
                if (x > other.x - 40) if i == 0 else (x < other.x + 40):
                    cost += 0.6
                if abs(x - other.x) < abs(x - p.x):
                    cost += 0.3
                if tgt.obj is self.target[1 - i]:
                    cost += 2.0
            if tgt is field.ufo:
                hit = field.first_hit(x, p.y - 20, 0, -SHOT)
                if not hit or hit[1] is not tgt.obj:
                    continue
                cost -= 0.6
            if self.target[i] is tgt.obj:
                cost -= 0.2
            if cost < best_cost:
                best, best_cost = (tgt, x), cost
        return best

    def threat(self, g, x, y, v, horizon=0.55):
        """Closest an enemy shot comes to a ship at (x, y) moving at v px/s."""
        worst = 1e9
        for b in g.eb:
            for k in range(1, 18):
                tau = horizon * k / 17
                sx = G.clamp(x + v * tau, 25, G.W - 25)
                worst = min(worst, math.hypot(b.x + b.vx * tau - sx, b.y + b.vy * tau - y))
        return worst

    def steer(self, g, i, p, goal_x, t):
        """Stick x for ship p: toward goal_x unless that walks into a shot."""
        want = 0 if goal_x is None or abs(goal_x - p.x) < 5 else (1 if goal_x > p.x else -1)
        d, until = self.dodge[i]
        if t < until:
            return d
        if p.inv > 0.3 or self.threat(g, p.x, p.y, want * p.speed) > 18:
            return want
        options = sorted((-1, 0, 1), key=lambda m: (m != want, m == 0))
        scored = [(self.threat(g, p.x, p.y, m * p.speed), m) for m in options]
        safe = [m for d, m in scored if d > 22]
        move = safe[0] if safe else max(scored)[1]
        self.dodge[i] = (move, t + 0.15)
        return move

    def play(self, t):
        g = G.g
        pads = self.pads
        field = Field(g)
        if g.merged:
            self.last_merge = t
            self.play_merged(g, field)
            return
        players = g.players
        for i, p in enumerate(players):
            if not p.alive:
                pads.stick(i, 0.0, 0.0)
                pads.release(i, "a")
                continue
            other = players[1 - i] if len(players) > 1 and players[1 - i].alive else None

            choice = self.choose(i, p, field, other)
            tgt, goal = choice if choice else (None, None)
            self.target[i] = tgt.obj if tgt else None

            # a capsule about to fall past, if this ship can still reach it
            for c in g.caps:
                fall = (p.y - c.y) / 115
                if 0 < fall < 1.6 and abs(c.x - p.x) / p.speed < fall - 0.1 and (
                        other is None or abs(c.x - p.x) <= abs(c.x - other.x)):
                    goal = c.x
                    break

            # never on top of each other: with one target between them (a
            # boss, the last invader) the other ship waits off to its side
            if other is not None:
                if goal is None:
                    goal = p.x
                if abs(goal - other.x) < 70:
                    goal = other.x + (-70 if i == 0 else 70)

            # lattice surgery: both ships into the field, but not so often
            # that the merged ship's every-colour shots crowd out the rest
            if g.lattice and other is not None and t - self.last_merge > 30:
                L = g.lattice
                goal = L.x + L.w * (0.35 if i == 0 else 0.65)

            move = self.steer(g, i, p, goal, t)
            pads.stick(i, float(move), 0.0)

            # fire if a shot from here lands on something this colour corrects
            x = G.clamp(p.x + move * p.speed * DT, 25, G.W - 25)
            hit = field.first_hit(x, p.y - 20, 0, -SHOT)
            fire = False
            if hit is not None:
                n = self.need(p, field.col.get(id(hit[1]), "any"))
                fire = n is None or n == p.colors[p.ci]
            pads.hold(i, "a", fire)
            # otherwise get the colour the chosen target needs ready
            if not fire and tgt is not None:
                n = self.need(p, tgt.col)
                if n is not None and n != p.colors[p.ci] and pads.frame >= self.swap_ready[i]:
                    pads.tap(i, "b", 2)
                    self.swap_ready[i] = pads.frame + 6

    def play_merged(self, g, field):
        """Lattice surgery: P1 steers the merged ship under the nearest
        target, P2 swings the aim onto it, both hold fire."""
        m = g.merged
        pads = self.pads
        best = None
        for tgt in field.live:
            k = 0
            for _ in range(3):
                x, y = tgt.pos(min(k, HORIZON))
                k = round(math.hypot(x - m.x, m.y - 30 - y) / 700 / DT)
            if 25 <= x <= G.W - 25 and (best is None or abs(x - m.x) < abs(best[0] - m.x)):
                best = (x, y)
        move = 0
        if best is not None and abs(best[0] - m.x) > 6:
            move = 1 if best[0] > m.x else -1
        pads.stick(0, float(move), 0.0)
        want = 0.0
        if best is not None:
            want = G.clamp(math.atan2(best[0] - m.x, (m.y - 30) - best[1]), -0.9, 0.9)
        turn = 0 if abs(want - m.angle) < 0.04 else (1 if want > m.angle else -1)
        pads.stick(1, float(turn), 0.0)
        pads.hold(0, "a", True)
        pads.hold(1, "a", True)
