"""PHOEBE's three specials (docs/superpowers/specs/2026-10-09-brawl-ket-phoebe-design.md):
LIGHT PILLAR only ever catches someone in the air, TUNNEL re-forms her past the rival and makes
her untouchable only while she is gone, and the LASER hovers, flies at 45 degrees, fires once
per jump and ends on the floor. And the CPU uses all three."""

from brawl_ket.bot import Bot
from brawl_ket.config import STAGE_RIGHT, TUNNEL_EXPOSED, TUNNEL_PAST
from brawl_ket.fight import Fight, Shot
from brawl_ket.fighter import IDLE, FighterInput
from brawl_ket.moves import CHARACTERS, PHOEBE, ROBERT

X = FighterInput(x=True)
DOWN_X = FighterInput(down=True, x=True)
UP = FighterInput(up=True)
TRAP, TUNNEL, LASER = (PHOEBE.moves[s] for s in ("stand.X", "crouch.X", "air.X"))
PHOTON = ROBERT.moves["stand.X"]


def versus(c1, c2, gap):
    fight = Fight({"p1": c1, "p2": c2})
    fight.fighters["p2"].x = fight.fighters["p1"].x + gap
    return fight


def step(fight, p1=IDLE, p2=IDLE):
    return fight.step({"p1": p1, "p2": p2})


def hits_on(events, player):
    return [e for e in events if e.kind in ("hit", "block") and e.player == player]


# --- LIGHT PILLAR -----------------------------------------------------------------------------


def test_light_pillar_never_touches_a_rival_on_the_ground():
    for rival in CHARACTERS.values():
        for gap in range(20, 80, 10):
            for crouch in (False, True):
                fight = versus(PHOEBE, rival, gap)
                events = step(fight, X, FighterInput(down=crouch))
                for _ in range(TRAP.startup + TRAP.active + 4):
                    events += step(fight, IDLE, FighterInput(down=crouch))
                assert not hits_on(events, "p2"), (rival.name, gap, crouch)


def test_light_pillar_knocks_down_a_rival_jumping_in():
    fight = versus(PHOEBE, ROBERT, 120)
    me, rival = fight.fighters["p1"], fight.fighters["p2"]
    events = step(fight, IDLE, FighterInput(up=True, dx=-1))
    pressed = False
    for _ in range(60):
        press = not pressed and rival.y > 30 and rival.x - me.x <= 60
        pressed |= press
        events += step(fight, X if press else IDLE, FighterInput(dx=-1))
        if rival.action == "knockdown":
            break
    assert pressed and [e.kind for e in hits_on(events, "p2")] == ["hit"]
    assert rival.action == "knockdown"


# --- TUNNEL -----------------------------------------------------------------------------------


def tunnel(gap, rival_x=None):
    fight = versus(PHOEBE, ROBERT, gap)
    if rival_x is not None:
        fight.fighters["p2"].x = rival_x
        fight.fighters["p1"].x = rival_x - gap
    me = fight.fighters["p1"]
    states = []
    events = step(fight, DOWN_X)
    states.append((me.frame, me.intangible, me.x, me.facing))
    for _ in range(TUNNEL.startup + TUNNEL.active + TUNNEL.recovery):
        events += step(fight, FighterInput(down=True))
        states.append((me.frame, me.intangible, me.x, me.facing))
    return fight, events, states


def test_tunnel_re_forms_past_the_rival_facing_them():
    fight, events, _ = tunnel(100)
    me, rival = fight.fighters["p1"], fight.fighters["p2"]
    assert me.x == rival.x + TUNNEL_PAST
    assert me.facing == -1                      # turned round to face the rival
    assert "tunnel" in [e.kind for e in events]
    assert not hits_on(events, "p2") and not hits_on(events, "p1")


def test_tunnel_is_untouchable_only_while_she_is_gone():
    _, _, states = tunnel(100)
    for frame, intangible, _x, _facing in states:
        if frame < TUNNEL.startup + TUNNEL.active + TUNNEL.recovery:
            assert intangible == (TUNNEL_EXPOSED <= frame < TUNNEL.startup + TUNNEL.active), frame


