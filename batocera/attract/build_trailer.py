"""Cut a ~42 s ARQADE trailer from the attract footage. V4, for internal use.

    launcher/.venv/bin/python batocera/attract/build_trailer.py
    launcher/.venv/bin/python batocera/attract/build_trailer.py --audio-only   # remix, keep the picture
    launcher/.venv/bin/python batocera/attract/build_trailer.py --short        # the ~20 s cut

Writes trailer/arqade_trailer.mp4 (1920x1080, 30 fps, AAC stereo), or
trailer/arqade_trailer_short.mp4, and a sheet with a frame of every shot
beside the folder.

Nothing in it is new material:

- the gameplay and its sound effects are the attract captures in clips/
  (capture.py writes <rom>.wav beside each <rom>.mp4, in sync);
- the music is Nihilore's "Motion Blur" from Batocera's own menu music
  (trailer_assets/, CC BY 4.0, see CREDITS.md). It runs at 86.66 BPM, and
  its first chorus ends on the beat at 48.45 s: that is where the mosaic
  hands over to the end card. The edit is laid out in beats backwards from
  there, so the track starts mid-flow and comes up through a low-pass filter
  under the intro. At the end a reverse cymbal rises into a crash, and the
  music's last bars ring out in a reverb tail under the end card;
- the logo, the CRT tube and the marquees are the reels' own;
- the TUM and MQT logos are in trailer_assets/ (see CREDITS.md).

The edit is TIMELINE below, in beats: the tube powers on to WELCOME TO THE
and the logo, which pixelates away into a box of four classic games filling
up one per beat; four cards (USE SUPERPOSITION, BECOME ENTANGLED, APPLY
QUANTUM GATES, FIGHT QUANTUM ERRORS), each followed by two games that are
about it; AND MUCH MORE with the rest; ALL WITHIN THE, then all ten games as
a mosaic around the logo, a zoom into the logo, and the logo coming to rest
over the TUM and MQT logos before the tube powers off.

A shot's start is seconds into the game's clip, or a name the game's bot
lists: "#n" is the bot's n-th HIGHLIGHT (best first), and a Planck Time
microgame verb ("ALIGN!", "PAIR!", ...) with an optional "#n" picks from the
bot's MOMENTS. Highlights are 2 s windows checked frame by frame; longer shots
run on past the checked part.
"""

from __future__ import annotations

import ast
import logging
import math
import multiprocessing
import os
import shutil
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import pygame

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_reel as reel  # noqa: E402  (Tube, Frames, marquee, the logo spin)

REPO = HERE.parents[1]
CLIPS = HERE / "clips"
BOTS = HERE / "bots"
ASSETS = HERE / "trailer_assets"
OUT_DIR = HERE / "trailer"
FONT = reel.FONT
LOGO_STILL = REPO / "quantum-pong" / "batocera" / "arqade-theme" / "art" / "mqt_splash.png"
logging.getLogger("imageio_ffmpeg").setLevel(logging.ERROR)

SIZE = (1920, 1080)
FPS = 30
RATE = 48000  # the trailer's audio
BLUE = reel.BLUE
WHITE = (238, 238, 246)

MUSIC = ASSETS / "Nihilore - Motion Blur.ogg"
MUSIC_CREDIT = 'MUSIC: NIHILORE - "MOTION BLUR" (CC BY 4.0)'
BPM = 86.66  # measured: onsets line up to 0.01 BPM over the first 47 s
BEAT = 60 / BPM
MUSIC_END = 48.448  # s into the track: the beat that ends the first chorus

