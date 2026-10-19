"""Qarrera: two people's cars and four bots, on each track in turn.

The first bot built on its game's own AI (qarrera/src/qarrera/ai.py) rather
than its own logic: the in-game opponents, the bots behind Qarrera's title
and this reel bot are one driver. Here it sits in P1's and P2's seats at
BRUTAL and its Controls become stick moves (up to raise the cruise speed,
down to lower it, a one-frame push left or right to change wires), exactly
what a person's stick does, while the match's own bots race at TOUGH
around them. See "AI opponents" in ../../../AGENTS.md.

Not yet recordable: capture.py reads a 2D display after its flip, and
Qarrera draws with OpenGL; it needs SDL's offscreen driver and a read of the
GL frame before the flip.

On the title it sets 2 players, 4 bots, TOUGH, first to 30 s in front and
the track, and goes on with Start (never A: the title's last row is QUIT);
in the racer select it moves both cursors to new racers each time and
presses Start; on the HOW TO PLAY card it presses A after a moment; after
the match it goes back to the title for the next track.
"""

from qarrera.ai import Driver
from qarrera.match import MATCH_END, RACE, SELECT, SELECT_COLS, SETTINGS_ROWS, TITLE, TUTORIAL
from qarrera.racers import ROSTER

SECONDS = 90.0
SKIP = 4.0
DT = 1 / 60
SEATS = {"p1": 0, "p2": 1}  # each person's stick: the left pad's and the right pad's
SETTINGS = {"PLAYERS": 2, "BOTS": 4, "LEVEL": "TOUGH", "LEAD": 30}
TRACKS = (0, 2, 1)  # figure 8, hairpin, split


def current(match, row):
    return {"PLAYERS": match.humans, "BOTS": match.bots, "LEVEL": match.level,
            "TRACK": match.track_index, "LEAD": match.target}[row]


class Bot:
    def __init__(self, pads, rng):
        self.pads, self.rng = pads, rng
        self.races = 0
        self.race = None
        self.drivers = {}
        self.last_press = -10.0

    def update(self, t):
        match = self.pads.loop.get("match")
        if match is None:
            return
        if match.paused:  # never meant to happen; B resumes
            self.press("b", t)
        elif match.state == RACE:
            self.drive(match)
            return
        self.hands_off()
        if match.state == TITLE:
            self.title(match, t)
        elif match.state == SELECT:
            self.select(match, t)
        elif match.state == TUTORIAL and match.t > 0.8:
            self.press("a", t)  # any button goes on
        elif match.state == MATCH_END and match.t > 2.5:
            self.press("b", t)  # back to the title, for the next track

    def press(self, button, t):
        if t - self.last_press > 0.5:
            self.pads.tap(0, button)
            self.last_press = t

    def hands_off(self):
        for pad in SEATS.values():
            self.pads.stick(pad, 0.0, 0.0)

    def title(self, match, t):
        want = dict(SETTINGS, TRACK=TRACKS[self.races % len(TRACKS)])
        wrong = [row for row in SETTINGS_ROWS if current(match, row) != want[row]]
        if not wrong:
            self.press("start", t)  # Start starts from any row, QUIT's included
            return
        if self.pads.frame % 2:  # every push needs a let-go before the next
            return
        target = SETTINGS_ROWS.index(wrong[0])
        if match.row != target:
            self.pads.stick(0, 0.0, 1.0 if target > match.row else -1.0)
        else:
            self.pads.stick(0, 1.0, 0.0)

    def select(self, match, t):
        """Each person's cursor a few racers on from last time, then Start."""
        n = len(ROSTER)
        want = {"p1": (self.races * 2) % n, "p2": (self.races * 2 + 5) % n}
        off = [p for p in want if match.picks.get(p) != want[p]]
        if not off:
            if match.t > 1.2:
                self.press("start", t)
            return
        if self.pads.frame % 2 == 0:
            p = off[0]
            down = want[p] // SELECT_COLS != match.picks[p] // SELECT_COLS  # rows first
            self.pads.stick(SEATS[p], 0.0 if down else 1.0, 1.0 if down else 0.0)

    def drive(self, match):
        if match.race is not self.race:
            self.race = match.race
            self.races += 1
            self.drivers = {p: Driver(p, "BRUTAL", self.rng) for p in SEATS}
        for player, pad in SEATS.items():
            c = self.drivers[player].controls(match.race, DT)
            x = -1.0 if c.left else (1.0 if c.right else 0.0)
            y = -1.0 if c.throttle else (1.0 if c.brake else 0.0)
            self.pads.stick(pad, x, y)
