"""One racer's driving: speed, lateral position, curves, off-road, boosts and bumps.

Pure Python, no pygame. `z` is the race distance from the start line in world units (it
keeps growing lap after lap, as the renderer's objects and the gate rows do), and `x` is
lateral in road half-widths: -1 to 1 is the road, beyond it the copper plate.

The handling is OutRun's: the car auto-accelerates to its top speed, the stick moves it
sideways at a rate proportional to speed, and a curve pushes it outward in proportion to
speed squared times the curve. Holding the brake through a curve takes some of the push
away, on top of the speed it sheds.

**Drifting** comes from the same two controls: the stick pulled back *and* steered
(|steer| >= DRIFT_STEER, from DRIFT_MIN_SPEED) is a drift, pulled straight back is the brake.
A drift runs at DRIFT_SPEED of the speed the car would have, with DRIFT_PUSH of the curve's
push, and charges by its length (DRIFT_LEVELS), but only while the road bends its way by
more than DRIFT_CHARGE_CURVE: on a straight (or against the bend) the charge holds and does
not grow, so weaving on a straight earns nothing. Letting go of it gives that level's
mini-turbo through `give_boost`. Steering the other way lets go too (and may start a new
one). Slowing below DRIFT_END_SPEED, a bump or a hit ends it with nothing.

Hits and items act on the car through `spin` (a spin-out: SPIN_SPEED of its speed, no stick
for SPIN_TIME), `slow` (a speed cap for a while), `clear_boosts` and `tunnel` (off-road at
full speed; the race also lets it through cars and hazards). `cues` lists what happened in
the last update, for the race to pass on: ("drift", level), ("turbo", level) and
("tunnel_end", None).
"""

from __future__ import annotations

from typing import NamedTuple

from gate_prix import config

TOP = config.TOP_SPEED


class Controls(NamedTuple):
    """One car's input for a frame: steer -1 (left) to 1 (right), brake 0 to 1, and whether
    to use the held item (true on the frame of a press: a held button would use the next
    item the moment a box gives it). `pace` multiplies the top speed (within config.PACE_LIMITS): a
    human always drives at 1.0, and the bots (ai.py) use it for their level and rubber-banding,
    so the race never needs to know who drives."""

    steer: float = 0.0
    brake: float = 0.0
    item: bool = False
    pace: float = 1.0


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