# (beats, kind, args). Kinds: intro, panel ((rom, start) x4), shot (rom,
# start, marquee?), card (lead-in or None, line), mosaic ((rom, start) x10), end.
TIMELINE = [
    (5, "intro", ()),  # WELCOME TO THE, the logo, which pixelates away
    # into a box of four classic-looking games, one more on every beat
    (5, "panel", (("quantum_pong", 53.7), ("error_invaders", 37.5), ("gate_drop", 15.0), ("ion_surfer", 34.0))),
    (2, "card", ("USE", "SUPERPOSITION")),
    (2.5, "shot", ("qurves", 9.7, True)),  # every bike splits into ghost copies
    (2.5, "shot", ("planck_time", "ALIGN!", True)),  # the Bloch-sphere arrow
    (2, "card", ("BECOME", "ENTANGLED")),
    (2.5, "shot", ("overquqed", 21.2, True)),  # both chefs on the Waffle Iron: ENTANGLED!
    (2.5, "shot", ("planck_time", "PAIR!", True)),  # the two particles swaying in sync
    (2, "card", ("APPLY", "QUANTUM GATES")),
    (2.5, "shot", ("quantum_towers", 74.3, True)),  # the race to the top, gates going in
    (2.5, "shot", ("superconductor", 57.3, True)),  # both chips busy, gates firing
    (2, "card", ("FIGHT", "QUANTUM ERRORS")),
    (2.5, "shot", ("error_invaders", 29.0, True)),  # the LOGICAL ERROR chain shot apart
    (2.5, "shot", ("gate_drop", 4.3, True)),  # FIXED!, a chain, a CNOT
    (2, "card", ("AND", "MUCH MORE")),
    (1.5, "shot", ("ion_surfer", 59.6, True)),
    (1.5, "shot", ("quantum_pong", 16.9, True)),  # four balls in play
    (1.5, "shot", ("brawl_ket", "#0", True)),  # CHARGE NOISE, a colour switch, a knockdown
    (1.5, "shot", ("planck_time", "SYNDROME!", True)),  # the boss strikes, both fix it
    (2, "card", (None, "ALL WITHIN THE")),
    # all ten around the logo, then the zoom into it (the last ZOOM_BEATS)
    (6, "mosaic", (("quantum_pong", 70.9), ("quantum_towers", 70.6), ("error_invaders", 31.5),
                   ("ion_surfer", 65.1), ("superconductor", 49.3), ("planck_time", "CANCEL!"),
                   ("gate_drop", 49.0), ("qurves", 73.5), ("overquqed", 55.0), ("brawl_ket", "#2"))),
    (7, "end", ()),
]
# The ~20 s cut: the same opening, then the games on their own without the
# cards (too much reading at this pace), a faster mosaic, and an end card where
# the logo is already face on (the mosaic's turn ends there) rather than
# turning once more. The games not in the opening box, 2.5 beats each
# (two felt rushed).
TIMELINE_SHORT = [
    (4, "intro", ()),
    (4, "panel", (("quantum_pong", 53.7), ("error_invaders", 37.5), ("gate_drop", 15.0), ("ion_surfer", 34.0))),
    (2.5, "shot", ("qurves", 9.7, True)),  # every bike splits into ghost copies
    (2.5, "shot", ("overquqed", 21.2, True)),  # ENTANGLED!
    (2.5, "shot", ("planck_time", "ALIGN!", True)),
    (2.5, "shot", ("quantum_towers", 74.3, True)),  # the race to the top
    (2.5, "shot", ("superconductor", 57.3, True)),
    (2.5, "shot", ("brawl_ket", "#0", True)),  # CHARGE NOISE, a colour switch, a knockdown
    (4, "mosaic", (("quantum_pong", 70.9), ("quantum_towers", 70.6), ("error_invaders", 31.5),
                   ("ion_surfer", 65.1), ("superconductor", 49.3), ("planck_time", "CANCEL!"),
                   ("gate_drop", 49.0), ("qurves", 73.5), ("overquqed", 55.0), ("brawl_ket", "#2"))),
    (5, "end", ()),
]
ZOOM_BEATS = 1.5
CELL_EVERY = 0.3  # beats between mosaic cells appearing
PIXELATE_BEATS = 0.75  # the logo breaking up at the end of the intro...
UNPIXELATE_BEATS = 0.5  # ...and the first shot coming out of it
POWER_ON_FRAMES = 10
POWER_OFF_FRAMES = 12
TAIL_FRAMES = 12  # black after the tube goes off
SFX_GAIN = 0.53  # the games' own effects under the music, once each game is levelled (SFX_TARGET)
# The games' effects differ wildly in level (Qlimbers' were ~19 dB louder than
# Superconductor's), so each game's are first brought to the same loudness:
# the RMS of the 50 ms windows that have sound in them, over the excerpts the
# trailer uses, made SFX_TARGET (the middle game's level), then a soft
# limiter on the whole effects track takes the edge off single spikes.
SFX_TARGET = -16.4  # dBFS
SFX_GAIN_RANGE = (-18.0, 9.0)  # dB: how far a game is turned down or up at most
SFX_LIMIT = 0.25  # the soft limiter's knee, about -12 dBFS
MUSIC_GAIN = 0.8
# Render processes. Each holds a 1080p tube, decoders and an x264 encoder:
# eight at once ran a 16 GB machine out of memory.
WORKERS = 3
SPIN_CROP = (200, 280, 1520, 520)  # where the logo turns in the 1920x1080 spin
END_SPIN_FROM = 10  # the end card's turn starts here: the zoom before it sees the logo face on
OUT_NAME = "arqade_trailer"
# What --short changes: (TIMELINE, CELL_EVERY, END_SPIN_FROM, OUT_NAME).
# END_SPIN_FROM 120 means no turn on the end card: the logo is face on.
EDITIONS = {
    "full": (TIMELINE, 0.3, 10, "arqade_trailer"),
    "short": (TIMELINE_SHORT, 0.2, 120, "arqade_trailer_short"),
}


def use(edition: str) -> None:
    global TIMELINE, CELL_EVERY, END_SPIN_FROM, OUT_NAME
    TIMELINE, CELL_EVERY, END_SPIN_FROM, OUT_NAME = EDITIONS[edition]
END_LIFT = 0.08  # of the height: the logo rises to make room for the partner logos


def frame_at(beats: float) -> int:
    return round(beats * BEAT * FPS)


