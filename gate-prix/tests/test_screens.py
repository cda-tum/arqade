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
    mm.draw(surface, (10, 10), [("p1", "p1", 1000.0), ("cpu1", "white", 80000.0)],
            players=("p1",))
    x, y = mm.point(1000.0)
    got = surface.get_at((10 + round(x), 10 + round(y)))[:3]
    assert all(abs(a - b) <= 4 for a, b in zip(got, config.PLAYER_COLORS["p1"]))


def test_every_dot_on_the_minimap_carries_its_cars_name():
    pygame.font.init()
    mm = Minimap.for_track(track.fridge(), (170, 118))
    assert set(mm._labels) == {"p1", "p2", *config.CPU_IDS}
    plain = pygame.Surface((300, 200))
    mm.draw(plain, (10, 10), [])
    for car_id, colour in (("cpu3", "silver"), ("p2", "p2")):
        surface = pygame.Surface((300, 200))
        mm.draw(surface, (10, 10), [(car_id, colour, 30000.0)], players=("p2",))
        x, y = mm.point(30000.0)
        right = pygame.Rect(10 + round(x) + 6, 10 + round(y) - 5, 20, 10)  # beside the dot
        changed = sum(surface.get_at(p) != plain.get_at(p)
                      for p in ((i, j) for i in range(right.left, right.right)
                                for j in range(right.top, right.bottom)))
        assert changed > 15, car_id


def test_in_a_bunch_the_names_never_overlap_and_the_peoples_always_show():
    pygame.font.init()
    mm = Minimap.for_track(track.fridge(), (170, 118))
    cars = [(c, c if c[0] == "p" else "white", 1000.0 + 10 * i)
            for i, c in enumerate(("p1", "p2", *config.CPU_IDS))]
    _, names = mm.layout((0, 0), cars, players=("p1", "p2"))
    ids = [car_id for car_id, _ in names]
    assert ids[:2] == ["p1", "p2"] and len(ids) < len(cars)
    rects = [r for _, r in names]
    assert all(a.collidelist([b for b in rects if b is not a]) < 0 for a in rects)
    lap = track.fridge().lap_length()
    spread = [(c, col, lap * i / 7) for i, (c, col, _) in enumerate(cars)]
    assert len(mm.layout((0, 0), spread, ("p1",))[1]) == len(cars)  # apart: every name


def test_the_peoples_cars_have_a_white_outline_the_bots_none(monkeypatch):
    pygame.font.init()

    def solid(img):
        return sum(img.get_at((i, j))[3] > 200 for i in range(img.get_width())
                   for j in range(img.get_height()))
    for kind in sprites.OUTLINED:
        with_line = sprites.render_sprite(kind, 300.0)[0]
        monkeypatch.setattr(sprites, "OUTLINED", ())
        without = sprites.render_sprite(kind, 300.0)[0]
        monkeypatch.undo()
        assert solid(with_line) > solid(without) * 1.05, kind
    assert sprites.OUTLINED == ("car:p1", "car:p2")
    assert not any(f"car:{c}" in sprites.OUTLINED for c in config.CPU_COLORS)


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
        m.update(DT, frame(p1={"nav": (1, 0)}))
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
    green = race.racer("cpu1")
    green.car.tunnel_time = 2.0
    race.shots.append(Shot("p1", "cpu1", 0.2))
    race.clouds.append(Cloud(0, p1.car.z + 3000, 0.0, "cpu2", 5.0))
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


def test_the_start_lights_go_with_the_gantry_too_near_to_draw(renderer):
    """Between the gantry's last cached size and the cut-off of the nearest-size pick
    there is no gantry: no lights either."""
    from gate_prix.road import RoadView

    view = RoadView((0, 0, 960, 540))
    cache = renderer.cache
    surface = pygame.Surface((960, 540), pygame.SRCALPHA)
    for scale in [s for s in cache.scales if s > sprites.GANTRY_MAX_SCALE][:2] + [600.0]:
        surface.fill((0, 0, 0, 0))
        renderer._gantry_lights(surface, view, [("gantry", 480, 530, scale, 540)], ("red", 5))
        drawn = cache.images["gantry"][cache.index(scale)] is not None
        assert (surface.get_bounding_rect().w > 0) == drawn, scale
    surface.fill((0, 0, 0, 0))
    renderer._gantry_lights(surface, view, [("gantry", 480, 530, 200.0, 540)], ("red", 5))
    assert surface.get_bounding_rect().w > 0


def test_the_title_the_card_and_quit_draw(renderer):
    from gate_prix.render import field_line, title_rows

    m = Match(random.Random(3))
    m.update(DT, FrameInput())
    assert [label for label, *_ in title_rows(m)] == list(config.TITLE_ITEMS)
    assert title_rows(m)[:3] == [("PLAYERS", "1", True, False), ("BOTS", "5", False, True),
                                 ("LEVEL", "TOUGH", False, False)]
    renderer.draw(m)
    m.bot_count = 0
    assert field_line(m) == "A TIME TRIAL: JUST YOU"
    m.mode = 2
    assert field_line(m) == "A DUEL: JUST THE TWO OF YOU"
    m.mode, m.bot_count = 1, 5
    for _ in range(3):
        m.update(DT, frame(p1={"nav": (0, 1)}))
    assert m.title_index == 3
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
