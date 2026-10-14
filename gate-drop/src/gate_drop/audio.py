"""Synthesised chiptune sound effects. No audio files, no numpy, and no music
(the cabinet's owners want music only in Overquqed).

The sample generators are adapted from Overquqed's audio.py (same repo). If
the mixer can't start (no sound card), everything becomes a silent no-op, so
the cabinet never crashes over audio.
"""

from __future__ import annotations

import array
import math
import random

import pygame

from gate_drop import config
from gate_drop.match import BoardEvent, Cue

SAMPLE_RATE = 22050
AMP = 32767

NOTE_INDEX = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def note_freq(name: str, transpose: int = 0) -> float:
    """'A4' -> 440.0; '-' (rest) -> 0."""
    if name == "-":
        return 0.0
    pitch, octave = name[:-1], int(name[-1])
    n = NOTE_INDEX[pitch] + 12 * (octave + 1) + transpose
    return 440.0 * 2 ** ((n - 69) / 12)


def _wave(kind: str, phase: float) -> float:
    p = phase % 1.0
    if kind == "square":
        return 1.0 if p < 0.5 else -1.0
    if kind == "pulse":  # 25% duty: thinner, NES-like lead
        return 1.0 if p < 0.25 else -1.0
    if kind == "triangle":
        return 4 * p - 1 if p < 0.5 else 3 - 4 * p
    if kind == "saw":
        return 2 * p - 1
    return math.sin(2 * math.pi * p)


def tone(freq: float, dur: float, vol: float, kind: str = "square", decay: float = 0.0,
         slide: float = 0.0, sr: int = SAMPLE_RATE) -> list[int]:
    """A note with optional exponential decay (1/s) and a pitch slide
    (the frequency multiplier reached by the end)."""
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


def noise_wave(dur: float, vol: float, decay: float = 0.0, hold: int = 1, seed: int = 1,
               sr: int = SAMPLE_RATE) -> list[int]:
    """White-ish noise; `hold` repeats each random value (lower = brighter)."""
    rng = random.Random(seed)
    n = max(1, int(sr * dur))
    out = []
    v = 0.0
    for i in range(n):
        if i % hold == 0:
            v = rng.uniform(-1, 1)
        env = math.exp(-decay * i / sr) if decay else 1.0
        out.append(int(AMP * vol * env * min(1.0, (n - 1 - i) / 80) * v))
    return out


def concat(*parts: list[int]) -> list[int]:
    out: list[int] = []
    for p in parts:
        out.extend(p)
    return out


def mix(*parts: list[int]) -> list[int]:
    n = max(len(t) for t in parts)
    out = [0] * n
    for t in parts:
        for i, v in enumerate(t):
            out[i] += v
    return [max(-AMP, min(AMP, v)) for v in out]


# --- sound effects ------------------------------------------------------------------------

CLEAR_NOTES = (("C5", "E5"), ("D5", "F#5"), ("E5", "G#5"), ("F#5", "A#5"), ("G#5", "C6"))


def _arp(freqs, dur, vol, kind="square"):
    return concat(*(tone(f, dur, vol, kind, decay=6) for f in freqs))


def build_sfx() -> dict[str, list[int]]:
    c = note_freq
    sfx = {
        "move": tone(520, 0.025, 0.16, "square"),
        "rotate": tone(760, 0.035, 0.2, "pulse", slide=1.3),
        "land": tone(180, 0.06, 0.3, "square", decay=25, slide=0.7),
        "error": concat(_arp([c("E6"), c("G6")], 0.05, 0.25), tone(c("C7"), 0.14, 0.2, "triangle", decay=8)),
        "attack": tone(300, 0.2, 0.3, "saw", slide=3.0),
        "cnot": concat(tone(110, 0.08, 0.35, "square", decay=25), _arp([c("C6"), c("E6"), c("G6")], 0.04, 0.22)),
        "noise": mix(noise_wave(0.18, 0.3, decay=12, hold=3, seed=4),
                     tone(120, 0.18, 0.25, "square", decay=12, slide=0.6)),
        "topout": concat(*(tone(f, 0.12, 0.3, "square", decay=4) for f in (330, 262, 196, 131))),
        "beep": tone(660, 0.08, 0.25, "square"),
        "blip": tone(880, 0.04, 0.22, "square"),
        "confirm": _arp([c("E6"), c("A6")], 0.045, 0.24),  # a menu pick, or the HOW TO PLAY card dismissed
        "back": _arp([c("A5"), c("E5")], 0.045, 0.2),
        "go": _arp([c("C5"), c("G5"), c("C6")], 0.06, 0.3),
        "round": _arp([c("C5"), c("E5"), c("G5"), c("C6")], 0.08, 0.3),
        "match": _arp([c("C5"), c("E5"), c("G5"), c("C6"), c("G5"), c("C6")], 0.1, 0.3, "triangle"),
    }
    for i, notes in enumerate(CLEAR_NOTES, start=1):
        sfx[f"clear{i}"] = _arp([c(n) for n in notes], 0.05, 0.28)
    return sfx


_CUE_SOUNDS = {"beep": "beep", "go": "go", "blip": "blip", "confirm": "confirm", "back": "back", "pause": "beep",
               "round_won": "round", "draw": "round", "match_won": "match", "level_clear": "match",
               "game_over": "topout"}
_BOARD_SOUNDS = {"move", "rotate", "land", "attack", "noise", "topout"}
_BOARD_RENAMES = {"propagate": "cnot"}


def sounds_for(events: list) -> list[str]:
    """The sounds a frame's events ask for, each at most once."""
    names = []
    for e in events:
        if isinstance(e, Cue):
            names.append(_CUE_SOUNDS[e.kind])
        elif isinstance(e, BoardEvent):
            kind = e.event.kind
            if kind in _BOARD_SOUNDS:
                names.append(kind)
            elif kind in _BOARD_RENAMES:
                names.append(_BOARD_RENAMES[kind])
            elif kind == "clear":
                names.append(f"clear{min(len(CLEAR_NOTES), max(1, e.event.value))}")
            elif kind == "errors":
                names.append("error")
    return list(dict.fromkeys(names))


# --- playback ---------------------------------------------------------------------------


class NullAudio:
    def play_events(self, events: list) -> None:
        pass


class Audio:
    def __init__(self) -> None:
        if not pygame.mixer.get_init():
            pygame.mixer.init(SAMPLE_RATE, -16, 1, 512)
        info = pygame.mixer.get_init()
        if not info:
            raise pygame.error("mixer did not initialise")
        self.freq, _fmt, self.channels = info
        pygame.mixer.set_num_channels(16)
        self.sounds = {k: self._sound(v) for k, v in build_sfx().items()}
        for s in self.sounds.values():
            s.set_volume(config.MASTER_VOLUME)

    def _sound(self, samples) -> pygame.mixer.Sound:
        buf = samples if isinstance(samples, array.array) else array.array("h", samples)
        if self.freq != SAMPLE_RATE:
            ratio = SAMPLE_RATE / self.freq
            buf = array.array("h", (buf[min(len(buf) - 1, int(i * ratio))] for i in range(int(len(buf) / ratio))))
        if self.channels > 1:
            stereo = array.array("h", [0]) * (len(buf) * self.channels)
            for ch in range(self.channels):
                stereo[ch::self.channels] = buf
            buf = stereo
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def play_events(self, events: list) -> None:
        for name in sounds_for(events):
            s = self.sounds.get(name)
            if s is not None:
                s.play()


def make_audio():
    try:
        return Audio()
    except (pygame.error, ValueError, OSError):
        return NullAudio()
