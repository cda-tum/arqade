"""Smoke tests: bot-against-bot fights render without errors."""

from itertools import pairwise

import pygame
import pytest

from brawl_ket import palette as P
from brawl_ket import qec
from brawl_ket.bot import Bot
from brawl_ket.config import FLOOR_Y, INTERNAL_HEIGHT, INTERNAL_WIDTH
from brawl_ket.fight import Event, Fight
from brawl_ket.fighter import TELEGRAPH_FRAMES
from brawl_ket.moves import CHARACTERS, QUINT, TRIO
from brawl_ket.render import (
    DANGER_BEAT,
    DIVIDER_GAP,
    LIGHT_GAP,
    Renderer,
    light_xs,
    tag_bounds,
    tag_half,
    tag_state,
)

PAIRINGS = [(a, b) for a in CHARACTERS.values() for b in CHARACTERS.values()]


@pytest.fixture
def surface():
    pygame.init()
    return pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))


def bot_frames(n, seed=1, chars=(TRIO, TRIO)):
    """n frames of bot-against-bot fights, starting a new round when one ends."""
    fight, bots = None, {}
    for i in range(n):
        if fight is None or fight.over:
            fight = Fight({"p1": chars[0], "p2": chars[1]})
            bots = {"p1": Bot("p1", seed + i), "p2": Bot("p2", seed + i + 1000)}
        yield fight, fight.step({k: b.input(fight) for k, b in bots.items()})


@pytest.mark.parametrize("chars", PAIRINGS, ids=lambda cs: "-".join(c.name for c in cs))
def test_600_bot_frames_draw(surface, chars):
    r = Renderer(surface)
    kinds = set()
    for fight, events in bot_frames(600, chars=chars):
        r.draw_fight(fight, events)
        kinds |= {e.kind for e in events}
    assert {"hit", "logical"} <= kinds      # the effects were exercised


def test_the_shockwave_and_reencode_effects_draw_and_expire(surface):
    r = Renderer(surface)
    fight = Fight({"p1": QUINT, "p2": TRIO})
    r.draw_fight(fight, [])
    r.draw_fight(fight, [Event("shockwave", "p1", "Z", fight.fighters["p1"].x, FLOOR_Y),
                         Event("reencode", "p1")])
    kinds = {fx.kind for fx in r.effects}
    assert {"wave", "pulse"} <= kinds
    assert r.flash["p1"][0] is not None             # the lights flash as they are wiped
    # the wave is drawn along the floor, around where the slam landed, then in Z's colour
    x = round(fight.fighters["p1"].x)
    row = {tuple(surface.get_at((i, FLOOR_Y - 2)))[:3] for i in range(x - 50, x + 50)}
    assert P.WHITE in row                           # the white flash of the impact
    for _ in range(8):                              # and it spreads out to the shockwave's reach
        r.draw_fight(fight, [])
    far = {tuple(surface.get_at((i, j)))[:3] for i in range(x - 56, x - 30) for j in range(FLOOR_Y - 12, FLOOR_Y + 8)}
    assert far & {P.GATE["Z"], P.lighten(P.GATE["Z"], 0.35)}
    for _ in range(120):
        r.draw_fight(fight, [])
    assert not r.effects


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


@pytest.mark.parametrize("chars", PAIRINGS, ids=lambda cs: "-".join(c.name for c in cs))
def test_code_tags_stay_on_their_own_side(surface, chars):
    r = Renderer(surface)
    h1, h2 = (tag_half(c.distance) for c in chars)
    for p1_x, p2_x in ((300, 330), (330, 300), (320, 320), (600, 616), (24, 40), (616, 600)):
        fight = Fight({"p1": chars[0], "p2": chars[1]})
        fight.fighters["p1"].x, fight.fighters["p2"].x = p1_x, p2_x
        r._reset()
        tags = tags_for(r, fight)
        a, b = tags["p1"][0], tags["p2"][0]
        assert abs(a - b) >= h1 + h2 - 1e-9, (p1_x, p2_x)      # even 60 px apart vertically
        if p1_x != p2_x:
            assert (a < b) == (p1_x < p2_x), (p1_x, p2_x)
        for x, c in ((a, chars[0]), (b, chars[1])):
            lo, hi = tag_bounds(c.distance)
            assert lo - 1e-9 <= x <= hi + 1e-9, (p1_x, p2_x)
            assert x - tag_half(c.distance) >= 0 and x + tag_half(c.distance) <= INTERNAL_WIDTH


BLANK = (1, 2, 3)


def drawn_columns(surface, r, f, key, cx=320, cy=120):
    """Draw only key's tag, centred at cx on a blank surface; the x range of what was drawn."""
    surface.fill(BLANK)
    r._code_tag(key, f, [cx, cy, cx], 0, 0)
    xs = [x for x in range(INTERNAL_WIDTH) for y in range(cy - 24, cy + 14)
          if tuple(surface.get_at((x, y)))[:3] != BLANK]
    return min(xs), max(xs)


