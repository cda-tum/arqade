"""Cut a ~40 s ARQADE trailer from the attract footage. V2, for internal use.

    launcher/.venv/bin/python batocera/attract/build_trailer.py

Writes trailer/arqade_trailer.mp4 (1920x1080, 30 fps, AAC stereo) and
trailer-sheet.png (a frame of every shot).

Nothing in it is new material:

- the gameplay and its sound effects are the attract captures in clips/
  (capture.py writes <rom>.wav beside each <rom>.mp4, in sync);
- the music is a placeholder from Batocera's own menu music, Bolt Action's
  "Some Potential" (trailer_assets/, licence in CREDITS.md). It runs at
  exactly 132 BPM and drops at 58.15 s, so the edit is laid out in beats and
  MUSIC_START puts the drop on the AND MANY MORE card: the build carries the
  four concept cards, everything after it runs at full tilt;
- the logo spin, the CRT tube and the marquees are the reels' own;
- the TUM and MQT logos are in trailer_assets/ (see CREDITS.md).

The edit is TIMELINE below, in beats: the tube powers on into a cold open,
four cards each followed by the game that is about it, AND MANY MORE with
two more games, two beats of every game, cuts that halve in length, all
eight games at once around the logo, a zoom into the logo in the middle,
the logo coming to rest over the TUM and MQT logos, and the tube powering
off. Change a line there and re-run; a different track needs MUSIC, BPM and
MUSIC_START.

Footage is cut from each bot's HIGHLIGHTS (2 s windows checked frame by
frame); shots longer than that run on past the checked part.
"""

from __future__ import annotations

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
ASSETS = HERE / "trailer_assets"
OUT_DIR = HERE / "trailer"
FONT = reel.FONT
logging.getLogger("imageio_ffmpeg").setLevel(logging.ERROR)

SIZE = (1920, 1080)
FPS = 30
RATE = 48000  # the trailer's audio
BLUE = reel.BLUE
WHITE = (238, 238, 246)

MUSIC = ASSETS / "Bolt Action - Some Potential.ogg"
MUSIC_CREDIT = 'MUSIC: BOLT ACTION - "SOME POTENTIAL"'
BPM = 132.0  # measured: onsets line up to 0.01 BPM over the whole loud part
BEAT = 60 / BPM
DROP_AT = 58.151  # s into the track: the first beat of the loud part
DROP_BEAT = 36  # the trailer's beat that lands on it: the AND MANY MORE card
MUSIC_START = DROP_AT - DROP_BEAT * BEAT  # where in the track the trailer starts

# (beats, kind, args). Kinds: shot (rom, start s, marquee?), card (kicker or
# None, line), grid (rom, start s) x8, end.
TIMELINE = [
    (4, "shot", ("quantum_pong", 12.7, True)),  # cold open: an H gate splits the ball
    (3, "card", ("FIND YOURSELF IN", "SUPERPOSITION")),
    (5, "shot", ("qurves", 9.7, True)),  # every bike splits into ghost copies
    (3, "card", ("BECOME", "ENTANGLED")),
    (5, "shot", ("overquqed", 21.2, True)),  # both chefs on the Waffle Iron: ENTANGLED!
    (3, "card", ("APPLY", "QUANTUM GATES")),
    (5, "shot", ("gate_drop", 4.3, True)),  # gates cancel, a CNOT, a chain
    (3, "card", ("FIGHT", "QUANTUM ERRORS")),
    (5, "shot", ("error_invaders", 29.0, True)),  # the LOGICAL ERROR chain shot apart
    (3, "card", (None, "AND MANY MORE")),  # on the drop
    (2.5, "shot", ("ion_surfer", 59.6, True)),
    (2.5, "shot", ("superconductor", 71.9, True)),
    # two beats of every game
    (2, "shot", ("quantum_towers", 74.3, True)),
    (2, "shot", ("quantum_pong", 16.9, True)),
    (2, "shot", ("error_invaders", 37.5, True)),
    (2, "shot", ("qurves", 54.4, True)),
    (2, "shot", ("gate_drop", 55.1, True)),
    (2, "shot", ("overquqed", 37.2, True)),
    (2, "shot", ("ion_surfer", 34.0, True)),
    (2, "shot", ("superconductor", 57.3, True)),
    # faster: a beat each, then half a beat each
    (1, "shot", ("quantum_towers", 60.2, False)),
    (1, "shot", ("error_invaders", 2.0, False)),
    (1, "shot", ("ion_surfer", 70.4, False)),
    (1, "shot", ("gate_drop", 15.0, False)),
    (0.5, "shot", ("quantum_pong", 53.7, False)),
    (0.5, "shot", ("qurves", 17.5, False)),
    (0.5, "shot", ("overquqed", 29.9, False)),
    (0.5, "shot", ("superconductor", 17.8, False)),
    (0.5, "shot", ("quantum_towers", 6.7, False)),
    (0.5, "shot", ("error_invaders", 48.5, False)),
    (0.5, "shot", ("gate_drop", 36.0, False)),
    (0.5, "shot", ("qurves", 23.6, False)),
    # all eight around the logo, one cell per half beat, clockwise from top
    # left; the last ZOOM_BEATS zoom into the logo in the middle
    (8, "grid", (("quantum_pong", 70.9), ("quantum_towers", 70.6), ("error_invaders", 31.5),
                 ("ion_surfer", 65.1), ("superconductor", 49.3), ("overquqed", 55.0),
                 ("qurves", 73.5), ("gate_drop", 49.0))),
    (10.5, "end", ()),
]
ZOOM_BEATS = 2
POWER_ON_FRAMES = 10
POWER_OFF_FRAMES = 12
TAIL_FRAMES = 12  # black after the tube goes off
SFX_GAIN = 0.6
MUSIC_GAIN = 0.75
MUSIC_FADE_OUT = 2.5  # s, ending with the tube
# Render processes. Each holds a 1080p tube, decoders and an x264 encoder:
# eight at once ran a 16 GB machine out of memory.
WORKERS = 3
SPIN_CROP = (200, 280, 1520, 520)  # where the logo turns in the 1920x1080 spin
END_SPIN_FROM = 10  # the end card's spin starts here: the zoom before it sees the logo face on
END_LIFT = 0.08  # of the height: the logo rises to make room for the partner logos


