"""Synthesised sound effects: no audio files, no numpy.

The engine hums at a pitch that follows the car's speed (one looping sound per speed
step, switched as the car speeds up or slows down); a right gate rings higher the longer
the streak, with a boost whoosh on top; a wrong or missed one buzzes; the CIRCUIT CHECK
plays a fanfare (a bigger one for a perfect circuit) as the view freezes, and the LIGHT
SPEED! warp after it is a long rising whoosh; the countdown beeps, items and boxes chime and cars
thud when they bump. Each item has its own sound as it is used; a MEASURE that lands zaps
its victim and rings for its shooter, and a DECOHERENCE cloud crackles for whoever drives
through it and chimes for its dropper; a mine spins you out with a falling whine.

Everything is rendered in a background thread at start-up (a second or two on the Pi), so
the game starts at once and a sound not ready yet is simply skipped. If the mixer can't
start (no sound card) the whole thing is a silent no-op: the cabinet never crashes over
audio. The tone helpers are adapted from Gate Drop's audio.py (same repo).
"""

from __future__ import annotations

import array
import math
import random
import threading

import pygame

from gate_prix import config
from gate_prix.match import Cue
from gate_prix.race import Event

SAMPLE_RATE = 22050
AMP = 32767
ENGINE_STEPS = 12  # looping engine sounds, from standing to the biggest boost
ENGINE_TOP = 2.0  # the speed (in top speeds) of the highest step: the biggest boost
ENGINE_VOLUME = 0.35

NOTE_INDEX = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8,
              "A": 9, "A#": 10, "B": 11}


def note(name: str) -> float:
    """'A4' -> 440.0."""
    pitch, octave = name[:-1], int(name[-1])
    n = NOTE_INDEX[pitch] + 12 * (octave + 1)
    return 440.0 * 2 ** ((n - 69) / 12)


def _wave(kind: str, phase: float) -> float:
    p = phase % 1.0
    if kind == "square":
        return 1.0 if p < 0.5 else -1.0
    if kind == "pulse":
        return 1.0 if p < 0.25 else -1.0
    if kind == "triangle":
        return 4 * p - 1 if p < 0.5 else 3 - 4 * p
    if kind == "saw":
        return 2 * p - 1
    return math.sin(2 * math.pi * p)


