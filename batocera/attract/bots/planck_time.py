"""Planck Time: a versus match, P1 on the blue handheld left, P2 on the red right.

The title is walked like two people would (the stick to 2 PLAYERS, then A,
and A again on the HOW TO PLAY card).
The microgames are dealt in a fixed order instead of from the shuffled deck,
so the capture holds the ones the trailer wants: ALIGN! and PAIR! twice
each, MEASURE!, SORT!, CANCEL!, MERGE!, FIX! and CONNECT!, and then the
SYNDROME! boss to end on (due after 10 wins here instead of 12). The rest is
the real game: its seeds, levels, SPEED UP! cards and scoring.

In versus both players get the same microgame from the same seed, so two
perfect bots would draw two identical screens. These two play like people
instead: a reaction time before the first move, the stick pushed at a human
pace, a beat on the right item before A. On ALIGN! one swings the arrow past
the star and comes back while the other stops short and nudges on; on PAIR!
each goes for its own half of the pair; MEASURE! and CANCEL! are pressed at
different points of the window; on MERGE! one turns the patch round once to
check before pushing in. What to aim for comes from the microgames' own
rules and bot() (the title's attract demo), which know the answer.

Three slips are planned, so it isn't all NICE!: P2 presses MEASURE! too
early, P1 is too late with SORT!'s second token, and P2 loses the card in
FIX!'s shuffle.
"""

import math
from collections import deque

from planck_time import config
from planck_time import session as S
from planck_time.microgames import REGISTRY, PlayerInput, align, cancel, sort

SCRIPT = (
    "ALIGN!", "PAIR!", "MEASURE!", "SORT!",   # level 1
    "CANCEL!", "ALIGN!", "MERGE!", "FIX!",    # level 2
    "PAIR!", "CONNECT!",                      # level 3, then the boss
)
SLIPS = {(2, 1): "early", (3, 0): "late", (7, 1): "lost"}  # (deal, player): the mistake

SECONDS = 71.1  # ends on the boss's NICE!, just before the next intro
SKIP = 3.6  # the first ALIGN! starts at 3.62 s, after the HOW TO PLAY card
# The times below were moved, not re-picked, when the HOW TO PLAY card came in
# and a won microgame started ending 0.4 s after the win: each is the same
# moment of the same deal (the outcomes are unchanged), but a short game's
# window now runs on into its NICE! card instead of the rest of its fuse.
HIGHLIGHTS = [  # 2 s windows with seed 1, best first
    30.1,  # ALIGN!: P1 stops short of the star and nudges on, P2 swings past and back; NICE x2
    45.7,  # PAIR!, six particles: each picks its half of the pair, the wavy bonds light up
    56.5,  # SYNDROME!: DECOHERENCE winds up and strikes, the checks light, both fix it (OW!)
    13.0,  # MEASURE!: P2 presses too early (red X), P1 collapses the needle to |1>
    68.9,  # SYNDROME!: the last strike, then NICE! QUBIT SAVED! as the monster dissolves
    40.0,  # FIX!: the cards shuffle, P1 applies Y to the Y bug, P2 lost it and picks X
    8.6,  # PAIR!, four particles: both cursors walk to the pair, picked and bonded
    35.4,  # MERGE!: P2 pushes straight in, P1 turns its patch round first; ZZ measured
]
MOMENTS = {  # microgame -> start times (s) of good 2 s play windows, seed 1
    "ALIGN!": [30.1, 3.8],
    "PAIR!": [45.7, 8.6],
    "MEASURE!": [13.0],
    "SORT!": [18.6],  # P2 sorts the second token, P1 is late and it hits the floor
    "CANCEL!": [25.8],
    "MERGE!": [35.4],
    "FIX!": [40.0],
    "CONNECT!": [50.1],
    "SYNDROME!": [56.5, 68.9, 58.7],  # 58.7: a double strike, four checks lit
}

# seconds of game time before a player first moves, by microgame
REACT = {"ALIGN!": (0.2, 0.45), "PAIR!": (0.9, 1.5), "MEASURE!": (0.2, 0.4), "SORT!": (0.0, 0.0),
         "CANCEL!": (0.0, 0.0), "MERGE!": (0.8, 1.2), "FIX!": (0.25, 0.45), "CONNECT!": (0.1, 0.3),
         "SYNDROME!": (0.0, 0.0)}
TUTORIAL_READ = 1.5  # seconds the HOW TO PLAY card stays up before the bot presses on
GAP = (0.16, 0.26)  # between two stick pushes
SETTLE = (0.12, 0.28)  # on the right item before pressing A
IDLE = PlayerInput()
DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))


def deal_script():
    """Deal SCRIPT first, then the game's own shuffled deck; the boss after it."""
    queue = [next(cls for cls in REGISTRY if cls.VERB == verb) for verb in SCRIPT]
    shuffled = S.Deck.draw

    def draw(deck):
        if queue:
            deck.last = queue.pop(0)
            return deck.last
        return shuffled(deck)

    S.Deck.draw = draw
    config.BOSS_EVERY = len(SCRIPT)


