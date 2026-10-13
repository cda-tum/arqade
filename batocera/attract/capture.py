"""Record a game's own gameplay, headless, as footage for the attract reel.

    launcher/.venv/bin/python batocera/attract/capture.py quantum_pong
    launcher/.venv/bin/python batocera/attract/capture.py qurves --seconds 30 --seed 4

Writes, next to this file:

  clips/<rom>.mp4        1920x1080, 30 fps, exactly what the cabinet shows
  clips/<rom>-sheet.png  one thumbnail every few seconds, to check the footage
  clips/<rom>.wav        the game's sound effects, in sync with the video
                         (`--sound-only` writes just this, for a clip that is
                         already there: the same seed gives the same footage)

The game runs in this process the way the launcher's child does (its real
`main()`, its real title screen and menus), with four things swapped in:

- **No window.** SDL's dummy video and audio drivers. The game is started
  windowed at 1920x1080, so its own present() letterboxes and scales exactly
  as it does on the panel, and that window is what gets recorded.
- **Simulated time.** pygame.time.Clock.tick() returns exactly one 60 fps
  frame and never sleeps, and get_ticks() follows it. A capture is therefore
  as smooth as the real thing however slow the machine, and faster than
  real time on most.
- **Two cabinet pads driven by a bot** (bots/<rom>.py) instead of people:
  the same raw button numbers and analog stick axes as the real encoders, so
  the game cannot tell the difference.
- **Every second frame is piped to ffmpeg** (imageio-ffmpeg's bundled one).
- **Every sound effect is logged** at the frame it is played and mixed into
  a WAV afterwards. The audio driver is a dummy too, so this is the only way
  to hear the footage. Looping sounds (the games' music) are left out: a
  reel or trailer brings its own.

The same seed gives the same footage: unseeded `random.Random()` and
`numpy.random.default_rng()` are seeded from it, and the script re-runs
itself with PYTHONHASHSEED=0 so set iteration order can't vary either. That
is what lets a bot list the timestamps of its best moments (`HIGHLIGHTS`)
for build_reel.py and have them still be right on the next capture.

A bot module defines `class Bot` with `__init__(self, pads, rng)` and
`update(self, t)`, called once per game frame with the simulated time in
seconds before the game reads its input. It may also set:

  SECONDS     how long to record (default 75)
  SKIP        leading seconds of title screens and menus, never cut from
  HIGHLIGHTS  start times (s) of the best ~3 s moments, best first; without
              them build_reel.py picks the busiest stretches after SKIP

See bots/quantum_pong.py.

Bots that want to play well rather than blind can look at the game:
`pads.loop` is the local variables of the game loop that is running right
now (the function that called clock.tick() -- a Pong match's `balls` and
paddles, say), and `pads.find("Ball")` every live object of that class.
The game's own package is importable from a bot, too.
"""

from __future__ import annotations

import argparse
import gc
import importlib
import os
import random
import sys
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CLIPS = HERE / "clips"
SIZE = (1920, 1080)
GAME_FPS = 60
VIDEO_FPS = 30
SHEET_EVERY = 4.0  # seconds between contact-sheet thumbnails

# The cabinet's raw button numbers (AGENTS.md, "Confirmed raw button numbers").
RAW = {"x": 0, "a": 1, "b": 2, "y": 3, "l": 4, "r": 5, "select": 8, "start": 9}


class Pad:
    """Stands in for pygame.joystick.Joystick: one cabinet pad."""

    def __init__(self, index: int):
        self.index = index
        self.buttons = [False] * 12
        self.axes = [0.0, 0.0]

    def init(self) -> None:
        pass

    def quit(self) -> None:
        pass

    def get_init(self) -> bool:
        return True

    def get_id(self) -> int:
        return self.index

    def get_instance_id(self) -> int:
        return self.index

    def get_guid(self) -> str:
        return f"arqade-capture-pad-{self.index}"

    def get_name(self) -> str:
        return f"ARQADE capture pad P{self.index + 1}"

    def get_power_level(self) -> str:
        return "wired"

    def get_numaxes(self) -> int:
        return 2

    def get_numbuttons(self) -> int:
        return 12

    def get_numhats(self) -> int:
        return 0  # like the cabinet: the stick is an analog axis

    def get_numballs(self) -> int:
        return 0

    def get_button(self, button: int) -> bool:
        return 0 <= button < len(self.buttons) and self.buttons[button]

    def get_axis(self, axis: int) -> float:
        return self.axes[axis] if 0 <= axis < len(self.axes) else 0.0

    def get_hat(self, hat: int):
        raise pygame.error("Invalid joystick hat")

    def get_ball(self, ball: int):
        raise pygame.error("Invalid joystick trackball")

    def rumble(self, low: float, high: float, duration: int) -> bool:
        return False

    def stop_rumble(self) -> None:
        pass


