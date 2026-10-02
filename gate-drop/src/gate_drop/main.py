"""Entry point: CLI args, then hand off to the game loop in game.py.

Same CLI as the sibling games, so the Batocera loader written by
deploy_batocera.sh can call main(["--fullscreen", "--no-keyboard"]).
"""

from __future__ import annotations

import argparse
import os
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
# SCALED fullscreen upscales on the GPU; keep it nearest-neighbour so the
# exact x4 (480x270 -> 1920x1080) stays sharp.
os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "nearest")

import pygame  # noqa: E402

from gate_drop import config, game  # noqa: E402
from gate_drop.display import make_display  # noqa: E402
from gate_drop.input import set_keyboard_enabled  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gate Drop")
    parser.add_argument("--input-test", action="store_true",
                        help="Show live joystick/keyboard state instead of running the game")
    parser.add_argument("--fullscreen", action="store_true", help="Run fullscreen at desktop resolution")
    parser.add_argument("--fps", action="store_true", help="Show the FPS overlay")
    parser.add_argument("--window-size", default="1440x810",
                        help="Windowed size as WxH (ignored with --fullscreen)")
    parser.add_argument("--no-keyboard", action="store_true",
                        help="Ignore the keyboard, joysticks only (used on the Batocera cabinet)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    set_keyboard_enabled(not args.no_keyboard)
    if args.input_test:
        from gate_drop.input_test import run_input_test

        pygame.init()
        pygame.joystick.init()
        surface, window = make_display(args.fullscreen, args.window_size)
        pygame.display.set_caption("Gate Drop")
        run_input_test(surface, window)
    else:
        game.run(fullscreen=args.fullscreen, window_size=args.window_size,
                 show_fps=args.fps or config.SHOW_FPS_DEFAULT)
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
