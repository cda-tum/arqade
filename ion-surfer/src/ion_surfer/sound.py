"""Short synthesized sound effects, built in code at start-up. No audio files,
no numpy.

The game is a surf poster, so the sounds are surf guitar: plucked strings
(Karplus-Strong) in E minor pentatonic through a spring-reverb-like echo,
tremolo-picked for the fanfare. The lab gear in the sandbox (laser kick,
cooling) gets plain sine sweeps instead. There is deliberately no sound for
holding a voltage: it would drone for the whole match.

Landing on the wave is as loud as the landing is hard (`impact_gain`), and
the laser beams and stray ions on screen make a quiet ambience of their own,
panned to where they are (`Ambience`).

The sample builders are pure and unit tested. Building pygame Sounds needs a
real mixer; without one (no sound card, a broken driver) every effect is a
silent no-op, so the cabinet never crashes over audio.
"""

from __future__ import annotations

import array
import math
import random

import pygame

SAMPLE_RATE = 22050

NOTES = {"E3": 164.81, "A3": 220.0, "B3": 246.94, "D4": 293.66, "E4": 329.63, "G4": 392.0,
         "A4": 440.0, "B4": 493.88, "D5": 587.33, "E5": 659.26, "G5": 783.99, "B5": 987.77}


def pluck(freq: float, duration: float, sr: int, seed: int = 1, decay: float = 0.996) -> list[float]:
    """A plucked string (Karplus-Strong): a burst of noise in a delay line one
    period long, averaged as it goes round, so it rings at freq and dies away."""
    period = max(2, round(sr / freq))
    rng = random.Random(seed)
    line = [rng.uniform(-1.0, 1.0) for _ in range(period)]
    out = []
    prev = 0.0
    for i in range(max(1, round(sr * duration))):
        k = i % period
        cur = line[k]
        line[k] = decay * 0.5 * (cur + prev)
        prev = cur
        out.append(cur)
    return out


def sweep(f0: float, f1: float, duration: float, sr: int, noise: float = 0.0,
          seed: int = 1) -> list[float]:
    """A sine sweeping linearly from f0 to f1, mixed with some white noise and
    decaying a little."""
    n = max(1, round(sr * duration))
    rng = random.Random(seed)
    phase = 0.0
    out = []
    for i in range(n):
        phase += 2 * math.pi * (f0 + (f1 - f0) * i / n) / sr
        value = (1 - noise) * math.sin(phase) + noise * rng.uniform(-1.0, 1.0)
        out.append(value * (1 - 0.6 * i / n))
    return out


def riff(notes: list[str], step: float, sr: int, ring: float = 0.35) -> list[float]:
    """Plucked notes, one every `step` seconds, each left to ring for `ring`
    seconds over the next. A repeated note is surf tremolo picking."""
    start = round(step * sr)
    out = [0.0] * (start * (len(notes) - 1) + round(ring * sr))
    for i, name in enumerate(notes):
        for j, v in enumerate(pluck(NOTES[name], ring, sr, seed=i + 1)):
            out[i * start + j] += v
    return out


def echo(samples: list[float], sr: int, delay: float = 0.09, feedback: float = 0.35,
         taps: int = 3) -> list[float]:
    """The spring reverb, roughly: a few fading repeats close behind."""
    d = round(delay * sr)
    out = samples + [0.0] * (d * taps)
    for t in range(1, taps + 1):
        g = feedback ** t
        for i, v in enumerate(samples):
            out[i + t * d] += g * v
    return out


def blip(f0: float, f1: float, duration: float, sr: int, tau: float = 0.025) -> list[float]:
    """A soft sine ping gliding from f0 to f1 and dying away with time
    constant tau, with a quiet octave on top."""
    n = max(1, round(sr * duration))
    phase = 0.0
    out = []
    for i in range(n):
        phase += 2 * math.pi * (f0 + (f1 - f0) * i / n) / sr
        out.append((math.sin(phase) + 0.25 * math.sin(2 * phase)) * math.exp(-i / sr / tau))
    return out