class Pads:
    """What a bot drives. Players are 0 (left, blue) and 1 (right, red);
    buttons by their printed name: a b x y l r start select."""

    def __init__(self):
        self.pads = [Pad(0), Pad(1)]
        self.events: list[pygame.event.Event] = []
        self._releases: list[tuple[int, int, str]] = []  # (frame, player, button)
        self.frame = 0
        self.loop: dict = {}  # the running game loop's locals, refreshed every frame

    @staticmethod
    def find(type_name: str) -> list:
        """Every live object whose class is called `type_name`."""
        return [o for o in gc.get_objects() if type(o).__name__ == type_name]

    def hold(self, player: int, button: str, down: bool = True) -> None:
        raw = RAW[button]
        pad = self.pads[player]
        if pad.buttons[raw] == down:
            return
        pad.buttons[raw] = down
        self.events.append(pygame.event.Event(
            pygame.JOYBUTTONDOWN if down else pygame.JOYBUTTONUP,
            joy=player, instance_id=player, button=raw))

    def release(self, player: int, button: str) -> None:
        self.hold(player, button, False)

    def tap(self, player: int, button: str, frames: int = 4) -> None:
        """Press now, let go `frames` game frames later."""
        self.hold(player, button, True)
        self._releases.append((self.frame + frames, player, button))

    def stick(self, player: int, x: float, y: float) -> None:
        """x: -1 left .. 1 right, y: -1 up .. 1 down (SDL's convention)."""
        pad = self.pads[player]
        for axis, value in ((0, x), (1, y)):
            value = float(max(-1.0, min(1.0, value)))
            if pad.axes[axis] != value:
                pad.axes[axis] = value
                self.events.append(pygame.event.Event(
                    pygame.JOYAXISMOTION, joy=player, instance_id=player,
                    axis=axis, value=value))

    def held(self, player: int, button: str) -> bool:
        return self.pads[player].buttons[RAW[button]]

    def release_all(self) -> None:
        for player in (0, 1):
            for button in RAW:
                self.release(player, button)
            self.stick(player, 0.0, 0.0)

    def step(self) -> None:
        self.frame += 1
        due = [r for r in self._releases if r[0] <= self.frame]
        self._releases = [r for r in self._releases if r[0] > self.frame]
        for _, player, button in due:
            self.release(player, button)


class Done(BaseException):
    """Raised from inside the game's loop once enough has been recorded.
    BaseException, so a game's own `except Exception` cannot swallow it."""


