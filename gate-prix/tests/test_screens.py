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
    m.banners["p1"].append(Banner("full", "MEASURE", 0.5))
    if "p2" in m.players:
        m.race.racer("p2").item = "SPLIT"
        m.banners["p2"].append(Banner("full", "SPLIT", 0.5))
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


def _close(got, want, tol=40):
    return sum(abs(a - b) for a, b in zip(got[:3], want)) <= tol


@pytest.mark.parametrize("size,spread", [((960, 540), None), ((480, 540), config.VIEW_2P_SPREAD)])
def test_the_gantry_is_drawn_at_its_exact_size_as_the_cars_pull_away(size, spread):
    """The start's flicker: the gantry used to be a sprite of the nearest cached size, 18%
    apart, so as the grid pulled away under it its posts and banner jumped every few frames
    and its lights (placed exactly) slid out of their sockets. Every frame from the back
    row of the grid to the line, its posts, its banner's gold edge and its lit lights must
    be where the road's projection puts them, and its width must only grow."""
    from gate_prix import gantry
    from gate_prix.road import RoadView

    pygame.font.init()
    sprites._FONTS.clear()
    view = RoadView((0, 0, *size), spread=spread)
    fridge = track.fridge()
    surface = pygame.Surface(size)
    found: list = []
    gantry.Gantry.shared().lights = ("green", 5)
    z, speed, widths = -2300.0, 0.0, []
    while z < -300:
        cam = z - config.CAR_AHEAD
        view.draw(surface, fridge, cam, -0.4, found, [(0.0, 0.0, "gantry")])
        view.draw_sprites(surface, found)
        x, y, u, _ = view.place(-cam, 0.0)
        row = round(y - 0.5 * u)
        steel = [i for i in range(size[0]) if _close(surface.get_at((i, row)), gantry.STEEL, 12)
                 or _close(surface.get_at((i, row)), gantry.SHINE, 12)]
        posts = [x + side * gantry.POST * u for side in (-1, 1)]
        seen = [p for p in posts if 0 <= p - gantry.POST_W * u / 2 and p + gantry.POST_W * u / 2 < size[0]]
        for p in seen:  # each post in sight is a post's width of steel, where it should be
            near = [i for i in steel if abs(i - p) <= gantry.POST_W * u / 2 + 2]
            assert near and abs(min(near) - (p - gantry.POST_W * u / 2)) <= 1.5, (z, p, near[:3])
        if len(seen) == 2:
            widths.append(max(steel) - min(steel))
        edge_y = round(y - (gantry.BANNER + gantry.EDGE / 2) * u)
        for ex in (x - 0.9 * u, x + 0.9 * u):
            if 0 <= round(ex) < size[0] and 0 <= edge_y and gantry.EDGE * u >= 3:
                assert _close(surface.get_at((round(ex), edge_y)), gantry.GOLD), (z, ex)
        r = gantry.LIGHT_R * u
        ly = y - gantry.LIGHT_Y * u
        for lx in gantry.LIGHT_X:
            px, py = round(x + lx * u + 0.45 * r), round(ly + 0.45 * r)
            if r >= 3 and 0 <= px < size[0] and 0 <= py:
                assert _close(surface.get_at((px, py)), gantry.LIGHT_COLOURS["green"], 60), (z, lx)
        speed += config.ACCEL / 60
        z += speed / 60
    assert len(widths) > 10 and all(b >= a for a, b in zip(widths, widths[1:]))


