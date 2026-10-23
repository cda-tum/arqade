import pytest

from brawl_ket.bot import Bot
from brawl_ket.config import ROUND_FRAMES
from brawl_ket.fight import Fight, Shot
from brawl_ket.fighter import FighterInput
from brawl_ket.moves import CHARACTERS

SEEDS = range(10)
PAIRINGS = [(a, b) for a in CHARACTERS for b in CHARACTERS]


def test_every_pairing_is_covered():
    assert {"ROBERT", "BOHR"} <= set(CHARACTERS)
    assert len(PAIRINGS) == len(CHARACTERS) ** 2


def play(seed, pairing=("ROBERT", "ROBERT")):
    """One round between two bots; returns the finished Fight and its events."""
    fight = Fight({"p1": CHARACTERS[pairing[0]], "p2": CHARACTERS[pairing[1]]}, seed=seed)
    bots = {"p1": Bot("p1", seed), "p2": Bot("p2", seed + 1000)}
    events = []
    for _ in range(2 * ROUND_FRAMES):      # hit freezes don't run the clock: room for them
        if fight.over:
            break
        events += fight.step({key: bot.input(fight) for key, bot in bots.items()})
    return fight, events


@pytest.mark.parametrize("pairing", PAIRINGS)
def test_bot_vs_bot_rounds_always_finish(pairing):
    for seed in SEEDS:
        fight, events = play(seed, pairing)
        assert fight.over, f"seed {seed} did not finish"


@pytest.mark.parametrize("pairing", PAIRINGS)
def test_bots_land_hits_in_both_colours(pairing):
    errors = set()
    for seed in SEEDS:
        _, events = play(seed, pairing)
        errors |= {e.error for e in events if e.kind == "hit"}
    fixed = all(CHARACTERS[name].fixed_basis for name in pairing)
    assert ({"X"} if fixed else {"X", "Z"}) <= errors, (pairing, errors)       # both colours land (DOS: green)


def test_bots_switch_basis_sometimes():
    switches = sum(1 for seed in SEEDS for e in play(seed)[1] if e.kind == "switch")
    assert switches > 0


@pytest.mark.parametrize("pairing", PAIRINGS)
def test_bots_are_deterministic(pairing):
    for seed in SEEDS:
        (f1, e1), (f2, e2) = play(seed, pairing), play(seed, pairing)
        assert f1.winner == f2.winner
        assert e1 == e2


# Since a jab can't chain into a jab (2026-10-23), ERWIN beats ROBERT in about 85% of bot rounds, so
# 10 seeds a side can all go his way: a character's edge, not a side's, for the user to decide
LOPSIDED = {("ROBERT", "ERWIN"), ("ERWIN", "ROBERT")}
SIDE_CASES = [pytest.param(p, marks=[pytest.mark.xfail(reason="ERWIN wins about 85% against ROBERT", strict=False)]
                           if p in LOPSIDED else []) for p in PAIRINGS]


@pytest.mark.parametrize("pairing", SIDE_CASES)
def test_neither_side_is_favoured(pairing):
    winners = {play(seed, pairing)[0].winner for seed in SEEDS}
    assert {"p1", "p2"} <= winners


def test_neither_character_always_wins():
    # ROBERT against BOHR, from both sides: each character wins some rounds
    won = set()
    for pairing in (("ROBERT", "BOHR"), ("BOHR", "ROBERT")):
        for seed in SEEDS:
            winner = play(seed, pairing)[0].winner
            if winner is not None:
                won.add(pairing[0] if winner == "p1" else pairing[1])
    assert won == {"ROBERT", "BOHR"}


def test_bohr_bots_use_their_specials():
    # over some rounds, a BOHR bot measures, waves and slams
    slots = set()
    for seed in range(40):
        if {"stand.X", "crouch.X", "air.X"} <= slots:
            break
        fight = Fight({"p1": CHARACTERS["BOHR"], "p2": CHARACTERS["ROBERT"]})
        bots = {"p1": Bot("p1", seed), "p2": Bot("p2", seed + 1000)}
        while not fight.over:
            fight.step({key: bot.input(fight) for key, bot in bots.items()})
            bohr = fight.fighters["p1"]
            if bohr.action == "attack":
                slots.add(bohr.slot)
    assert {"stand.X", "crouch.X", "air.X"} <= slots