def ease(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def outro_beat() -> float:
    """Beats before the end card. Keep it whole: the trailer's beats line up
    with the music's only if the cut at MUSIC_END falls on a whole beat."""
    return sum(beats for beats, kind, _ in TIMELINE if kind != "end")


def music_start() -> float:
    """Where in the track the trailer starts: its cut is at MUSIC_END."""
    return MUSIC_END - outro_beat() * BEAT


@dataclass
class Segment:
    index: int
    beats: float
    start: float  # in beats
    kind: str
    args: tuple

    @property
    def first(self) -> int:
        return frame_at(self.start)

    @property
    def last(self) -> int:  # exclusive
        return frame_at(self.start + self.beats)


def segments() -> list[Segment]:
    out, at = [], 0.0
    for i, (beats, kind, args) in enumerate(TIMELINE):
        out.append(Segment(i, beats, at, kind, args))
        at += beats
    return out


# --- where in a clip ----------------------------------------------------------


def bot_settings(rom: str) -> dict:
    path = BOTS / f"{rom}.py"
    values = {}
    if path.is_file():
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                try:
                    values[node.targets[0].id] = ast.literal_eval(node.value)
                except ValueError:
                    pass
    return values


def when(rom: str, start: float | str) -> float:
    """Seconds into the clip for a shot's start (see the module doc)."""
    if not isinstance(start, str):
        return float(start)
    settings = bot_settings(rom)
    name, _, n = start.partition("#")
    k = int(n or 0)
    if name:
        moments = settings.get("MOMENTS") or {}
        if name not in moments:
            raise SystemExit(f"{rom}: its bot lists no {name} (MOMENTS has {', '.join(moments) or 'nothing'})")
        return float(moments[name][k % len(moments[name])])
    highlights = settings.get("HIGHLIGHTS") or []
    if not highlights:
        raise SystemExit(f"{rom}: its bot lists no HIGHLIGHTS")
    return float(highlights[k % len(highlights)])


# --- pictures -----------------------------------------------------------------


def pixelate(frame: pygame.Surface, block: float) -> pygame.Surface:
    if block <= 1.5:
        return frame
    w, h = frame.get_size()
    small = pygame.transform.smoothscale(frame, (max(1, round(w / block)), max(1, round(h / block))))
    return pygame.transform.scale(small, (w, h))


class Painter:
    """Everything a worker needs to draw any segment."""

    def __init__(self):
        w, h = SIZE
        pygame.font.init()
        self.tube = reel.Tube(SIZE)
        self.word_font = pygame.font.Font(str(FONT), 72)
        self.kicker_font = pygame.font.Font(str(FONT), 40)
        self.credit_font = pygame.font.Font(str(FONT), 16)
        self.tags: dict[str, pygame.Surface | None] = {}
        self.margin = (round(w * 0.045), round(h * 0.06))
        self.white = pygame.Surface(SIZE)
        self.white.fill((255, 255, 255))
        self.black = pygame.Surface(SIZE)
        tum = pygame.image.load(str(ASSETS / "tum_white.png"))
        mqt = pygame.image.load(str(ASSETS / "mqt_light.png"))
        self.partners = [pygame.transform.smoothscale(img, (round(img.get_width() * hh / img.get_height()), hh))
                         for img, hh in ((tum, 78), (mqt, 104))]

    def tag(self, rom: str) -> pygame.Surface | None:
        if rom not in self.tags:
            self.tags[rom] = reel.marquee(rom, SIZE[1])
        return self.tags[rom]

    def flash(self, frame: pygame.Surface, strength: float) -> None:
        if strength > 0:
            self.white.set_alpha(round(255 * min(1.0, strength)))
            frame.blit(self.white, (0, 0))

    # Each draw_* yields finished frames (tube included) for its segment.

    def draw_intro(self, seg: Segment):
        """WELCOME TO THE typed in, the logo (face on, standing still) coming
        up under it, and the whole picture pixelating away at the end."""
        w, h = SIZE
        n = seg.last - seg.first
        logo = pygame.image.load(str(LOGO_STILL))
        lead = "WELCOME TO THE"
        typing_from, typing = round(0.25 * FPS), max(1, round(0.7 * BEAT * FPS))
        logo_in = typing_from + typing + round(0.15 * FPS)
        break_up = n - frame_at(PIXELATE_BEATS)
        lead_pos = (w // 2, round(h * 0.235))
        for i in range(n):
            frame = pygame.Surface(SIZE)
            if i >= logo_in:
                fade = ease((i - logo_in + 1) / (0.4 * FPS))
                logo.set_alpha(round(255 * fade))
                frame.blit(logo, (0, 0))
            shown = lead[: max(0, math.ceil(len(lead) * min(1.0, (i - typing_from + 1) / typing)))] if i >= typing_from else ""
            if shown:
                full = self.kicker_font.size(lead)
                text = self.kicker_font.render(shown, False, BLUE)
                frame.blit(text, (lead_pos[0] - full[0] // 2, lead_pos[1] - full[1] // 2))
            if i >= break_up:
                k = (i - break_up + 1) / (n - break_up)
                frame = pixelate(frame, 96 ** k)
            yield self.tube(frame)

    def draw_panel(self, seg: Segment, cells: tuple):
        """A 2x2 box of games filling up one cell per beat, each game starting
        as its cell appears, with its marquee in the cell's corner. Coming out
        of the intro, the first cell resolves out of the logo's pixels."""
        w, h = SIZE
        gap = 24
        ch = (h - 3 * gap) // 2
        cw = ch * 16 // 9
        x0, y0 = (w - (2 * cw + gap)) // 2, gap
        n = seg.last - seg.first
        appear = [frame_at(k) for k in range(len(cells))]
        streams = [None] * len(cells)
        tags = [reel.marquee(rom, round(ch * 1.1)) for rom, _ in cells]
        out_of_pixels = frame_at(UNPIXELATE_BEATS)
        for i in range(n):
            frame = pygame.Surface(SIZE)
            frame.fill((4, 5, 8))
            for k, (rom, start) in enumerate(cells):
                if i < appear[k]:
                    continue
                if streams[k] is None:
                    streams[k] = reel.Frames(CLIPS / f"{rom}.mp4", (cw, ch), when(rom, start)).take(n - appear[k])
                picture = next(streams[k])
                since = i - appear[k]
                if k > 0:
                    self.flash(picture, (0.6, 0.3, 0.1)[since] if since < 3 else 0)
                x, y = x0 + (k % 2) * (cw + gap), y0 + (k // 2) * (ch + gap)
                frame.blit(picture, (x, y))
                if tags[k] is not None:
                    frame.blit(tags[k], tags[k].get_rect(bottomleft=(x + 14, y + ch - 12)))
            if i < out_of_pixels:
                frame = pixelate(frame, 96 ** (1 - (i + 1) / out_of_pixels))
            yield self.tube(frame)

    def draw_shot(self, seg: Segment, rom: str, start: float | str, show_tag: bool):
        n = seg.last - seg.first
        out_of_pixels = frame_at(UNPIXELATE_BEATS) if seg.index > 0 and TIMELINE[seg.index - 1][1] == "intro" else 0
        flash = () if out_of_pixels else ((0.6, 0.3, 0.1) if seg.beats >= 4 else (0.25,))
        for i, frame in enumerate(reel.Frames(CLIPS / f"{rom}.mp4", SIZE, when(rom, start)).take(n)):
            if i < out_of_pixels:
                frame = pixelate(frame, 96 ** (1 - (i + 1) / out_of_pixels))
            self.flash(frame, flash[i] if i < len(flash) else 0)
            frame = self.tube(frame)
            tag = self.tag(rom) if show_tag else None
            if tag is not None:
                frame.blit(tag, tag.get_rect(bottomleft=(self.margin[0], SIZE[1] - self.margin[1])))
            yield frame

    def draw_card(self, seg: Segment, kicker: str | None, line: str):
        """A small blue lead-in over the big line, typed out over most of a
        beat, with a blue rule growing under it."""
        w, h = SIZE
        n = seg.last - seg.first
        typing = max(1, round(0.7 * BEAT * FPS))
        full = self.word_font.size(line)
        left = (w - full[0]) // 2
        lead = self.kicker_font.render(kicker, False, BLUE) if kicker else None
        for i in range(n):
            frame = pygame.Surface(SIZE)
            grow = min(1.0, (i + 1) / typing)
            shown = line[: max(1, math.ceil(len(line) * grow))]
            if lead is not None:
                frame.blit(lead, lead.get_rect(bottomleft=(left, h // 2 - full[1] // 2 - 22)))
            frame.blit(self.word_font.render(shown, False, WHITE), (left, h // 2 - full[1] // 2))
            pygame.draw.rect(frame, BLUE, (left, h // 2 + full[1] // 2 + 22, round(full[0] * grow), 6))
            yield self.tube(frame)

    def draw_mosaic(self, seg: Segment, cells: tuple):
        """Ten games in a 4x3 grid around the turning logo, which takes the
        two middle cells; then a zoom into the logo: the cells fade out while
        the logo grows until it is exactly the size and turn of the end card's
        first frame."""
        w, h = SIZE
        gap = 20
        cw = (w - 5 * gap) // 4
        ch = cw * 9 // 16
        x0, y0 = (w - (4 * cw + 3 * gap)) // 2, (h - (3 * ch + 2 * gap)) // 2
        spots = [(0, 0), (1, 0), (2, 0), (3, 0), (3, 1), (3, 2), (2, 2), (1, 2), (0, 2), (0, 1)]  # clockwise
        n = seg.last - seg.first
        zoom_frames = frame_at(ZOOM_BEATS)
        logo_w = min(2 * cw + gap, round(ch * SPIN_CROP[2] / SPIN_CROP[3]))
        zoom_to = SPIN_CROP[2] / logo_w  # the logo at the end card's size
        streams = [reel.Frames(CLIPS / f"{rom}.mp4", (cw, ch), when(rom, start)).take(n) for rom, start in cells]
        # Full-size logo frames, phased so the last one is the frame before
        # the end card's first: the turn carries straight on across the cut.
        # (Skipped rather than seeked: a seek and a loop together would
        # restart every loop at the seek point.)
        spin_from = (END_SPIN_FROM - n) % 120
        spin = reel.Frames(reel.SPIN, (SPIN_CROP[2], SPIN_CROP[3]), loop=True, crop=SPIN_CROP).take(spin_from + n)
        for _ in range(spin_from):
            next(spin)
        center = (w // 2, h // 2)
        for i in range(n):
            frame = pygame.Surface(SIZE)
            frame.fill((4, 5, 8))
            beat = i / (BEAT * FPS)
            for k, ((cx, cy), stream) in enumerate(zip(spots, streams)):
                picture = next(stream)
                appear = CELL_EVERY * k
                if beat >= appear:
                    self.flash(picture, max(0.0, 0.7 - (beat - appear) / 0.5))
                    frame.blit(picture, (x0 + cx * (cw + gap), y0 + cy * (ch + gap)))
            logo = next(spin)
            z = 1.0
            into = i - (n - zoom_frames)
            if into >= 0:
                e = ease((into + 1) / zoom_frames)
                z = 1 + (zoom_to - 1) * e
                self.black.set_alpha(round(255 * e))
                frame.blit(self.black, (0, 0))
                view = pygame.Rect(0, 0, round(w / z), round(h / z))
                view.center = center
                frame = pygame.transform.smoothscale(frame.subsurface(view.clip(frame.get_rect())), SIZE)
            size = (round(logo_w * z), round(logo_w * z * SPIN_CROP[3] / SPIN_CROP[2]))
            logo = logo if size == logo.get_size() else pygame.transform.smoothscale(logo, size)
            frame.blit(logo, logo.get_rect(center=center), special_flags=pygame.BLEND_RGB_MAX)
            yield self.tube(frame)

    def draw_end(self, seg: Segment):
        """The logo finishes its turn where the zoom left it, rises, and the
        TUM and MQT logos come up under it, with the music's credit."""
        w, h = SIZE
        n = seg.last - seg.first
        turn_frames = 120 - END_SPIN_FROM  # the rest of the turn, then face on
        if turn_frames:
            spin = reel.Frames(reel.SPIN, SIZE, start=END_SPIN_FROM / FPS).take(turn_frames)
            still = None
        else:  # the mosaic's zoom already ended face on: the spin's first frame
            still = pygame.image.load(str(LOGO_STILL))
        lift_from, lift_frames = frame_at(2), frame_at(1)
        logos_in = frame_at(2.5)
        row_w = sum(img.get_width() for img in self.partners) + 120
        credit = self.credit_font.render(MUSIC_CREDIT, False, (110, 116, 132))
        for i in range(n):
            if i < turn_frames:
                frame = next(spin)
                still = frame.copy() if i == turn_frames - 1 else still
            else:
                frame = still.copy() if still is not None else pygame.Surface(SIZE)
            lift = round(h * END_LIFT * ease((i - lift_from) / lift_frames))
            if lift:
                lifted = pygame.Surface(SIZE)
                lifted.blit(frame, (0, -lift))
                frame = lifted
            if i >= logos_in:
                alpha = min(255, round(255 * (i - logos_in) / (0.5 * FPS)))
                x = (w - row_w) // 2
                for k, img in enumerate(self.partners):
                    img.set_alpha(alpha)
                    frame.blit(img, img.get_rect(midleft=(x, round(h * 0.8))))
                    x += img.get_width() + 120
                    if k == 0:
                        line = pygame.Surface((3, 96))
                        line.fill((90, 96, 110))
                        line.set_alpha(alpha)
                        frame.blit(line, line.get_rect(center=(x - 60, round(h * 0.8))))
                credit.set_alpha(alpha)
                frame.blit(credit, credit.get_rect(midbottom=(w // 2, h - round(h * 0.055))))
            yield self.tube(frame)


def power(frame: pygame.Surface, k: int, frames: int, on: bool) -> pygame.Surface:
    """A tube switching on (the picture opens out of a bright line) or off
    (it collapses into a line, then a dot)."""
    w, h = SIZE
    t = (k + 1) / frames if on else k / frames
    out = pygame.Surface(SIZE)
    if on or t < 0.65:
        open_ = t if on else 1 - t / 0.65
        hh = max(2, round(h * open_ ** 2))
        squeezed = pygame.transform.smoothscale(frame, (w, hh))
        out.blit(squeezed, (0, (h - hh) // 2))
        glow = pygame.Surface((w, max(2, round(6 * (1 - open_) + 2))))
        glow.fill((230, 240, 255))
        glow.set_alpha(round(255 * (1 - open_)))
        out.blit(glow, glow.get_rect(center=(w // 2, h // 2)))
    else:
        s = 1 - (t - 0.65) / 0.35
        lw = max(4, round(w * s ** 3))
        pygame.draw.rect(out, (230, 240, 255), pygame.Rect(0, 0, lw, 3).move((w - lw) // 2, h // 2 - 1))
        if s < 0.3:
            pygame.draw.circle(out, (255, 255, 255), (w // 2, h // 2), max(1, round(8 * s / 0.3)))
    return out


def render_segments(job: tuple[int, list[Segment], Path, int]) -> tuple[Path, list[tuple[str, bytes]]]:
    """Render consecutive segments into one part file."""
    part, segs, out_dir, total_frames = job
    painter = Painter()
    path = out_dir / f"part_{part:02d}.mp4"
    writer = imageio_ffmpeg.write_frames(
        str(path), SIZE, fps=FPS, codec="libx264", pix_fmt_in="rgb24", macro_block_size=1, quality=None,
        output_params=["-crf", "18", "-preset", "medium", "-threads", "4", "-profile:v", "high",
                       "-level", "4.2", "-g", str(2 * FPS), "-an"])
    writer.send(None)
    thumbs = []
    for seg in segs:
        kind, args = seg.kind, seg.args
        if kind == "shot":
            frames = painter.draw_shot(seg, *args)
        elif kind == "card":
            frames = painter.draw_card(seg, *args)
        elif kind == "mosaic":
            frames = painter.draw_mosaic(seg, args)
        elif kind == "intro":
            frames = painter.draw_intro(seg)
        elif kind == "panel":
            frames = painter.draw_panel(seg, args)
        else:
            frames = painter.draw_end(seg)
        n = seg.last - seg.first
        for i, frame in enumerate(frames):
            f = seg.first + i
            if f < POWER_ON_FRAMES:
                frame = power(frame, f, POWER_ON_FRAMES, on=True)
            if f >= total_frames - POWER_OFF_FRAMES:
                frame = power(frame, f - (total_frames - POWER_OFF_FRAMES), POWER_OFF_FRAMES, on=False)
            # Some segments are worth two looks: built up, and at the end.
            looks = {min(4, n - 1)} | ({n * 2 // 3} if kind in ("mosaic", "end", "intro", "panel") else set())
            if i in looks:
                what = f"{args[0]} {args[1]}" if kind == "shot" else args[1] if kind == "card" else ""
                thumbs.append((f"{seg.index}: {kind} {what}",
                               pygame.image.tostring(pygame.transform.smoothscale(frame, (256, 144)), "RGB")))
            writer.send(pygame.image.tostring(frame, "RGB"))
        if seg is segs[-1] and seg.kind == "end":
            black = pygame.image.tostring(pygame.Surface(SIZE), "RGB")
            for _ in range(TAIL_FRAMES):
                writer.send(black)
    writer.close()
    return path, thumbs


# --- sound --------------------------------------------------------------------


def to_rate(samples: np.ndarray, rate: int) -> np.ndarray:
    """Mono float samples from `rate` to RATE (linear interpolation is fine
    for the games' synthesised effects)."""
    if rate == RATE or len(samples) == 0:
        return samples
    n = round(len(samples) * RATE / rate)
    return np.interp(np.arange(n) * rate / RATE, np.arange(len(samples)), samples).astype(np.float32)


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path)) as f:
        data = np.frombuffer(f.readframes(f.getnframes()), np.int16).astype(np.float32) / 32768
        data = data.reshape(-1, f.getnchannels()).mean(axis=1)
        return data, f.getframerate()


def place(track: np.ndarray, at: float, samples: np.ndarray, gain: float = 1.0) -> None:
    """Add mono or stereo `samples` into the stereo `track` at `at` seconds."""
    start = round(at * RATE)
    end = min(len(track), start + len(samples))
    if start < end:
        piece = samples[: end - start] * gain
        track[start:end] += piece if piece.ndim == 2 else piece[:, None]


def lowpass_sweep(x: np.ndarray, seconds: float, f0: float, f1: float) -> np.ndarray:
    """Open a two-pole low-pass from f0 to f1 Hz (exponentially) over the
    first `seconds`; the rest passes untouched. Done in blocks of 64 samples
    so the coefficient can move without a Python loop per sample."""
    n = min(len(x), round(seconds * RATE))
    out = x.copy()
    y1 = np.zeros(x.shape[1], np.float32)
    y2 = np.zeros(x.shape[1], np.float32)
    for b in range(0, n, 64):
        f = f0 * (f1 / f0) ** (b / n)
        a = 1 - math.exp(-2 * math.pi * f / RATE)
        block = x[b:min(n, b + 64)]
        res = np.empty_like(block)
        for i in range(len(block)):
            y1 += a * (block[i] - y1)
            y2 += a * (y1 - y2)
            res[i] = y2
        out[b:b + len(block)] = res
    # cross-fade the last 20 ms into the dry signal, so nothing clicks
    k = round(0.02 * RATE)
    if n > k:
        fade = np.linspace(0, 1, k, dtype=np.float32)[:, None]
        out[n - k:n] = out[n - k:n] * (1 - fade) + x[n - k:n] * fade
    return out


def reverb(x: np.ndarray, seconds: float = 3.5, seed: int = 5) -> np.ndarray:
    """A plain synthetic hall: convolution with decaying, slightly different
    noise in each channel. Returns the wet signal, `seconds` longer than x."""
    rng = np.random.default_rng(seed)
    n = round(seconds * RATE)
    decay = np.exp(-6.9 * np.arange(n) / n).astype(np.float32)  # -60 dB at the end
    out = np.zeros((len(x) + n - 1, 2), np.float32)
    size = 1 << (len(x) + n - 2).bit_length()
    for c in range(2):
        ir = rng.standard_normal(n).astype(np.float32) * decay
        ir[: round(0.01 * RATE)] *= np.linspace(0, 1, round(0.01 * RATE))  # no hard onset
        ir /= np.sqrt(np.sum(ir ** 2))
        out[:, c] = np.fft.irfft(np.fft.rfft(x[:, c], size) * np.fft.rfft(ir, size), size)[: len(out)]
    return out


def music(total: float) -> np.ndarray:
    """The track from music_start() to MUSIC_END, filtered in under the intro,
    then cut on that beat with a reverse cymbal into a crash, and the last
    bars ringing on in a reverb tail under the end card."""
    length = MUSIC_END - music_start()
    raw = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-ss", f"{music_start():.4f}",
                          "-i", str(MUSIC), "-t", f"{length + 0.05:.4f}", "-ac", "2", "-ar", str(RATE),
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    dry = np.frombuffer(raw, np.int16).astype(np.float32).reshape(-1, 2) / 32768
    end = round(length * RATE)
    dry = dry[:end].copy()
    # In: from a muffled 250 Hz to fully open over the intro, and up from silence.
    intro = TIMELINE[0][0] * BEAT
    dry = lowpass_sweep(dry, intro, 250, 18000)
    rise = round(1.2 * RATE)
    dry[:rise] *= np.linspace(0, 1, rise, dtype=np.float32)[:, None] ** 2
    dry[-round(0.01 * RATE):] *= np.linspace(1, 0, round(0.01 * RATE), dtype=np.float32)[:, None]

    track = np.zeros((round(total * RATE), 2), np.float32)
    place(track, 0, dry, MUSIC_GAIN)
    # The last two bars ring on: their reverb, starting where they do.
    ring = round(8 * BEAT * RATE)
    tail = reverb(dry[-ring:] * MUSIC_GAIN, 6.0)
    place(track, length - ring / RATE, tail, 0.6)
    rng = np.random.default_rng(11)
    # A reverse cymbal: bright noise swelling over two beats into the cut.
    swell = round(2 * BEAT * RATE)
    noise = rng.standard_normal((swell, 2)).astype(np.float32)
    noise[1:] -= 0.85 * noise[:-1]  # tip it towards the highs
    env = (np.linspace(0, 1, swell, dtype=np.float32) ** 3)[:, None]
    place(track, length - swell / RATE, noise * env, 0.09)
    # The crash on the cut, with a low hit under it, into the same hall.
    crash_n = round(3.0 * RATE)
    crash = rng.standard_normal((crash_n, 2)).astype(np.float32)
    crash[1:] -= 0.9 * crash[:-1]
    crash *= np.exp(-np.arange(crash_n) / (0.9 * RATE)).astype(np.float32)[:, None]
    boom_n = round(0.9 * RATE)
    tt = np.arange(boom_n) / RATE
    boom = (np.sin(2 * np.pi * (58 * tt - 9 * tt * tt)) * np.exp(-tt / 0.25)).astype(np.float32)
    hit = crash * 0.12
    hit[:boom_n] += boom[:, None] * 0.5
    place(track, length, hit)
    place(track, length, reverb(hit, 5.0, seed=6), 0.45)
    return track


def active_rms(x: np.ndarray, window: float = 0.05, floor_db: float = -50.0) -> float:
    """RMS over the windows that have sound in them: how loud the effects
    are while they play, not averaged with the silence between them."""
    n = round(window * RATE)
    blocks = x[: len(x) // n * n].reshape(-1, n)
    levels = np.sqrt((blocks ** 2).mean(axis=1))
    on = levels[levels > 10 ** (floor_db / 20)]
    return float(np.sqrt((on ** 2).mean())) if len(on) else 0.0


def soundtrack(segs: list[Segment], total: float) -> np.ndarray:
    track = music(total)
    games: dict[str, tuple[np.ndarray, int]] = {}
    fade = np.linspace(0, 1, round(0.005 * RATE), dtype=np.float32)
    pieces: list[tuple[str, float, np.ndarray]] = []
    for seg in segs:
        if seg.kind != "shot":
            continue
        rom, start = seg.args[0], when(seg.args[0], seg.args[1])
        wav = CLIPS / f"{rom}.wav"
        if not wav.is_file():
            continue  # Ion Surfer has no sound
        if rom not in games:
            games[rom] = read_wav(wav)
        data, rate = games[rom]
        dur = (seg.last - seg.first) / FPS
        piece = to_rate(data[round(start * rate): round((start + dur) * rate)], rate).copy()
        if len(piece) > 2 * len(fade):
            piece[: len(fade)] *= fade
            piece[-len(fade):] *= fade[::-1]
        pieces.append((rom, seg.first / FPS, piece))
    # One gain per game, from all of its excerpts together.
    gains = {}
    for rom in dict.fromkeys(r for r, _, _ in pieces):
        level = active_rms(np.concatenate([p for r, _, p in pieces if r == rom]))
        db = SFX_TARGET - 20 * math.log10(level) if level > 0 else 0.0
        db = min(max(db, SFX_GAIN_RANGE[0]), SFX_GAIN_RANGE[1])
        gains[rom] = 10 ** (db / 20)
        print(f"  effects {rom:<16} {20 * math.log10(level) if level else -99:6.1f} dBFS -> {db:+5.1f} dB")
    sfx = np.zeros_like(track)
    for rom, at, piece in pieces:
        place(sfx, at, piece, gains[rom])
    sfx = SFX_LIMIT * np.tanh(sfx / SFX_LIMIT)
    track += sfx * SFX_GAIN
    # The tube going off: a falling sine, and silence after it.
    off = (segs[-1].last - POWER_OFF_FRAMES) / FPS
    gone = round((off + POWER_OFF_FRAMES / FPS) * RATE)
    fade_n = round(0.4 * RATE)
    track[gone - fade_n:gone] *= np.linspace(1, 0, fade_n, dtype=np.float32)[:, None]
    track[gone:] = 0
    sweep = np.sin(2 * np.pi * np.cumsum(np.linspace(1400, 210, round(0.4 * RATE)) / RATE))
    sweep *= np.exp(-np.linspace(0, 2.0, len(sweep))) * 0.18
    place(track, off, sweep.astype(np.float32))
    peak = float(np.max(np.abs(track))) or 1.0
    return track * min(1.0, 0.89 / peak)


# --- putting it together ------------------------------------------------------


def write_sound(segs: list[Segment], total: float, path: Path) -> None:
    sound = soundtrack(segs, total)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes((np.clip(sound, -1, 1) * 32767).astype(np.int16).tobytes())


def remix() -> None:
    """Only the sound again, under the picture already rendered: for changes
    to the mix, which don't need minutes of video."""
    segs = segments()
    total = (segs[-1].last + TAIL_FRAMES) / FPS
    out = OUT_DIR / f"{OUT_NAME}.mp4"
    if not out.is_file():
        raise SystemExit(f"no {out.relative_to(REPO)} to remix: render it first")
    wav = OUT_DIR / "sound.wav"
    tmp = OUT_DIR / "remix.mp4"
    write_sound(segs, total, wav)
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-y", "-i", str(out), "-i", str(wav),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                    "-movflags", "+faststart", str(tmp)], check=True)
    tmp.replace(out)
    wav.unlink()
    print(f"remixed {out.relative_to(REPO)}")


def main() -> None:
    use("short" if "--short" in sys.argv[1:] else "full")
    if "--audio-only" in sys.argv[1:]:
        remix()
        return
    segs = segments()
    total_frames = segs[-1].last
    total = (total_frames + TAIL_FRAMES) / FPS
    roms = {s.args[0] for s in segs if s.kind == "shot"} | {c[0] for s in segs if s.kind in ("mosaic", "panel")
                                                            for c in s.args}
    missing = sorted(r for r in roms if not (CLIPS / f"{r}.mp4").is_file())
    if missing:
        raise SystemExit(f"no clip for {', '.join(missing)}: run capture.py")
    for s in segs:  # resolve every named start now, so a typo fails before rendering
        for rom, start in ([s.args[:2]] if s.kind == "shot" else s.args if s.kind in ("mosaic", "panel") else []):
            when(rom, start)
    print(f"{len(segs)} segments, {total:.1f} s; music {music_start():.2f}-{MUSIC_END:.2f} s of the track, "
          f"cut at {outro_beat() * BEAT:.2f} s into the trailer", flush=True)
    OUT_DIR.mkdir(exist_ok=True)
    parts_dir = OUT_DIR / "parts"
    parts_dir.mkdir(exist_ok=True)

    # Spread the segments over the workers by frame count, keeping order.
    workers = min(os.cpu_count() or 1, WORKERS)
    share = total_frames / workers
    jobs: list[list[Segment]] = [[]]
    for seg in segs:
        if jobs[-1] and sum(s.last - s.first for s in jobs[-1]) >= share:
            jobs.append([])
        jobs[-1].append(seg)
    with multiprocessing.get_context("fork").Pool(len(jobs)) as pool:
        results = pool.map(render_segments, [(i, job, parts_dir, total_frames) for i, job in enumerate(jobs)])

    video = parts_dir / "video.mp4"
    listing = parts_dir / "parts.txt"
    listing.write_text("".join(f"file '{path.name}'\n" for path, _ in results))
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ffmpeg, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-c", "copy", str(video)], check=True)

    wav = parts_dir / "sound.wav"
    write_sound(segs, total, wav)
    out = OUT_DIR / f"{OUT_NAME}.mp4"
    subprocess.run([ffmpeg, "-v", "error", "-y", "-i", str(video), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                    str(out)], check=True)
    print(f"wrote {out.relative_to(REPO)}: {total:.1f} s, {out.stat().st_size / 1e6:.1f} MB")
    shutil.rmtree(parts_dir)

    thumbs = [t for _, row in results for t in row]
    cols = 8
    sheet = pygame.Surface((cols * 256, -(-len(thumbs) // cols) * 144))
    pygame.font.init()
    label_font = pygame.font.Font(None, 22)
    for i, (label, data) in enumerate(thumbs):
        x, y = (i % cols) * 256, (i // cols) * 144
        sheet.blit(pygame.image.frombuffer(data, (256, 144), "RGB"), (x, y))
        sheet.blit(label_font.render(label, True, (255, 255, 0), (0, 0, 0)), (x + 3, y + 3))
    sheet_path = OUT_DIR.with_name(f"{OUT_NAME.removeprefix('arqade_')}-sheet.png")
    pygame.image.save(sheet, str(sheet_path))
    print(f"wrote {sheet_path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