def frame_at(beats: float) -> int:
    return round(beats * BEAT * FPS)


def ease(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


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


# --- pictures -----------------------------------------------------------------


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

    def draw_shot(self, seg: Segment, rom: str, start: float, show_tag: bool):
        n = seg.last - seg.first
        flash = (0.6, 0.3, 0.1) if seg.beats >= 4 else (0.25,)
        for i, frame in enumerate(reel.Frames(CLIPS / f"{rom}.mp4", SIZE, start).take(n)):
            self.flash(frame, flash[i] if i < len(flash) else 0)
            frame = self.tube(frame)
            tag = self.tag(rom) if show_tag else None
            if tag is not None:
                frame.blit(tag, tag.get_rect(bottomleft=(self.margin[0], SIZE[1] - self.margin[1])))
            yield frame

    def draw_card(self, seg: Segment, kicker: str | None, line: str):
        """A small blue lead-in over the big line, typed out over most of a
        beat, with a blue rule growing under it. The card on the drop flashes."""
        w, h = SIZE
        n = seg.last - seg.first
        typing = max(1, round(0.7 * BEAT * FPS))
        full = self.word_font.size(line)
        left = (w - full[0]) // 2
        lead = self.kicker_font.render(kicker, False, BLUE) if kicker else None
        on_drop = seg.start == DROP_BEAT
        for i in range(n):
            frame = pygame.Surface(SIZE)
            grow = min(1.0, (i + 1) / typing)
            shown = line[: max(1, math.ceil(len(line) * grow))]
            if lead is not None:
                frame.blit(lead, lead.get_rect(bottomleft=(left, h // 2 - full[1] // 2 - 22)))
            frame.blit(self.word_font.render(shown, False, WHITE), (left, h // 2 - full[1] // 2))
            pygame.draw.rect(frame, BLUE, (left, h // 2 + full[1] // 2 + 22, round(full[0] * grow), 6))
            if on_drop:
                self.flash(frame, (0.9, 0.6, 0.35, 0.15)[i] if i < 4 else 0)
            yield self.tube(frame)

    def draw_grid(self, seg: Segment, cells: tuple):
        """The eight games around the turning logo, then a zoom into the
        logo: the cells fade out while the middle cell grows until its logo is
        exactly the size and turn of the end card's first frame."""
        w, h = SIZE
        gap = 20
        cw, ch = (h - 4 * gap) // 3 * 16 // 9, (h - 4 * gap) // 3
        x0 = (w - (3 * cw + 2 * gap)) // 2
        spots = [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2), (1, 2), (0, 2), (0, 1)]  # clockwise
        n = seg.last - seg.first
        zoom_frames = frame_at(ZOOM_BEATS)
        zoom_to = SPIN_CROP[2] / cw  # the cell's logo at the end card's size
        streams = [reel.Frames(CLIPS / f"{rom}.mp4", (cw, ch), start).take(n) for rom, start in cells]
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
                appear = 0.5 * k
                if beat >= appear:
                    self.flash(picture, max(0.0, 0.7 - (beat - appear) / 0.5))
                    frame.blit(picture, (x0 + cx * (cw + gap), gap + cy * (ch + gap)))
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
            size = (round(cw * z), round(cw * z * SPIN_CROP[3] / SPIN_CROP[2]))
            logo = logo if size == logo.get_size() else pygame.transform.smoothscale(logo, size)
            frame.blit(logo, logo.get_rect(center=center), special_flags=pygame.BLEND_RGB_MAX)
            yield self.tube(frame)

    def draw_end(self, seg: Segment):
        """The logo finishes its turn where the zoom left it, rises, and the
        TUM and MQT logos come up under it."""
        w, h = SIZE
        n = seg.last - seg.first
        turn_frames = 120 - END_SPIN_FROM  # the rest of the turn, then face on
        spin = reel.Frames(reel.SPIN, SIZE, start=END_SPIN_FROM / FPS).take(turn_frames)
        still = None
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
        elif kind == "grid":
            frames = painter.draw_grid(seg, args)
        else:
            frames = painter.draw_end(seg)
        n = seg.last - seg.first
        for i, frame in enumerate(frames):
            f = seg.first + i
            if f < POWER_ON_FRAMES:
                frame = power(frame, f, POWER_ON_FRAMES, on=True)
            if f >= total_frames - POWER_OFF_FRAMES:
                frame = power(frame, f - (total_frames - POWER_OFF_FRAMES), POWER_OFF_FRAMES, on=False)
            # The grid and the end card are worth two looks: built up, and at the end.
            looks = {min(4, n - 1)} | ({n * 2 // 3} if kind in ("grid", "end") else set())
            if i in looks:
                label = f"{seg.index}: {kind} {args[0] if kind == 'shot' else args[1] if kind == 'card' else ''}"
                thumbs.append((label, pygame.image.tostring(pygame.transform.smoothscale(frame, (256, 144)), "RGB")))
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
    """Add mono `samples` into the stereo `track` at `at` seconds."""
    start = round(at * RATE)
    end = min(len(track), start + len(samples))
    if start < end:
        track[start:end] += (samples[: end - start] * gain)[:, None]


def music(total: float) -> np.ndarray:
    """The track from MUSIC_START, in stereo, faded in briefly and out at the end."""
    raw = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-ss", f"{MUSIC_START:.4f}",
                          "-i", str(MUSIC), "-t", f"{total:.4f}", "-ac", "2", "-ar", str(RATE),
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    track = np.zeros((round(total * RATE), 2), np.float32)
    data = np.frombuffer(raw, np.int16).astype(np.float32).reshape(-1, 2) / 32768
    track[: len(data)] = data[: len(track)]
    fade_in = round(0.15 * RATE)
    track[:fade_in] *= np.linspace(0, 1, fade_in, dtype=np.float32)[:, None]
    return track * MUSIC_GAIN


def soundtrack(segs: list[Segment], total: float) -> np.ndarray:
    track = music(total)
    games: dict[str, tuple[np.ndarray, int]] = {}
    fade = np.linspace(0, 1, round(0.005 * RATE), dtype=np.float32)
    for seg in segs:
        if seg.kind != "shot":
            continue
        rom, start = seg.args[0], seg.args[1]
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
        place(track, seg.first / FPS, piece, SFX_GAIN)
    # Fade the music with the end card, ending as the tube goes off.
    off = (segs[-1].last - POWER_OFF_FRAMES) / FPS
    a, b = round((off + POWER_OFF_FRAMES / FPS - MUSIC_FADE_OUT) * RATE), round((off + POWER_OFF_FRAMES / FPS) * RATE)
    track[a:b] *= np.linspace(1, 0, b - a, dtype=np.float32)[:, None]
    track[b:] = 0
    sweep = np.sin(2 * np.pi * np.cumsum(np.linspace(1400, 210, round(0.4 * RATE)) / RATE))
    sweep *= np.exp(-np.linspace(0, 2.0, len(sweep))) * 0.18
    place(track, off, sweep.astype(np.float32))
    peak = float(np.max(np.abs(track))) or 1.0
    return track * min(1.0, 0.89 / peak)


# --- putting it together ------------------------------------------------------


def main() -> None:
    segs = segments()
    total_frames = segs[-1].last
    total = (total_frames + TAIL_FRAMES) / FPS
    missing = sorted({s.args[0] for s in segs if s.kind == "shot" and not (CLIPS / f"{s.args[0]}.mp4").is_file()})
    if missing:
        raise SystemExit(f"no clip for {', '.join(missing)}: run capture.py")
    drop = next(s for s in segs if s.start == DROP_BEAT)
    print(f"{len(segs)} segments, {total:.1f} s; the drop lands on segment {drop.index} ({drop.kind} "
          f"{drop.args[-1]}) at {drop.first / FPS:.2f} s", flush=True)
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

    sound = soundtrack(segs, total)
    wav = parts_dir / "sound.wav"
    with wave.open(str(wav), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes((np.clip(sound, -1, 1) * 32767).astype(np.int16).tobytes())
    out = OUT_DIR / "arqade_trailer.mp4"
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
    sheet_path = OUT_DIR.with_name("trailer-sheet.png")
    pygame.image.save(sheet, str(sheet_path))
    print(f"wrote {sheet_path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
