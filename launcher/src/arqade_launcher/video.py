"""Video in the menu: the attract reel and the spinning ARQADE logo.

pygame cannot decode video, so ffmpeg does (imageio-ffmpeg's bundled binary,
so nothing has to be installed), in a background thread, straight into raw
RGB frames at the size they are shown at. Without imageio-ffmpeg or without
the file, `available()` says so and the menu simply does without.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from pathlib import Path

import pygame

from arqade_launcher.catalog import REPO_ROOT

# It warns on every scaled read that the frames aren't the source's size.
logging.getLogger("imageio_ffmpeg").setLevel(logging.ERROR)

REELS = REPO_ROOT / "batocera" / "attract" / "reels"
SPIN = REPO_ROOT / "logos" / "animation" / "arqade_loading_v3_1080p.webm"
# The part of the 1920x1080 spin the logo turns in, with a little room.
SPIN_CROP = pygame.Rect(200, 280, 1520, 520)


def available(path: Path) -> bool:
    try:
        import imageio_ffmpeg  # noqa: F401
    except ImportError:
        return False
    return path.is_file()


def reels() -> list[Path]:
    """The attract reels (batocera/attract/build_reel.py), if they can play."""
    return [p for p in sorted(REELS.glob("arqade_reel_*.mp4")) if available(p)]


class Player:
    """Plays a video, on a loop or once, decoding ahead in a thread.

    `frame()` returns the frame for the time since the player was made (or
    the latest one decoded, if decoding falls behind), None until the first
    one arrives. Played once, `done` turns true after the last frame has been
    shown. Call `close()` when finished with it: it stops ffmpeg.
    """

    def __init__(self, path: Path, size: tuple[int, int], crop: pygame.Rect | None = None,
                 fps: float = 30.0, buffered: int = 6, loop: bool = True):
        self.size = size
        self.fps = fps
        self.loop = loop
        self.decoded = threading.Event()  # set once the whole file has been read
        self.frames: queue.Queue[bytes] = queue.Queue(maxsize=buffered)
        self.stopping = threading.Event()
        self.current: pygame.Surface | None = None
        self.shown = 0
        self.started = time.monotonic()
        filters = []
        if crop is not None:
            filters.append(f"crop={crop.w}:{crop.h}:{crop.x}:{crop.y}")
        filters.append(f"scale={size[0]}:{size[1]}:flags=area")
        self.thread = threading.Thread(target=self._decode, args=(path, ",".join(filters)), daemon=True)
        self.thread.start()

    def _decode(self, path: Path, filters: str) -> None:
        import imageio_ffmpeg

        try:
            reader = imageio_ffmpeg.read_frames(str(path), input_params=["-stream_loop", "-1"] if self.loop else [],
                                                output_params=["-vf", filters])
            next(reader)
        except (OSError, RuntimeError, StopIteration):
            self.decoded.set()
            return
        try:
            for data in reader:
                while not self.stopping.is_set():
                    try:
                        self.frames.put(data, timeout=0.1)
                        break
                    except queue.Full:
                        pass
                if self.stopping.is_set():
                    break
        except RuntimeError:  # ffmpeg died or the file is broken: just stop
            pass
        finally:
            reader.close()
            self.decoded.set()

    @property
    def done(self) -> bool:
        return self.decoded.is_set() and self.frames.empty()

    def frame(self) -> pygame.Surface | None:
        due = int((time.monotonic() - self.started) * self.fps) + 1
        while self.shown < due:
            try:
                data = self.frames.get_nowait()
            except queue.Empty:
                break
            self.current = pygame.image.frombuffer(data, self.size, "RGB")
            self.shown += 1
        return self.current

    def close(self) -> None:
        self.stopping.set()
