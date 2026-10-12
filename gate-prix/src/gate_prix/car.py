"""One racer's driving: speed, lateral position, curves, off-road, boosts and bumps.

Pure Python, no pygame. `z` is the race distance from the start line in world units (it
keeps growing lap after lap, as the renderer's objects and the gate rows do), and `x` is
lateral in road half-widths: -1 to 1 is the road, beyond it the copper plate.

The handling is OutRun's: the car auto-accelerates to its top speed, the stick moves it
sideways at a rate proportional to speed, and a curve pushes it outward in proportion to
speed squared times the curve. Holding the brake through a curve drifts: it takes some of
the push away, on top of the speed it sheds.
"""

from __future__ import annotations

from typing import NamedTuple

from gate_prix import config

TOP = config.TOP_SPEED


class Controls(NamedTuple):
    """One car's input for a frame: steer -1 (left) to 1 (right), brake 0 to 1."""

    steer: float = 0.0
    brake: float = 0.0
    item: bool = False  # use the held item (Task 4)


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
        self.drifting = False  # braking through a curve
        self.offroad = False
        self.knock = 0.0  # lateral speed left from a side bump, half-widths a second
        self.prev_z = 0.0  # where the last update started, to find where it crossed a row
        self.prev_x = lane_x

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

    def top_speed(self) -> float:
        """The speed the car accelerates (or coasts) to where it is now."""
        top = TOP * (1 + self.boost)
        return top * config.OFFROAD_SPEED_FACTOR if self.offroad else top

    # --- Driving ----------------------------------------------------------------------------

    def push(self, curve: float, brake: float = 0.0) -> float:
        """How fast the curve pushes the car sideways (half-widths a second, negative is
        left): outward, with speed squared, less when a brake is held (the drift)."""
        f = self.speed / TOP
        return -config.CURVE_PUSH * f * f * curve * (1 - config.DRIFT * brake)

    def steer_rate(self) -> float:
        """How fast full stick moves the car sideways, at its speed now."""
        return config.STEER_RATE * self.speed / TOP

    def update(self, dt: float, steer: float, brake: float, segment) -> None:
        """Drive for dt seconds on `segment` (the track's segment under the car)."""
        steer = _clamp(steer, -1.0, 1.0)
        brake = _clamp(brake, 0.0, 1.0)
        self.prev_z, self.prev_x = self.z, self.x
        if self._boosts:
            for b in self._boosts:
                b[1] -= dt
            self._boosts = [b for b in self._boosts if b[1] > 0]
        self.offroad = abs(self.x) > 1.0
        top = self.top_speed()
        if self.speed > top:
            decel = config.OFFROAD_DECEL if self.offroad else config.COAST_DECEL
            self.speed = max(top, self.speed - decel * dt)
        if brake > 0:
            floor = min(self.speed, config.BRAKE_FLOOR * TOP)
            self.speed = max(floor, self.speed - config.BRAKE * brake * dt)
        elif self.speed < top:
            accel = config.BOOST_ACCEL if self.boost else config.ACCEL
            self.speed = min(top, self.speed + accel * dt)
        self.drifting = brake > 0 and segment.curve != 0
        lateral = steer * self.steer_rate() + self.push(segment.curve, brake) + self.knock
        self.x = _clamp(self.x + lateral * dt, -config.X_LIMIT, config.X_LIMIT)
        if self.knock:
            self.knock *= max(0.0, 1 - config.BUMP_KNOCK_DECAY * dt)
            if abs(self.knock) < 0.01:
                self.knock = 0.0
        self.z += self.speed * dt
        self.steer = steer


def aim(car: Car, goal_x: float, segment, gain: float = 4.0, brake_at: float = 0.95):
    """(steer, brake) that take a car toward goal_x: it cancels the curve's push and closes
    the gap at `gain` per second. When the push alone needs more than `brake_at` of full
    stick, it brakes too (and the drift takes some of the push away). For scripted drivers
    and the CPU racers."""
    rate = car.steer_rate()
    if rate <= 0:
        return 0.0, 0.0
    brake = 1.0 if abs(car.push(segment.curve)) > brake_at * rate else 0.0
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
