import random

import pygame
import pytest

from gate_prix import circuit, config, sprites, track
from gate_prix.road import RoadView
from gate_prix.sprites import Background, SpriteCache
from gate_prix.track import SEG, Track

pygame.font.init()


def flat(n=400, curve=0.0):
    return Track([curve] * n, [0.0] * n)


def crest(n=400, at=30, drop=-4000.0, over=20):
    """Flat up to segment `at`, then a steep drop over `over` segments, then flat."""
    hills = [0.0] * n
    for i in range(at, at + over):
        hills[i] = drop / over
    hills[-1] = -drop  # close the lap's height far behind the camera
    return Track([0.0] * n, hills)


# --- Projection -----------------------------------------------------------------------------


def test_a_segment_further_away_is_higher_and_narrower():
    view = RoadView((0, 0, 960, 270))
    view.project(flat(), cam_z=1234.0, cam_x=0.0)
    ks = [k for k in range(view.segments + 1) if view.z[k] > 100]
    for a, b in zip(ks, ks[1:]):
        assert view.sy[b] < view.sy[a]  # higher on screen
        assert view.sw[b] < view.sw[a]  # narrower
        assert view.sy[b] > view.horizon  # but never above the horizon on the flat
    on_screen = [k for k in ks[:-1] if view.sy[k + 1] < view.height]
    assert len(on_screen) > 100 and all(view.visible[k] for k in on_screen)


def test_the_road_is_centred_under_a_centred_camera_and_shifts_when_it_moves():
    view = RoadView((0, 0, 960, 270))
    view.project(flat(), cam_z=0.0, cam_x=0.0)
    assert view.sx[10] == pytest.approx(480)
    view.project(flat(), cam_z=0.0, cam_x=0.5)
    assert view.sx[10] < 480  # the camera moved right, so the road moved left


def test_a_right_bend_moves_the_far_road_right():
    view = RoadView((0, 0, 960, 270))
    view.project(flat(curve=2.0), cam_z=0.0, cam_x=0.0)
    assert view.sx[60] > view.sx[30] > view.sx[10] > 480


def test_the_one_player_view_has_the_same_horizon_fraction():
    small, big = RoadView((0, 0, 960, 270)), RoadView((0, 0, 960, 540))
    assert small.horizon == 112 and big.horizon == 224
    for view in (small, big):  # the camera's own car sits just above the bottom
        view.project(flat(), 0.0, 0.0)
        x, y, scale, clip = view.place(config.CAR_AHEAD, 0.0)
        assert y / view.height == pytest.approx(260 / 270, abs=0.01)


def test_the_hill_clip_hides_the_segments_behind_a_crest():
    view = RoadView((0, 0, 960, 270))
    view.project(crest(), cam_z=0.0, cam_x=0.0)
    before = [k for k in range(25) if view.sy[k + 1] < view.height]
    assert len(before) > 15
    assert all(view.visible[k] for k in before)
    hidden = list(range(31, 45))  # the drop just past the crest
    assert not any(view.visible[k] for k in hidden)
    crest_y = view.sy[30]
    for k in hidden:  # their sprites are clipped at the crest
        assert view.clip[k] == pytest.approx(crest_y)
        assert view.sy[k] > view.clip[k]
    # on the flat it never happens
    view.project(flat(), 0.0, 0.0)
    assert all(view.clip[k] == pytest.approx(min([270.0] + view.sy[1:k + 1])) for k in range(1, 100))


def test_place_interpolates_between_segment_points():
    view = RoadView((0, 0, 960, 270))
    view.project(flat(), cam_z=0.0, cam_x=0.0)
    x, y, scale, _ = view.place(10 * SEG, 0.0)
    assert (x, y, scale) == pytest.approx((view.sx[10], view.sy[10], view.sw[10]))
    x, _, _, _ = view.place(10 * SEG, 1.0)
    assert x == pytest.approx(view.sx[10] + view.sw[10])  # one half-width to the right
    assert view.place(-5.0, 0.0) is None
    assert view.place(config.DRAW_SEGMENTS * SEG + 10, 0.0) is None


# --- Drawing --------------------------------------------------------------------------------


def test_draw_reports_sprites_far_to_near_with_roadside_and_objects():
    fridge = track.fridge()
    surface = pygame.Surface((960, 540))
    view = RoadView((0, 270, 960, 270))
    out = [("stale", 0, 0, 0, 0)]
    objects = [(5000.0, 0.3, "arch:H:lit"), (9000.0, -0.5, "box"), (2000.0, 0.0, "car:green"),
               (-500.0, 0.0, "car:lime")]  # behind the camera: not drawn
    view.draw(surface, fridge, 0.0, 0.0, out, objects)
    kinds = [s[0] for s in out]
    assert "stale" not in kinds
    assert {"arch:H:lit", "box", "car:green", "coax"} <= set(kinds)
    assert "car:lime" not in kinds
    scales = [s[3] for s in out]
    assert scales == sorted(scales)  # far (small) to near (big)
    view.draw_sprites(surface, out)
    # it drew into its own rect: the top view's area is still black
    assert surface.get_at((480, 100))[:3] == (0, 0, 0)
    assert surface.get_at((480, 400))[:3] != (0, 0, 0)


