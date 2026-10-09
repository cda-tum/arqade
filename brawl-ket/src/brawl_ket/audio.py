"""Synthesised chiptune: a title loop, a 150 bpm fight loop and the effects for
every hit, bounce, basis switch and round call. No audio files, no numpy.

Adapted from Planck Time's audio.py (from Gate Drop's, from Overquqed's). Music
is built by tiling one waveform period per note (array repetition runs in C),
so even the Pi renders a loop quickly, and the tracks are rendered in a
background thread at start-up. If the mixer can't start (no sound card),
everything becomes a silent no-op, so the cabinet never crashes over audio.
"""

from __future__ import annotations

import array
import math
import random
import threading
from dataclasses import dataclass

import pygame

from . import config
from . import match as M
from .match import Cue

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


def mix(*tracks: list[int]) -> list[int]:
    n = max(len(t) for t in tracks)
    out = [0] * n
    for t in tracks:
        for i, v in enumerate(t):
            out[i] += v
    return [max(-AMP, min(AMP, v)) for v in out]


def _period(kind: str, freq: float, vol: float, sr: int) -> array.array:
    length = max(2, round(sr / freq))
    return array.array("h", (int(AMP * vol * _wave(kind, i / length)) for i in range(length)))


def voice(notes: list, bpm: float, kind: str, vol: float, staccato: float = 0.85,
          sr: int = SAMPLE_RATE) -> array.array:
    """A melodic line from (note, beats) pairs, built by tiling single periods."""
    out = array.array("h")
    beat = 60.0 / bpm
    for name, beats in notes:
        n = int(sr * beats * beat)
        f = note_freq(name)
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
        "s": array.array("h", noise_wave(0.08, vol * 0.8, decay=35, hold=2, seed=3)),
        "h": array.array("h", noise_wave(0.025, vol * 0.4, decay=120, hold=1, seed=5)),
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


# --- the music ------------------------------------------------------------------------
# Both original. The title: G major, G - Em - C - D twice, an easy triangle lead.
# The fight: E minor, i - VI - VII - i, then i - VI - VII - V (a B major, for the
# pull back round), a pulse lead over a pumping eighth-note bass and double kicks.

TITLE_MELODY = [
    "G4 B4 D5 G5 D5 B4 D5 G5", "E5 D5 B4 G4 E4 G4 B4 E5",
    "C5 E5 G5 E5 C5 E5 G5 C6", "D5 F#5 A5 F#5 D5 A4 F#5 A5",
    "B5 A5 G5 D5 B4 D5 G5 B5", "E5 G5 B5 G5 E5 B4 G4 B4",
    "C5 E5 A5 G5 E5 C5 D5 E5", "D5 F#5 A5 C6 B5 A5 F#5 D5",
]
TITLE_BASS = ["G2 D3 G2 D3", "E2 B2 E2 B2", "C3 G3 C3 G3", "D3 A3 D3 A3"] * 2

FIGHT_MELODY = [
    "E5 E5 B4 E5 G5 F#5 E5 B4", "C5 E5 G5 E5 C6 B5 G5 E5",
    "D5 F#5 A5 F#5 D6 C6 A5 F#5", "E5 G5 B5 G5 E6 D6 B5 G5",
    "B5 B5 G5 E5 B5 A5 G5 F#5", "G5 G5 E5 C5 G5 F#5 E5 D5",
    "F#5 A5 D6 A5 F#5 D5 E5 F#5", "D#5 F#5 B5 A5 F#5 D#5 B4 -",
]
FIGHT_BASS = [f"{r}2 {r}2 {r}3 {r}2 {r}2 {r}2 {r}3 {r}2" for r in ("E", "C", "D", "E", "E", "C", "D", "B")]


@dataclass(frozen=True)
class Tune:
    melody: list
    bass: list
    bass_beats: float  # each bass note's length
    bass_wave: str
    bass_vol: float
    drums: str
    drum_vol: float


