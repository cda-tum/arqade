"""Entry point: CLI args, then hand off to the game loop in game.py.

Same CLI as Quantum Pong / Quantum Towers, so the Batocera loader written by
deploy_batocera.sh can run `asyncio.run(main(["--fullscreen"]))`.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402
from arqade_common.input import PAD_LAYOUTS  # noqa: E402

from error_invaders import config, game  # noqa: E402
from error_invaders.input import set_keyboard_enabled  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pauli Invaders")
    parser.add_argument(
        "--input-test",
        action="store_true",
        help="Show live joystick/keyboard state instead of running the game",
    )
    parser.add_argument(
        "--fullscreen", action="store_true", help="Run fullscreen at desktop resolution"
    )
    parser.add_argument("--fps", action="store_true", help="Force the FPS overlay on")
    parser.add_argument(
        "--window-size",
        default="960x720",
        help="Windowed size as WxH, e.g. 960x720 (ignored with --fullscreen)",
    )
    parser.add_argument(
        "--no-keyboard",
        action="store_true",
        help="Ignore the keyboard, joysticks only (used on the Batocera cabinet)",
    )
    parser.add_argument(
        "--pad-layout",
        choices=sorted(PAD_LAYOUTS),
        default=None,
        help="How to read pad buttons: encoder (the cabinet's sticks, default), "
        "xbox (an Xbox-style pad on a PC), standard (browser gamepads)",
    )
    return parser.parse_args(argv)


async def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    set_keyboard_enabled(not args.no_keyboard)
    await game.run(
        fullscreen=args.fullscreen,
        window_size=args.window_size,
        show_fps=args.fps or config.SHOW_FPS_DEFAULT,
        input_test=args.input_test,
        pad_layout=PAD_LAYOUTS.get(args.pad_layout),
    )
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