@pytest.mark.parametrize("size", [(960, 270), (960, 540)])
def test_every_gate_row_is_readable_a_second_ahead(size):
    """From a second before its row reaches the camera's car until it does, the row stands
    on screen, within the draw distance, and no crest hides it."""
    fridge = track.fridge()
    view = RoadView((0, 0, *size))
    target = circuit.random_target(random.Random(0), config.SLOTS)
    for row in track.gate_rows(fridge, target, 0)[: config.ROWS_PER_LAP]:
        arrive = row.z - config.CAR_AHEAD
        for t in range(0, 49, 4):  # 1 s ahead to 0.2 s ahead, at top speed
            cam_z = arrive - config.TOP_SPEED * (1 - t / 60)
            cam_x = fridge.segment_at(cam_z).line
            view.project(fridge, cam_z, cam_x)
            # the whole row is on screen in the first half second, its centre always
            offsets = (-0.8, 0.0, 0.8) if t <= 30 else (0.0,)
            for offset in offsets:
                placed = view.place(row.z - cam_z, offset)
                assert placed is not None, (row.slot, t)
                x, y, scale, clip_y = placed
                assert 0 < x < size[0], (row.slot, t, offset, x)
                # the arch's crown (its top) is above the crest, its feet nearly so
                crown = y - config.ARCH_HALF_WIDTH * scale
                assert crown < clip_y, (row.slot, t)
                assert y <= clip_y + 2, (row.slot, t, y, clip_y)


# --- Sprites and backgrounds ----------------------------------------------------------------


@pytest.fixture(scope="module")
def cache():
    return SpriteCache.shared()


def test_the_sprite_cache_holds_every_kind_at_every_size(cache):
    assert len(cache.scales) == config.SPRITE_SIZES
    expected = {"coax", "attenuator", "standoff", "box", "clone"}
    expected |= {f"arch:{g}" for g in circuit.GATES} | {f"arch:{g}:lit" for g in circuit.GATES}
    expected |= {f"car:{name}" for name in config.CAR_COLORS}
    assert set(cache.images) == expected
    for kind, images in cache.images.items():
        assert len(images) == config.SPRITE_SIZES
        heights = [img.get_height() for img, _, _ in images]
        # within a pixel: far away an arch's badge keeps a minimum size, so it barely grows
        assert all(b >= a - 1 for a, b in zip(heights, heights[1:])), kind
        assert heights[-1] > 4 * heights[0], kind


def test_a_gate_letter_keeps_a_minimum_size_far_away(cache):
    """A second ahead an arch is ~12 px high: its badge must still be big enough to read."""
    for kind in ("arch:H", "arch:H:lit"):
        img, ax, ay = cache.images[kind][0]
        r = config.ARCH_HALF_WIDTH * cache.scales[0]
        # the badge (min letter 10 px, badge 1.6x that) stands above the crown
        assert ay - r >= 0.55 * 1.6 * sprites.BADGE_LETTER_MIN - 1, kind


def test_the_sprite_cache_builds_once(cache, monkeypatch):
    assert SpriteCache.shared() is cache

    def refuse(*args, **kwargs):
        raise AssertionError("a sprite was rebuilt after start-up")

    monkeypatch.setattr(sprites, "render_sprite", refuse)
    monkeypatch.setattr(pygame.transform, "smoothscale", refuse)
    monkeypatch.setattr(pygame.transform, "scale", refuse)
    assert SpriteCache.shared() is cache
    surface = pygame.Surface((960, 270))
    for kind in cache.images:
        for scale in (18, 25, 77, 300, 999, 1080):
            assert cache.blit(surface, kind, 480, 200, scale)


def test_blit_picks_the_nearest_size_and_skips_what_is_too_near(cache):
    for i, scale in enumerate(cache.scales):
        assert cache.index(scale) == i
        assert cache.index(scale * 1.04) == i
    assert cache.index(config.SPRITE_SCALE_MAX * 1.2) is None
    assert cache.index(5) is None


def test_blit_hides_what_is_below_the_clip(cache):
    surface = pygame.Surface((400, 400), pygame.SRCALPHA)
    assert not cache.blit(surface, "coax", 200, 300, 300, clip_y=300 - 200)  # all below
    surface.fill((0, 0, 0, 0))
    assert cache.blit(surface, "coax", 200, 300, 300, clip_y=250)
    assert surface.get_bounding_rect().bottom <= 250


def test_backgrounds_are_built_once_per_view_size():
    a = Background.for_size((960, 270))
    assert Background.for_size((960, 270)) is a
    b = Background.for_size((960, 540))
    assert b is not a and b.horizon == 224
    assert a.far.get_size() == (1920, 270)
    # the far layer repeats every view width, so the parallax can wrap
    for x in (5, 300, 700):
        assert a.far.get_at((x, 60)) == a.far.get_at((x + 960, 60))


def test_the_camera_rides_above_its_car_so_the_car_stays_put_on_hills():
    fridge = track.fridge()
    view = RoadView((0, 0, 960, 270))
    view.project(fridge, 0.0, 0.0)
    flat_y = view.place(config.CAR_AHEAD, 0.0)[1]
    for start, end in fridge.drops:
        for k in range(start - 20, end + 20, 5):
            cam_z = k * SEG - config.CAR_AHEAD
            view.project(fridge, cam_z, 0.0)
            assert view.place(config.CAR_AHEAD, 0.0)[1] == pytest.approx(flat_y, abs=0.5)
