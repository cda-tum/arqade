"""Entry point: the command line, then the game loop in game.py.

The same flags as the sibling games, so the Batocera loader (deploy_batocera.sh) can run
asyncio.run(main(["--fullscreen", "--no-keyboard"])) and the ARQADE launcher can pass
--window-size, --no-keyboard and --fps. In the browser (pygbag) it is asyncio.run(main([])).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
# SCALED fullscreen upscales on the GPU: exactly 2x, so nearest-neighbour doubles every pixel
# and nothing is blurred.
os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "nearest")

import pygame  # noqa: E402
from arqade_common.input import PAD_LAYOUTS  # noqa: E402

from gate_prix import config  # noqa: E402
from gate_prix.input import set_keyboard_enabled  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="gate_prix", description="GATE PRIX")
    parser.add_argument("--input-test", action="store_true",
                        help="show live joystick and keyboard state instead of the game")
    parser.add_argument("--fullscreen", action="store_true", help="fullscreen, scaled 2x")
    parser.add_argument("--fps", action="store_true", help="show the frame rate")
    parser.add_argument("--window-size", default="1440x810",
                        help="the window's size as WxH (ignored with --fullscreen)")
    parser.add_argument("--no-keyboard", action="store_true",
                        help="ignore the keyboard, pads only (the Batocera cabinet)")
    parser.add_argument("--pad-layout", choices=sorted(PAD_LAYOUTS), default=None,
                        help="how to read pad buttons: encoder (the cabinet's sticks, the "
                             "default), xbox (an Xbox-style pad on a PC), standard (browser "
                             "gamepads)")
    parser.add_argument("--selftest", type=float, metavar="SECONDS",
                        help="play a scripted session (attract, 1P and 2P races, pause, "
                             "results, idle) for up to SECONDS of game time, as fast as "
                             "possible, and exit 0 if every check held")
    parser.add_argument("--shots", metavar="DIR", help="with --selftest: save screenshots here")
    parser.add_argument("--seed", type=int, help="the match's random seed")
    return parser.parse_args(argv)


async def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    set_keyboard_enabled(not args.no_keyboard)
    code = 0
    if args.input_test:
        from gate_prix.display import make_display
        from gate_prix.input_test import run_input_test

        pygame.init()
        pygame.joystick.init()
        surface, window = make_display(args.fullscreen, args.window_size)
        pygame.display.set_caption("GATE PRIX input test")
        run_input_test(surface, window)
    else:
        from gate_prix import game

        code = await game.run(fullscreen=args.fullscreen, window_size=args.window_size,
                              show_fps=args.fps or config.SHOW_FPS_DEFAULT, seed=args.seed,
                              selftest=args.selftest, shots=args.shots,
                              pad_layout=PAD_LAYOUTS.get(args.pad_layout))
    pygame.quit()
    sys.exit(code)


if __name__ == "__main__":
    asyncio.run(main())
