"""Quantum Pong: two evenly matched players who aim for the gates.

Each paddle works out where the ball heading its way will cross its line
(walls included, by stepping the game's own physics), misjudges that a little
while the ball is far off, and settles as it closes in. With several balls
coming, it plays the first one it can still reach. It angles each return to
send the ball through an H gate where it can, else through any other gate,
else at a random angle -- so the field fills up with balls and gate tricks.

Now and then a paddle stops a few pixels short and lets the ball past. How
often is set so the score climbs by about one point every PACE seconds (the
balls a crowded field costs count towards it), the player ahead misses more
than the one behind, and nobody gives away match point before the recording
is nearly over: a close match, not a quick 7-0.
"""

import math

from quantum_pong import config
from quantum_pong.pong import Ball, step_ball

SECONDS = 85.0
SKIP = 0.5
HIGHLIGHTS = [  # 2 s windows with seed 1, best first
    16.9,  # four balls in play, P1 scores twice
    53.7,  # three balls after an H split, P2 pulls level 4-4
    70.9,  # multi-ball, a point each way: 6-4, 6-5
    12.7,  # a return through H splits the ball, three in play
    74.3,  # another H split, P2 equalises 6-6
    5.6,   # the first H split of the match
    29.2,  # one-ball rally, P2 scores twice
    38.3,  # a rally through the X and Z gates
]

PACE = 7.5  # seconds per point the scoreboard should average
MULTI_SLACK = 1.5  # with several balls in play, points behind before anyone misses on purpose
DT = 1 / 60
STEP = config.PADDLE_SPEED * DT  # paddle travel per frame
HALF = config.PADDLE_HEIGHT / 2
REACH = HALF + config.PADDLE_CATCH_GRACE  # ball-to-paddle-centre distance still caught
LINE = (config.PADDLE_MARGIN + config.PADDLE_WIDTH + config.BALL_RADIUS,
        config.INTERNAL_WIDTH - config.PADDLE_MARGIN - config.PADDLE_WIDTH - config.BALL_RADIUS)
LOWEST = config.INTERNAL_HEIGHT - HALF  # lowest a paddle's centre goes


def arrival(ball, player):
    """(frames, y) until `ball` reaches `player`'s paddle line, or None."""
    if ball.vx * (-1 if player == 0 else 1) <= 0:
        return None
    for frames in range(1, 400):
        ball = step_ball(ball, DT, config.INTERNAL_HEIGHT, config.BALL_RADIUS)
        if (ball.x <= LINE[0]) if player == 0 else (ball.x >= LINE[1]):
            return frames, ball.y
    return None


def first_gate(ball, gates):
    """The first gate `ball` would run through before reaching a paddle."""
    reach = config.GATE_RADIUS + config.BALL_RADIUS - 5  # a little inside the real hit circle
    for _ in range(400):
        ball = step_ball(ball, DT, config.INTERNAL_HEIGHT, config.BALL_RADIUS)
        if not LINE[0] < ball.x < LINE[1]:
            return None
        for gate in gates:
            if math.hypot(ball.x - gate.x, ball.y - gate.y) <= reach:
                return gate
    return None


class Player:
    def __init__(self, index):
        self.index = index
        self.eta = None  # frames until the ball being played arrives
        self.miss = 0.0  # px to let the ball by, or 0 to play it
        self.offset = 0.0  # where on the paddle to take the ball, -1 top .. 1 bottom
        self.misread = 0.0  # px the early read of the ball is off by
        self.react = 0  # frames before the paddle reacts to a new ball
        self.gates = None  # the gates the current aim was worked out for


