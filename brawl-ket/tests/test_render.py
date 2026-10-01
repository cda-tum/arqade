"""Smoke tests: bot-against-bot fights render without errors."""

from itertools import pairwise

import pygame
import pytest

from brawl_ket import palette as P
from brawl_ket import qec
from brawl_ket.bot import Bot
from brawl_ket.config import FLOOR_Y, INTERNAL_HEIGHT, INTERNAL_WIDTH
from brawl_ket.fight import Event, Fight
from brawl_ket.moves import TRIO
from brawl_ket.render import (
    DANGER_BEAT,
    DIVIDER_GAP,
    LIGHT_GAP,
    TAG_HI,
    TAG_LO,
    TAG_W,
    Renderer,
    light_xs,
    tag_state,
)


@pytest.fixture
def surface():
    pygame.init()
    return pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))


def bot_frames(n, seed=1):
    """n frames of bot-against-bot TRIO fights, starting a new round when one ends."""
    fight, bots = None, {}
    for i in range(n):
        if fight is None or fight.over:
            fight = Fight({"p1": TRIO, "p2": TRIO})
            bots = {"p1": Bot("p1", seed + i), "p2": Bot("p2", seed + i + 1000)}
        yield fight, fight.step({k: b.input(fight) for k, b in bots.items()})


def test_600_bot_frames_draw(surface):
    r = Renderer(surface)
    kinds = set()
    for fight, events in bot_frames(600):
        r.draw_fight(fight, events)
        kinds |= {e.kind for e in events}
    assert {"hit", "logical"} <= kinds      # the effects were exercised


def test_round_pips_draw(surface):
    r = Renderer(surface)
    fight = Fight({"p1": TRIO, "p2": TRIO})
    for wins in ({"p1": 0, "p2": 0}, {"p1": 1, "p2": 0}, {"p1": 1, "p2": 1}):
        r.draw_fight(fight, [], wins)


def test_effects_expire(surface):
    r = Renderer(surface)
    fight = Fight({"p1": TRIO, "p2": TRIO})
    r.draw_fight(fight, [Event("hit", "p2", "X", 330, 220), Event("logical", "p1", "Z", 300, 250),
                         Event("corrected", "p1")])
    assert r.effects
    for _ in range(240):
        r.draw_fight(fight, [])
    assert not r.effects
    assert r.shake == 0


def test_the_floor_is_drawn_where_the_fighters_stand(surface):
    r = Renderer(surface)
    r.draw_fight(Fight({"p1": TRIO, "p2": TRIO}), [])
    # away from the fighters, just below FLOOR_Y is floor and just above it is wall
    xs = range(0, 150, 3)
    floor = {tuple(surface.get_at((x, FLOOR_Y + 3)))[:3] for x in xs} - {P.INK}
    wall = {tuple(surface.get_at((x, FLOOR_Y - 12)))[:3] for x in xs} - {P.INK}
    assert floor and wall and not floor & wall


def tags_for(r, fight):
    """Where the two code tags go for the fighters as they stand (heads straight over x)."""
    tags = {p: r._tag_place(p, fight.fighters[p], (fight.fighters[p].x, 150.0 + 60 * (p == "p1")))
            for p in ("p1", "p2")}
    r._separate(tags, fight)
    return tags


def test_code_tags_stay_on_their_own_side(surface):
    r = Renderer(surface)
    for p1_x, p2_x in ((300, 330), (330, 300), (320, 320), (600, 616), (24, 40)):
        fight = Fight({"p1": TRIO, "p2": TRIO})
        fight.fighters["p1"].x, fight.fighters["p2"].x = p1_x, p2_x
        r._reset()
        tags = tags_for(r, fight)
        a, b = tags["p1"][0], tags["p2"][0]
        assert abs(a - b) >= TAG_W - 1e-9, (p1_x, p2_x)        # even 60 px apart vertically
        if p1_x != p2_x:
            assert (a < b) == (p1_x < p2_x), (p1_x, p2_x)
        assert TAG_LO <= min(a, b) and max(a, b) <= TAG_HI, (p1_x, p2_x)


def test_a_cancel_blends_out_of_the_pose_drawn(surface):
    from brawl_ket.poses import EASE_FRAMES, POSES, lerp

    r = Renderer(surface)
    f = Fight({"p1": TRIO, "p2": TRIO}).fighters["p1"]
    jab, heavy = TRIO.moves["stand.A"], TRIO.moves["stand.B"]
    f.action, f.move, f.slot, f.frame = "attack", jab, "stand.A", jab.startup
    assert r._pose("p1", f) == POSES["jab_hit"]
    f.move, f.slot, f.frame = heavy, "stand.B", 0          # cancelled into the heavy
    assert r._pose("p1", f) == lerp(POSES["jab_hit"], POSES["heavy_wind"], 1 / EASE_FRAMES)
    f.move, f.slot, f.frame = jab, "stand.A", jab.startup   # and a jab into a jab: frame went back
    r._pose("p1", f)
    f.frame = 0
    assert r._pose("p1", f) == lerp(POSES["jab_hit"], POSES["jab_wind"], 1 / EASE_FRAMES)