def shimmer(partials: list[tuple[float, float]], duration: float, sr: int,
            breaths: int = 1, depth: float = 0.4) -> list[float]:
    """A seamless loop of `duration` seconds: sines (freq, amplitude), each
    rounded to a whole number of cycles in the loop so the end runs into the
    start, swelling and fading `breaths` times per loop. Two partials a
    cycle or two apart beat slowly, which is the shimmer. A table lookup
    instead of math.sin keeps it quick to build on the Pi."""
    n = max(1, round(sr * duration))
    table = [math.sin(2 * math.pi * j / n) for j in range(n)]
    out = [0.0] * n
    for f, a in partials:
        c = max(1, round(f * duration))
        out = [v + a * table[c * i % n] for i, v in enumerate(out)]
    q = n // 4
    return [v * (1 - depth * 0.5 * (1 + table[(breaths * i + q) % n])) for i, v in enumerate(out)]


def to_pcm(samples: list[float], volume: float, fade: bool = True) -> list[int]:
    """16-bit samples, the peak scaled to `volume` and the ends faded, so
    nothing clicks. A seamless loop (fade=False) keeps its ends."""
    n = len(samples)
    peak = max((abs(v) for v in samples), default=0.0) or 1.0
    gain = max(0.0, min(1.0, volume)) * 32767 / peak
    if not fade:
        return [round(v * gain) for v in samples]
    ramp = max(1, min(120, n // 4))
    return [round(v * gain * min(1.0, i / ramp, (n - 1 - i) / ramp)) for i, v in enumerate(samples)]


# ------------------------------ landing on the wave ------------------------------
# The game passes the ion's speed into the wave (the normal component of its
# velocity relative to the surface, px/s) whenever it lands. For scale: G
# pulls at 1300 px/s^2, so a drop of 15 px lands at ~200, 60 px at ~400 and a
# throw from the top of the screen at well over 1000.
IMPACT_MIN = 200.0     # slower than this is rolling, not landing: silent
IMPACT_FULL = 1100.0   # this hard or harder is full volume (the cap)
IMPACT_FLOOR = 0.06    # volume at IMPACT_MIN, of the full one: about -24 dB
IMPACT_CURVE = 1.5     # >1 keeps everyday landings well down
IMPACT_PEAK = 0.34     # peak of a full-volume landing (it was a fixed 0.28)
IMPACT_GAP_MS = 150    # shortest gap between two landing sounds ...
IMPACT_LOUDER = 1.6    # ... unless the new one is this many times louder


def impact_strength(speed: float) -> float:
    """0 at IMPACT_MIN, 1 at IMPACT_FULL and above."""
    return max(0.0, min(1.0, (speed - IMPACT_MIN) / (IMPACT_FULL - IMPACT_MIN)))


def impact_gain(speed: float) -> float:
    """Volume (0..1, of the loudest) of a landing at `speed`: nothing below
    IMPACT_MIN, a faint IMPACT_FLOOR just above it, rising as the strength
    to the power IMPACT_CURVE to 1 at IMPACT_FULL, and capped there."""
    if speed < IMPACT_MIN:
        return 0.0
    return IMPACT_FLOOR + (1 - IMPACT_FLOOR) * impact_strength(speed) ** IMPACT_CURVE


def impact_effect(speed: float) -> str:
    """Which landing sound: duller for soft ones, brighter for hard ones."""
    u = impact_strength(speed)
    return "bounce_soft" if u < 0.3 else "bounce" if u < 0.65 else "bounce_hard"


# name: (builder(sample_rate) -> float samples, volume)
EFFECTS = {
    # menus
    "move": (lambda sr: pluck(NOTES["E5"], 0.12, sr), 0.22),
    "confirm": (lambda sr: echo(riff(["B4", "E5"], 0.06, sr, 0.25), sr), 0.32),
    "back": (lambda sr: riff(["E5", "B4"], 0.06, sr, 0.22), 0.28),
    "pause": (lambda sr: echo(pluck(NOTES["B4"], 0.2, sr), sr), 0.3),
    "start": (lambda sr: echo(riff(["E4", "E4", "E4", "G4", "B4", "E5"], 0.055, sr, 0.3), sr), 0.4),
    # surfing
    "electrode": (lambda sr: sweep(1500, 1500, 0.025, sr), 0.1),
    "photon": (lambda sr: echo(sweep(1300, 2600, 0.08, sr), sr, 0.06, 0.4), 0.3),
    # landing on the wave, softest to hardest: see impact_gain. Each is built
    # at the loudest a landing can be and turned down as it plays. Harder is
    # also brighter and starts higher.
    "bounce_soft": (lambda sr: sweep(190, 60, 0.10, sr, noise=0.3), IMPACT_PEAK),
    "bounce": (lambda sr: sweep(260, 70, 0.12, sr, noise=0.6), IMPACT_PEAK),
    "bounce_hard": (lambda sr: sweep(340, 55, 0.14, sr, noise=0.75), IMPACT_PEAK),
    "lost": (lambda sr: echo(sweep(700, 110, 0.45, sr, noise=0.25), sr, 0.12, 0.3, 2), 0.42),
    "over": (lambda sr: echo(riff(["E4", "D4", "B3", "A3", "E3"], 0.14, sr, 0.5), sr, 0.12), 0.42),
    "win": (lambda sr: echo(riff(["E4", "E4", "E4", "G4", "A4", "B4", "B4", "D5", "E5", "E5"],
                                 0.07, sr, 0.4), sr, 0.11), 0.42),
    # sandbox
    "kick": (lambda sr: sweep(250, 1800, 0.12, sr, noise=0.1), 0.32),
    "ion_add": (lambda sr: riff(["A4", "E5"], 0.05, sr, 0.2), 0.3),
    "ion_remove": (lambda sr: riff(["E5", "A4"], 0.05, sr, 0.2), 0.3),
    "cool": (lambda sr: sweep(1800, 300, 0.35, sr), 0.2),
    "toggle_on": (lambda sr: riff(["E5", "B5"], 0.05, sr, 0.18), 0.26),
    "toggle_off": (lambda sr: riff(["B5", "E5"], 0.05, sr, 0.18), 0.26),
    "warn": (lambda sr: sweep(190, 170, 0.09, sr, noise=0.3) + [0.0] * round(0.05 * sr)
             + sweep(190, 170, 0.09, sr, noise=0.3), 0.26),
}

# Shortest gap (ms) between two plays of one effect. (Landings have their
# own rule, IMPACT_GAP_MS.)
MIN_GAP_MS = {"electrode": 40}


# ------------------------------ ambience ------------------------------
# Laser beams hum and stray ions blip, quietly, from where they are on
# screen. They are background: their peaks stay well under every effect's,
# they swell in and out slowly, and a beam's hum breathes rather than drones.
# name: (builder(sample_rate) -> float samples, peak at full proximity)
AMBIENT_SOUNDS = {
    # a beam pushing up: a high airy shimmer (two partials beating at 2 Hz)
    "beam_up": (lambda sr: shimmer([(1318.0, 1.0), (1320.0, 0.8), (1976.0, 0.18)], 2.0, sr, 1), 0.05),
    # a beam pushing down: the same a fifth lower, beating at 1.5 Hz
    "beam_down": (lambda sr: shimmer([(880.0, 1.0), (881.5, 0.8), (1318.0, 0.2)], 2.0, sr, 1), 0.05),
    # a stray ion: a soft sonar ping
    "stray": (lambda sr: blip(1568.0, 1397.0, 0.09, sr), 0.07),
}
AMBIENT_LOOPS = ("beam_up", "beam_down")    # one reserved channel each, looping
AMBIENT_TICKS = ("stray",)                  # one reserved channel, a ping now and then
AMBIENT_BASE = 0.3      # level of a far source, of the level right next to it
AMBIENT_WIDTH = 0.8     # how far the screen edges pan (1 would be one speaker only)
AMBIENT_MARGIN = 80     # px off the screen edge over which a source fades out
AMBIENT_ATTACK = 0.8    # s for a hum to swell from silence to full ...
AMBIENT_RELEASE = 0.5   # ... and to die away again
STRAY_EVERY = (1.3, 0.55)   # s between a stray's pings: far away, right next to an ion
TOTAL_CHANNELS = 12     # mixer channels: the ambience reserves the first three


def nearness(distance: float, reach: float) -> float:
    """1 right at the source, 0 at `reach` and beyond, rising gently: the
    square, so a source perks up only once it is close."""
    return max(0.0, 1.0 - distance / reach) ** 2


def pan(x: float, width: float) -> float:
    """-AMBIENT_WIDTH at the screen's left edge, 0 in the middle,
    AMBIENT_WIDTH at its right edge (and no further off screen)."""
    return AMBIENT_WIDTH * max(-1.0, min(1.0, 2 * x / width - 1))


def stereo(p: float) -> tuple[float, float]:
    """Equal-power panning: (left, right) gains for a pan of -1 (left) .. 1
    (right). Their squares always add up to 1, so a sound moving across
    keeps its loudness."""
    a = (max(-1.0, min(1.0, p)) + 1) * math.pi / 4
    return math.cos(a), math.sin(a)


def presence(x: float, width: float) -> float:
    """1 on screen, fading to 0 within AMBIENT_MARGIN px off either edge."""
    m = AMBIENT_MARGIN
    return max(0.0, min(1.0, (x + m) / m, (width + m - x) / m))


def ambient_level(near: float) -> float:
    """Volume (0..1, of the source's peak) at nearness `near`."""
    return AMBIENT_BASE + (1 - AMBIENT_BASE) * max(0.0, min(1.0, near))


def loop_targets(sources, width: float) -> dict[str, tuple[float, float]]:
    """The (left, right) volume each looping hum should have for these
    sources: the power sum over every source of that kind, so two beams are
    a little louder than one, but never more than full."""
    acc = {name: [0.0, 0.0] for name in AMBIENT_LOOPS}
    for kind, _key, x, near in sources:
        if kind not in acc:
            continue
        g = ambient_level(near) * presence(x, width)
        left, right = stereo(pan(x, width))
        acc[kind][0] += (g * left) ** 2
        acc[kind][1] += (g * right) ** 2
    return {k: (min(1.0, math.sqrt(l2)), min(1.0, math.sqrt(r2))) for k, (l2, r2) in acc.items()}


def slew(current: float, target: float, dt: float) -> float:
    """Move a volume towards its target no faster than the attack/release
    allow, so nothing ever pops in or out."""
    if target > current:
        return min(target, current + dt / AMBIENT_ATTACK)
    return max(target, current - dt / AMBIENT_RELEASE)


class Ambience:
    """The beams' hums and the strays' pings, on mixer channels of their own
    (reserved, so the effects never land on them and inherit a pan).

    update() takes every source on screen as (kind, key, screen x, nearness
    to the closest ion) once a frame; an empty list fades everything out.
    A hum only plays while it is audible: it starts when its first beam
    comes in and stops once the last has faded away."""

    def __init__(self, sounds: dict, channels: dict, width: float) -> None:
        self._sounds = sounds        # kind -> Sound
        self._channels = channels    # kind -> Channel
        self.width = width
        self.level = {name: [0.0, 0.0] for name in AMBIENT_LOOPS}
        self._playing = {name: False for name in AMBIENT_LOOPS}
        self._timers: dict = {}      # a stray's key -> seconds to its next ping

    def update(self, sources, dt: float) -> None:
        targets = loop_targets(sources, self.width)
        for name in AMBIENT_LOOPS:
            ch, snd = self._channels.get(name), self._sounds.get(name)
            if ch is None or snd is None:
                continue
            lv = self.level[name]
            tl, tr = targets[name]
            lv[0], lv[1] = slew(lv[0], tl, dt), slew(lv[1], tr, dt)
            if lv[0] > 0 or lv[1] > 0:
                if not self._playing[name]:
                    ch.set_volume(0.0, 0.0)
                    ch.play(snd, loops=-1)
                    self._playing[name] = True
                ch.set_volume(lv[0], lv[1])
            elif self._playing[name]:
                ch.stop()
                self._playing[name] = False

        timers = {}
        for kind, key, x, near in sources:
            if kind not in AMBIENT_TICKS:
                continue
            far, close = STRAY_EVERY
            every = far + (close - far) * max(0.0, min(1.0, near))
            left = self._timers.get(key, 0.5 * every) - dt
            if left <= 0:
                self._ping(kind, x, near)
                left = every
            timers[key] = left
        self._timers = timers

    def _ping(self, kind: str, x: float, near: float) -> None:
        ch, snd = self._channels.get(kind), self._sounds.get(kind)
        g = ambient_level(near) * presence(x, self.width)
        if ch is None or snd is None or g <= 0:
            return
        left, right = stereo(pan(x, self.width))
        ch.play(snd)
        ch.set_volume(g * left, g * right)


class Sounds:
    """Plays effects by name. Built empty, it is silent (no mixer, tests)."""

    def __init__(self, sounds: dict | None = None, ambience: Ambience | None = None) -> None:
        self._sounds = sounds or {}
        self._last: dict[str, int] = {}
        self._ambience = ambience
        self._impact_at = -IMPACT_GAP_MS
        self._impact_gain = 0.0

    def play(self, name: str) -> None:
        effect = self._sounds.get(name)
        if effect is None:
            return
        gap = MIN_GAP_MS.get(name)
        if gap:
            now = pygame.time.get_ticks()
            if now - self._last.get(name, -gap) < gap:
                return
            self._last[name] = now
        effect.play()

    def impact(self, speed: float) -> None:
        """The ion landing on the wave at `speed` px/s into it. A soft roll
        is silent; within IMPACT_GAP_MS of the last landing only a much
        harder one sounds, so a ball rattling along a bumpy curve, or a
        curve pushed up under it, doesn't machine-gun."""
        gain = impact_gain(speed)
        if gain <= 0:
            return
        now = pygame.time.get_ticks()
        if now - self._impact_at < IMPACT_GAP_MS and gain < IMPACT_LOUDER * self._impact_gain:
            return
        effect = self._sounds.get(impact_effect(speed))
        if effect is None:
            return
        self._impact_at, self._impact_gain = now, gain
        # On the Sound, not its channel: the attract capture logs a play
        # with the Sound's own volume.
        effect.set_volume(gain)
        effect.play()

    def ambient(self, sources, dt: float) -> None:
        """See Ambience.update. Silent without a mixer."""
        if self._ambience is not None:
            self._ambience.update(sources, dt)


def pre_init() -> None:
    """Ask for the rate the effects are built at, before pygame.init() opens
    the mixer with its own defaults. A small buffer keeps them snappy."""
    pygame.mixer.pre_init(SAMPLE_RATE, -16, 2, 512)


def _make_sound(samples: list[int], channels: int) -> pygame.mixer.Sound:
    buf = array.array("h")
    for value in samples:
        buf.extend([value] * channels)
    # Looked up at call time, not imported: the attract capture swaps
    # pygame.mixer.Sound for a subclass that logs every play.
    return pygame.mixer.Sound(buffer=buf.tobytes())


def load_sounds(width: float = 1200) -> Sounds:
    """Build every effect for whatever the mixer negotiated, or fall back to
    silence if there is no audio at all. `width` is the screen's, for
    panning the ambience."""
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(SAMPLE_RATE, -16, 2, 512)
        init_info = pygame.mixer.get_init()
        if not init_info:
            raise pygame.error("mixer did not initialize")
        freq, size, channels = init_info
        if abs(size) != 16:
            raise pygame.error(f"{size}-bit mixer")
        effects = {
            name: _make_sound(to_pcm(build(freq), volume), max(1, channels))
            for name, (build, volume) in EFFECTS.items()
        }
    except (pygame.error, ValueError):
        return Sounds()
    return Sounds(effects, _load_ambience(freq, max(1, channels), width))


def _load_ambience(freq: int, channels: int, width: float) -> Ambience | None:
    """The ambience's sounds and its three reserved channels. If that fails
    the effects still play, just without the ambience."""
    try:
        kinds = AMBIENT_LOOPS + AMBIENT_TICKS
        pygame.mixer.set_num_channels(max(TOTAL_CHANNELS, pygame.mixer.get_num_channels()))
        if pygame.mixer.set_reserved(len(kinds)) < len(kinds):
            return None
        sounds = {
            name: _make_sound(to_pcm(build(freq), peak, fade=name not in AMBIENT_LOOPS), channels)
            for name, (build, peak) in AMBIENT_SOUNDS.items()
        }
        return Ambience(sounds, {k: pygame.mixer.Channel(i) for i, k in enumerate(kinds)}, width)
    except (pygame.error, ValueError):
        return None