def tone(freq: float, dur: float, vol: float, kind: str = "square", decay: float = 0.0,
         slide: float = 0.0, sr: int = SAMPLE_RATE) -> list[int]:
    """A note with an optional exponential decay (1/s) and a pitch slide (the frequency
    multiplier reached by the end)."""
    n = max(1, int(sr * dur))
    out = []
    phase = 0.0
    fade = max(1, min(160, n // 6))
    for i in range(n):
        f = freq * (1 + (slide - 1) * i / n) if slide else freq
        phase += f / sr
        env = math.exp(-decay * i / sr) if decay else 1.0
        edge = min(1.0, i / fade, (n - 1 - i) / fade)
        out.append(int(AMP * vol * env * edge * _wave(kind, phase)))
    return out


def noise(dur: float, vol: float, decay: float = 0.0, hold: int = 1, seed: int = 1,
          swell: bool = False, sr: int = SAMPLE_RATE) -> list[int]:
    """White-ish noise; `hold` repeats each value (higher is darker). `swell` fades it in
    over its first half, for a whoosh."""
    rng = random.Random(seed)
    n = max(1, int(sr * dur))
    out = []
    v = 0.0
    for i in range(n):
        if i % hold == 0:
            v = rng.uniform(-1, 1)
        env = math.exp(-decay * i / sr) if decay else 1.0
        if swell:
            env *= min(1.0, 2 * i / n)
        out.append(int(AMP * vol * env * min(1.0, (n - 1 - i) / 80) * v))
    return out


def concat(*parts: list[int]) -> list[int]:
    out: list[int] = []
    for p in parts:
        out.extend(p)
    return out


def mix(*tracks: list[int]) -> list[int]:
    n = max(len(t) for t in tracks)
    out = [0] * n
    for t in tracks:
        for i, v in enumerate(t):
            out[i] += v
    return [max(-AMP, min(AMP, v)) for v in out]


def _arp(names, dur, vol, kind="square", decay=6.0):
    return concat(*(tone(note(n), dur, vol, kind, decay=decay) for n in names))


RIGHT_NOTES = ("C5", "D5", "E5", "G5", "A5", "C6")  # the streak climbs a pentatonic scale


def warp_sound() -> list[int]:
    """LIGHT SPEED!: a rising whoosh (noise, darker to brighter) over a climbing tone."""
    parts = [noise(0.25, 0.10 + 0.04 * i, hold=max(1, 4 - i), seed=20 + i, swell=i == 0)
             for i in range(4)]
    rush = concat(*parts) + noise(0.6, 0.22, decay=4, seed=24)
    climb = tone(110, 1.0, 0.16, "saw", slide=4.0) + tone(440, 0.6, 0.12, "saw", decay=5)
    return mix(rush, climb)


def build_sfx() -> dict[str, list[int]]:
    whoosh = noise(0.45, 0.3, hold=1, seed=7, swell=True)
    sfx = {
        "blip": tone(880, 0.04, 0.2, "square"),
        "select": _arp(("E5", "B5"), 0.05, 0.25),
        "pause": tone(440, 0.09, 0.25, "triangle"),
        "count": tone(660, 0.12, 0.28, "square", decay=6),
        "go": tone(note("C6"), 0.35, 0.3, "square", decay=4),
        "wrong": mix(tone(150, 0.2, 0.3, "saw", decay=8, slide=0.7),
                     tone(158, 0.2, 0.22, "square", decay=8, slide=0.7)),
        "miss": tone(220, 0.16, 0.25, "triangle", decay=10, slide=0.6),
        "boost": whoosh,
        "check": _arp(("C5", "E5", "G5"), 0.1, 0.26, "square"),
        "perfect": _arp(("C5", "E5", "G5", "C6", "E6", "G6"), 0.09, 0.27, "pulse"),
        "warp": warp_sound(),
        "lap": _arp(("G5", "C6"), 0.08, 0.25, "triangle"),
        "finish": _arp(("C5", "G5", "C6", "E6", "G6", "C7"), 0.1, 0.26, "triangle", decay=3),
        "box": _arp(("A5", "E6", "A6"), 0.04, 0.22, "triangle"),
        "box_empty": tone(330, 0.08, 0.2, "triangle", decay=20),
        "box_full": tone(520, 0.05, 0.16, "triangle", decay=30),
        "split": mix(tone(400, 0.25, 0.22, "saw", slide=2.0), tone(600, 0.25, 0.15, "saw", slide=0.66)),
        "qec": _arp(("E6", "G6", "B6"), 0.05, 0.22, "sine", decay=4),
        "split_end": tone(500, 0.12, 0.18, "triangle", slide=0.6),
        "bump": mix(tone(90, 0.12, 0.4, "sine", decay=25, slide=0.6),
                    noise(0.08, 0.25, decay=40, hold=4, seed=3)),
        "result": _arp(("C5", "E5", "G5", "C6"), 0.09, 0.25, "triangle"),
        # the second playtest's items and hazards
        "zap": mix(tone(1400, 0.18, 0.2, "square", slide=0.35), tone(2100, 0.1, 0.1, "sine", decay=20)),
        "collapsed": mix(tone(700, 0.35, 0.24, "saw", decay=5, slide=0.2),
                         noise(0.3, 0.16, decay=8, hold=3, seed=11)),
        "scored": _arp(("G5", "D6", "G6"), 0.05, 0.24, "pulse", decay=8),
        "static": noise(0.32, 0.26, decay=7, hold=6, seed=5),
        "deco_scored": _arp(("D6", "A5", "D6"), 0.05, 0.2, "triangle", decay=8),
        "spin": mix(tone(520, 0.4, 0.22, "square", slide=0.3), noise(0.15, 0.2, decay=20, seed=9)),
        "tunnel": mix(tone(300, 0.3, 0.16, "sine", slide=2.5), tone(450, 0.3, 0.1, "triangle", slide=2.5)),
        "drop": tone(260, 0.2, 0.22, "triangle", slide=0.5),
        "drift": tone(1200, 0.05, 0.14, "pulse", decay=20),
        "turbo": mix(whoosh, tone(500, 0.2, 0.15, "saw", slide=2.0)),
        "fizzle": tone(240, 0.22, 0.18, "saw", decay=10, slide=0.5),
    }
    for i, name in enumerate(RIGHT_NOTES):
        ring = concat(tone(note(name), 0.05, 0.26, "pulse"),
                      tone(note(name) * 1.5, 0.12, 0.24, "triangle", decay=10))
        sfx[f"right{i + 1}"] = mix(ring, whoosh)  # the boost's whoosh
    return sfx


def engine_freq(step: int) -> float:
    """The engine's pitch at a speed step: ~50 Hz standing, rising with speed."""
    return 50.0 + 120.0 * step / (ENGINE_STEPS - 1)


def engine_loop(step: int, sr: int = SAMPLE_RATE) -> array.array:
    """A seamless engine loop: a saw and a square an octave down, whole periods only."""
    f = engine_freq(step)
    period = max(4, round(sr / f)) * 2  # two saw periods = one sub period
    one = array.array("h", (int(AMP * ENGINE_VOLUME * (0.6 * _wave("saw", 2 * i / period)
                                                     + 0.4 * _wave("square", i / period)))
                            for i in range(period)))
    return one * max(1, round(0.12 * sr / period))


def engine_step(speed: float) -> int:
    """The engine step for a speed in top speeds (0 standing, 1 top speed, up to 1.8)."""
    return max(0, min(ENGINE_STEPS - 1, round(speed / ENGINE_TOP * (ENGINE_STEPS - 1))))


ITEM_SOUNDS = {"SPLIT": "split", "QEC": "qec", "MEASURE": "zap", "TUNNEL": "tunnel",
               "DECOHERENCE": "drop"}
SCORED = {"collapse": "scored", "decohered": "deco_scored"}  # for the shooter or dropper


def sound_for(event, players=()) -> str | None:
    """The sound one of the match's events asks for, if any. A MEASURE hit ("collapse") and
    a cloud driven through ("decohered") reach both sides: the victim (`event.car`) hears
    its own sound, the shooter or dropper (`event.value`, one of `players` and not the
    victim) a scoring one."""
    if isinstance(event, Cue):
        return {"blip": "blip", "select": "select", "count": "count", "go": "go",
                "pause": "pause", "resume": "blip", "title": "blip",
                "result": "result"}.get(event.kind)
    if isinstance(event, Event):
        kind, value = event.kind, event.value
        if kind == "right":
            return f"right{min(len(RIGHT_NOTES), max(1, int(value)))}"
        if kind == "check":
            return "perfect" if value == 0 else "check"
        if kind == "warp":
            return "warp"
        if kind == "box":
            return "box" if value else "box_empty"
        if kind == "item":
            return ITEM_SOUNDS.get(value, "qec")
        if kind in SCORED and event.car not in players and value in players:
            return SCORED[kind]
        if kind == "hazard":
            return "spin" if value == "mine" else "static"
        return {"wrong": "wrong", "miss": "miss", "lap": "lap", "finish": "finish",
                "bump": "bump", "box_full": "box_full", "split_end": "split_end",
                "turbo": "turbo", "drift": "drift", "collapse": "collapsed",
                "decohered": "static", "fizzle": "fizzle", "immune": "box_full",
                "tunnel_end": "split_end"}.get(kind)
    return None


def sounds_for(events: list, players=()) -> list[str]:
    """The frame's sounds, each at most once (`players`: the cars people drive). When both
    sides of a hit are players (P1 MEASUREs P2), both sounds play."""
    names = []
    for e in events:
        names.append(sound_for(e, players))
        if (isinstance(e, Event) and e.kind in SCORED and e.car in players
                and e.value in players and e.value != e.car):
            names.append(SCORED[e.kind])
    return list(dict.fromkeys(n for n in names if n))


class NullAudio:
    def play_events(self, events: list, players=()) -> None:
        pass

    def engines(self, speeds: dict[str, float]) -> None:
        pass

    def ready(self) -> bool:
        return True


class Audio:
    def __init__(self) -> None:
        if not pygame.mixer.get_init():
            pygame.mixer.init(SAMPLE_RATE, -16, 1, 512)
        info = pygame.mixer.get_init()
        if not info:
            raise pygame.error("mixer did not initialise")
        self.freq, _fmt, self.channels = info
        pygame.mixer.set_num_channels(16)
        pygame.mixer.set_reserved(2)
        self.engine_channels = {"p1": pygame.mixer.Channel(0), "p2": pygame.mixer.Channel(1)}
        self.engine_playing: dict[str, int | None] = {"p1": None, "p2": None}
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.engine_sounds: list[pygame.mixer.Sound] = []
        self._done = False
        self._lock = threading.Lock()
        threading.Thread(target=self._render_all, daemon=True).start()

    def _sound(self, samples) -> pygame.mixer.Sound:
        buf = samples if isinstance(samples, array.array) else array.array("h", samples)
        if self.freq != SAMPLE_RATE:
            ratio = SAMPLE_RATE / self.freq
            buf = array.array("h", (buf[min(len(buf) - 1, int(i * ratio))]
                                    for i in range(int(len(buf) / ratio))))
        if self.channels > 1:
            wide = array.array("h", [0]) * (len(buf) * self.channels)
            for ch in range(self.channels):
                wide[ch::self.channels] = buf
            buf = wide
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def _render_all(self) -> None:
        engines = [self._sound(engine_loop(i)) for i in range(ENGINE_STEPS)]
        for s in engines:
            s.set_volume(config.MASTER_VOLUME * 0.5)
        with self._lock:
            self.engine_sounds = engines
        for name, samples in build_sfx().items():
            snd = self._sound(samples)
            snd.set_volume(config.MASTER_VOLUME)
            with self._lock:
                self.sounds[name] = snd
        self._done = True

    def ready(self) -> bool:
        return self._done

    def play_events(self, events: list, players=()) -> None:
        for name in sounds_for(events, players):
            with self._lock:
                snd = self.sounds.get(name)
            if snd is not None:
                snd.play()

    def engines(self, speeds: dict[str, float]) -> None:
        """Each player's engine at its speed (in top speeds); a player left out is silent."""
        with self._lock:
            loops = self.engine_sounds
        for p, channel in self.engine_channels.items():
            step = engine_step(speeds[p]) if p in speeds and loops else None
            if step == self.engine_playing[p]:
                continue
            self.engine_playing[p] = step
            if step is None:
                channel.stop()
            else:
                channel.play(loops[step], loops=-1)


def make_audio():
    try:
        return Audio()
    except (pygame.error, ValueError, OSError):
        return NullAudio()
