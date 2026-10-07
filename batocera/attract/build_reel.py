"""Cut the attract reels: the spinning logo, then rapid-fire gameplay cuts.

    launcher/.venv/bin/python batocera/attract/build_reel.py
    launcher/.venv/bin/python batocera/attract/build_reel.py --reels 6 --size 1920x1080

Reads the captures in clips/ (capture.py) and writes reels/arqade_reel_<n>.mp4
next to this file, plus reels-sheet.png (the first frame of every cut, one row
per reel) to check them. The cabinet plays them as EmulationStation's
screensaver and the launcher as its attract mode. Both pick a reel at random,
play it to the end and pick again, until someone touches a control. Several
short reels rather than one long one is what keeps it varied: every pick is a
different selection of moments.

Each reel is LOGO_TURNS turns of the ARQADE logo with a blinking PRESS ANY
BUTTON under it, then CUTS hard cuts of CUT_SECONDS each: about 20 s of
gameplay, every game at least once, never the same game twice in a row. A cut
is the game's own footage, letterboxed the way the panel shows it, with the
game's marquee (batocera/logos/<rom>-marquee.png) bottom left and a steady
PRESS ANY BUTTON badge bottom right. The whole picture is shown on a curved
CRT tube -- scanlines, vignette, rounded glass -- so it reads as a recording
playing, not as a game waiting for input. The marquee and badge sit on top of
the glass, so they stay sharp.

The reels are 1280x720 by default, though the captures are 1080p: on the Pi 4,
EmulationStation's screensaver decodes H.264 in software through libVLC and
uploads every frame as a texture, and 720p is about half the work (see
README.md). ES scales it up to fill the panel.

Where to cut comes from each bot's HIGHLIGHTS (bots/<rom>.py), best first,
each the start of a 2 s window; a game without enough of them gets its
busiest stretches after SKIP, measured as the frame-to-frame change in a small
greyscale copy of the clip. Each moment is used once across all reels before
any is used again.
"""

from __future__ import annotations

import argparse
import ast
import logging
import multiprocessing
import os
import random
import xml.etree.ElementTree as ET
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import pygame

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CLIPS = HERE / "clips"
BOTS = HERE / "bots"
OUT_DIR = HERE / "reels"
SPIN = REPO / "logos" / "animation" / "arqade_loading_v3_1080p.webm"
GAMELIST = REPO / "batocera" / "gamelist.xml"
MARQUEES = REPO / "batocera" / "logos"
FONT = REPO / "launcher" / "src" / "arqade_launcher" / "assets" / "fonts" / "PressStart2P-Regular.ttf"
logging.getLogger("imageio_ffmpeg").setLevel(logging.ERROR)  # "frame size differs" on every scaled read

FPS = 30
REELS = 4
LOGO_TURNS = 3
TURN_SECONDS = 4.0  # the spin's own pace: one seamless turn is 120 frames
CUTS = 11  # per reel: about 20 s of gameplay
CUT_SECONDS = 1.8
CUT_LEAD = 0.1  # start this far into a 2 s highlight window
WINDOW = 2.0  # what a highlight (or a busiest stretch) covers
PROMPT = "PRESS ANY BUTTON"
BLUE = (49, 112, 179)  # the ARQADE blue, #3170B3
FIRST_FLASH = (0.85, 0.55, 0.3, 0.12)  # white over the first cut after the logo
CUT_FLASH = (0.28, 0.1)  # ...and a lighter flick on every cut after it
FADE_IN_FRAMES = 5  # the logo comes up from black
SEED = 7


# --- what to cut --------------------------------------------------------------