def test_tag_state_is_danger_once_t_lights_are_down():
    for distance in (3, 5, 7):
        code = qec.Code(distance, 120)
        states = []
        for _ in range(code.t + 1):
            states.append(tag_state(code))
            code.hit(qec.X)
        assert states == ["ok"] * code.t + ["danger"], distance
        assert tag_state(code) == "ok"     # the last hit was one more than t: a logical error, re-encoded


def test_the_majority_line_sits_after_the_first_t_lights():
    for n in (3, 5):
        t = (n - 1) // 2
        xs = light_xs(100.0, n, t)
        gaps = [b - a for a, b in pairwise(xs)]
        assert gaps[t - 1] == LIGHT_GAP + DIVIDER_GAP       # the room for the line
        assert [g for i, g in enumerate(gaps) if i != t - 1] == [LIGHT_GAP] * (n - 2)


def colours_in_tag(surface, r, fight, key, frames):
    """Every colour drawn in a tag's rectangle, over `frames` frames."""
    seen = set()
    for _ in range(frames):
        r.draw_fight(fight, [])
        tag_y = r.tag_y[key]
        x = round(fight.fighters[key].x)
        area = pygame.Rect(x - TAG_W // 2, round(tag_y) - 20, TAG_W, 34).clip(surface.get_rect())
        seen |= {tuple(surface.get_at((i, j)))[:3] for i in range(area.left, area.right)
                 for j in range(area.top, area.bottom)}
    return seen


def test_the_danger_state_is_drawn_on_the_tag(surface):
    r = Renderer(surface)
    fight = Fight({"p1": TRIO, "p2": TRIO})
    p2 = fight.fighters["p2"]
    safe = colours_in_tag(surface, r, fight, "p2", DANGER_BEAT * 2)
    assert P.ORANGE not in safe
    assert tag_state(p2.code) == "ok"
    p2.code.hit(qec.X)                       # t = 1 light down: the next X is a logical error
    assert tag_state(p2.code) == "danger"
    danger = colours_in_tag(surface, r, fight, "p2", DANGER_BEAT * 2)
    assert P.ORANGE in danger                # the unflipped lights pulse orange
    assert P.lighten(P.ORANGE, 0.3) in danger  # ... between two shades of it
    assert P.BAD in danger                   # the flipped light, and the blinking "!"


def test_a_bot_fight_with_the_danger_state_draws(surface):
    r = Renderer(surface)
    danger_seen = False
    for fight, events in bot_frames(900):
        r.draw_fight(fight, events)
        danger_seen |= any(tag_state(f.code) == "danger" for f in fight.fighters.values())
    assert danger_seen


def probe_tag(surface, r, fight, key, beat_on):
    """Draw one frame with the pulse on (or off) and return its pixels' view of p's tag:
    (cy, the x columns with a 12 px white run (the majority line), the colours drawn in the
    band right of the ket label)."""
    r.t = 0 if beat_on else DANGER_BEAT // 2
    r.draw_fight(fight, [])
    r.t -= 1                         # draw_fight counted a frame; keep the beat where it was drawn
    cy = round(r.tag_y[key])
    x_lo, x_hi = round(fight.fighters[key].x) - 40, round(fight.fighters[key].x) + 40
    line = [x for x in range(x_lo, x_hi)
            if all(tuple(surface.get_at((x, y)))[:3] == P.WHITE for y in range(cy - 6, cy + 6))]
    bang = {tuple(surface.get_at((x, y)))[:3] for x in range(x_hi - 52, x_hi) for y in range(cy - 18, cy - 6)}
    return line, bang


def test_the_majority_line_and_the_bang_are_drawn(surface):
    r = Renderer(surface)
    fight = Fight({"p1": TRIO, "p2": TRIO})
    p2 = fight.fighters["p2"]
    bang_colours = (P.BAD, P.lighten(P.BAD, 0.5))
    line, bang = probe_tag(surface, r, fight, "p2", True)
    assert len(line) == 2 and line[1] == line[0] + 1       # the 2 px majority line, in every state
    assert not set(bang_colours) & bang                    # and no "!" while the code is safe
    p2.code.hit(qec.X)
    for beat_on, colour in ((True, bang_colours[0]), (False, bang_colours[1])):
        line2, bang2 = probe_tag(surface, r, fight, "p2", beat_on)
        assert line2 == line                                # the line stays put
        assert colour in bang2, beat_on                     # the "!" is there on both halves of the beat