class Recorder:
    def __init__(self, out: Path, sheet: Path, seconds: float):
        import imageio_ffmpeg

        self.out, self.sheet_path, self.seconds = out, sheet, seconds
        self.flips = 0
        self.thumbs: list[tuple[float, pygame.Surface]] = []
        self.writer = imageio_ffmpeg.write_frames(
            str(out), SIZE, fps=VIDEO_FPS, codec="libx264", pix_fmt_in="rgb24",
            macro_block_size=1, quality=None,
            output_params=["-crf", "16", "-preset", "veryfast"])
        self.writer.send(None)
        self.canvas = pygame.Surface(SIZE)

    def frame(self, t: float) -> None:
        self.flips += 1
        if self.flips % (GAME_FPS // VIDEO_FPS):
            return
        surf = pygame.display.get_surface()
        if surf is None:
            return
        if surf.get_size() != SIZE:  # a game that ignored --window-size
            self.canvas.fill((0, 0, 0))
            w, h = surf.get_size()
            scale = min(SIZE[0] / w, SIZE[1] / h)
            scaled = pygame.transform.scale(surf, (round(w * scale), round(h * scale)))
            self.canvas.blit(scaled, scaled.get_rect(center=(SIZE[0] // 2, SIZE[1] // 2)))
            surf = self.canvas
        self.writer.send(pygame.image.tostring(surf, "RGB"))
        if not self.thumbs or t - self.thumbs[-1][0] >= SHEET_EVERY:
            self.thumbs.append((t, pygame.transform.smoothscale(surf, (320, 180))))

    def close(self) -> None:
        self.writer.close()
        if not self.thumbs:
            return
        cols = 6
        rows = (len(self.thumbs) + cols - 1) // cols
        sheet = pygame.Surface((cols * 320, rows * 180))
        font = pygame.font.Font(None, 28)
        for i, (t, thumb) in enumerate(self.thumbs):
            x, y = (i % cols) * 320, (i // cols) * 180
            sheet.blit(thumb, (x, y))
            label = font.render(f"{t:5.1f}s", True, (255, 255, 0), (0, 0, 0))
            sheet.blit(label, (x + 4, y + 4))
            pygame.draw.rect(sheet, (60, 60, 60), (x, y, 320, 180), 1)
        pygame.image.save(sheet, str(self.sheet_path))


class SoundLog:
    """Logs every Sound.play() with the simulated time, then mixes them.

    Every game builds its sounds with pygame.mixer.Sound(buffer=...) and plays
    effects with .play(); music goes through Channel.play(loops=-1), which is
    not logged. pygame.mixer.Sound is swapped for a subclass that notes each
    play, so this has to be installed before the game is imported."""

    def __init__(self, now):
        self.events: list[tuple[float, pygame.mixer.Sound, float]] = []
        log = self

        class LoggedSound(pygame.mixer.Sound):
            def play(self, loops: int = 0, *args, **kwargs):
                if loops == 0:
                    log.events.append((now(), self, self.get_volume()))
                return super().play(loops, *args, **kwargs)

        pygame.mixer.Sound = LoggedSound

    def write(self, path: Path, seconds: float) -> bool:
        import wave

        import numpy as np

        init = pygame.mixer.get_init()
        if not init or not self.events:
            return False
        freq, size, channels = init
        if abs(size) != 16:
            print(f"WARNING: mixer is {size}-bit, sounds not written")
            return False
        total = np.zeros((int(seconds * freq) + 1, channels), np.float32)
        samples: dict[int, np.ndarray] = {}
        for t, sound, volume in self.events:
            if id(sound) not in samples:
                samples[id(sound)] = np.frombuffer(sound.get_raw(), np.int16).reshape(-1, channels)
            data = samples[id(sound)]
            start = round(t * freq)
            end = min(len(total), start + len(data))
            if start < end:
                total[start:end] += data[: end - start] * volume
        with wave.open(str(path), "wb") as out:
            out.setnchannels(channels)
            out.setsampwidth(2)
            out.setframerate(freq)
            out.writeframes(np.clip(total, -32768, 32767).astype(np.int16).tobytes())
        return True


def seed_all(seed: int) -> None:
    """Make every random source the games use follow `seed`."""
    random.seed(seed)
    source = random.Random(seed)

    class SeededRandom(random.Random):
        def __init__(self, x=None):
            super().__init__(source.getrandbits(64) if x is None else x)

    random.Random = SeededRandom
    try:
        import numpy
    except ImportError:
        return
    numpy.random.seed(seed)
    default_rng = numpy.random.default_rng
    numpy.random.default_rng = lambda s=None: default_rng(source.getrandbits(64) if s is None else s)


def project_dir(rom: str) -> Path:
    for d in sorted(REPO.iterdir()):
        if d.is_dir() and d.name.replace("-", "_") == rom and (d / "src" / rom / "main.py").is_file():
            return d
    raise SystemExit(f"no game called {rom!r} in {REPO}")


def capture(rom: str, seconds: float | None, seed: int, out: Path | None = None,
            sound_only: bool = False) -> Path:
    game_dir = project_dir(rom)
    sys.path.insert(0, str(game_dir / "src"))
    bot_mod = importlib.import_module(f"bots.{rom}")
    seconds = seconds or getattr(bot_mod, "SECONDS", 75.0)
    CLIPS.mkdir(exist_ok=True)
    out = out or CLIPS / f"{rom}.mp4"
    sheet = out.with_name(out.stem + "-sheet.png")

    seed_all(seed)

    pads = Pads()
    bot = bot_mod.Bot(pads, random.Random(seed))
    recorder = None if sound_only else Recorder(out, sheet, seconds)
    state = {"frame": 0}

    def now() -> float:
        return state["frame"] / GAME_FPS

    sounds = SoundLog(now)

    class SimClock:
        def __init__(self):
            self._last = state["frame"]

        def tick(self, framerate: float = 0) -> int:
            before = round(state["frame"] * 1000 / GAME_FPS)
            state["frame"] += 1
            pads.step()
            if now() >= seconds:
                raise Done
            pads.loop = sys._getframe(1).f_locals
            bot.update(now())
            self._last = round(state["frame"] * 1000 / GAME_FPS) - before
            return self._last

        tick_busy_loop = tick

        def get_time(self) -> int:
            return self._last

        def get_rawtime(self) -> int:
            return self._last

        def get_fps(self) -> float:
            return float(GAME_FPS)

    original_get = pygame.event.get
    announced = False

    def get(*args, **kwargs):
        nonlocal announced
        events = [e for e in original_get(*args, **kwargs)
                  if e.type not in (pygame.KEYDOWN, pygame.KEYUP, pygame.QUIT)]
        if not announced and pygame.joystick.get_init():
            announced = True
            events += [pygame.event.Event(pygame.JOYDEVICEADDED, device_index=i,
                                          guid=pad.get_guid()) for i, pad in enumerate(pads.pads)]
        events += pads.events
        pads.events = []
        return events

    original_flip, original_update = pygame.display.flip, pygame.display.update

    def flip():
        original_flip()
        if recorder is not None:
            recorder.frame(now())

    def update(*args, **kwargs):
        original_update(*args, **kwargs)
        if recorder is not None:
            recorder.frame(now())

    pygame.time.Clock = SimClock
    pygame.time.get_ticks = lambda: round(state["frame"] * 1000 / GAME_FPS)
    pygame.time.wait = pygame.time.delay = lambda ms: 0
    pygame.event.get = get
    pygame.joystick.get_count = lambda: len(pads.pads)
    pygame.joystick.Joystick = lambda i: pads.pads[i]
    pygame.display.flip = flip
    pygame.display.update = update

    os.chdir(game_dir)
    main = importlib.import_module(f"{rom}.main").main
    try:
        main(["--window-size", f"{SIZE[0]}x{SIZE[1]}", "--no-keyboard"])
    except (Done, SystemExit):
        pass
    finally:
        if recorder is not None:
            recorder.close()
    wav = out.with_suffix(".wav")
    if sounds.write(wav, seconds):
        print(f"{rom}: {len(sounds.events)} sound effects -> {wav.name}")
    print(f"{rom}: {now():.1f}s recorded -> {out.relative_to(REPO) if out.is_relative_to(REPO) else out}")
    if now() < seconds - 1:
        print(f"WARNING: {rom} quit after {now():.1f}s of the {seconds:.0f}s asked for")
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("rom", help="the game's package name, e.g. quantum_pong")
    parser.add_argument("--seconds", type=float, help="length (default: the bot's SECONDS)")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", type=Path, help="default: clips/<rom>.mp4")
    parser.add_argument("--sound-only", action="store_true",
                        help="only write the .wav (the video would come out the same)")
    args = parser.parse_args(argv)
    if os.environ.get("PYTHONHASHSEED") != "0":
        os.environ["PYTHONHASHSEED"] = "0"
        os.execv(sys.executable, [sys.executable, *sys.argv])
    sys.path.insert(0, str(HERE))
    pygame.init()
    # pygame.init() opens the mixer at its defaults, and a game's own
    # mixer.init() is then ignored: its sounds would be read as the wrong
    # rate and channel count. Let each game open it the way it asks.
    pygame.mixer.quit()
    capture(args.rom, args.seconds, args.seed, args.out, args.sound_only)


if __name__ == "__main__":
    main()
