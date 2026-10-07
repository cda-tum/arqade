"""Qlimbers: two climbers racing up the tower, gate by gate.

Each player finds the shortest run of gates from their qubit to the floor's
target (a breadth-first search over the game's own gates), then plays it the
way a person would: a moment to read the new target, a beat between presses,
and a push up to climb once it matches.

They are not perfect. Now and then a player presses a wrong gate and has to
work back from it (which costs that floor's charge), or pushes up one gate
too early and is stunned for a second. The player ahead fumbles more and
reads slower than the one behind, so the race stays close and both fill
their charge bars: knockbacks fly both ways.
"""

from collections import deque

from quantum_towers import config
from quantum_towers.quantum import ACTIONS, states_equal

SECONDS = 85.0
SKIP = 0.5
HIGHLIGHTS = [  # 2 s windows with seed 1, best first
    74.3,  # photo finish: both reach floor 15, the tower top in sight
    70.6,  # knockbacks traded just below the top
    60.2,  # P1 knocks P2 off floor 13, P2 fires straight back
    6.7,   # P2 knocked to the ground floor, climbs and hits back
    34.5,  # attack and counter-attack mid-tower
    54.0,  # P2 pushes up on the wrong state and is stunned; P1 clears a floor
    20.1,  # an exchange of attacks low down, PERFECT floors
    44.5,  # level at floor 8, gates going in on both sides
]

# The button each gate is on, by its printed name -- the game's own legend.
BUTTON = {gate: label.lower()
          for label, gate in zip(config.BUTTON_LABELS, config.GATE_AT_POSITION) if gate}
GATES = ("X", "Y", "Z", "H")
FUMBLE = 0.3  # chance a floor gets one wrong gate, before the catch-up rule
EARLY = 0.04  # chance a floor is confirmed one gate too early (a stun)
READ = (0.55, 1.1)  # seconds to take in a new target
GAP = (0.25, 0.45)  # seconds between presses


def shortest(start, target, rng):
    """The fewest gates from `start` to `target`, ties broken at random."""
    names = list(ACTIONS)
    queue, seen = deque([(start, [])]), [start]
    while queue:
        state, path = queue.popleft()
        if states_equal(state, target):
            return path
        rng.shuffle(names)
        for name in names:
            after = ACTIONS[name](state)
            if not any(states_equal(after, s) for s in seen):
                seen.append(after)
                queue.append((after, path + [name]))
    return []


class Climber:
    def __init__(self, index):
        self.index, self.key = index, ("p1", "p2")[index]
        self.floor = None  # (floor, target) being worked on
        self.next_at = 0.0  # game time of this climber's next move
        self.fumble = False  # press one wrong gate on this floor
        self.early = False  # push up one gate too soon on this floor


class Bot:
    def __init__(self, pads, rng):
        self.pads, self.rng = pads, rng
        self.climbers = [Climber(0), Climber(1)]
        self.menu_since = None

    def update(self, t):
        loop = self.pads.loop
        if "players" not in loop:
            self.menu(t, loop)
            return
        self.menu_since = None
        for c in self.climbers:
            self.play(c, loop)

    def menu(self, t, loop):
        """Title or winner screen: straight on into the next match."""
        if self.menu_since is None:
            self.menu_since = t
            for c in self.climbers:
                c.floor = None
        wait = 1.0 if "winner" in loop else 0.25
        if t - self.menu_since >= wait and not self.pads.held(0, "a"):
            self.pads.tap(0, "a", 1)
            self.menu_since = t

    def play(self, c, loop):
        now = loop["game_time"]
        me = loop["players"][c.key]
        them = loop["players"][("p2", "p1")[c.index]]
        if self.pads.pads[c.index].axes[1] < 0:
            self.pads.stick(c.index, 0.0, 0.0)  # let go after a push up
        if (me.floor, me.current_target) != c.floor:
            first = c.floor is None
            c.floor = (me.floor, me.current_target)
            self.read_floor(c, now, me.floor - them.floor, first)
            return
        if now < max(c.next_at, loop["stun_until"][c.key]):
            return
        lead = me.floor - them.floor
        if states_equal(me.state, me.current_target):
            self.pads.stick(c.index, 0.0, -1.0)  # climb
            c.next_at = now + 0.5
            return
        path = shortest(me.state, me.current_target, self.rng)
        if c.early and len(path) == 1:
            c.early = False
            self.pads.stick(c.index, 0.0, -1.0)  # too soon: stunned
            c.next_at = now + 0.5
            return
        gate = path[0]
        if c.fumble and (len(path) == 1 or self.rng.random() < 0.5):
            c.fumble = False
            gate = self.rng.choice([g for g in GATES if g != gate])
        self.pads.tap(c.index, BUTTON[gate], 7)
        last = path == [gate]  # the next move is the climb
        c.next_at = now + self.rng.uniform(*((0.2, 0.35) if last else GAP)) * self.pace(lead)

    def read_floor(self, c, now, lead, first):
        """A new target is up: take a moment to read it, and decide how this
        floor will go."""
        c.next_at = now + (0.6 if first else self.rng.uniform(*READ) * self.pace(lead))
        c.fumble = self.rng.random() < min(max(FUMBLE + 0.12 * lead, 0.15), 0.85)
        c.early = self.rng.random() < EARLY

    @staticmethod
    def pace(lead):
        """Slower when ahead, quicker when behind."""
        return min(max(1 + 0.12 * lead, 0.7), 1.6)
