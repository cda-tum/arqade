"""Short procedurally generated sound effects. No audio assets.

The same little synth as Qurves: every effect is a sine sweep, some with
noise, some with a second step (a two-note chime). sweep_samples is pure and
unit tested. Building pygame Sounds needs a real mixer; without one (no
sound card), every effect is a silent no-op, so a cabinet running unattended
never crashes over audio.

Bots make the same sounds as people for what happens to them (a bump, a
spin-out, a copy), but the red warning, boosts, jumps, being put back in and
taking the lead sound only for people: with eight racers, the bots' would be
noise. The last seconds before anyone wins tick for everyone. There is
deliberately no engine hum: it would grate on a public cabinet.

Drifting is not a one-shot but a loop: a soft slot-car squeal (built with
numpy, drift_loop_samples) on a channel of its own, which fades in while a
person's racer drifts, louder the harder it slides, and fades out when it
stops (drift_target, DriftVoice). Bots' drifts make no sound. The item and
gate pickups are deliberately soft and low (SOFT), and a SWAP makes no sound
at all (SILENT): the gates come by often, and a chirp each time grated.
"""

from __future__ import annotations

import array
import math
import random

import numpy as np
import pygame

from qarrera import config

SAMPLE_RATE = 22050

# name: steps of (start Hz, end Hz, seconds, noise mix 0..1), played in a row
EFFECTS = {
    "beep": ((660, 660, 0.09, 0.0),),
    "go": ((990, 990, 0.25, 0.0),),
    "blip": ((880, 880, 0.05, 0.0),),
    "confirm": ((700, 1400, 0.09, 0.0),),
    "lock": ((660, 660, 0.06, 0.0), (990, 990, 0.12, 0.0)),
    "warn": ((1500, 1500, 0.04, 0.0), (1500, 1500, 0.04, 0.0)),
    "spin": ((600, 90, 0.45, 0.5),),
    "bump": ((170, 90, 0.08, 0.6),),
    "push": ((240, 110, 0.13, 0.5),),
    "copy": ((260, 620, 0.20, 0.0),),
    "copy_lost": ((700, 300, 0.15, 0.2),),
    "decohered": ((900, 250, 0.25, 0.1),),
    "err_armed": ((330, 560, 0.11, 0.0),),
    "launch": ((900, 1700, 0.08, 0.1),),
    "bitflip": ((1700, 400, 0.15, 0.25),),
    "phaseflip": ((320, 120, 0.28, 0.35),),
    "zeno_armed": ((820, 820, 0.07, 0.0),),
    "zeno": ((2400, 2400, 0.08, 0.0), (1800, 1800, 0.25, 0.0)),
    "boost": ((300, 1400, 0.22, 0.25),),
    "jump": ((500, 1100, 0.12, 0.1),),
    "land": ((160, 70, 0.10, 0.6),),
    "reset": ((200, 1200, 0.22, 0.3),),
    "lead": ((784, 784, 0.07, 0.0), (1175, 1175, 0.12, 0.0)),
    "tick": ((1400, 1400, 0.03, 0.0),),
    "match_won": ((523, 523, 0.10, 0.0), (659, 659, 0.10, 0.0), (784, 784, 0.10, 0.0), (1046, 1046, 0.35, 0.0)),
}
VOLUME = {"warn": 0.35, "bump": 0.5, "zeno_armed": 0.2, "err_armed": 0.25, "copy": 0.45, "land": 0.5,
          "jump": 0.6, "lead": 0.6, "tick": 0.5}
PEOPLE_ONLY = {"warn", "boost", "jump", "land", "reset", "lead"}
# picking up an item or a gate: lower, quieter and with a slow, rounded
# attack and release, so the many pickups in a race stay in the background
SOFT = {"copy", "err_armed", "zeno_armed"}
# cues with no one-shot sound: a SWAP is silent on purpose, and drifting is
# the drift loop (Sounds.update_drift)
SILENT = {"swap", "drift"}
_ALIASES = {"pause": "beep"}

# The drift squeal: a loop of DRIFT_LOOP seconds, faded in over DRIFT_IN and
# out over DRIFT_OUT. At the drift limit it plays at DRIFT_QUIET of its
# level, rising to the full DRIFT_VOLUME at the red (config.WARN_LOAD).
DRIFT_LOOP = 1.0
DRIFT_VOLUME = 0.15
DRIFT_QUIET = 0.4
DRIFT_IN = 0.12
DRIFT_OUT = 0.25