TUNES = {
    "title": Tune(TITLE_MELODY, TITLE_BASS, 1.0, "triangle", 0.30, "k.hsk.hs", 0.22),
    "fight": Tune(FIGHT_MELODY, FIGHT_BASS, 0.5, "square", 0.15, "kkshkhsh", 0.30),
}
TRACKS = {  # name: (bpm, lead wave, tune)
    "title": (116, "triangle", "title"),
    "fight": (150, "pulse", "fight"),
}


def render_track(bpm: float, lead: str, tune: Tune) -> array.array:
    mel = [(n, 0.5) for bar in tune.melody for n in bar.split()]
    bass = [(n, tune.bass_beats) for bar in tune.bass for n in bar.split()]
    a = voice(mel, bpm, lead, 0.18 if lead == "saw" else 0.2)
    b = voice(bass, bpm, tune.bass_wave, tune.bass_vol, staccato=0.95 if tune.bass_beats >= 1 else 0.7)
    d = drums(tune.drums, bpm, len(tune.melody), tune.drum_vol)
    n = min(len(a), len(b), len(d))
    return array.array("h", (max(-AMP, min(AMP, a[i] + b[i] + d[i])) for i in range(n)))


def music_for(m: M.Match) -> str:
    """The title loop on the title, select and result screens; the fight loop in a round."""
    return "fight" if m.state in (M.ROUND_INTRO, M.FIGHT, M.ROUND_END) else "title"


# --- sound effects ------------------------------------------------------------------------


def _arp(freqs, dur, vol, kind="square"):
    return concat(*(tone(f, dur, vol, kind, decay=6) for f in freqs))


def build_sfx() -> dict[str, list[int]]:
    c = note_freq
    return {
        "blip": tone(880, 0.04, 0.22, "square"),
        "pause": tone(660, 0.08, 0.25, "square"),
        # the round calls
        "round": concat(tone(c("G4"), 0.08, 0.28, "pulse"), tone(c("G4"), 0.08, 0.28, "pulse"),
                        tone(c("D5"), 0.2, 0.3, "pulse", decay=4)),
        "fight": mix(_arp([c("C5"), c("G5"), c("C6")], 0.05, 0.28),
                     noise_wave(0.15, 0.25, decay=14, hold=3, seed=7)),
        "ko": mix(concat(tone(c("C5"), 0.12, 0.3, "square", decay=3), tone(c("C4"), 0.5, 0.32, "saw", decay=3,
                                                                           slide=0.5)),
                  noise_wave(0.4, 0.3, decay=6, hold=5, seed=11)),
        "timeout": concat(tone(c("A5"), 0.1, 0.25, "square"), tone(0, 0.05, 0), tone(c("A5"), 0.1, 0.25, "square"),
                          tone(0, 0.05, 0), tone(c("E5"), 0.3, 0.28, "square", decay=4)),
        "perfect": _arp([c("C6"), c("E6"), c("G6"), c("C7")], 0.05, 0.22, "pulse"),
        "draw": concat(tone(c("E5"), 0.15, 0.25, "triangle", decay=4), tone(c("E5"), 0.3, 0.25, "triangle", decay=4)),
        "match": _arp([c("C5"), c("E5"), c("G5"), c("C6"), c("G5"), c("C6")], 0.1, 0.3, "triangle"),
        # the fight
        "swing": noise_wave(0.06, 0.1, decay=45, hold=3, seed=2),
        "hit": mix(tone(150, 0.08, 0.35, "square", decay=30, slide=0.5), noise_wave(0.06, 0.3, decay=50, hold=2)),
        # a wrong-colour hit: a bright ping as the attack bounces off
        "ping": concat(tone(c("E6"), 0.03, 0.2, "triangle"), tone(c("B6"), 0.09, 0.16, "triangle", decay=18)),
        # a basis switch (an H): a quick rising whoosh
        "whoosh": mix(tone(400, 0.12, 0.14, "triangle", decay=8, slide=2.5), noise_wave(0.1, 0.1, decay=25, hold=2, seed=4)),
        # MEASURE collapsing the rival into BOHR's basis: a falling zap
        "measure": tone(c("C6"), 0.18, 0.2, "square", decay=10, slide=0.35),
        "photon": tone(700, 0.16, 0.2, "pulse", decay=10, slide=2.2),
        # PHOEBE: the LIGHT PILLAR's buzzing beam, the TUNNEL's falling-then-rising shimmer, the
        # LASER's short zap, and the sizzle of a laser reaching the floor
        "pillar": mix(tone(880, 0.28, 0.14, "square", decay=4, slide=1.6),
                      tone(440, 0.28, 0.12, "saw", decay=4, slide=1.6)),
        "tunnel": concat(tone(1100, 0.09, 0.15, "triangle", decay=4, slide=0.35),
                         tone(380, 0.12, 0.15, "triangle", decay=5, slide=2.8)),
        "laser": tone(1500, 0.07, 0.18, "square", decay=22, slide=0.5),
        "sizzle": noise_wave(0.07, 0.12, decay=35, hold=1, seed=9),
        "shockwave": mix(tone(70, 0.3, 0.45, "sine", decay=8, slide=0.5), noise_wave(0.25, 0.3, decay=12, hold=6)),
    }