@pytest.mark.parametrize("pairing", PAIRINGS)
def test_presses_are_edges_not_held(pairing):
    fight = Fight({"p1": CHARACTERS[pairing[0]], "p2": CHARACTERS[pairing[1]]})
    bot, rival = Bot("p1", 3), Bot("p2", 4)
    last = None
    for _ in range(ROUND_FRAMES):
        if fight.over:
            break
        mine = bot.input(fight)
        fight.step({"p1": mine, "p2": rival.input(fight)})
        pressed = (mine.a, mine.b, mine.x, mine.y)
        assert not any(p and q for p, q in zip(pressed, last or (False,) * 4))
        last = pressed


ERWIN, DOS, ROBERT = CHARACTERS["ERWIN"], CHARACTERS["DOS"], CHARACTERS["ROBERT"]
PHOTON = ROBERT.moves["stand.X"]


def test_erwin_boxes_against_a_shot_that_would_hurt():
    fight = Fight({"p1": ERWIN, "p2": ROBERT})
    me = fight.fighters["p1"]
    fight.shots.append(Shot("p2", PHOTON, me.x + 50, 0.0, -PHOTON.projectile.speed, 200))
    bot = Bot("p1", seed=1, skill=1.0)
    pressed = [inp for inp in (bot.input(fight) for _ in range(30)) if inp.x]
    assert pressed and not pressed[0].down              # X standing: THE BOX


def test_erwin_waits_in_the_box_then_pops_out_near_the_rival():
    fight = Fight({"p1": ERWIN, "p2": ROBERT})
    me, rival = fight.fighters["p1"], fight.fighters["p2"]
    fight.step({"p1": FighterInput(x=True)})
    while not me.boxed:
        fight.step({})
    bot = Bot("p1", seed=1, skill=1.0)
    assert not bot.input(fight).a                       # far from both boxes: he waits
    rival.x = me.boxes[1] + 30
    bot.gap = 0
    assert bot.input(fight).a                           # the rival came close: out with a swipe


def test_dos_copies_an_incoming_shot_and_pastes_at_once():
    fight = Fight({"p1": DOS, "p2": ROBERT})
    dos = fight.fighters["p1"]
    fight.shots.append(Shot("p2", PHOTON, dos.x + 80, 0.0, -PHOTON.projectile.speed, 200))
    bot = Bot("p1", seed=1, skill=1.0)
    assert any(bot.input(fight).y for _ in range(20))
    fight.shots.clear()
    dos.clipboard = (PHOTON, "X")
    bot.gap = 0
    assert bot.input(fight).y


def test_dos_never_uses_y_to_dodge_or_feint():
    for seed in range(5):
        fight = Fight({"p1": DOS, "p2": ROBERT}, seed=seed)
        bots = {"p1": Bot("p1", seed), "p2": Bot("p2", seed + 1000)}
        while not fight.over:
            ins = {k: b.input(fight) for k, b in bots.items()}
            if ins["p1"].y:     # every Y of his is a COPY at a shot or a PASTE
                assert fight.fighters["p1"].clipboard is not None or any(s.owner == "p2" for s in fight.shots)
            fight.step(ins)


# M-CUTIE SPINs at a rival in the air: against ERWIN, who jumps to drop his boxes
@pytest.mark.parametrize("name,extra,rival", [("ERWIN", {"box_split", "pounce", "box_drop"}, "ROBERT"),
                                              ("DOS", {"floppy", "mouse", "crt_drop", "copy", "paste"}, "ROBERT"),
                                              ("M-CUTIE", {"charge2", "trap_set", "spin"}, "ERWIN"),
                                              ("ALICE & BOB", {"toss", "teleport", "bell_dive"}, "ROBERT")])
def test_the_new_bots_use_all_their_specials(name, extra, rival):
    kinds: set[str] = set()
    for seed in range(40):
        if extra <= kinds:
            break
        fight = Fight({"p1": CHARACTERS[name], "p2": CHARACTERS[rival]}, seed=seed)
        bots = {"p1": Bot("p1", seed), "p2": Bot("p2", seed + 1000)}
        while not fight.over:
            kinds |= {e.kind for e in fight.step({k: b.input(fight) for k, b in bots.items()}) if e.player == "p1"}
    assert extra <= kinds, extra - kinds


M_CUTIE, BOHR = CHARACTERS["M-CUTIE"], CHARACTERS["BOHR"]