def sweep_samples(
    f0: float, f1: float, duration: float, sample_rate: int, volume: float,
    noise: float = 0.0, seed: int = 1, soft: bool = False,
) -> list[int]:
    """Mono 16-bit samples: a sine sweeping linearly from f0 to f1, mixed with
    some white noise, faded in and out (no clicks) and decaying a little.
    Soft: the fades are long (a third of it each) and rounded, so it swells
    and dies away instead of starting with a tick."""
    n = max(1, round(sample_rate * duration))
    amplitude = round(max(0.0, min(1.0, volume)) * 32767)
    fade = max(1, n // 3 if soft else min(200, n // 4))
    rng = random.Random(seed)
    phase = 0.0
    out = []
    for i in range(n):
        phase += 2 * math.pi * (f0 + (f1 - f0) * i / n) / sample_rate
        value = (1 - noise) * math.sin(phase) + noise * rng.uniform(-1.0, 1.0)
        edge = min(1.0, min(i, n - 1 - i) / fade)
        if soft:
            edge = math.sin(edge * math.pi / 2) ** 2
        envelope = edge * (1 - 0.6 * i / n)
        out.append(round(amplitude * envelope * value))
    return out


def effect_samples(name: str, sample_rate: int, volume: float = 0.45) -> list[int]:
    out: list[int] = []
    for f0, f1, duration, noise in EFFECTS[name]:
        out += sweep_samples(f0, f1, duration, sample_rate, volume * VOLUME.get(name, 1.0), noise,
                             soft=name in SOFT)
    return out


def drift_loop_samples(sample_rate: int, volume: float = DRIFT_VOLUME) -> np.ndarray:
    """One seamless loop of the drift squeal, mono int16: a slot car's tyres
    chirping on the track. A thin tone around 1.3 kHz that warbles (two slow
    wobbles in its pitch), chatters (a fast flutter in its level) and sits in
    a little band-passed hiss. Every rate is a whole number of cycles per
    loop and the hiss is shaped round the loop (FFT), so it repeats without
    a seam. Its peak is `volume` of full scale."""
    n = round(sample_rate * DRIFT_LOOP)
    t = np.arange(n) / sample_rate
    # pitch: 1300 Hz, wobbling +-70 Hz at 3 Hz and +-25 Hz at 11 Hz
    phase = 2 * np.pi * 1300 * t + 70 / 3 * np.sin(2 * np.pi * 3 * t) + 25 / 11 * np.sin(2 * np.pi * 11 * t + 1.0)
    tone = np.sin(phase) + 0.25 * np.sin(2 * phase + 0.5)
    chatter = 0.75 + 0.25 * np.sin(2 * np.pi * 31 * t) * np.sin(2 * np.pi * 4 * t + 0.3)
    rng = np.random.default_rng(7)
    spectrum = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / sample_rate)
    spectrum *= np.exp(-(((f - 1600) / 500) ** 2))  # a band around 1.6 kHz, nothing bright
    hiss = np.fft.irfft(spectrum, n)
    hiss /= max(1e-9, np.abs(hiss).max())
    wave = tone * chatter + 0.35 * hiss
    wave *= volume / np.abs(wave).max()
    return np.round(wave * 32767).astype(np.int16)


def drift_target(race, people) -> float:
    """How loud the drift squeal should be (0..1): the hardest drift among the
    people's racers on the ground, from DRIFT_QUIET at the drift limit to 1
    at the red. Bots' drifts don't count."""
    worst = 0.0
    for b in race.bodies:
        if b.player not in people or b.air or b.spin > 0 or b.load <= config.DRIFT_LOAD:
            continue
        over = (b.load - config.DRIFT_LOAD) / (config.WARN_LOAD - config.DRIFT_LOAD)
        worst = max(worst, DRIFT_QUIET + (1 - DRIFT_QUIET) * min(1.0, over))
    return worst


class DriftVoice:
    """The drift loop's level, following drift_target: up over DRIFT_IN, down
    over DRIFT_OUT, so it swells in and dies away rather than switching."""

    def __init__(self) -> None:
        self.level = 0.0

    def step(self, target: float, dt: float) -> float:
        if target > self.level:
            self.level = min(target, self.level + dt / DRIFT_IN)
        else:
            self.level = max(target, self.level - dt / DRIFT_OUT)
        return self.level


def event_sounds(events: list, people: tuple[str, ...] | set[str]) -> list[str]:
    """The sounds a frame's events ask for, each at most once."""
    names = []
    for e in events:
        name = _ALIASES.get(e.kind, e.kind)
        if name not in EFFECTS:
            continue
        if name in PEOPLE_ONLY and e.player not in people:
            continue
        names.append(name)
    return list(dict.fromkeys(names))


class Sounds:
    def __init__(self, sounds: dict, drift: pygame.mixer.Sound | None = None,
                 drift_channel: pygame.mixer.Channel | None = None) -> None:
        self._sounds = sounds
        self._drift = drift
        self._drift_channel = drift_channel
        self.drift = DriftVoice()

    def play_events(self, events: list, people: tuple[str, ...] | set[str] = ()) -> None:
        for name in event_sounds(events, people):
            effect = self._sounds.get(name)
            if effect is not None:
                effect.play()

    def update_drift(self, race, people: tuple[str, ...] | set[str], dt: float) -> None:
        """Once a frame: the drift loop follows the people's drifting. race is
        None whenever nothing is racing (paused, a menu), and it fades out."""
        level = self.drift.step(drift_target(race, people) if race is not None else 0.0, dt)
        channel = self._drift_channel
        if channel is None or self._drift is None:
            return
        if level <= 0.0:
            if channel.get_busy():
                channel.stop()
            return
        channel.set_volume(level)
        if not channel.get_busy():
            channel.play(self._drift, loops=-1)
            channel.set_volume(level)


def _make_sound(samples: list[int], channels: int) -> pygame.mixer.Sound:
    buf = array.array("h")
    for value in samples:
        for _ in range(channels):
            buf.append(value)
    return pygame.mixer.Sound(buffer=buf.tobytes())


def load_sounds() -> Sounds:
    """Init the mixer and build every effect for whatever it negotiated, or
    fall back to silence if there is no audio at all."""
    try:
        pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2)
        init_info = pygame.mixer.get_init()
        if not init_info:
            raise pygame.error("mixer did not initialize")
        freq, _format, channels = init_info
        pygame.mixer.set_num_channels(16)
        pygame.mixer.set_reserved(1)  # channel 0 is the drift loop's: effects never take it
        drift = _make_sound(drift_loop_samples(freq).tolist(), max(1, channels))
        return Sounds({name: _make_sound(effect_samples(name, freq), max(1, channels)) for name in EFFECTS},
                      drift, pygame.mixer.Channel(0))
    except (pygame.error, ValueError):
        return Sounds({})