CUE_SOUNDS = {"blip": "blip", "pause": "pause", "round": "round", "fight": "fight", "ko": "ko",
              "timeout": "timeout", "perfect": "perfect", "draw": "draw", "match_won": "match"}
# the fight's events; None: deliberately silent (a landing would chatter)
EVENT_SOUNDS = {"attack": "swing", "hit": "hit", "block": "ping", "switch": "whoosh", "measure": "measure",
                "projectile": "photon", "shockwave": "shockwave",
                "pillar": "pillar", "tunnel": "tunnel", "laser": "laser", "fizzle": "sizzle",
                "land": None, "ko": None, "timeout": None}   # ko/timeout: the cues play those
SUPERSEDES = {"measure": "hit",     # MEASURE's zap replaces the thump of its own throw
              "laser": "photon"}    # a LASER is a projectile too: its zap, not the photon's


def sounds_for(events: list) -> list[str]:
    """The sounds a frame's cues and fight events ask for, each at most once."""
    names = [CUE_SOUNDS.get(e.kind) if isinstance(e, Cue) else EVENT_SOUNDS.get(e.kind) for e in events]
    names = list(dict.fromkeys(n for n in names if n))
    for loud, quiet in SUPERSEDES.items():
        if loud in names and quiet in names:
            names.remove(quiet)
    return names


# --- playback ---------------------------------------------------------------------------


class NullAudio:
    def play_events(self, events: list) -> None:
        pass

    def music(self, name: str) -> None:
        pass

    def update(self) -> None:
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
        pygame.mixer.set_reserved(1)
        self.music_channel = pygame.mixer.Channel(0)
        self.sounds = {k: self._sound(v) for k, v in build_sfx().items()}
        for s in self.sounds.values():
            s.set_volume(config.MASTER_VOLUME)
        self.tracks: dict[str, pygame.mixer.Sound] = {}
        self.want: str | None = None
        self.playing: str | None = None
        self._lock = threading.Lock()
        threading.Thread(target=self._render_all, daemon=True).start()

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

    def _render_all(self) -> None:
        for name, (bpm, lead, tune) in TRACKS.items():
            snd = self._sound(render_track(bpm, lead, TUNES[tune]))
            snd.set_volume(config.MUSIC_VOLUME)
            with self._lock:
                self.tracks[name] = snd

    def play_events(self, events: list) -> None:
        for name in sounds_for(events):
            s = self.sounds.get(name)
            if s is not None:
                s.play()

    def music(self, name: str) -> None:
        if name != self.want:
            self.want = name
            self.update()

    def update(self) -> None:
        """Start (or switch to) the wanted track once it has been rendered."""
        if self.want is None:
            return
        key = self.want
        if key == self.playing:
            return
        with self._lock:
            snd = self.tracks.get(key)
        if snd is None:
            return
        self.music_channel.play(snd, loops=-1, fade_ms=150)
        self.playing = key


def make_audio():
    try:
        return Audio()
    except (pygame.error, ValueError, OSError):
        return NullAudio()
