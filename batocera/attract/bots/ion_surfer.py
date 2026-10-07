"""Ion Surfer: two surfers racing in 2-player VERSUS.

Each player shapes their own curve to carry their ion along: a gentle slope
down to the right, steeper while the ion is slower than it should be and
tipped the other way to brake near the screen's right edge. The cursor
works on whichever electrode is furthest from where it should be, nearest
the ion first. Obstacles bend the plan: the curve rises over blocks and
defects, dips under ceilings, energy caps and high loss holes, and climbs
over low ones. A stray ion sits on the average of both curves, so blue
rides high over it and red low under it. Raising the curve right under a
moving ion throws it into the air, so that only happens when it has nearly
stopped; an ion rolling back, or near the left edge, gets a wall behind it.
Whoever is ahead waits for the other, as the camera follows the leader.
"""

import math
from pathlib import Path

from ion_surfer import game as GM

SECONDS = 85.0
SKIP = 0.5
HIGHLIGHTS = [
    34.0,  # past a stray ion: blue rides high over it, red low under it, photons
    59.6,  # big swoops, blue in the air, photons to pick up
    70.4,  # blue's curve heaves around a stray, laser beams behind
    30.0,  # surfing past a loss hole towards a stray
    13.1,  # blue sails over the blocks, red climbs out of an energy cap
    65.1,  # through the laser beams, red thrown high
    18.0,  # swooping curves between the blocks
    78.4,  # late and fast: energy caps, a defect, a wall to climb
]

# The game would otherwise read (and in solo/co-op write) the real records in ~.
GM.SCORE_FILE = Path("/nonexistent/ion_surfer_scores.json")

EW, R, W = GM.EW, GM.R, GM.W
CRUISE = 130      # riding height of the ion, where nothing is in the way
SPEED = 170       # px/s the ion should surf at
AHEAD = 5         # electrodes ahead of the ion that are kept in shape
CARRY = 0.5       # see Surfer.update: share of the curve at the ion that may be raised
SLOW = 100        # px/s: below this the ion may be pushed from right under it


def clamp(v, a, b):
    return a if v < a else b if v > b else v