def bot_settings(rom: str) -> dict:
    """SKIP, HIGHLIGHTS, ... read from the bot module without importing it
    (importing would import the game, too)."""
    path = BOTS / f"{rom}.py"
    if not path.is_file():
        return {}
    values = {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                values[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return values


def menu_order() -> list[str]:
    root = ET.parse(GAMELIST).getroot()
    return [Path((g.findtext("path") or "").strip()).stem for g in root.iter("game")]


def busiest(clip: Path, skip: float, count: int, avoid: list[float]) -> list[float]:
    """Start times of up to `count` non-overlapping windows with the most
    motion, clear of the windows starting at `avoid`."""
    w, h = 64, 36
    reader = imageio_ffmpeg.read_frames(str(clip), pix_fmt="gray", bpp=1, output_params=["-vf", f"scale={w}:{h}"])
    next(reader)
    frames = np.array([np.frombuffer(f, np.uint8) for f in reader], dtype=np.float32)
    motion = np.abs(np.diff(frames, axis=0)).mean(axis=1)
    n = int(WINDOW * FPS)
    scores = np.convolve(motion, np.ones(n), "valid")
    first = int(skip * FPS)
    taken = [round(a * FPS) for a in avoid]
    picked: list[int] = []
    for i in np.argsort(scores)[::-1]:
        if i < first or any(abs(i - p) < n for p in taken + picked):
            continue
        picked.append(int(i))
        if len(picked) == count:
            break
    return [p / FPS for p in picked]


def moments(roms: list[str], clips: Path, need: int) -> dict[str, list[float]]:
    """Per game, at least `need` start times: its HIGHLIGHTS, then busiest stretches."""
    found = {}
    for rom in roms:
        settings = bot_settings(rom)
        starts = [float(s) for s in settings.get("HIGHLIGHTS") or []]
        own = len(starts)
        if len(starts) < need:
            starts += busiest(clips / f"{rom}.mp4", float(settings.get("SKIP", 3.0)), need - len(starts), starts)
        found[rom] = starts
        print(f"{rom:<16} {own} highlights{f' + {len(starts) - own} busiest' if len(starts) > own else ''}")
    return found


def plan(roms: list[str], starts: dict[str, list[float]], reels: int) -> list[list[tuple[str, float]]]:
    """The cuts of each reel: (rom, start second). Every game in every reel,
    the rest of the slots shared out evenly, no game twice in a row, and each
    game's moments dealt out in turn so a moment repeats only once all of that
    game's moments have been shown."""
    rng = random.Random(SEED)
    next_moment = {rom: 0 for rom in roms}
    extra_turn = 0
    out = []
    for _ in range(reels):
        picks = list(roms)
        while len(picks) < CUTS:
            picks.append(roms[extra_turn % len(roms)])
            extra_turn += 1
        for _ in range(100):  # shuffle until no game follows itself
            rng.shuffle(picks)
            if all(a != b for a, b in zip(picks, picks[1:])):
                break
        cuts = []
        for rom in picks[:CUTS]:
            options = starts[rom]
            cuts.append((rom, options[next_moment[rom] % len(options)] + CUT_LEAD))
            next_moment[rom] += 1
        out.append(cuts)
    return out


# --- the picture --------------------------------------------------------------


class Frames:
    """Raw RGB frames from a video, at the reel's size."""

    def __init__(self, path: Path, size: tuple[int, int], start: float = 0.0, loop: bool = False,
                 crop: tuple[int, int, int, int] | None = None):
        params = ["-stream_loop", "-1"] if loop else []
        if start:
            params += ["-ss", f"{start:.3f}"]
        cut = f"crop={crop[2]}:{crop[3]}:{crop[0]}:{crop[1]}," if crop else ""
        self.reader = imageio_ffmpeg.read_frames(
            str(path), input_params=params,
            output_params=["-vf", f"{cut}scale={size[0]}:{size[1]}:flags=area"])
        next(self.reader)
        self.size = size

    def take(self, count: int):
        for _ in range(count):
            yield pygame.image.frombuffer(bytearray(next(self.reader)), self.size, "RGB")
        self.reader.close()


class Tube:
    """A curved CRT screen: barrel curvature, scanlines, vignette, rounded
    glass with a faintly lit black and a faint reflection, in a black bezel.
    Everything that doesn't depend on the picture is worked out once; per
    frame it is one bilinear remap and a multiply, in integer maths."""

    CURVE = (0.035, 0.05)  # how far the corners bow out, x and y
    SCANLINES = 240  # a 240-line tube: one every 3 px at 720p, 4.5 px at 1080p
    SCANLINE_DEPTH = 0.2
    VIGNETTE = 0.42
    CORNER = 0.07  # glass corner radius, as a fraction of the height
    GAIN = 1.1  # makes up for the light the mask takes
    PHOSPHOR = (7, 9, 12)  # a tube's black is never quite black
    GLARE = 7

    def __init__(self, size: tuple[int, int]):
        w, h = size
        self.size = size
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        u, v = (xs + 0.5) / w * 2 - 1, (ys + 0.5) / h * 2 - 1
        # Classic CRT-shader curvature: each axis bows with the other's square.
        su = u * (1 + self.CURVE[0] * v * v)
        sv = v * (1 + self.CURVE[1] * u * u)
        sx = np.clip((su + 1) / 2 * w - 0.5, 0, w - 1.001)
        sy = np.clip((sv + 1) / 2 * h - 0.5, 0, h - 1.001)
        x0, y0 = np.floor(sx).astype(np.int32), np.floor(sy).astype(np.int32)
        fx, fy = sx - x0, sy - y0
        self.index = [(y0 + dy) * w + (x0 + dx) for dy in (0, 1) for dx in (0, 1)]
        weights = [np.round(((1 - fx) if dx == 0 else fx) * ((1 - fy) if dy == 0 else fy) * 256)
                   for dy in (0, 1) for dx in (0, 1)]
        weights[-1] = 256 - weights[0] - weights[1] - weights[2]  # exactly 256 in all
        self.weight = [wt.astype(np.uint16)[..., None] for wt in weights]

        # The glass: a rounded rectangle around the bowed picture, soft-edged.
        inside = np.clip(1 - np.maximum(np.abs(su), np.abs(sv)), 0, None)
        r = self.CORNER * 2
        cu = np.clip(np.abs(su) - (1 - r * h / w), 0, None) / (r * h / w)
        cv = np.clip(np.abs(sv) - (1 - r), 0, None) / r
        corner = np.clip((1 - np.sqrt(cu * cu + cv * cv)) * 18, 0, 1)
        glass = np.clip(inside * 120, 0, 1) * corner
        scan = 1 - self.SCANLINE_DEPTH * (0.5 - 0.5 * np.cos(2 * np.pi * (ys + 0.5) * self.SCANLINES / h))
        vignette = np.clip(1 - self.VIGNETTE * (0.6 * su * su + 0.4 * sv * sv) ** 1.4, 0, 1)
        self.mask = np.round(glass * scan * vignette * self.GAIN * 256).astype(np.uint32)[..., None]
        # The lit black and a soft reflection of a window, top left.
        glare = np.clip(1 - np.hypot((u + 0.55) / 0.6, (v + 0.65) / 0.35), 0, 1) ** 2 * self.GLARE
        floor = np.array(self.PHOSPHOR, np.float32) * vignette[..., None] + glare[..., None]
        self.floor = np.round(floor * glass[..., None]).astype(np.uint32)

    def __call__(self, frame: pygame.Surface) -> pygame.Surface:
        w, h = self.size
        flat = np.frombuffer(pygame.image.tostring(frame, "RGB"), np.uint8).reshape(-1, 3)
        acc = sum(flat[i].astype(np.uint16) * wt for i, wt in zip(self.index, self.weight))
        out = (acc >> 8).astype(np.uint32) * self.mask >> 8
        out = np.minimum(np.maximum(out, self.floor), 255).astype(np.uint8)
        # A hint of colour fringing, as on a real shadow mask.
        out[:, 1:, 0] = out[:, :-1, 0].copy()
        out[:, :-1, 2] = out[:, 1:, 2].copy()
        return pygame.image.frombuffer(out.tobytes(), (w, h), "RGB")


def marquee(rom: str, height: int) -> pygame.Surface | None:
    path = MARQUEES / f"{rom}-marquee.png"
    if not path.is_file():
        return None
    img = pygame.image.load(str(path))
    box_w, box_h = round(height * 0.4), round(height * 0.085)
    scale = min(box_w / img.get_width(), box_h / img.get_height())
    img = pygame.transform.smoothscale(img, (round(img.get_width() * scale), round(img.get_height() * scale)))
    # A dark outline behind it, so it reads over any game's colours.
    shadow = img.copy()
    shadow.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MIN)
    pad = max(3, height // 120)
    out = pygame.Surface((img.get_width() + 2 * pad, img.get_height() + 2 * pad), pygame.SRCALPHA)
    for dx in (-pad, 0, pad):
        for dy in (-pad, 0, pad):
            out.blit(shadow, (pad + dx, pad + dy))
    out.blit(img, (pad, pad))
    return out


def badge(font: pygame.font.Font, height: int) -> pygame.Surface:
    """PRESS ANY BUTTON on a dark panel with a blue rim: readable on anything."""
    text = font.render(PROMPT, False, (238, 238, 246))
    pad_x, pad_y = round(height * 0.022), round(height * 0.016)
    out = pygame.Surface((text.get_width() + 2 * pad_x, text.get_height() + 2 * pad_y), pygame.SRCALPHA)
    radius = round(height * 0.012)
    pygame.draw.rect(out, (6, 8, 16, 215), out.get_rect(), border_radius=radius)
    pygame.draw.rect(out, (*BLUE, 255), out.get_rect(), max(2, height // 360), border_radius=radius)
    out.blit(text, (pad_x, pad_y))
    return out


# --- writing ------------------------------------------------------------------


def render(n: int, reel: list[tuple[str, float]], size: tuple[int, int], clips: Path,
           out_dir: Path) -> list[tuple[str, bytes]]:
    """Write reel number `n`; return a thumbnail of each segment for the sheet."""
    w, h = size
    pygame.font.init()
    prompt_font = pygame.font.Font(str(FONT), max(8, round(h * 32 / 1080 / 8) * 8))
    prompt = prompt_font.render(PROMPT, False, (238, 238, 246))
    prompt_pos = prompt.get_rect(center=(w // 2, round(h * 0.84)))
    corner = badge(pygame.font.Font(str(FONT), max(8, round(h * 24 / 1080 / 8) * 8)), h)
    margin_x, margin_y = round(w * 0.045), round(h * 0.06)
    corner_pos = corner.get_rect(bottomright=(w - margin_x, h - margin_y))
    tags = {rom: marquee(rom, h) for rom, _ in reel}
    tube = Tube(size)
    white = pygame.Surface(size)
    white.fill((255, 255, 255))
    black = pygame.Surface(size)

    out = out_dir / f"arqade_reel_{n}.mp4"
    writer = imageio_ffmpeg.write_frames(
        str(out), size, fps=FPS, codec="libx264", pix_fmt_in="rgb24", macro_block_size=1, quality=None,
        output_params=["-crf", "21", "-preset", "slow", "-profile:v", "high", "-level", "4.1",
                       "-g", str(2 * FPS), "-movflags", "+faststart", "-an"])
    writer.send(None)
    thumbs: list[tuple[str, bytes]] = []

    def emit(frame: pygame.Surface, label: str | None = None) -> None:
        if label is not None:
            thumbs.append((label, pygame.image.tostring(pygame.transform.smoothscale(frame, (256, 144)), "RGB")))
        writer.send(pygame.image.tostring(frame, "RGB"))

    for i, frame in enumerate(Frames(SPIN, size, loop=True).take(round(LOGO_TURNS * TURN_SECONDS * FPS))):
        if i < FADE_IN_FRAMES:
            black.set_alpha(round(255 * (1 - (i + 1) / (FADE_IN_FRAMES + 1))))
            frame.blit(black, (0, 0))
        t = i / FPS
        if t >= 0.5 and (t - 0.5) % 1.0 < 0.65:
            frame.blit(prompt, prompt_pos)
        emit(tube(frame), "logo" if i == 0 else None)
    for k, (rom, start) in enumerate(reel):
        flash = FIRST_FLASH if k == 0 else CUT_FLASH
        for i, frame in enumerate(Frames(clips / f"{rom}.mp4", size, start).take(round(CUT_SECONDS * FPS))):
            if i < len(flash):
                white.set_alpha(round(255 * flash[i]))
                frame.blit(white, (0, 0))
            frame = tube(frame)
            if tags[rom] is not None:
                frame.blit(tags[rom], tags[rom].get_rect(bottomleft=(margin_x, h - margin_y)))
            frame.blit(corner, corner_pos)
            emit(frame, f"{rom} {start:.1f}s" if i == len(flash) else None)
    writer.close()
    seconds = LOGO_TURNS * TURN_SECONDS + len(reel) * CUT_SECONDS
    print(f"wrote {out.name}: {seconds:.1f} s, {len(reel)} cuts, {out.stat().st_size / 1e6:.1f} MB", flush=True)
    return thumbs


def build(size: tuple[int, int], reels: int, clips: Path = CLIPS, out_dir: Path = OUT_DIR) -> None:
    roms = [rom for rom in menu_order() if (clips / f"{rom}.mp4").is_file()]
    missing = [rom for rom in menu_order() if rom not in roms]
    if missing:
        print(f"no clip yet (run capture.py): {', '.join(missing)}")
    if not roms:
        raise SystemExit("no clips to cut from")
    per_game = -(-reels * CUTS // len(roms))  # ceil: how often each game comes up
    cuts = plan(roms, moments(roms, clips, per_game), reels)

    out_dir.mkdir(exist_ok=True)
    for stale in out_dir.glob("arqade_reel_*.mp4"):
        stale.unlink()
    # The tube effect is numpy work on every frame: one process per reel.
    with multiprocessing.get_context("fork").Pool(min(reels, os.cpu_count() or 1)) as pool:
        thumbs = pool.starmap(render, [(n, reel, size, clips, out_dir) for n, reel in enumerate(cuts, 1)])

    cols = max(len(row) for row in thumbs)
    sheet = pygame.Surface((cols * 256, len(thumbs) * 144))
    pygame.font.init()
    label_font = pygame.font.Font(None, 22)
    for r, row in enumerate(thumbs):
        for c, (label, data) in enumerate(row):
            sheet.blit(pygame.image.frombuffer(data, (256, 144), "RGB"), (c * 256, r * 144))
            sheet.blit(label_font.render(label, True, (255, 255, 0), (0, 0, 0)), (c * 256 + 3, r * 144 + 3))
    sheet_path = out_dir.with_name(out_dir.name + "-sheet.png")
    pygame.image.save(sheet, str(sheet_path))
    print(f"wrote {sheet_path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--size", default="1280x720", help="WxH (default %(default)s)")
    parser.add_argument("--reels", type=int, default=REELS, help="how many (default %(default)s)")
    parser.add_argument("--out", type=Path, default=OUT_DIR, help="folder for the reels")
    parser.add_argument("--clips", type=Path, default=CLIPS, help="captures to cut from")
    args = parser.parse_args(argv)
    w, h = (int(v) for v in args.size.lower().split("x"))
    build((w, h), args.reels, args.clips, args.out.resolve())


if __name__ == "__main__":
    main()
