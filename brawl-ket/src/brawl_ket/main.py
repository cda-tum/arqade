"""Entry point: CLI args, then hand off to the game loop in game.py.

Same CLI as the sibling games, so the Batocera loader written by
deploy_batocera.sh can run asyncio.run(main(["--fullscreen", "--no-keyboard"])).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
# SCALED fullscreen upscales on the GPU; keep it nearest-neighbour so the
# exact x3 (640x360 -> 1920x1080) stays sharp.
os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "nearest")

import pygame
from arqade_common.input import PAD_LAYOUTS

from . import config, game
from .display import make_display
from .input import set_keyboard_enabled, set_pad_layout, start_devices


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Brawl-Ket")
    parser.add_argument("--input-test", action="store_true",
                        help="Show live joystick/keyboard state instead of running the game")
    parser.add_argument("--fullscreen", action="store_true", help="Run fullscreen at desktop resolution")
    parser.add_argument("--fps", action="store_true", help="Show the FPS overlay")
    parser.add_argument("--window-size", default="1280x720",
                        help="Windowed size as WxH (ignored with --fullscreen)")
    parser.add_argument("--no-keyboard", action="store_true",
                        help="Ignore the keyboard, joysticks only (used on the Batocera cabinet)")
    parser.add_argument("--pad-layout", choices=sorted(PAD_LAYOUTS), default=None,
                        help="How to read pad buttons: encoder (the cabinet's sticks, default), "
                        "xbox (an Xbox-style pad on a PC), standard (browser gamepads)")
    return parser.parse_args(argv)


async def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    set_keyboard_enabled(not args.no_keyboard)
    if args.pad_layout:
        set_pad_layout(PAD_LAYOUTS[args.pad_layout])
    if args.input_test:
        from .input_test import run_input_test

        pygame.init()
        pygame.joystick.init()
        start_devices()
        surface, window = make_display(args.fullscreen, args.window_size)
        pygame.display.set_caption("Brawl-Ket")
        run_input_test(surface, window)
    else:
        await game.run(fullscreen=args.fullscreen, window_size=args.window_size,
                 show_fps=args.fps or config.SHOW_FPS_DEFAULT)
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
