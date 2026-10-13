"""A seamless loop of the trailer's mosaic, for a slide's background.

    launcher/.venv/bin/python batocera/attract/build_loop.py

Writes trailer/arqade_loop.mp4: the ten games running around the turning
ARQADE logo, on the tube, LOOP_TURNS turns of the logo long (4 s each) and
silent, so that played on repeat it never jumps:

- The logo turns exactly LOOP_TURNS times, so its last frame leads into its
  first.
- Each game plays N + FADE frames of its capture, and its last FADE frames
  are cross-faded into its first ones: frame N would follow frame N - 1, and
  the loop shows it there, fading into frame 0's footage over FADE frames.
- Each tile is started at a different point of its own loop, so the ten
  fades happen at different times rather than all at once.

The moments are the minute version's (build_trailer.MINUTE_CELLS): early
enough in the ~85 s captures to play the whole loop.
"""

from __future__ import annotations

import multiprocessing
import shutil
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
import pygame

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_trailer as t  # noqa: E402

reel = t.reel
LOOP_TURNS = 8
TURN = 120  # frames per turn of the logo (4 s at 30 fps)
N = LOOP_TURNS * TURN
FADE = 30  # frames each tile takes to fade from its end back into its start
CELLS = t.MINUTE_CELLS
OUT = t.OUT_DIR / "arqade_loop.mp4"


def cell_frames(k: int, rom: str, start: float, size: tuple[int, int], i0: int, i1: int):
    """Tile k's pictures for loop frames i0..i1-1. The tile is phased by
    k * N / len(CELLS) frames, so its fade comes at its own time."""
    phase = k * N // len(CELLS)
    first = round(t.when(rom, start) * t.FPS)  # the capture's frame the loop starts on

    def at(j: int) -> float:
        """Where to seek for the loop's source frame j: half a frame early, as
        a seek lands on the first frame at or after it, and one a hair late
        of a frame's own time skips that frame."""
        return (first + j - 0.5) / t.FPS
    js = [(i + phase) % N for i in range(i0, i1)]
    # Runs of consecutive source frames: a reader each (one more for the
    # frames past N that fade out over a run's first FADE frames).
    runs, a = [], 0
    for b in range(1, len(js) + 1):
        if b == len(js) or js[b] != js[b - 1] + 1:
            runs.append((js[a], b - a))
            a = b
    for j0, count in runs:
        main = reel.Frames(t.CLIPS / f"{rom}.mp4", size, at(j0)).take(count)
        over = max(0, min(FADE, j0 + count) - j0)  # how many of this run fall in [0, FADE)
        tail = reel.Frames(t.CLIPS / f"{rom}.mp4", size, at(N + j0)).take(over) if over else None
        for m in range(count):
            picture = next(main)
            j = j0 + m
            if j < FADE:
                old = next(tail)
                old.set_alpha(round(255 * (1 - (j + 0.5) / FADE)))
                picture.blit(old, (0, 0))
            yield picture


def render(job: tuple[int, int, int, Path]) -> Path:
    part, i0, i1, out_dir = job
    w, h = t.SIZE
    painter = t.Painter()
    gap, cw, ch, x0, y0, spots, logo_w = painter.mosaic_layout()
    logo_size = (logo_w, round(logo_w * t.SPIN_CROP[3] / t.SPIN_CROP[2]))
    cells = [cell_frames(k, rom, start, (cw, ch), i0, i1) for k, (rom, start) in enumerate(CELLS)]
    spin = reel.Frames(reel.SPIN, (t.SPIN_CROP[2], t.SPIN_CROP[3]), loop=True, crop=t.SPIN_CROP).take(i1)
    for _ in range(i0):
        next(spin)
    path = out_dir / f"part_{part:02d}.mp4"
    writer = imageio_ffmpeg.write_frames(
        str(path), t.SIZE, fps=t.FPS, codec="libx264", pix_fmt_in="rgb24", macro_block_size=1, quality=None,
        output_params=["-crf", "18", "-preset", "medium", "-threads", "4", "-profile:v", "high",
                       "-level", "4.2", "-g", str(2 * t.FPS), "-an"])
    writer.send(None)
    for _ in range(i0, i1):
        frame = pygame.Surface(t.SIZE)
        frame.fill((4, 5, 8))
        for (cx, cy), cell in zip(spots, cells):
            frame.blit(next(cell), (x0 + cx * (cw + gap), y0 + cy * (ch + gap)))
        logo = pygame.transform.smoothscale(next(spin), logo_size)
        frame.blit(logo, logo.get_rect(center=(w // 2, h // 2)), special_flags=pygame.BLEND_RGB_MAX)
        writer.send(pygame.image.tostring(painter.tube(frame), "RGB"))
    writer.close()
    return path


def main() -> None:
    parts_dir = t.OUT_DIR / "loop_parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    workers = t.WORKERS
    bounds = [round(N * p / workers) for p in range(workers + 1)]
    jobs = [(p, bounds[p], bounds[p + 1], parts_dir) for p in range(workers)]
    print(f"{N} frames ({N / t.FPS:.0f} s, {LOOP_TURNS} turns), {workers} workers", flush=True)
    with multiprocessing.get_context("fork").Pool(workers) as pool:
        paths = pool.map(render, jobs)
    listing = parts_dir / "parts.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in paths))
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(OUT)], check=True)
    shutil.rmtree(parts_dir)
    print(f"wrote {OUT.relative_to(t.REPO)}: {N / t.FPS:.0f} s, {OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