def far_fight(rival=ROBERT, gap=300):
    fight = Fight({"p1": M_CUTIE, "p2": rival})
    fight.fighters["p2"].x = fight.fighters["p1"].x + gap
    return fight


def test_m_cutie_mashes_a_random_2_to_6_steps_at_range(monkeypatch):
    from brawl_ket import bot as B
    monkeypatch.setattr(B, "CHARGE_ODDS", 1.0)          # only the charge, at once
    monkeypatch.setattr(B, "TRAP_ODDS", (0.0, 0.0))
    steps = set()
    for seed in range(30):
        fight = far_fight()
        me = fight.fighters["p1"]
        bot = Bot("p1", seed, skill=1.0)
        top = 0
        for _ in range(120):
            fight.step({"p1": bot.input(fight)})
            top = max(top, me.charge)
            if fight.shots:
                break
        assert fight.shots, seed                         # it fired
        steps.add(top)
    assert steps <= set(range(2, 7)) and len(steps) >= 4


def test_m_cutie_sets_traps_while_the_rival_is_far_and_never_a_third(monkeypatch):
    from brawl_ket import bot as B
    monkeypatch.setattr(B, "TRAP_ODDS", (1.0, 1.0))
    monkeypatch.setattr(B, "CHARGE_ODDS", 0.0)
    fight = far_fight(gap=320)
    bot, sets = Bot("p1", 1, skill=1.0), 0
    for _ in range(400):
        mine = sum(1 for t in fight.traps if t.owner == "p1" and not t.closed)
        events = fight.step({"p1": bot.input(fight)})
        new = sum(1 for e in events if e.kind == "trap_set")
        assert not (new and mine == 2)                   # two down: she waits
        sets += new
        fight.fighters["p2"].x = fight.fighters["p1"].x + 320     # keep the rival far
    assert sets == 2


def test_m_cutie_hits_a_rival_her_trap_holds():
    from brawl_ket.fight import Trap
    from brawl_ket.moves import TRAP_HOLD
    fight = far_fight(gap=90)
    rival = fight.fighters["p2"]
    trap = Trap("p1", TRAP_HOLD, rival.x, "Z", age=100)
    fight.traps.append(trap)
    fight.step({})                                       # it closes on him
    assert trap.held == "p2" and rival.action == "hitstun"
    bot = Bot("p1", 1, skill=1.0)
    hits = []
    for _ in range(TRAP_HOLD.hitstun + 10):
        hits += [e for e in fight.step({"p1": bot.input(fight)}) if e.kind == "hit" and e.player == "p2"]
    assert hits                                          # walked in and struck before it let go


def test_m_cutie_jumps_at_a_dashing_grab_and_spins_its_thrower_out_of_it(monkeypatch):
    from brawl_ket import bot as B
    monkeypatch.setattr(B, "GRAB_JUMP", 1.0)
    fight = far_fight(rival=BOHR, gap=70)
    me = fight.fighters["p1"]
    bot = Bot("p1", 1, skill=1.0)
    events = []
    for i in range(70):
        events += fight.step({"p1": bot.input(fight), "p2": FighterInput(x=i == 0)})   # MEASURE
    assert not [e for e in events if e.kind == "hit" and e.player == "p1" and e.error == "Y"]   # never grabbed
    assert "spin" in {e.kind for e in events if e.player == "p1"} and me.health == M_CUTIE.health


def test_m_cutie_spins_only_in_a_jump_made_for_it():
    fight = far_fight(gap=60)
    me = fight.fighters["p1"]
    fight.step({"p1": FighterInput(up=True)})
    for _ in range(3):
        fight.step({})
    bot = Bot("p1", 1, skill=1.0)
    assert not bot.input(fight).x                        # an ordinary jump: no SPIN
    bot.spin_jump, bot.air_pressed, bot.gap = True, False, 0
    assert me.y > 0 and bot.input(fight).x               # one made for it: SPIN