class Car:
    """A car on the track. The race owns its laps, circuit and place; this is the driving."""

    def __init__(self, id: str, colour: str, lane_x: float) -> None:
        self.id = id
        self.colour = colour  # a key of config.CAR_COLORS
        self.kind = f"car:{colour}"  # its sprite
        self.lane = lane_x  # its grid lane
        self.x = lane_x
        self.z = 0.0
        self.speed = 0.0
        self._boosts: list[list[float]] = []  # [strength, seconds left], each running down
        self.steer = 0.0  # the stick as last applied, for a lean
        self.drifting = False  # in a drift: stick back and steered (see the top)
        self.drift_dir = 0  # its direction: 1 right, -1 left, 0 when not drifting
        self.drift_time = 0.0  # its charge: seconds of it into a bend (DRIFT_CHARGE_CURVE)
        self.drift_angle = 0.0  # the slide's angle now, radians (positive: nose to the right)
        self.turbo_level = 0  # the level of the last mini-turbo ...
        self.turbo_flash = 0.0  # ... and the seconds its flash has left
        self.spin_time = 0.0  # seconds of a spin-out left: the stick does nothing
        self.slow_time = 0.0  # seconds of a speed cap left ...
        self.slow_cap = 1.0  # ... and the cap, a share of the top speed
        self.tunnel_time = 0.0  # seconds of TUNNEL left
        self.cues: list[tuple[str, object]] = []  # what happened in the last update
        self.offroad = False
        self.knock = 0.0  # lateral speed left from a side bump, half-widths a second
        self.prev_z = 0.0  # where the last update started, to find where it crossed a row
        self.prev_x = lane_x
        self.pace = 1.0  # the top speed's multiplier, from the controls

    # --- Boosts -----------------------------------------------------------------------------

    def give_boost(self, strength: float, seconds: float) -> bool:
        """Start a boost (extra top speed as a fraction, for seconds).

        Boosts never cut each other short. Each runs down on its own clock and the car goes
        at the strongest one running: a stronger boost takes over at once, and a weaker one
        that outlasts it carries on as a tail once it ends. So a new boost never lowers the
        car's boost at any moment. It is ignored (False) when a running boost is at least
        as strong and lasts at least as long, since it would add nothing."""
        if strength <= 0 or seconds <= 0:
            return False
        if any(s >= strength and t >= seconds for s, t in self._boosts):
            return False
        self._boosts = [[s, t] for s, t in self._boosts if s > strength or t > seconds]
        self._boosts.append([strength, seconds])
        return True

    @property
    def boost(self) -> float:
        """The extra top speed now, as a fraction: the strongest running boost's."""
        return max((s for s, _ in self._boosts), default=0.0)

    @property
    def boost_time(self) -> float:
        """Seconds left at the present strength (a weaker tail may follow)."""
        return max((t for s, t in self._boosts if s == self.boost), default=0.0)

    @property
    def boosts(self) -> tuple[tuple[float, float], ...]:
        """Every running boost, as (strength, seconds left)."""
        return tuple((s, t) for s, t in self._boosts)

    def clear_boosts(self) -> None:
        """Every running boost ends now (a cloud, a MEASURE)."""
        self._boosts = []

    def top_speed(self) -> float:
        """The speed the car accelerates (or coasts) to where it is now."""
        top = TOP * (1 + self.boost) * self.pace
        if self.offroad and not self.tunnelling:
            top *= config.OFFROAD_SPEED_FACTOR
        if self.slow_time > 0:
            top = min(top, self.slow_cap * TOP)
        return top

    # --- Effects ----------------------------------------------------------------------------

    @property
    def drift_level(self) -> int:
        """The drift's charge: 0, then 1 and 2 after DRIFT_LEVELS seconds."""
        if not self.drifting:
            return 0
        return sum(self.drift_time >= t - 1e-9 for t in config.DRIFT_LEVELS)

    @property
    def spinning(self) -> bool:
        return self.spin_time > 0

    @property
    def tunnelling(self) -> bool:
        return self.tunnel_time > 0

    def end_drift(self, turbo: bool = False) -> None:
        """End a drift: with `turbo`, letting go, and its level's mini-turbo if charged."""
        level = self.drift_level
        self.drifting, self.drift_dir, self.drift_time = False, 0, 0.0
        if turbo and level:
            self.give_boost(*config.DRIFT_TURBOS[level - 1])
            self.turbo_level, self.turbo_flash = level, config.TURBO_FLASH
            self.cues.append(("turbo", level))

    def spin(self) -> None:
        """A spin-out: SPIN_SPEED of its speed (a boost's share aside: at most of the top
        speed), and no stick for SPIN_TIME."""
        self.end_drift()
        self.speed = config.SPIN_SPEED * min(self.speed, TOP)
        self.spin_time = config.SPIN_TIME

    def slow(self, cap: float, seconds: float) -> None:
        """Cap its speed at `cap` of the top speed for `seconds`, starting now."""
        self.end_drift()
        self.slow_cap, self.slow_time = cap, seconds
        self.speed = min(self.speed, cap * TOP)

    def tunnel(self, seconds: float) -> None:
        self.tunnel_time = seconds

    # --- Driving ----------------------------------------------------------------------------

    def push(self, curve: float, brake: float = 0.0, drift: bool | None = None) -> float:
        """How fast the curve pushes the car sideways (half-widths a second, negative is
        left): outward, with speed squared; less with a brake held, and less again in a
        drift (`drift` None: whether it is drifting now)."""
        f = self.speed / TOP
        drifting = self.drifting if drift is None else drift
        grip = config.DRIFT_PUSH if drifting else 1 - config.BRAKE_PUSH * brake
        return -config.CURVE_PUSH * f * f * curve * grip

    def steer_rate(self) -> float:
        """How fast full stick moves the car sideways, at its speed now."""
        return config.STEER_RATE * self.speed / TOP

    def update(self, dt: float, steer: float, brake: float, segment, pace: float = 1.0) -> None:
        """Drive for dt seconds on `segment` (the track's segment under the car), at `pace`
        times the top speed."""
        steer = _clamp(steer, -1.0, 1.0)
        brake = _clamp(brake, 0.0, 1.0)
        self.pace = _clamp(pace, *config.PACE_LIMITS)
        self.prev_z, self.prev_x = self.z, self.x
        self.cues = []
        if self.spin_time > 0:  # spinning out: the stick does nothing
            steer = brake = 0.0
        self._tick(dt)
        if self._boosts:
            for b in self._boosts:
                b[1] -= dt
            self._boosts = [b for b in self._boosts if b[1] > 0]
        self._drift(steer, brake)
        self.offroad = abs(self.x) > 1.0
        top = self.top_speed()
        if self.drifting:
            top *= config.DRIFT_SPEED
        if self.speed > top:
            decel = (config.OFFROAD_DECEL if self.offroad and not self.tunnelling
                     else config.COAST_DECEL)
            self.speed = max(top, self.speed - decel * dt)
        if brake > 0 and not self.drifting:
            floor = min(self.speed, config.BRAKE_FLOOR * TOP)
            self.speed = max(floor, self.speed - config.BRAKE * brake * dt)
        elif self.speed < top:
            accel = config.BOOST_ACCEL if self.boost else config.ACCEL
            self.speed = min(top, self.speed + accel * dt)
        if self.drifting and self.drift_dir * segment.curve > config.DRIFT_CHARGE_CURVE:
            self.drift_time += dt  # charging only into a real bend
            level = self.drift_level
            if level and self.drift_time - dt < config.DRIFT_LEVELS[level - 1] - 1e-9:
                self.cues.append(("drift", level))
        aim_angle = config.DRIFT_ANGLE * self.drift_dir
        step = config.DRIFT_ANGLE_RATE * dt
        self.drift_angle = _clamp(aim_angle, self.drift_angle - step, self.drift_angle + step)
        lateral = steer * self.steer_rate() + self.push(segment.curve, brake) + self.knock
        self.x = _clamp(self.x + lateral * dt, -config.X_LIMIT, config.X_LIMIT)
        if self.knock:
            self.knock *= max(0.0, 1 - config.BUMP_KNOCK_DECAY * dt)
            if abs(self.knock) < 0.01:
                self.knock = 0.0
        self.z += self.speed * dt
        self.steer = steer

    def _tick(self, dt: float) -> None:
        """Run the effects' clocks down."""
        self.spin_time = max(0.0, self.spin_time - dt)
        self.slow_time = max(0.0, self.slow_time - dt)
        self.turbo_flash = max(0.0, self.turbo_flash - dt)
        if self.tunnel_time > 0:
            self.tunnel_time = max(0.0, self.tunnel_time - dt)
            if self.tunnel_time < 1e-9:
                self.tunnel_time = 0.0
                self.cues.append(("tunnel_end", None))
        for name in ("spin_time", "slow_time", "turbo_flash"):
            if getattr(self, name) < 1e-9:
                setattr(self, name, 0.0)

    def _drift(self, steer: float, brake: float) -> None:
        """Start, hold or end a drift from the stick (see the top)."""
        want = brake > config.DRIFT_PULL and abs(steer) >= config.DRIFT_STEER
        side = 1 if steer > 0 else -1
        if self.drifting:
            if self.speed < config.DRIFT_END_SPEED * TOP:
                self.end_drift()  # it slowed too much: lost
            elif not want or side != self.drift_dir:
                self.end_drift(turbo=True)  # let go
        if (not self.drifting and want and not self.spinning
                and self.speed >= config.DRIFT_MIN_SPEED * TOP):
            self.drifting, self.drift_dir, self.drift_time = True, side, 0.0