def raw(v):
    """The axis value that reads as `v` once the game's deadzone is cut out."""
    dz = config.INPUT_CONFIG["axis_deadzone"]
    return 0.0 if v == 0 else math.copysign(dz + (1 - dz) * min(1.0, abs(v)), v)


class Player:
    """One player's hands on one microgame at a time."""

    def __init__(self, index, rng):
        self.index, self.rng = index, rng
        self.game = None

    def new_game(self, game, deal, slip, style):
        r = self.rng
        self.game, self.deal, self.slip, self.style = game, deal, slip, style
        self.react = r.uniform(*REACT.get(game.VERB, (0.2, 0.4)))
        self.gap = r.uniform(*GAP)
        self.settle = r.uniform(*SETTLE)
        self.last = -1.0  # game time of the last push or press
        self.plan = None
        self.stage, self.since = 0, 0.0
        self.passes, self.inside, self.prev = 0, False, None
        self.token, self.delay = -1, 0.0

    def play(self, g):
        if g.result is not None or g.t < self.react:
            return IDLE
        how = getattr(self, "play_" + type(g).__name__.lower(), self.follow)
        return how(g)

    def paced(self, g, inp):
        """`inp`, but a push only every `gap` and A only after `settle`."""
        if inp.step != (0, 0) or inp.a:
            if g.t - self.last < (self.settle if inp.a else self.gap):
                return PlayerInput(stick=inp.stick)
            self.last = g.t
        return inp

    def follow(self, g):
        """The microgame's own bot, at this player's pace."""
        return self.paced(g, g.bot())

    # --- ALIGN!: swing past the star and come back, or stop short and nudge on
    def play_align(self, g):
        d = align.wrap(g.target - g.angle)
        if self.plan is None:
            self.way = 1 if d > 0 else -1
            off = (40, 55) if self.style == "past" else (25, 33)  # degrees past, or short
            self.off = math.radians(self.rng.uniform(*off))
            if self.style == "past" and abs(d) + self.off > math.radians(170):
                self.style = "short"
                self.off = math.radians(self.rng.uniform(25, 33))
            self.see = math.radians(self.rng.uniform(12, 22))  # how far past before it's noticed
            self.hold = self.rng.uniform(0.2, 0.35)  # stopped short, a look before nudging on
            self.plan = self.style
        aim = g.target
        if self.plan == "past" and self.stage < 2:
            aim = g.target + self.way * self.off
            if self.stage == 0 and align.wrap(g.angle - g.target) * self.way > self.see:
                self.stage, self.since = 1, g.t
            elif self.stage == 1 and g.t - self.since > 0.1:
                self.stage = 2
        elif self.plan == "short" and self.stage < 2:
            aim = g.target - self.way * self.off
            if self.stage == 0 and abs(align.wrap(g.angle - aim)) < 0.05:
                self.stage, self.since = 1, g.t
            elif self.stage == 1 and g.t - self.since > self.hold:
                self.stage = 2
        return PlayerInput(stick=(math.sin(aim), -math.cos(aim)))

    # --- PAIR!: walk the cursor to this player's half of the pair, then A
    def play_pair(self, g):
        if self.plan is None:
            self.plan = g.pair[(self.index + self.deal) % 2]
        if g.cursor in g.pair:
            return self.paced(g, PlayerInput(a=True, a_held=True))
        first = {g.cursor: None}
        todo = deque([g.cursor])
        while todo:
            i = todo.popleft()
            for d in DIRS:
                j = g.nearest(i, d)
                if j not in first:
                    first[j] = first[i] or d
                    if j == self.plan:
                        return self.paced(g, PlayerInput(step=first[j]))
                    todo.append(j)
        return IDLE

    # --- MEASURE!: A somewhere in the zone, on the way up or on the way back
    def play_measure(self, g):
        a, zone = g.angle, g.zone
        coming = self.prev is not None and abs(a) < abs(self.prev)
        self.prev = a
        if self.slip == "early":  # a few degrees before the zone, still on the way up
            return PlayerInput(a=coming and zone + 0.1 < a < zone + 0.2)
        if self.plan is None:
            self.plan = (self.rng.uniform(0.35, 0.8), self.index)  # depth into the zone, passes to let go by
        depth, skip = self.plan
        inside = abs(a) < zone * depth
        if inside and not self.inside:
            self.passes += 1
        self.inside = inside
        return PlayerInput(a=inside and coming and self.passes > skip)

    # --- SORT!: each token a moment after it appears, full stick, easing off over the bin
    def play_sort(self, g):
        if g.i >= len(g.kinds) or g.wait > 0:
            return IDLE
        if g.i != self.token:
            self.token = g.i
            fall = (sort.BIN_TOP - sort.TOKEN[1] / 2 - sort.SPAWN_Y) / g.v
            late = self.slip == "late" and g.i == 1
            self.delay = fall - 0.2 if late else self.rng.uniform(0.12, 0.35)
        if (g.y - sort.SPAWN_Y) / g.v < self.delay:
            return IDLE
        d = sort.TARGETS[g.kinds[g.i]] - g.x
        return IDLE if abs(d) < 3 else PlayerInput(stick=(max(-1.0, min(1.0, d / 12)), 0.0))

    # --- CANCEL!: A as the twin slides over the slot, a little early or late
    def play_cancel(self, g):
        if self.plan is None:
            self.plan = self.rng.uniform(-4.0, 6.0)
        return PlayerInput(a=g.twin[0] <= cancel.SLOT_X + self.plan)

    # --- MERGE!: turn the patch if its edge doesn't match, push in; when it
    # already matches, one of them turns it round once to check
    def play_merge(self, g):
        if g.pushed or g.spinning:
            return IDLE
        if self.plan is None:
            self.plan = 2 if g.wins(g.rot, g.lane) and self.index == self.deal % 2 else 0
        lane = next(lane for lane in range(len(g.fixed)) if any(g.wins(rot, lane) for rot in (0, 1)))
        if lane != g.lane:
            return self.paced(g, PlayerInput(step=(0, 1 if lane > g.lane else -1)))
        if self.plan or not g.wins(g.rot, g.lane):
            inp = self.paced(g, PlayerInput(a=True, a_held=True))
            if inp.a and self.plan:
                self.plan -= 1
            return inp
        return self.paced(g, PlayerInput(step=(-1, 0)))

    # --- FIX!: the right card after the shuffle; or onto it before, and lose it
    def play_fix(self, g):
        if self.slip == "lost":
            if self.plan is None:
                self.plan = g.order.index(g.fix)  # where it is before the shuffle
            goal = self.plan
        elif g.shuffle_pending:
            return IDLE  # watching the cards move
        else:
            goal = g.order.index(g.fix)
        if goal != g.cursor:
            return self.paced(g, PlayerInput(step=(1 if goal > g.cursor else -1, 0)))
        if g.shuffle_pending:
            return IDLE
        return self.paced(g, PlayerInput(a=True, a_held=True))

    # --- SYNDROME!: read the lit checks (it cheats: it knows the flips), step, X
    def play_syndrome(self, g):
        if not g.flips or g.t - g.landed_at < self.think:
            return IDLE
        target = min(g.flips, key=lambda q: (abs(q - g.cursor), q))
        if target == g.cursor:
            return self.paced(g, PlayerInput(a=True, a_held=True))
        return self.paced(g, PlayerInput(step=(1 if target > g.cursor else -1, 0)))

    @property
    def think(self):
        return 0.3 + 0.12 * self.index