class Surfer:
    """One player's cursor, curve and ion."""

    def __init__(self, player):
        self.player = player

    def plan(self, game, ion, wait):
        """Target voltage for each electrode around the ion: a slope down
        to the right, steeper while the ion is slower than it should be,
        bent around whatever is coming."""
        lead = ion.x - game.cam_x
        want = SPEED
        if lead > 0.75 * W:
            want = 90
        elif lead < 380:
            want = 230
        if wait:
            want = min(want, 60)
        if any(e.type == "stray" and e.active and 0 < e.x - ion.x < 500 for e in game.ents):
            want = min(want, 110)
        slope = clamp(0.2 * (want - ion.vx), -10, 40)  # px per electrode, downhill to the right
        if ion.vx > 330 or lead > 0.82 * W:
            slope = -18   # brake: bouncing off the screen's edge sends it all the way back
        rise = clamp(slope, 10, 30)                      # the same, on ground that must be lifted
        k = math.floor(ion.x / EW - 0.5)
        nodes = range(k - 2, k + AHEAD + 1)
        limits = {j: self.bounds(game, (j + 0.5) * EW, ion.x) for j in nodes}
        # The ion rolls down to anything but has to be lifted up to it, so it
        # rides at least as high as what is coming has to be cleared, and a
        # little higher for every electrode before it, to keep rolling.
        # Under a ceiling (a cap, say) it can't be lifted: it keeps rolling
        # down and gets over what follows on its speed.
        floor, run = {}, -1e9
        for j in reversed(nodes):
            lo, hi = limits[j]
            run = max(lo, run + rise)
            if run > hi:
                run = hi
                floor[j] = GM.VMIN
            else:
                floor[j] = run
        here = game.potential(ion.curve, ion.x)
        out, prev = {}, None
        for j in nodes:
            lo, hi = limits[j]
            hi = min(hi, GM.VMAX)
            x = (j + 0.5) * EW
            base = min(CRUISE, hi) - slope * (x - ion.x) / EW
            if x < ion.x and (ion.vx < -40 or lead < 0.35 * W):
                # rolling back, or near the left edge: a wall behind it
                base = max(base, here + 120 * (ion.x - x) / EW)
            want = clamp(base, max(floor[j], GM.VMIN), hi)
            if prev is not None and j > k and slope > 0:
                want = max(floor[j], min(want, prev - 5))  # never uphill ahead
            out[j] = prev = want
        return out

    def bounds(self, game, x, past):
        """(lowest, highest) voltage the electrode at x may have for the ion
        to get through what is around it, ignoring what is behind `past`."""
        lo, hi = GM.VMIN, GM.VMAX
        for e in game.ents:
            if e.type == "block":
                if e.x + e.w > past - 2 * R and e.x - 120 < x < e.x + e.w + 120:
                    if e.y0 <= 0:
                        lo = max(lo, e.y1 + R + 35)
                    else:
                        hi = min(hi, e.y0 - 2 * R - 30)
            elif e.type == "cap":
                # inside it the curve is cut off at the cap; ride in level
                # with it rather than dropping off a cliff into it
                if e.x + e.w + 60 > past and e.x - 150 < x < e.x + e.w + 160:
                    hi = min(hi, e.h - 20)
            elif e.type == "hole":
                if e.x > past - 40 and abs(x - e.x) < 170:
                    if e.y > 170:
                        hi = min(hi, e.y - 90)
                    else:
                        lo = max(lo, e.y + 100)
            elif e.type == "defect":
                if e.x + e.w > past and abs(x - e.x) < 2 * e.w + 60:
                    lo = max(lo, e.a + 10)
            elif e.type == "stray" and e.active:
                # A stray rests on the average of the two curves. Blue goes
                # over it and red under it, so it ends up between the two
                # ions, far from both, and drops behind once they are past.
                if e.x > past - 30 and abs(x - e.x) < 140:
                    if self.player == 0:
                        lo = max(lo, 420)
                    else:
                        hi = min(hi, 40)
        if lo > hi:
            lo = hi
        return lo, hi

    def ion(self, game):
        cursor = next(c for c in game.cursors if self.player in c.pads)
        return next(i for i in game.ions if i.curve is cursor.curve)

    def update(self, game, pads, wait):
        p = self.player
        cursor = next(c for c in game.cursors if p in c.pads)
        ion = self.ion(game)
        if not ion.alive:
            pads.stick(p, 0.0, 0.0)
            return
        curve = cursor.curve
        first = math.ceil(game.cam_x / EW - 0.5)
        last = math.floor((game.cam_x + W) / EW - 0.5)
        k = math.floor(ion.x / EW - 0.5)
        # the electrodes either side of the ion matter most, then the next
        # ones it will reach; a far one is only worth it for a big change
        weight = {k - 2: 0.5, k - 1: 0.7, k: 1.5, k + 1: 1.5, k + 2: 1.1, k + 3: 0.8, k + 4: 0.5, k + 5: 0.35}
        # Raising the curve right under the ion at full rate throws it in the
        # air (it bounces off the rising surface), so an electrode that
        # carries more than half of the curve at the ion only goes up while
        # the ion is in flight or nearly stopped. The push comes from the
        # ones behind.
        f = ion.x / EW - 0.5 - k
        carries = {k - 1: 0.5 * (-f + 2 * f * f - f ** 3), k: 0.5 * (2 - 5 * f * f + 3 * f ** 3),
                   k + 1: 0.5 * (f + 4 * f * f - 3 * f ** 3), k + 2: 0.5 * (f ** 3 - f * f)}
        flying = ion.y - game.potential(curve, ion.x) > R + 25
        best, best_score, stay = None, 0.0, None
        plan = self.plan(game, ion, wait)
        for j, want in plan.items():
            if not first <= j <= last:
                continue
            game.ensure(curve, j)
            if j > k + 1 and want > curve.v[j]:
                # lift from behind: never raise one ahead of the ion above
                # the one before it, or it becomes a wall the ion rolls back from
                want = min(want, max(curve.v[j - 1] - 5, curve.v[j]))
            err = want - curve.v[j]
            if err > 0 and carries.get(j, 0) > CARRY and not flying and ion.vx > SLOW:
                continue
            if j == cursor.sel and abs(err) >= 6:
                stay = (j, err)
            if abs(err) < 10:
                continue
            score = weight[j] * min(abs(err), 200) / (0.1 + 0.05 * abs(j - cursor.sel))
            if best is None or score > best_score:
                best, best_score = (j, err), score
        if stay is not None and (best is None or best[0] == stay[0] or
                                 weight[stay[0]] * min(abs(stay[1]), 200) / 0.1 > 0.6 * best_score):
            best = stay   # finish the electrode under the cursor first
        if best is None:
            pads.stick(p, 0.0, 0.0)
            return
        j, err = best
        if j != cursor.sel:
            # flick the stick: on for two frames, off for one
            on = pads.frame % 3 != 2
            pads.stick(p, (1.0 if j > cursor.sel else -1.0) if on else 0.0, 0.0)
        else:
            pads.stick(p, 0.0, -1.0 if err > 0 else 1.0)


class Bot:
    def __init__(self, pads, rng):
        self.pads, self.rng = pads, rng
        self.surfers = [Surfer(0), Surfer(1)]
        self.next_menu = 0.0

    def update(self, t):
        pads = self.pads
        game = pads.loop.get("game")
        if game is None:
            return
        if game.state == "play":
            # versus: whoever is ahead waits for the other, or the camera
            # would follow the leader and leave the other one behind
            ions = {s.player: s.ion(game) for s in self.surfers}
            for s in self.surfers:
                me, other = ions[s.player], ions[1 - s.player]
                wait = other.alive and other.x - game.cam_x < 0.4 * GM.W and me.x > other.x + 150
                s.update(game, pads, wait)
            return
        pads.release_all()
        if t < self.next_menu:
            return
        self.next_menu = t + 0.3
        if game.state == "menu":
            if game.menu_sel != 1:      # 2 PLAYERS: VERSUS
                pads.stick(0, 0.0, 1.0 if game.menu_sel < 1 else -1.0)
            else:
                pads.tap(0, "a", 3)
        elif game.state == "over":
            if game.menu_sel != 1:      # NEW SEED
                pads.stick(0, 0.0, 1.0 if game.menu_sel < 1 else -1.0)
            else:
                pads.tap(0, "a", 3)