@pytest.mark.parametrize("char", list(CHARACTERS.values()), ids=lambda c: c.name)
def test_a_tag_is_drawn_inside_its_own_width(surface, char):
    r = Renderer(surface)
    fight = Fight({"p1": TRIO, "p2": char})
    f = fight.fighters["p2"]
    half = tag_half(char.distance)
    left, right = drawn_columns(surface, r, f, "p2")
    assert 320 - half <= left and right <= 320 + half
    for _ in range(f.code.t):
        f.code.hit(qec.X)                    # danger: the "!" beside the ket is the widest part
    assert tag_state(f.code) == "danger"
    left, right = drawn_columns(surface, r, f, "p2")
    assert 320 - half <= left and right <= 320 + half
    assert right >= 320 + half - 2           # and the width is not padded out
    r.flash["p2"] = (P.GOOD, 21)
    left, right = drawn_columns(surface, r, f, "p2")
    assert 320 - half <= left and right <= 320 + half


def test_a_bigger_code_has_a_wider_tag(surface):
    assert tag_half(5) > tag_half(3)
    assert tag_bounds(5)[0] > tag_bounds(3)[0] and tag_bounds(5)[1] < tag_bounds(3)[1]


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
    half = round(tag_half(fight.fighters[key].char.distance))
    for _ in range(frames):
        r.draw_fight(fight, [])
        tag_y = r.tag_y[key]
        x = round(fight.fighters[key].x)
        area = pygame.Rect(x - half, round(tag_y) - 20, 2 * half, 34).clip(surface.get_rect())
        seen |= {tuple(surface.get_at((i, j)))[:3] for i in range(area.left, area.right)
                 for j in range(area.top, area.bottom)}
    return seen


@pytest.mark.parametrize("char", list(CHARACTERS.values()), ids=lambda c: c.name)
def test_the_danger_state_is_drawn_on_the_tag(surface, char):
    r = Renderer(surface)
    fight = Fight({"p1": TRIO, "p2": char})
    p2 = fight.fighters["p2"]
    safe = colours_in_tag(surface, r, fight, "p2", DANGER_BEAT * 2)
    assert P.ORANGE not in safe
    assert tag_state(p2.code) == "ok"
    for _ in range(p2.code.t):
        p2.code.hit(qec.X)                   # t lights down: the next X is a logical error
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


# --- the telegraph glint on a neutral heavy or sweep -------------------------------------------


def striker_pixels(r, f, key, joint):
    """The colour on the striking joint's centre, on the last frame drawn."""
    from brawl_ket.poses import joints

    feet = (f.x, FLOOR_Y - f.y)
    cx, cy = (round(v) for v in joints(r.pose_last[key], f.char.build, feet, f.facing)[joint])
    return r.surface.get_at((cx, cy))[:3]


def glint_run(surface, pressed, joint, prep=lambda fight: None, char=TRIO):
    """Start a move for p1 and draw every frame of its startup; returns [(telegraphing, centre)]."""
    from brawl_ket.fighter import IDLE

    r = Renderer(surface)
    fight = Fight({"p1": char, "p2": TRIO})
    prep(fight)
    p1 = fight.fighters["p1"]
    seen = []
    for i in range(char.moves["stand.B"].startup + 1):
        events = fight.step({"p1": pressed if i == 0 else IDLE, "p2": IDLE})
        r.draw_fight(fight, events)
        if p1.action == "attack" and p1.phase == "startup":
            seen.append((p1.telegraphing, striker_pixels(r, p1, "p1", joint)))
    return seen


@pytest.mark.parametrize("char", list(CHARACTERS.values()), ids=lambda c: c.name)
def test_the_glint_blinks_at_the_striking_hand_only_in_the_last_16_frames(surface, char):
    from brawl_ket.fighter import FighterInput

    seen = glint_run(surface, FighterInput(b=True), "hand_f", char=char)
    assert len(seen) == char.moves["stand.B"].startup
    early = [c for tele, c in seen if not tele]
    window = [c for tele, c in seen if tele]
    assert len(window) == TELEGRAPH_FRAMES == 16 and P.WHITE not in early
    assert P.WHITE in window and any(c != P.WHITE for c in window)     # it blinks


@pytest.mark.parametrize("char", list(CHARACTERS.values()), ids=lambda c: c.name)
def test_the_sweeps_glint_is_at_the_foot(surface, char):
    from brawl_ket.fighter import FighterInput

    seen = glint_run(surface, FighterInput(down=True, b=True), "foot_f",
                     prep=lambda fight: fight.fighters["p1"].code.switch(), char=char)
    window = [c for tele, c in seen if tele]
    assert len(window) == 16 and P.WHITE in window and any(c != P.WHITE for c in window)


def test_quint_is_drawn_broader_than_trio(surface):
    # the same pose (arms up, out of the way): across the chest, QUINT is far broader
    from brawl_ket.poses import POSES, joints
    from brawl_ket.render import draw_puppet

    widths = {}
    for c in (TRIO, QUINT):
        surface.fill(BLANK)
        pose = POSES["slam"]
        draw_puppet(surface, pose, c.build, (320, FLOOR_Y), 1, (64, 136, 248), P.GOLD)
        j = joints(pose, c.build, (320, FLOOR_Y), 1)
        chest = round(j["hip"][1] + 0.6 * (j["shoulder_f"][1] - j["hip"][1]))
        xs = [x for x in range(INTERNAL_WIDTH) if tuple(surface.get_at((x, chest)))[:3] != BLANK]
        widths[c.name] = max(xs) - min(xs) + 1
    assert widths["QUINT"] >= widths["TRIO"] * 1.6, widths