def _in_a_spin(rival_name: str, gap: float):
    """`rival_name` (p1, a bot's) idle on the floor, M-CUTIE (p2) mid-SPIN `gap` px from them."""
    fight = Fight({"p1": CHARACTERS[rival_name], "p2": CHARACTERS["M-CUTIE"]})
    me, cutie = fight.fighters["p1"], fight.fighters["p2"]
    cutie.x = me.x + 300
    fight.step({"p2": FighterInput(up=True)})
    for _ in range(7):
        fight.step({})
    fight.step({"p2": FighterInput(x=True)})
    while cutie.phase != "active":
        fight.step({})
    cutie.x = me.x + gap
    assert cutie.move.name == "SPIN" and me.action == "idle" and Bot.would_hurt(cutie, cutie.move, me)
    return fight


def _in_charge_noise(rival_name: str, gap: float):
    """...and BOHR (p2) crackling with CHARGE NOISE `gap` px away instead."""
    fight = Fight({"p1": CHARACTERS[rival_name], "p2": CHARACTERS["BOHR"]})
    me, bohr = fight.fighters["p1"], fight.fighters["p2"]
    bohr.x = me.x + gap
    fight.step({"p2": FighterInput(down=True, x=True)})
    while bohr.phase != "active":
        fight.step({"p2": FighterInput(down=True)})
    assert bohr.move.name == "CHARGE NOISE" and me.action == "idle" and Bot.would_hurt(bohr, bohr.move, me)
    return fight


def test_bots_back_away_from_a_spin_as_from_a_field():
    """SPIN is no field (COPY can't catch it), but a bot on the ground still walks out of an
    active SPIN that would hurt it, as it does out of CHARGE NOISE."""
    from brawl_ket.bot import is_spin, keep_clear_of
    spin, noise = CHARACTERS["M-CUTIE"].moves["air.X"], CHARACTERS["BOHR"].moves["crouch.X"]
    assert is_spin(spin) and not spin.field and keep_clear_of(spin) and keep_clear_of(noise)
    assert not any(keep_clear_of(m) for c in CHARACTERS.values() for m in c.moves.values() if m not in (spin, noise))
    for fight in (_in_charge_noise("ROBERT", 88), _in_a_spin("ROBERT", 88)):
        bot = Bot("p1", seed=1, skill=1.0)
        assert bot.input(fight).dx == -1


def test_dos_never_copies_a_spin_but_copies_charge_noise():
    bot = Bot("p1", seed=1, skill=1.0)
    fight = _in_a_spin("DOS", 95)
    assert not any(bot.input(fight).y for _ in range(20))
    bot = Bot("p1", seed=1, skill=1.0)
    fight = _in_charge_noise("DOS", 95)
    assert any(bot.input(fight).y for _ in range(20))


# --- ALICE & BOB: the bot is Alice; Bob follows by himself -------------------------------------------

ALICE_BOB = CHARACTERS["ALICE & BOB"]


def kids_fight(rival=ROBERT, gap=200.0):
    fight = Fight({"p1": ALICE_BOB, "p2": rival})
    alice, bob = fight.fighters["p1"], fight.echoes["p1"]
    fight.fighters["p2"].x = alice.x + gap
    return fight, alice, bob


def test_their_bot_tosses_a_key_exchange_at_range(monkeypatch):
    from brawl_ket import bot as B
    monkeypatch.setattr(B, "KEY_ODDS", 1.0)
    fight, alice, bob = kids_fight(gap=200.0)
    bot = Bot("p1", 1, skill=1.0)
    kinds = []
    for _ in range(40):
        kinds += [e.kind for e in fight.step({"p1": bot.input(fight)}) if e.player == "p1"]
        fight.fighters["p2"].x = alice.x + 200.0
    assert "toss" in kinds and "catch" in kinds


def test_their_bot_teleports_when_the_rival_stands_between_them_and_bob_is_anchored(monkeypatch):
    from brawl_ket import bot as B
    monkeypatch.setattr(B, "TELEPORT_ODDS", 1.0)
    fight, alice, bob = kids_fight(gap=200.0)
    rival = fight.fighters["p2"]
    bot = Bot("p1", 1, skill=1.0)
    bob.anchored = True
    rival.x = alice.x - 20.0                    # between Alice and Bob, 40 px behind her
    assert bob.x < rival.x < alice.x
    press = bot.input(fight)
    assert press.down and press.x
    events = []
    for _ in range(10):
        events += fight.step({"p1": press})
        press = bot.input(fight)
    assert "teleport" in [e.kind for e in events]


