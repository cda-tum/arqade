"""Drive a real race of GATE PRIX: the Car model, the gate rows, laps and the CIRCUIT CHECK.

    uv run python tools/drive_demo.py [--views 1|2] [--seed N] [--auto]
    uv run python tools/drive_demo.py --auto --seconds 95 --screenshot OUT.png

P1 (top view) steers with S/F, brakes with D and uses its item with Q, or pad 0's stick
(pulled back brakes) and A; P2 (bottom) uses the arrows, Down and ".", or pad 1. The CPU cars
are the real AI (ai.py, at TOUGH). Every cue is printed (each bump once). --auto drives P1 through
every right arch. --screenshot runs --seconds of the race headless with
P1 on --auto, saves the last frame and exits. Esc quits.
"""

from __future__ import annotations

import argparse
import os
import sys

import pygame

from gate_prix import ai, config, track
from gate_prix.car import Controls, aim
from gate_prix.race import Race
from gate_prix.road import RoadView
from gate_prix.sprites import SpriteCache, font

W, H = config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT
DT = 1 / config.FPS


def perfect(race, racer):
    car = racer.car
    goal = race.track.segment_at(car.z + 600).line
    if racer.next_row < len(race.rows) and race.rows[racer.next_row].z - car.z < 1.5 * config.TOP_SPEED:
        goal = next(a.offset for a in race.rows[racer.next_row].arches if a.right)
    return Controls(*aim(car, goal, race.track.segment_at(car.z)))


def human(keys, pads, p):
    left, right, down, use = ((pygame.K_s, pygame.K_f, pygame.K_d, pygame.K_q),
                              (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_DOWN, pygame.K_PERIOD))[p]
    steer = (1.0 if keys[right] else 0.0) - (1.0 if keys[left] else 0.0)
    brake = 1.0 if keys[down] else 0.0
    item = bool(keys[use])
    dead = config.INPUT_CONFIG["axis_deadzone"]
    if p < len(pads) and pads[p].get_numaxes() >= 2:
        sx, sy = pads[p].get_axis(0), pads[p].get_axis(1)
        steer = sx if abs(sx) > dead else steer
        brake = 1.0 if sy > dead else brake
        item = item or bool(pads[p].get_button(config.INPUT_CONFIG["system"]["a_button"]))
    return Controls(steer, brake, item)


def draw(screen, views, race, statics, cache):
    objects = statics + race.box_objects() + race.car_objects() + race.clone_objects()
    sprites: list = []
    for view, racer in zip(views, race.racers):
        car = racer.car
        view.draw(screen, race.track, car.z - config.CAR_AHEAD, car.x, sprites, objects)
        view.draw_sprites(screen, sprites, cache)
        c = racer.circuit
        marks = "".join("." if r is None else ("+" if r else "x") for r in c.results)
        text = (f"{car.id.upper()}  P{racer.place}  LAP {racer.lap}/{config.LAPS}  "
                f"{car.speed / config.TOP_SPEED:4.0%}  STREAK {c.streak}  "
                f"BOOST {car.boost:+.0%} {car.boost_time:3.1f}s  NEXT {c.target[c.filled] if c.filled < len(c.target) else '-'}"
                f"  ITEM {racer.item or '-'}{'  SPLIT ' + str(racer.split_rows) if racer.split else ''}")
        screen.blit(font(12).render(text, True, config.CAR_COLORS[car.colour]),
                    (view.rect.x + 10, view.rect.y + 8))
        screen.blit(font(10).render(marks, True, (230, 235, 255)), (view.rect.x + 10, view.rect.y + 28))
    if len(views) == 2:
        pygame.draw.line(screen, (10, 10, 20), (0, 270), (W, 270), 4)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--views", type=int, choices=(1, 2), default=1)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--auto", action="store_true", help="P1 takes every right arch")
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--screenshot", help="run headless, save the last frame here and exit")
    args = parser.parse_args(argv)

    if args.screenshot:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.font.init()
        screen = pygame.Surface((W, H))
    else:
        pygame.init()
        screen = pygame.display.set_mode((W, H), pygame.SCALED)
        pygame.display.set_caption("GATE PRIX drive demo")
    race = Race(args.seed, args.views)
    statics = track.arch_objects(race.rows)
    bots = ai.field(race, args.seed)
    views = ([RoadView((0, 0, W, 270)), RoadView((0, 270, W, 270))] if args.views == 2
             else [RoadView((0, 0, W, H))])
    cache = SpriteCache.shared()
    print("target", " ".join(race.target))
    pads = [] if args.screenshot else [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
    clock = pygame.time.Clock()
    while True:
        if args.screenshot:
            if race.time >= args.seconds or race.over:
                break
            keys = None
        else:
            clock.tick(config.FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    pygame.quit()
                    return
            keys = pygame.key.get_pressed()
        controls = ai.drive(race, bots)
        for p, racer in enumerate(race.racers):
            if not racer.player:
                continue
            if (args.auto or keys is None) and p == 0:
                controls[racer.car.id] = perfect(race, racer)
            elif keys is not None:
                controls[racer.car.id] = human(keys, pads, p)
        for e in race.update(DT, controls):
            if e.kind != "bump" or e.car < e.value:  # each bump once
                print(f"{race.time:7.2f}  {e.car:7} {e.kind:6} {e.value}")
        draw(screen, views, race, statics, cache)
        if not args.screenshot:
            pygame.display.flip()
    print("places", race.places())
    pygame.image.save(screen, args.screenshot)
    print("saved", args.screenshot)


if __name__ == "__main__":
    main(sys.argv[1:])
