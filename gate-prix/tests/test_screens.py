"""The second playtest's screens: the HOW TO PLAY demo, the minimap and the renderer's
new pieces (drawn from caches only: nothing is scaled or rendered per frame)."""

import random

import pygame
import pytest

from gate_prix import config, icons, sprites, track
from gate_prix.match import HOWTO, RACE, Banner, FrameInput, Match, PlayerInput
from gate_prix.minimap import Minimap
from gate_prix.race import Cloud, Shot
from gate_prix.tutorial import Demo

DT = 1 / 60


# --- The HOW TO PLAY demo ----------------------------------------------------------------------


def test_the_demo_steers_through_the_right_arch_boosts_then_starts_over():
    demo = Demo()
    car = demo.car
    assert demo.phase == 0 and demo.row.z > car.z
    right = next(a for a in demo.row.arches if a.right)
    assert abs(car.x - right.offset) > 0.5  # it has to steer to get there
    seen = []
    for _ in range(round(6.5 / DT)):
        seen += [e.kind for e in demo.update(DT)]
        if demo.phase == 1 and demo.after < 1.0:
            assert demo.car.boost > 0
    assert seen.count("right") >= 2 and "wrong" not in seen and "miss" not in seen
    assert any(kind.startswith("flame:") for _, _, kind in demo.objects()) or demo.phase == 0


# --- The minimap -------------------------------------------------------------------------------


def test_the_minimap_is_the_lap_from_above_fitted_in_its_box():
    pygame.font.init()
    fridge = track.fridge()
    mm = Minimap.for_track(fridge, (170, 118))
    assert Minimap.for_track(fridge, (170, 118)) is mm
    xs = [p[0] for p in mm.points]
    ys = [p[1] for p in mm.points]
    assert 0 <= min(xs) and max(xs) <= 170 and 0 <= min(ys) and max(ys) <= 118
    start, end = mm.points[0], mm.points[-1]
    assert abs(start[0] - end[0]) < 2 and abs(start[1] - end[1]) < 2  # the lap closes
    lap = fridge.lap_length()
    assert mm.point(lap) == pytest.approx(mm.point(0.0))
    assert mm.point(2 * lap + 500) == pytest.approx(mm.point(500.0))
    surface = pygame.Surface((300, 200))
    surface.fill((0, 0, 0))
    mm.draw(surface, (10, 10), [("p1", 1000.0), ("green", 80000.0)], players=("p1",))
    x, y = mm.point(1000.0)
    got = surface.get_at((10 + round(x), 10 + round(y)))[:3]
    assert all(abs(a - b) <= 4 for a, b in zip(got, config.PLAYER_COLORS["p1"]))


# --- The renderer ------------------------------------------------------------------------------


def frame(p1=None, p2=None):
    return FrameInput({"p1": PlayerInput(**(p1 or {})), "p2": PlayerInput(**(p2 or {}))},
                      activity=True)


@pytest.fixture(scope="module")
def renderer():
    if not pygame.font.get_init():
        pygame.font.init()
    sprites._FONTS.clear()  # a test before may have quit pygame: its cached fonts are dead
    from gate_prix.render import Renderer

    return Renderer(pygame.Surface((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT)))


def started(mode):
    m = Match(random.Random(2))
    m.update(DT, FrameInput())
    if mode == 2:
        m.update(DT, frame(p1={"nav": (0, 1)}))
    m.update(DT, frame(p1={"start": True, "held": True}))
    assert m.state == HOWTO
    for _ in range(30):
        m.update(DT, FrameInput())
    m.update(DT, frame(p2={"button": True}))
    for _ in range(round(config.COUNTDOWN / DT) + 2):
        m.update(DT, FrameInput())
    assert m.state == RACE
    return m


def busy(m):
    """Every new effect at once: a drift, a turbo flash, a tunnel, a shot, a cloud, a blind
    racer, held items, a tip and a reveal, the storm, the final lap's banner."""
    race = m.race
    p1 = race.racer("p1")
    p1.car.drifting, p1.car.drift_dir, p1.car.drift_time, p1.car.drift_angle = True, 1, 1.6, 0.3
    p1.car.turbo_level, p1.car.turbo_flash = 2, 0.2
    p1.item = "MEASURE"
    green = race.racer("green")
    green.car.tunnel_time = 2.0
    race.shots.append(Shot("p1", "green", 0.2))
    race.clouds.append(Cloud(0, p1.car.z + 3000, 0.0, "white", 5.0))
    p1.blind_time = 1.0
    m.banners["p1"] += [Banner("tip", "TUNNEL", 1.0), Banner("final", 3, 2.0)]
    m.banners["p1"].append(Banner("reveal", "DECOHERENCE", 0.5))
    from gate_prix import storm

    p1.hazards = storm.storm(random.Random(1), 8, p1.car.z + 2000, p1.car.z + 60000, race.track)


@pytest.mark.parametrize("mode", [1, 2])
def test_a_race_with_every_new_effect_draws_from_caches_only(renderer, monkeypatch, mode):
    m = started(mode)
    busy(m)
    renderer.draw(m)  # the first frame may fill the text cache

    def refuse(*args, **kwargs):
        raise AssertionError("scaled or re-rendered per frame")

    for name in ("smoothscale", "scale", "rotozoom", "rotate"):
        monkeypatch.setattr(pygame.transform, name, refuse)
    monkeypatch.setattr(sprites, "render_sprite", refuse)
    for _ in range(20):
        m.update(DT, FrameInput())
        renderer.draw(m)


def test_the_title_the_card_and_quit_draw(renderer):
    m = Match(random.Random(3))
    m.update(DT, FrameInput())
    for _ in range(2):
        m.update(DT, frame(p1={"nav": (0, 1)}))
    assert m.title_index == 2
    renderer.draw(m)
    m.update(DT, frame(p1={"start": True, "held": True}))
    assert m.state == HOWTO
    for _ in range(60):
        m.update(DT, FrameInput())
        renderer.draw(m)
    assert renderer.howto.demo.race.time > 0.9


def test_every_item_has_an_icon_at_every_size_used():
    pygame.font.init()
    for item in config.ITEMS:
        for size in (30, 44, 56):
            img = icons.icon(item, size)
            assert img.get_size() == (size, size) and icons.icon(item, size) is img