def test_their_bot_never_teleports_with_nobody_between_them(monkeypatch):
    from brawl_ket import bot as B
    monkeypatch.setattr(B, "TELEPORT_ODDS", 1.0)
    fight, alice, bob = kids_fight(gap=200.0)
    bot = Bot("p1", 1, skill=1.0)
    for _ in range(200):
        events = fight.step({"p1": bot.input(fight)})
        assert "teleport" not in [e.kind for e in events]


def test_their_bot_bell_dives_on_a_rival_below(monkeypatch):
    from brawl_ket import bot as B
    monkeypatch.setattr(B, "DIVE_JUMP_ODDS", 1.0)
    monkeypatch.setattr(B, "KEY_ODDS", 0.0)
    fight, alice, bob = kids_fight(gap=90.0)
    bot = Bot("p1", 1, skill=1.0)
    dives = []
    for _ in range(60):
        events = fight.step({"p1": bot.input(fight)})
        dives += [e for e in events if e.kind == "bell_dive" and e.player == "p1"]
    assert len(dives) == 2                       # hers, and Bob's echo of it


def test_their_bot_only_ever_drives_alice():
    """The fight gives Bob nothing but Alice's own inputs, 12 frames late, hitstop included (the
    bot never presses for him)."""
    from brawl_ket.config import ECHO_DELAY
    from brawl_ket.fighter import IDLE
    fight, alice, bob = kids_fight(gap=150.0)
    bot = Bot("p1", 3)
    pressed, replayed = [], []
    real = bob.replay
    bob.replay = lambda inp: (replayed.append(real(inp)), replayed[-1])[1]
    for _ in range(200):
        pressed.append(bot.input(fight))
        fight.step({"p1": pressed[-1]})
    assert replayed == [IDLE] * ECHO_DELAY + pressed[:-ECHO_DELAY]


def test_their_bot_anchors_bob_with_the_rival_close(monkeypatch):
    from brawl_ket import bot as B
    monkeypatch.setattr(B, "ANCHOR_ODDS", 1.0)
    fight, alice, bob = kids_fight(gap=80.0)
    bot = Bot("p1", 1, skill=1.0)
    events = []
    for _ in range(20):
        events += fight.step({"p1": bot.input(fight)})
    assert "anchor" in [e.kind for e in events] and bob.anchored


# --- SUPERposition ----------------------------------------------------------------------------------


def test_dos_fires_his_blue_screen_with_a_full_bar_and_a_rival_on_the_ground_in_reach():
    from brawl_ket import basis
    from brawl_ket.moves import CHARACTERS
    from brawl_ket.superpos import FULL
    fight = Fight({"p1": CHARACTERS["DOS"], "p2": ROBERT}, seed=1)
    fight.fighters["p1"].x, fight.fighters["p2"].x = 300.0, 450.0
    fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
    bot = Bot("p1", 1)
    inp = bot.input(fight)
    assert inp.a and inp.b


def test_not_with_the_rival_out_of_reach_or_in_the_air():
    from brawl_ket import basis
    from brawl_ket.config import CRASH_REACH
    from brawl_ket.moves import CHARACTERS
    from brawl_ket.superpos import FULL
    for gap, y in ((CRASH_REACH + 30, 0.0), (100.0, 60.0)):
        fight = Fight({"p1": CHARACTERS["DOS"], "p2": ROBERT}, seed=1)
        fight.fighters["p1"].x, fight.fighters["p2"].x = 300.0, 300.0 + gap
        fight.fighters["p2"].y = y
        fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
        inp = Bot("p1", 1).input(fight)
        assert not (inp.a and inp.b)


def test_a_bot_jumps_away_from_a_blue_screen_winding_up_in_reach(monkeypatch):
    import brawl_ket.bot as bot_module
    from brawl_ket.moves import BLUE_SCREEN, CHARACTERS
    monkeypatch.setattr(bot_module, "SUPER_DODGE_ODDS", 1.0)
    fight = Fight({"p1": ROBERT, "p2": CHARACTERS["DOS"]}, seed=1)
    fight.fighters["p1"].x, fight.fighters["p2"].x = 300.0, 420.0
    dos = fight.fighters["p2"]
    dos.action, dos.move, dos.slot, dos.frame = "attack", BLUE_SCREEN, "super", 1
    inp = Bot("p1", 1).input(fight)
    assert inp.up and inp.dx == -1