@pytest.mark.parametrize("mode", [1, 2])
def test_the_gantry_holds_still_in_the_countdown_and_only_grows_as_the_race_starts(renderer, mode):
    """Through the real match and renderer: in the countdown every view's gantry is the same
    rectangle each frame; from GO to 3 s in, it only grows, at the road's exact scale, and
    once it has passed overhead it never comes back."""
    m = Match(random.Random(2))
    m.update(DT, FrameInput())
    if mode == 2:
        m.update(DT, frame(p1={"nav": (1, 0)}))
    m.update(DT, frame(p1={"start": True, "held": True}))
    for _ in range(30):
        m.update(DT, FrameInput())
    m.update(DT, frame(p2={"button": True}))
    assert m.state == "countdown"
    views = renderer.views[mode]
    still, grown = None, [[] for _ in views]
    while m.state == "countdown" or m.race.time < 3.0:
        renderer.draw(m)
        drawn = list(renderer.gantry.drawn)
        if m.state == "countdown":
            assert len(drawn) == mode
            assert still is None or drawn == still
            still = drawn
        else:
            assert len(drawn) <= mode
            for i, (view, car_id) in enumerate(zip(views, m.viewed)):
                cam = m.race.racer(car_id).car.z - config.CAR_AHEAD
                placed = view.place(-cam, 0.0)
                rect = next((rc for rc, u in drawn if placed and u == pytest.approx(placed[2])), None)
                grown[i].append(rect.width if rect else None)
        m.update(DT, FrameInput())
    for widths in grown:
        assert widths[0] is not None
        shown = [w for w in widths if w is not None]
        gone = widths.index(None) if None in widths else len(widths)
        assert all(w is None for w in widths[gone:])  # passed overhead: never back
        assert all(b >= a for a, b in zip(shown, shown[1:]))