def aim(car: Car, goal_x: float, segment, gain: float = 4.0, brake_at: float = 0.95):
    """(steer, brake) that take a car toward goal_x: it cancels the curve's push and closes
    the gap at `gain` per second. When the push alone (not drifting) needs more than
    `brake_at` of full stick, it brakes too, which takes some of the push away; with the
    stick steered past DRIFT_STEER that brake is a drift, and the car's own drift push is
    what it cancels. For scripted drivers and the AI."""
    rate = car.steer_rate()
    if rate <= 0:
        return 0.0, 0.0
    brake = 1.0 if abs(car.push(segment.curve, drift=False)) > brake_at * rate else 0.0
    want = gain * (goal_x - car.x) - car.push(segment.curve, brake)
    return _clamp(want / rate, -1.0, 1.0), brake


def _wrapped(dz: float, lap: float) -> float:
    """dz brought into [-lap/2, lap/2): cars a lap apart are side by side on the track."""
    return (dz + lap / 2) % lap - lap / 2


def bump(a: Car, b: Car, lap: float) -> str | None:
    """Resolve two cars that overlap. Side by side they are pushed apart and knocked
    sideways; one behind the other, the car behind is put back to touching, slowed and nudged
    to the side it overlaps on, so that it slides past rather than rams the car again.
    Returns "side", "rear" or None when they don't touch."""
    dx = b.x - a.x
    dz = _wrapped(b.z - a.z, lap)
    over_x = config.CAR_WIDTH - abs(dx)
    over_z = config.CAR_LENGTH - abs(dz)
    if over_x <= 0 or over_z <= 0:
        return None
    a.end_drift()  # a bump ends a drift, with no turbo
    b.end_drift()
    if over_x / config.CAR_WIDTH <= over_z / config.CAR_LENGTH:
        sign = 1.0 if dx >= 0 else -1.0  # b goes to the right of a
        a.x = _clamp(a.x - sign * over_x / 2, -config.X_LIMIT, config.X_LIMIT)
        b.x = _clamp(b.x + sign * over_x / 2, -config.X_LIMIT, config.X_LIMIT)
        a.knock = -sign * config.BUMP_KNOCK
        b.knock = sign * config.BUMP_KNOCK
        return "side"
    front, back = (b, a) if dz > 0 else (a, b)
    back.z -= over_z
    back.speed = min(back.speed, config.BUMP_SLOW * front.speed)
    back.knock = config.BUMP_NUDGE if back.x >= front.x else -config.BUMP_NUDGE
    return "rear"