class Bot:
    def __init__(self, pads, rng):
        self.pads, self.rng = pads, rng
        self.players = [Player(0), Player(1)]
        self.menu_since = None
        self.match_start = 0.0

    def update(self, t):
        loop = self.pads.loop
        if "balls" not in loop:
            self.menu(t, loop)
            return
        if self.menu_since is not None:
            self.menu_since, self.match_start = None, t
        paddles = (loop["p1_paddle"], loop["p2_paddle"])
        for p in self.players:
            centre = paddles[p.index].y + HALF
            gap = self.play(p, t, loop, centre) - centre
            self.pads.stick(p.index, 0.0, 0.0 if abs(gap) < STEP / 2 else math.copysign(1.0, gap))

    def menu(self, t, loop):
        """Title or winner screen: straight on into the next match."""
        for player in (0, 1):
            self.pads.stick(player, 0.0, 0.0)
        if self.menu_since is None:
            self.menu_since = t
        wait = 1.0 if "winner" in loop else 0.25
        if t - self.menu_since >= wait and not self.pads.held(0, "a"):
            self.pads.tap(0, "a", 1)
            self.menu_since = t

    def play(self, p, t, loop, centre):
        """Where this paddle's centre should be."""
        coming = [(a, b) for a, b in ((arrival(b, p.index), b) for b in loop["balls"]) if a]
        if not coming:
            p.eta = None
            edge = 0 if p.index == 0 else config.INTERNAL_WIDTH
            ball = min(loop["balls"], key=lambda b: abs(b.x - edge))
            return (config.INTERNAL_HEIGHT / 2 + ball.y) / 2  # keep an eye on it, from the middle
        reachable = [c for c in coming if abs(c[0][1] - centre) - REACH <= c[0][0] * STEP]
        (frames, y), ball = min(reachable or coming, key=lambda c: c[0][0])
        if p.eta is None or abs(frames - (p.eta - 1)) > 2:  # a different ball to play
            self.plan(p, t, loop)
        p.eta = frames
        if p.react > 0:
            p.react -= 1
            return centre
        if p.gates != loop["active_gates"]:
            self.aim(p, loop, ball, y)
        y += p.misread * min(1.0, frames / 50)
        if p.miss:
            # Stop just short of it, on whichever side the paddle comes from.
            side = 1 if centre > y else -1
            return min(max(y + side * (REACH + p.miss), HALF), LOWEST)
        return y - p.offset * HALF

    def plan(self, p, t, loop):
        """A new ball is coming: how quickly and how well this player reads it."""
        p.react = self.rng.randint(4, 12)
        p.misread = self.rng.uniform(-25, 25)
        p.offset = self.rng.uniform(-0.7, 0.7)
        p.gates = None
        missing = self.rng.random() < self.miss_chance(p.index, t, loop)
        p.miss = self.rng.uniform(3, 10) if missing else 0.0

    def miss_chance(self, index, t, loop):
        score = loop["score"]
        mine, theirs = score[("p1", "p2")[index]], score[("p2", "p1")[index]]
        if t - self.match_start < 4 or (theirs >= config.WINNING_SCORE - 1 and t < SECONDS - 6):
            return 0.0  # never the first serve, nor match point before the recording is over
        behind_schedule = (t - self.match_start) / PACE + 0.5 - (mine + theirs)
        if len(loop["balls"]) > 1:
            behind_schedule -= MULTI_SLACK  # multi-ball costs points by itself
        chance = min(max(0.03 + 0.12 * behind_schedule, 0.0), 0.5)
        if mine < theirs:
            return chance * 0.4
        if mine > theirs + 1:
            return max(chance, 0.3)  # a comfortable lead makes you careless
        return chance * (1.8 if mine > theirs else 1.0)

    def aim(self, p, loop, ball, y):
        """Pick the angle that sends the return through a gate, if any does."""
        p.gates = loop["active_gates"]
        if p.miss or not p.gates:
            return
        speed = min(math.hypot(ball.vx, ball.vy) + config.BALL_SPEED_INCREMENT,
                    config.BALL_MAX_SPEED)
        toward = 1 if p.index == 0 else -1
        splits = len(loop["balls"]) < config.MAX_BALLS_ON_SCREEN
        found = {}
        for i in range(-16, 17):
            offset = i / 20
            angle = math.radians(offset * config.BALL_MAX_BOUNCE_ANGLE_DEG)
            back = Ball(LINE[p.index], y, toward * speed * math.cos(angle), speed * math.sin(angle))
            gate = first_gate(back, p.gates)
            if gate is not None:
                found.setdefault("H" if gate.kind == "H" and splits else "other", []).append(offset)
        offsets = found.get("H") or found.get("other")
        if offsets:
            p.offset = offsets[len(offsets) // 2]