def test_tunnel_with_no_room_behind_the_rival_re_forms_in_front():
    fight, _, _ = tunnel(100, rival_x=STAGE_RIGHT - 10)
    me, rival = fight.fighters["p1"], fight.fighters["p2"]
    assert me.x == rival.x - TUNNEL_PAST and me.facing == 1


def test_a_shot_passes_through_her_while_she_is_gone():
    for gone in (True, False):
        fight = versus(PHOEBE, ROBERT, 200)
        me = fight.fighters["p1"]
        if gone:
            step(fight, DOWN_X)
            while not me.intangible:
                step(fight, FighterInput(down=True))
        fight.shots.append(Shot("p2", PHOTON, me.x, 0.0, -PHOTON.projectile.speed, 200))
        events = step(fight, FighterInput(down=gone))
        assert bool(hits_on(events, "p1")) is not gone


# --- LASER ------------------------------------------------------------------------------------


def jump_and_fire(fight, fire_at=8):
    events = step(fight, UP)
    for _ in range(fire_at - 1):
        events += step(fight)
    events += step(fight, X)
    return events


def test_the_laser_hovers_and_flies_down_at_45_degrees():
    fight = versus(PHOEBE, ROBERT, 300)
    me = fight.fighters["p1"]
    jump_and_fire(fight)
    height = me.y
    for _ in range(LASER.startup + LASER.active - 1):
        step(fight)
        assert me.y == height and me.vx == 0         # hanging in the air
    (shot,) = fight.shots
    assert (shot.vx, shot.vy) == (LASER.projectile.speed, -LASER.projectile.speed)
    x, y = shot.x, shot.y
    step(fight)
    assert (shot.x - x, shot.y - y) == (14.0, -14.0)


def test_the_laser_fires_once_per_jump_and_ends_on_the_floor():
    fight = versus(PHOEBE, ROBERT, 400)
    me = fight.fighters["p1"]
    events = jump_and_fire(fight)
    while me.y > 0:
        events += step(fight, X)                     # mashing X in the air: no second laser
    for _ in range(60):     # the shot reaches the floor (and a buffered X's trap plays out)
        events += step(fight)
    assert sum(e.kind == "laser" for e in events) == 1
    assert [e.kind for e in events].count("fizzle") == 1 and not fight.shots
    # a new jump, a new laser
    events = jump_and_fire(fight)
    for _ in range(LASER.startup + 1):
        events += step(fight)
    assert sum(e.kind == "laser" for e in events) == 1


def test_a_laser_and_a_photon_cancel_each_other():
    fight = versus(PHOEBE, ROBERT, 300)
    me = fight.fighters["p1"]
    # after one step the laser's box spans x+130..150, 76..96 px up; the photon's x+128..144, 81..95
    fight.shots.append(Shot("p1", LASER, me.x + 100, 40.0, 14.0, 30, vy=-14.0))
    fight.shots.append(Shot("p2", PHOTON, me.x + 148, 25.0, -4.0, 200))
    step(fight)
    assert not fight.shots


# --- the CPU ----------------------------------------------------------------------------------


def test_the_bot_beams_a_rival_in_the_air_above_her():
    fight = versus(PHOEBE, ROBERT, 50)
    rival = fight.fighters["p2"]
    rival.y, rival.vy, rival.action = 90.0, 0.0, "jump"
    bot = Bot("p1", seed=1, skill=1.0)
    assert any(bot.input(fight).x for _ in range(20))


def test_the_bot_tunnels_through_a_shot_that_would_hurt():
    fight = versus(PHOEBE, ROBERT, 300)
    me = fight.fighters["p1"]
    fight.shots.append(Shot("p2", PHOTON, me.x + 60, 0.0, -PHOTON.projectile.speed, 200))
    bot = Bot("p1", seed=1, skill=1.0)
    pressed = [inp for inp in (bot.input(fight) for _ in range(30)) if inp.x]
    assert pressed and pressed[0].down


def test_the_bot_fires_lasers_and_tunnels_in_a_fight():
    seen = set()
    for seed in range(6):
        fight = versus(PHOEBE, CHARACTERS["BOHR"], 200)
        b1, b2 = Bot("p1", seed), Bot("p2", seed + 50)
        while not fight.over:
            seen |= {e.kind for e in fight.step({"p1": b1.input(fight), "p2": b2.input(fight)})}
    assert {"laser", "tunnel"} <= seen