class Bot:
    def __init__(self, pads, rng):
        self.pads, self.rng = pads, rng
        self.players = [Player(i, rng) for i in (0, 1)]
        self.deals = -1
        self.dealt = None
        self.next_menu = 0.25
        deal_script()

    def update(self, t):
        s = self.pads.loop.get("session")
        if s is None:
            return
        if s.state == S.TITLE:
            self.title(t, s)
            return
        if s.state == S.TUTORIAL:  # the HOW TO PLAY card: a moment to show it, then A
            self.apply(0, IDLE)
            if s.t >= TUTORIAL_READ and not self.pads.held(0, "a"):
                self.pads.tap(0, "a", 4)
            return
        if s.games.get("p1") is not self.dealt:
            self.dealt = s.games.get("p1")
            self.deals += 1
        if s.state != S.PLAY or s.paused:
            for i in (0, 1):
                self.apply(i, IDLE)
            return
        styles = ("past", "short") if self.deals % 2 == 0 else ("short", "past")
        for i, player in enumerate(self.players):
            g = s.games.get(S.PLAYERS[i])
            if g is None:
                continue
            if g is not player.game:
                player.new_game(g, self.deals, SLIPS.get((self.deals, i)), styles[i])
            self.apply(i, player.play(g))

    def title(self, t, s):
        """To 2 PLAYERS, then A (never Start: in play it pauses). The row is
        read, not counted, so it can never end up on QUIT below it."""
        self.pads.stick(0, 0.0, 0.0)
        if t < self.next_menu:
            return
        self.next_menu = t + 0.3
        want = S.TITLE_ITEMS.index("2 PLAYERS")
        if s.title_index != want:
            self.pads.stick(0, 0.0, 1.0 if s.title_index < want else -1.0)
        else:
            self.pads.tap(0, "a", 4)

    def apply(self, i, inp):
        x, y = inp.step if inp.step != (0, 0) else inp.stick
        self.pads.stick(i, raw(x), raw(y))
        if inp.a and not self.pads.held(i, "a"):
            self.pads.tap(i, "a", 4)