def refuse_scaling(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("scaled or re-rendered per frame")

    for name in ("smoothscale", "scale", "rotozoom", "rotate"):
        monkeypatch.setattr(pygame.transform, name, refuse)
    monkeypatch.setattr(sprites, "render_sprite", refuse)
    from gate_prix import bloch, wordmark

    monkeypatch.setattr(bloch, "sphere", refuse)
    monkeypatch.setattr(wordmark, "build", refuse)


@pytest.mark.parametrize("mode", [1, 2])
def test_the_results_and_the_title_draw_from_caches_only(renderer, monkeypatch, mode):
    """The results' circuits, checks and Bloch spheres, and the title's wordmark, are drawn
    once at start-up: per frame they are blits."""
    from gate_prix.match import RESULT

    m = started(mode)
    m.race.racer("p1").circuit.take(0, "H")
    m._freeze()
    m._set(RESULT)
    m.t = config.RESULT_LOCK + 0.1
    renderer.draw(m)  # the first frame may fill the text cache
    refuse_scaling(monkeypatch)
    for _ in range(5):
        renderer.draw(m)
    title = Match(random.Random(4))
    title.update(DT, FrameInput())
    monkeypatch.undo()
    renderer.draw(title)
    refuse_scaling(monkeypatch)
    for _ in range(5):
        renderer.draw(title)


def test_the_title_the_card_and_quit_draw(renderer):
    from gate_prix.render import field_line, title_rows

    m = Match(random.Random(3))
    m.update(DT, FrameInput())
    assert [label for label, *_ in title_rows(m)] == list(config.TITLE_ITEMS)
    assert title_rows(m)[:3] == [("PLAYERS", "1", True, False), ("BOTS", "5", False, True),
                                 ("LEVEL", "EASY", True, False)]
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


def test_the_text_cache_is_bounded_and_keeps_what_is_still_used(renderer):
    from gate_prix.render import TEXT_CACHE

    renderer._text.clear()
    keep = renderer.text("LAP 1/3", 12)
    for i in range(TEXT_CACHE + 50):
        renderer.text(f"{i}", 10)
        if i % 100 == 0:
            assert renderer.text("LAP 1/3", 12) is keep  # used all along: never dropped
    assert len(renderer._text) <= TEXT_CACHE
    assert renderer.text("LAP 1/3", 12) is keep
    assert ("0", 10, (255, 255, 255), True) not in renderer._text  # the oldest went first


# --- Hints that name what the players hold -----------------------------------------------------


def _texts_drawn(renderer, monkeypatch, *matches) -> set[str]:
    """Every text the renderer draws for these matches (one frame each)."""
    seen: set[str] = set()
    real = type(renderer).text

    def text(self, s, *args, **kwargs):
        seen.add(s)
        return real(self, s, *args, **kwargs)

    monkeypatch.setattr(type(renderer), "text", text)
    for m in matches:
        renderer.draw(m)
    monkeypatch.undo()
    return seen


def _screens(mode: int) -> list[Match]:
    """The title, the HOW TO PLAY card, a race with an item and its tip, the pause and the
    result, for `mode` players."""
    from gate_prix.match import RESULT

    title = Match(random.Random(3))
    title.mode = mode
    title.update(DT, FrameInput())
    card = Match(random.Random(3))
    card.mode = mode
    card._set(HOWTO)
    race = started(mode)
    race.race.racer("p1").item = "MEASURE"
    race.banners["p1"].append(Banner("tip", "MEASURE", 1.0))
    paused = started(mode)
    paused.update(DT, frame(p1={"start": True}))
    result = started(mode)
    result._freeze()
    result._set(RESULT)
    result.t = config.RESULT_LOCK + 0.1
    return [title, card, race, paused, result]


def test_on_the_pads_the_hints_name_the_pads_buttons(renderer, monkeypatch):
    """The cabinet's screens: before anyone presses anything, off the browser, it's pads."""
    seen = _texts_drawn(renderer, monkeypatch, *_screens(1))
    for want in ("PRESS START", "STICK UP / DOWN: CHOOSE   LEFT / RIGHT: CHANGE   A OR START: RACE",
                 "PRESS ANY BUTTON TO START", "START + SELECT: QUIT",
                 "EITHER PAD DRIVES", "PRESS A TO USE MEASURE", "A: PICK   B OR START: RESUME",
                 "A: REMATCH        B: TITLE"):
        assert want in seen, want
    # the card's controls (its picture was drawn at start-up)
    pads = ("STICK LEFT / RIGHT", "STICK BACK", "A", "START")
    assert renderer.howto.names("p1") == renderer.howto.names(None) == pads


def test_on_the_keyboard_the_hints_name_the_keys(monkeypatch):
    """The browser's screens: everyone starts on the keyboard, P1 on W A S D with B for A,
    P2 on the arrows with L; the title, which both read, names both."""
    from arqade_common.input import KEYBOARD, LastDevice

    from gate_prix.render import Renderer

    keys = Renderer(pygame.Surface((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT)),
                    LastDevice(KEYBOARD))
    seen = _texts_drawn(keys, monkeypatch, *_screens(1))
    for want in ("PRESS SPACE / ENTER",
                 "WASD / ARROWS UP / DOWN: CHOOSE   LEFT / RIGHT: CHANGE   B / L OR SPACE / "
                 "ENTER: RACE",
                 "A / D: STEER", "S: BRAKE", "S + STEER: DRIFT", "B: USE YOUR ITEM",
                 "SPACE: PAUSE", "PRESS ANY KEY TO START", "SPACE + L-SHIFT: QUIT",
                 "WASD OR ARROW KEYS DRIVE", "PRESS B TO USE MEASURE",
                 "B: PICK   V OR SPACE: RESUME", "B: REMATCH        V: TITLE"):
        assert want in seen, want
    assert not [s for s in seen if "STICK" in s or "START:" in s or "PRESS START" in s]
    assert keys.howto.names("p1") == ("A / D", "S", "B", "SPACE")
    assert keys.howto.names("p2") == ("LEFT / RIGHT", "DOWN", "L", "ENTER")
    two = _texts_drawn(keys, monkeypatch, *_screens(2))
    for want in ("P1: WASD KEYS     P2: ARROW KEYS", "SPACE + L-SHIFT / ENTER + R-SHIFT: QUIT",
                 "PRESS B", "B / L: REMATCH        V / K: TITLE"):
        assert want in two, want
    # the 2P card names both players' keys (its picture was drawn at start-up)
    assert keys.howto.names(None) == ("A / D, LEFT / RIGHT", "S / DOWN", "B / L", "SPACE / ENTER")
