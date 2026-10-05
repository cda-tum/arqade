"""Entry point: `arqade` (or `python -m arqade_launcher`)."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from arqade_launcher import catalog, settings  # noqa: E402
from arqade_launcher.app import App  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="arqade", description="Munich Quantum Arcade: every game behind one menu.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--fullscreen", action="store_true",
                      help="Fullscreen this session (default: the saved setting)")
    mode.add_argument("--windowed", action="store_true",
                      help="In a window this session (default: the saved setting)")
    parser.add_argument("--window-size", default="1280x720", help="Window size as WxH")
    parser.add_argument("--kiosk", action="store_true",
                        help="For public demos: no quitting or settings from the menu (Ctrl+Q still quits)")
    parser.add_argument("--config", type=Path, default=settings.default_path(),
                        help="Settings file (default: %(default)s)")
    parser.add_argument("--games-root", type=Path, default=catalog.REPO_ROOT,
                        help="Folder holding the game projects (default: this repo)")
    parser.add_argument("--list", action="store_true", help="List the games found, then exit")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    games = catalog.discover(args.games_root)
    if args.list:
        for game in games:
            art = game.art.relative_to(args.games_root) if game.art else "(placeholder)"
            print(f"{game.name:<18} {game.package:<16} {art}")
        return

    stored = settings.load(args.config)
    persisted_fullscreen = stored.fullscreen
    if args.fullscreen or args.windowed:
        stored.fullscreen = args.fullscreen
    width, height = (int(v) for v in args.window_size.lower().split("x"))

    # Only what the menu needs: no joystick or audio, which the games open
    # themselves and should have to themselves.
    pygame.display.init()
    pygame.font.init()
    app = App(games, stored, args.config, kiosk=args.kiosk, window_size=(width, height),
              persisted_fullscreen=persisted_fullscreen)
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
