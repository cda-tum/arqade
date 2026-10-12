"""Synthesised chiptune: sound effects and looping kitchen music. No audio
files, no numpy.

The sample generators are pure functions (unit tested). Music notes are
built by tiling one waveform period (array repetition runs in C), so even
the Pi renders a loop quickly; the tracks are rendered in a background
thread at start-up and each starts as soon as it is ready. If the mixer
can't start (no sound card), everything becomes a silent no-op, so the
cabinet never crashes over audio.
"""

from __future__ import annotations

import array
import math
import random
import threading

import pygame

from overquqed import config

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


# --- pure sample generators ---------------------------------------------------------


def _wave(kind: str, phase: float) -> float:
    """One sample at `phase` in cycles (0..1)."""
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
    (multiplier reached by the end, e.g. 2.0 = up an octave)."""
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
        edge = min(1.0, (n - 1 - i) / 80)
        out.append(int(AMP * vol * env * edge * v))
    return out


def concat(*parts: list[int]) -> list[int]:
    out: list[int] = []
    for p in parts:
        out.extend(p)
    return out


def mix(*tracks: list[int]) -> list[int]:
    """Sum tracks (padded to the longest) with hard clipping."""
    n = max(len(t) for t in tracks)
    out = [0] * n
    for t in tracks:
        for i, v in enumerate(t):
            out[i] += v
    return [max(-AMP, min(AMP, v)) for v in out]


def _period(kind: str, freq: float, vol: float, sr: int) -> array.array:
    length = max(2, round(sr / freq))
    return array.array("h", (int(AMP * vol * _wave(kind, i / length)) for i in range(length)))


def voice(notes: list[tuple[str, float]], bpm: float, kind: str, vol: float, transpose: int = 0,
          staccato: float = 0.85, sr: int = SAMPLE_RATE) -> array.array:
    """A melodic line: (note, beats) pairs. Built by tiling single periods,
    with a 2-step envelope (attack level, then 70% sustain) per note."""
    out = array.array("h")
    beat = 60.0 / bpm
    for name, beats in notes:
        n = int(sr * beats * beat)
        f = note_freq(name, transpose)
        if f <= 0:
            out.extend(array.array("h", [0]) * n)
            continue
        on = int(n * staccato)
        loud, soft = _period(kind, f, vol, sr), _period(kind, f, vol * 0.7, sr)
        attack = min(on, int(sr * 0.04))
        seg = (loud * (attack // len(loud) + 1))[:attack]
        seg.extend((soft * ((on - attack) // len(soft) + 1))[: on - attack])
        out.extend(seg)
        out.extend(array.array("h", [0]) * (n - on))
    return out


def drums(pattern: str, bpm: float, bars: int, vol: float, sr: int = SAMPLE_RATE) -> array.array:
    """8th-note pattern per bar: k = kick, s = snare, h = hat, . = rest."""
    step = int(sr * 60.0 / bpm / 2)
    hits = {
        "k": array.array("h", tone(90, 0.09, vol, "sine", decay=30, slide=0.4)),
        "s": array.array("h", noise(0.08, vol * 0.8, decay=35, hold=2, seed=3)),
        "h": array.array("h", noise(0.025, vol * 0.4, decay=120, hold=1, seed=5)),
    }
    out = array.array("h")
    for _ in range(bars):
        for ch in pattern:
            cell = array.array("h", [0]) * step
            hit = hits.get(ch)
            if hit is not None:
                m = min(step, len(hit))
                cell[:m] = hit[:m]
            out.extend(cell)
    return out


# --- the music ---------------------------------------------------------------------------
# An original tune (I - vi - IV - V in C), 8 bars of eighth notes.

MELODY = [
    "E5 G5 A5 G5 E5 C5 D5 E5", "A4 C5 E5 D5 C5 - A4 -",
    "F5 A5 G5 F5 E5 G5 C5 E5", "D5 E5 D5 B4 C5 - - -",
    "G5 E5 G5 A5 G5 E5 C5 E5", "A5 G5 E5 C5 D5 E5 C5 -",
    "F5 E5 F5 A5 G5 F5 E5 D5", "B4 D5 G5 F5 E5 C5 C5 -",
]
BASS = ["C3 G3 C3 G3", "A2 E3 A2 E3", "F2 C3 F2 C3", "G2 D3 G2 B2"] * 2
DRUMS = "k.hsk.hs"

TRACKS = {
    # name: (bpm, transpose, lead wave, fast bpm or None)
    "title": (112, 0, "triangle", None),
    "tutorial": (120, 0, "triangle", None),
    "snackbar": (138, 0, "pulse", 168),
    "trattoria": (120, -3, "square", 146),
    "cosmic": (144, 2, "pulse", 176),
}


def render_track(bpm: float, transpose: int, lead: str) -> array.array:
    mel = [(n, 0.5) for bar in MELODY for n in bar.split()]
    bass = [(n, 1.0) for bar in BASS for n in bar.split()]
    a = voice(mel, bpm, lead, 0.22, transpose)
    b = voice(bass, bpm, "triangle", 0.30, transpose, staccato=0.95)
    d = drums(DRUMS, bpm, len(MELODY), 0.25)
    n = min(len(a), len(b), len(d))
    return array.array("h", (max(-AMP, min(AMP, a[i] + b[i] + d[i])) for i in range(n)))


# --- sound effects ----------------------------------------------------------------------


def _arp(freqs, dur, vol, kind="square"):
    return concat(*(tone(f, dur, vol, kind, decay=6) for f in freqs))


def build_sfx() -> dict[str, list[int]]:
    c = note_freq
    return {
        "blip": tone(880, 0.04, 0.25, "square"),
        "confirm": _arp([c("C5"), c("G5")], 0.05, 0.3),
        "back": _arp([c("G5"), c("C5")], 0.045, 0.22),
        "nope": tone(140, 0.09, 0.3, "square", decay=10),
        "pick": tone(620, 0.05, 0.25, "triangle", slide=1.5),
        "put": tone(420, 0.05, 0.25, "triangle", slide=0.7),
        "fridge": mix(noise(0.3, 0.25, decay=8, hold=3, seed=7), tone(1400, 0.3, 0.06, "sine", slide=0.5)),
        "flip": tone(300, 0.18, 0.35, "square", decay=8, slide=2.6),  # boing
        "stir": noise(0.16, 0.25, decay=14, hold=4, seed=9),
        "whirr": tone(180, 0.12, 0.18, "saw", slide=1.6),
        "blend_done": concat(tone(260, 0.12, 0.25, "saw", slide=2.4), tone(c("E6"), 0.06, 0.2, "square")),
        "cnot": mix(tone(110, 0.14, 0.4, "square", decay=20), noise(0.06, 0.2, decay=40, hold=6)),
        "cnot_sparkle": concat(tone(110, 0.1, 0.35, "square", decay=25),
                               _arp([c("C6"), c("E6"), c("G6"), c("C7")], 0.045, 0.2)),
        "sink": noise(0.35, 0.18, decay=5, hold=2, seed=11),
        "bin": tone(90, 0.12, 0.4, "square", decay=18, slide=0.6),
        "serve": _arp([c("C5"), c("E5"), c("G5"), c("C6")], 0.06, 0.28),
        "refuse": concat(tone(220, 0.12, 0.3, "square", decay=4), tone(160, 0.22, 0.3, "square", decay=4)),
        "leave": _arp([c("E4"), c("C4"), c("A3")], 0.1, 0.28, "triangle"),
        "order": tone(c("A6"), 0.25, 0.18, "sine", decay=10),
        "siren": concat(*(tone(f, 0.18, 0.2, "square", slide=1.3) for f in (600, 800, 600, 800))),
        "cosmic": mix(noise(0.6, 0.45, decay=5, hold=5, seed=13), tone(70, 0.5, 0.3, "sine", decay=6)),
        "swap": _arp([c("G5"), c("D6")], 0.04, 0.22),
        "timeup": _arp([c("G4"), c("C5"), c("E5"), c("G5"), c("C6")], 0.08, 0.3),
        "results": _arp([c("C5"), c("E5"), c("G5"), c("E5"), c("C6")], 0.1, 0.25, "triangle"),
        "type": tone(1200, 0.02, 0.12, "square"),
    }


# --- playback ------------------------------------------------------------------------------


class NullAudio:
    def play(self, name: str) -> None:
        pass

    def music(self, name: str) -> None:
        pass

    def tempo(self, fast: bool) -> None:
        pass

    def update(self) -> None:
        pass


class Audio:
    MUSIC_CHANNEL = 0

    def __init__(self) -> None:
        if not pygame.mixer.get_init():
            pygame.mixer.init(SAMPLE_RATE, -16, 1, 512)
        info = pygame.mixer.get_init()
        if not info:
            raise pygame.error("mixer did not initialise")
        self.freq, _fmt, self.channels = info
        pygame.mixer.set_num_channels(16)
        pygame.mixer.set_reserved(1)
        self.music_channel = pygame.mixer.Channel(self.MUSIC_CHANNEL)
        self.sounds = {k: self._sound(v) for k, v in build_sfx().items()}
        for s in self.sounds.values():
            s.set_volume(config.MASTER_VOLUME)
        self.tracks: dict[str, pygame.mixer.Sound] = {}
        self.want: str | None = None
        self.playing: str | None = None
        self.fast = False
        self._lock = threading.Lock()
        threading.Thread(target=self._render_all, daemon=True).start()

    def _sound(self, samples) -> pygame.mixer.Sound:
        buf = samples if isinstance(samples, array.array) else array.array("h", samples)
        if self.freq != SAMPLE_RATE:
            ratio = SAMPLE_RATE / self.freq
            buf = array.array("h", (buf[min(len(buf) - 1, int(i * ratio))] for i in range(int(len(buf) / ratio))))
        if self.channels > 1:
            stereo = array.array("h", [0]) * (len(buf) * self.channels)
            for c in range(self.channels):
                stereo[c::self.channels] = buf
            buf = stereo
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def _render_all(self) -> None:
        order = ["title"] + [k for k in TRACKS if k != "title"]
        for name in order:
            bpm, tr, lead, fast = TRACKS[name]
            for key, tempo in ((name, bpm), (name + ":fast", fast)):
                if tempo is None:
                    continue
                snd = self._sound(render_track(tempo, tr, lead))
                snd.set_volume(config.MUSIC_VOLUME)
                with self._lock:
                    self.tracks[key] = snd

    def play(self, name: str) -> None:
        s = self.sounds.get(name)
        if s is not None:
            s.play()

    def music(self, name: str) -> None:
        if name == "results":
            name = "title"
        self.want = name
        self.fast = False
        self.update()

    def tempo(self, fast: bool) -> None:
        if fast != self.fast:
            self.fast = fast
            self.update()

    def update(self) -> None:
        """Start (or switch to) the wanted track once it has been rendered."""
        if self.want is None:
            return
        key = self.want + (":fast" if self.fast and (self.want + ":fast") in TRACKS_FAST else "")
        if key == self.playing:
            return
        with self._lock:
            snd = self.tracks.get(key)
        if snd is None:
            return
        self.music_channel.play(snd, loops=-1, fade_ms=150)
        self.playing = key


TRACKS_FAST = {k + ":fast" for k, v in TRACKS.items() if v[3]}


def make_audio():
    try:
        return Audio()
    except (pygame.error, ValueError, OSError):
        return NullAudio()