@pytest.mark.parametrize("name,gap", [("ROBERT", 150.0), ("BOHR", 400.0), ("PHOEBE", 300.0),
                                      ("ERWIN", 120.0), ("M-CUTIE", 400.0), ("ALICE & BOB", 80.0)])
def test_every_bot_fires_its_super_when_it_will_land(name, gap):
    from brawl_ket import basis
    from brawl_ket.moves import CHARACTERS
    from brawl_ket.superpos import FULL
    fight = Fight({"p1": CHARACTERS[name], "p2": ROBERT}, seed=1)
    fight.fighters["p1"].x, fight.fighters["p2"].x = 150.0, 150.0 + gap
    fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
    inp = Bot("p1", 1).input(fight)
    assert inp.a and inp.b


@pytest.mark.parametrize("gap", [200.0, 300.0])
def test_a_bot_times_its_jump_over_the_bloch_sphere(monkeypatch, gap):
    """It is 100 px tall and MID: a bot that always dodges jumps late enough to be over it."""
    import brawl_ket.bot as bot_module
    from brawl_ket import basis
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import BLOCH_SPHERE, CHARACTERS
    from brawl_ket.superpos import FULL
    monkeypatch.setattr(bot_module, "SUPER_DODGE_ODDS", 1.0)
    fight = Fight({"p1": CHARACTERS["ROBERT"], "p2": ROBERT}, seed=1)
    fight.fighters["p1"].x, fight.fighters["p2"].x = 150.0, 150.0 + gap
    fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
    bot = Bot("p2", 1)
    fight.step({"p1": FighterInput(a=True, b=True)})
    rolls = 0
    for _ in range(160):
        events = fight.step({"p2": bot.input(fight)})
        robert = fight.fighters["p1"]
        rolls += sum(1 for e in events if e.kind == "hit" and e.player == "p2" and robert.move is BLOCH_SPHERE)
    assert rolls == 0


def test_a_bot_walks_off_a_locked_ring(monkeypatch):
    import brawl_ket.bot as bot_module
    from brawl_ket.moves import CHARACTERS, WAVE_COLLAPSE
    monkeypatch.setattr(bot_module, "SUPER_DODGE_ODDS", 1.0)
    fight = Fight({"p1": ROBERT, "p2": CHARACTERS["BOHR"]}, seed=1)
    fight.fighters["p1"].x, fight.fighters["p2"].x = 300.0, 500.0
    bohr = fight.fighters["p2"]
    bohr.action, bohr.move, bohr.slot, bohr.frame = "attack", WAVE_COLLAPSE, "super", 30
    bohr.target_x = 300.0
    inp = Bot("p1", 1).input(fight)
    assert inp.dx != 0 and not inp.up


# --- the CPU's levels ---------------------------------------------------------------------------------


def level_share(a: str, b: str, names=("ROBERT", "BOHR", "M-CUTIE"), seeds=range(8)) -> float:
    """Level a's share of the decided rounds against level b, mirrors, from both sides."""
    from brawl_ket.config import ROUND_FRAMES
    from brawl_ket.moves import CHARACTERS
    won = played = 0
    for name in names:
        for seed in seeds:
            for flip in (False, True):
                c = CHARACTERS[name]
                fight = Fight({"p1": c, "p2": c}, seed=seed)
                la, lb = (b, a) if flip else (a, b)
                bots = {"p1": Bot("p1", seed, level=la), "p2": Bot("p2", seed + 1000, level=lb)}
                for _ in range(2 * ROUND_FRAMES):
                    if fight.over:
                        break
                    fight.step({k: x.input(fight) for k, x in bots.items()})
                if fight.winner is not None:
                    played += 1
                    won += (fight.winner == "p1") != flip
    return won / played


def test_the_levels_are_a_ladder():
    """BRUTAL beats TOUGH and TOUGH beats EASY, clearly (over every fighter's mirror: about 81% and
    90%, tools-measured on 2026-10-22)."""
    assert level_share("TOUGH", "EASY") >= 0.7
    assert level_share("BRUTAL", "TOUGH") >= 0.65


def test_a_bot_without_a_level_is_tough():
    from brawl_ket.bot import SKILLS
    plain, tough = Bot("p1", 1), Bot("p1", 1, level="TOUGH")
    assert (plain.skill, plain.strike, plain.dodge) == (tough.skill, tough.strike, tough.dodge)
    assert SKILLS["TOUGH"].react == 0.8
