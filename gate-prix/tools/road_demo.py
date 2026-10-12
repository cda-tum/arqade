"""Drive the camera round THE FRIDGE at top speed, to see the road.

    uv run python tools/road_demo.py [--views 1|2] [--seed N]
    uv run python tools/road_demo.py --views 2 --at 30000 --screenshot OUT.png

P1 (top view) steers with S/F or pad 0's stick, P2 (bottom) with the arrows or pad 1's.
Esc quits. --screenshot draws one frame at race distance --at, saves it and exits (no
display needed). A few CPU cars drive round at a little under top speed.
"""

from __future__ import annotations

import argparse
import os
import random
import sys

import pygame

from gate_prix import circuit, config, track
from gate_prix.road import RoadView
from gate_prix.sprites import SpriteCache, font

W, H = config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT
CPU = (("green", 2500, 0.93), ("white", 6000, 0.95), ("lime", 9000, 0.9), ("steel", 14000, 0.97))


def scene(seed: int):
    fridge = track.fridge()
    target = circuit.random_target(random.Random(seed), config.SLOTS)
    rows = track.gate_rows(fridge, target, seed)
    statics = track.arch_objects(rows) + track.box_objects(fridge, config.LAPS)
    return fridge, statics


def cars(fridge, t: float, players):
    """(z, x, kind) for the CPU cars at time t, and the players' own cars."""
    out = []
    for name, start, speed in CPU:
        z = start + speed * config.TOP_SPEED * t
        out.append((z, fridge.segment_at(z).line, f"car:{name}"))
    for name, cam_z, cam_x in players:
        out.append((cam_z + config.CAR_AHEAD, cam_x, f"car:{name}"))
    return out


def frame(screen, views, fridge, statics, t, cams, cache, labels):
    players = [(name, z, x) for (name, (z, x)) in zip(("p1", "p2"), cams)]
    objects = statics + cars(fridge, t, players[: len(views)])
    sprites: list = []
    for view, (cam_z, cam_x), label in zip(views, cams, labels):
        view.draw(screen, fridge, cam_z, cam_x, sprites, objects)
        view.draw_sprites(screen, sprites, cache)
        screen.blit(label, (view.rect.x + 14, view.rect.bottom - 30))
    if len(views) == 2:
        pygame.draw.line(screen, (10, 10, 20), (0, 270), (W, 270), 4)
        pygame.draw.line(screen, (200, 205, 225), (0, 269), (W, 269), 1)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--views", type=int, choices=(1, 2), default=2)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--at", type=float, default=0.0, help="race distance to start from")
    parser.add_argument("--gap", type=float, default=3000.0, help="how far P2 starts behind")
    parser.add_argument("--screenshot", help="save one frame here and exit")
    args = parser.parse_args(argv)

    if args.screenshot:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.font.init()
        screen = pygame.Surface((W, H))
    else:
        pygame.init()
        screen = pygame.display.set_mode((W, H), pygame.SCALED)
        pygame.display.set_caption("GATE PRIX road demo")
    cache = SpriteCache.shared()
    fridge, statics = scene(args.seed)
    if args.views == 2:
        views = [RoadView((0, 0, W, 270)), RoadView((0, 270, W, 270))]
    else:
        views = [RoadView((0, 0, W, H))]
    labels = [font(32 // 2).render(tag, True, col) for tag, col in
              (("P1", config.CAR_COLORS["p1"]), ("P2", config.CAR_COLORS["p2"]))]
    cams = [[args.at, 0.0], [args.at - args.gap, -0.3]]

    if args.screenshot:
        frame(screen, views, fridge, statics, 0.0, cams, cache, labels)
        pygame.image.save(screen, args.screenshot)
        print("saved", args.screenshot)
        return

    pads = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
    clock = pygame.time.Clock()
    t = 0.0
    fps_img = None
    keys_for = ((pygame.K_s, pygame.K_f), (pygame.K_LEFT, pygame.K_RIGHT))
    while True:
        dt = clock.tick(config.FPS) / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                pygame.quit()
                return
        keys = pygame.key.get_pressed()
        for p, cam in enumerate(cams):
            left, right = keys_for[p]
            steer = (1 if keys[right] else 0) - (1 if keys[left] else 0)
            if p < len(pads) and pads[p].get_numaxes():
                axis = pads[p].get_axis(0)
                if abs(axis) > config.INPUT_CONFIG["axis_deadzone"]:
                    steer = axis
            if len(views) == 1 and p == 0 and not steer:
                right2, left2 = keys[pygame.K_RIGHT], keys[pygame.K_LEFT]
                steer = (1 if right2 else 0) - (1 if left2 else 0)
            cam[1] = max(-2.2, min(2.2, cam[1] + steer * 2.0 * dt))
            cam[0] += config.TOP_SPEED * dt
        t += dt
        frame(screen, views, fridge, statics, t, cams, cache, labels)
        if int(t * 2) != int((t - dt) * 2) or fps_img is None:
            lap = int(cams[0][0] // fridge.lap_length()) + 1
            fps_img = font(14).render(f"{clock.get_fps():.0f} fps  lap {lap}", True, (230, 235, 255))
        screen.blit(fps_img, (W - fps_img.get_width() - 10, H - 24))
        pygame.display.flip()


if __name__ == "__main__":
    main(sys.argv[1:])
