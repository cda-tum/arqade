"""DOS (docs/superpowers/specs/2026-10-21-brawl-ket-erwin-dos-design.md, sections 3 and 4): a
classical bit, always green, so Y never switches him and MEASURE never collapses him; his Y
is COPY (catch a rival's shot, or BOHR's crackling field) and then PASTE (fire it back, straight
ahead, in the colour it was fired in, or crackle with the field); FLOPPY, MOUSE CABLE and CRT
DROP."""

from brawl_ket import basis
from brawl_ket.basis import X_BASIS, Z_BASIS
from brawl_ket.config import COPY_CAUGHT_RECOVERY, DRIVE_SLOT_Y, PASTE_SPEED
from brawl_ket.fight import Fight, Shot, body_width
from brawl_ket.fighter import IDLE, FighterInput
from brawl_ket.moves import BOHR, DOS, ERWIN, PHOEBE, ROBERT

Y = FighterInput(y=True)
COPY, PASTE = DOS.extra["copy"], DOS.extra["paste"]
FLOPPY, MOUSE, DROP = (DOS.moves[s] for s in ("stand.X", "crouch.X", "air.X"))
NOISE, BOX_DROP = BOHR.moves["crouch.X"], ERWIN.moves["air.X"]
DOWN_X = FighterInput(down=True, x=True)
PHOTON, LASER = ROBERT.moves["stand.X"], PHOEBE.moves["air.X"]
TUNNEL = PHOEBE.moves["crouch.X"]
TUNNEL_STEPS = TUNNEL.startup + TUNNEL.active + TUNNEL.recovery


def versus(c1, c2, gap, seed=0):
    fight = Fight({"p1": c1, "p2": c2}, seed=seed)
    fight.fighters["p2"].x = fight.fighters["p1"].x + gap
    return fight


def step(fight, p1=IDLE, p2=IDLE):
    return fight.step({"p1": p1, "p2": p2})


def kinds(events):
    return [e.kind for e in events]


def hits_on(events, player):
    return [e for e in events if e.kind in ("hit", "block") and e.player == player]


# --- always green -------------------------------------------------------------------------------


def test_y_never_switches_dos():
    fight = versus(DOS, ROBERT, 300)
    dos = fight.fighters["p1"]
    events = []
    for i in range(60):
        events += step(fight, FighterInput(y=i % 10 == 0))
    assert dos.basis == Z_BASIS and "switch" not in kinds(events)
    dos.switch()                        # any colour-changing move does nothing to him either
    assert dos.basis == Z_BASIS


def test_measure_hurts_dos_but_never_collapses_him():
    fight = versus(BOHR, DOS, 80)
    bohr, dos = fight.fighters["p1"], fight.fighters["p2"]
    bohr.basis = X_BASIS                # BOHR purple: MEASURE would collapse anyone else into purple
    events = []
    for i in range(70):
        events += step(fight, FighterInput(x=i == 0))
    assert [(e.kind, e.error) for e in hits_on(events, "p2")] == [("hit", basis.Y)]
    assert dos.health == DOS.health - 12 and dos.basis == Z_BASIS and "measure" not in kinds(events)


# --- COPY ---------------------------------------------------------------------------------------


def test_copy_catches_a_photon_and_the_shot_is_gone():
    fight = versus(DOS, ROBERT, 300)
    dos = fight.fighters["p1"]
    shot = Shot("p2", PHOTON, dos.x + 70, 0.0, -PHOTON.projectile.speed, 200, X_BASIS)
    fight.shots.append(shot)
    events = []
    for i in range(10):
        events += step(fight, Y if i == 0 else IDLE)
    assert shot not in fight.shots and dos.clipboard == (PHOTON, X_BASIS)
    assert "copy" in kinds(events) and dos.health == DOS.health


def test_copy_catches_a_laser_falling_on_him():
    fight = versus(DOS, PHOEBE, 300)
    dos = fight.fighters["p1"]
    speed = LASER.projectile.speed
    fight.shots.append(Shot("p2", LASER, dos.x + 94, 74.0, -speed, 30, Z_BASIS, -speed))
    for i in range(6):
        step(fight, Y if i == 0 else IDLE)
    assert not fight.shots and dos.clipboard == (LASER, Z_BASIS) and dos.health == DOS.health


def test_dos_copies_a_floppy_and_keeps_its_green():
    fight = versus(DOS, DOS, 300)
    me = fight.fighters["p1"]
    fight.shots.append(Shot("p2", FLOPPY, me.x + 64, 0.0, -FLOPPY.projectile.speed, 240, Z_BASIS))
    for i in range(12):
        step(fight, Y if i == 0 else IDLE)
    assert me.clipboard == (FLOPPY, Z_BASIS)


def test_a_copy_that_catches_nothing_leaves_him_open():
    fight = versus(DOS, ROBERT, 300)
    dos = fight.fighters["p1"]
    step(fight, Y)
    frames = 1
    while dos.action == "attack":
        step(fight)
        frames += 1
    assert frames >= COPY.startup + COPY.active + COPY.recovery
    assert COPY.active == 12 and COPY.recovery == 18          # 0.2 s to catch, 0.3 s to recover


def test_a_catch_cuts_his_recovery_short():
    fight = versus(DOS, ROBERT, 300)
    dos = fight.fighters["p1"]
    fight.shots.append(Shot("p2", PHOTON, dos.x + 70, 0.0, -PHOTON.projectile.speed, 200))
    after = None
    for i in range(40):
        events = step(fight, Y if i == 0 else IDLE)
        if after is None and "copy" in kinds(events):
            after = 0
        elif after is not None:
            after += 1
        if after is not None and dos.action != "attack":
            break
    assert after is not None and after <= COPY_CAUGHT_RECOVERY


def test_copy_cannot_start_in_hitstun_or_knocked_down():
    fight = versus(DOS, ROBERT, 300)
    dos = fight.fighters["p1"]
    dos.take_hit(ROBERT.moves["stand.B"], basis.X, -1)
    assert dos.action == "hitstun"
    step(fight, Y)
    assert dos.move is None and dos.action == "hitstun"
    dos.take_hit(ROBERT.moves["crouch.B"], basis.X, -1)
    assert dos.action == "knockdown"
    step(fight, Y)
    assert dos.move is None


# --- PASTE --------------------------------------------------------------------------------------


def test_paste_fires_the_shot_straight_ahead_in_its_own_colour_and_empties_the_clipboard():
    fight = versus(DOS, ROBERT, 300)
    dos = fight.fighters["p1"]
    dos.clipboard = (LASER, X_BASIS)            # a purple LASER, caught from above
    events = []
    for i in range(PASTE.startup + 2):
        events += step(fight, Y if i == 0 else IDLE)
    (shot,) = fight.shots
    assert shot.owner == "p1" and shot.move is LASER and shot.basis == X_BASIS
    assert shot.vx == LASER.projectile.speed and shot.vy == 0.0           # level now
    assert shot.y + LASER.projectile.box.y == DRIVE_SLOT_Y and dos.clipboard is None
    assert "paste" in kinds(events)


def test_a_pasted_shot_keeps_the_colour_it_was_fired_in():
    for rival_basis, want in ((X_BASIS, "hit"), (Z_BASIS, "block")):
        fight = versus(DOS, ROBERT, 200)
        dos, rival = fight.fighters["p1"], fight.fighters["p2"]
        rival.basis = rival_basis
        dos.clipboard = (PHOTON, X_BASIS)       # purple: it hurts a purple ROBERT, not a green one
        events = []
        for i in range(80):
            events += step(fight, Y if i == 0 else IDLE)
        assert kinds(hits_on(events, "p2")) == [want], rival_basis


def test_a_pasted_shot_into_a_box_measures_erwin():
    fight = Fight({"p1": DOS, "p2": ERWIN})
    dos, erwin = fight.fighters["p1"], fight.fighters["p2"]
    step(fight, IDLE, FighterInput(x=True))
    for _ in range(ERWIN.moves["stand.X"].startup):
        step(fight)
    assert erwin.boxed
    dos.clipboard = (PHOTON, Z_BASIS)
    events = []
    for i in range(60):
        events += step(fight, Y if i == 0 else IDLE)
        if not erwin.boxed:
            break
    assert kinds(events).count("box_collapse") == 1


# --- FLOPPY, MOUSE CABLE, CRT DROP --------------------------------------------------------------


def test_floppy_leaves_his_drive_slot_at_3_px_a_frame():
    fight = versus(DOS, ROBERT, 300)
    for i in range(FLOPPY.startup + 1):
        step(fight, FighterInput(x=i == 0))
    (shot,) = fight.shots
    x = shot.x
    step(fight)
    assert shot.x - x == 3.0 and shot.y + FLOPPY.projectile.box.y == DRIVE_SLOT_Y and shot.basis == Z_BASIS


def mouse(gap, rival_basis=None, rival_input=IDLE, frames=45):
    fight = versus(DOS, ROBERT, gap)
    dos, rival = fight.fighters["p1"], fight.fighters["p2"]
    if rival_basis is not None:
        rival.basis = rival_basis
    events = []
    for i in range(frames):
        events += step(fight, DOWN_X if i == 0 else IDLE, rival_input)
    return fight, dos, rival, events


def test_mouse_cable_reels_a_rival_in_to_just_in_front_of_him():
    fight, dos, rival, events = mouse(160)
    assert "mouse" in kinds(events) and kinds(hits_on(events, "p2")) == ["hit"]
    assert rival.health == ROBERT.health - MOUSE.damage
    assert abs(rival.x - (dos.x + fight.body_width)) <= 6          # pulled right up to him


def test_mouse_cable_pulls_a_rival_of_the_other_colour_without_hurting():
    fight, dos, rival, events = mouse(160, rival_basis=X_BASIS)
    assert kinds(hits_on(events, "p2")) == ["block"] and rival.health == ROBERT.health
    assert abs(rival.x - (dos.x + fight.body_width)) <= 6


def test_a_jump_clears_the_mouse_and_it_stops_at_its_reach():
    fight, dos, rival, events = mouse(160, rival_input=FighterInput(up=True), frames=30)
    assert hits_on(events, "p2") == [] and not fight.shots
    fight, dos, rival, events = mouse(260)                         # out of reach
    assert hits_on(events, "p2") == [] and rival.x == dos.x + 260


def test_hitting_dos_cuts_his_mouse_cable():
    fight = versus(DOS, ROBERT, 300)
    dos = fight.fighters["p1"]
    for i in range(MOUSE.startup + 2):
        step(fight, DOWN_X if i == 0 else IDLE)
    assert any(s.move is MOUSE for s in fight.shots)
    # a level LASER (MID: his crouch doesn't duck it, as it would a PHOTON)
    fight.shots.append(Shot("p2", LASER, dos.x + 10, 0.0, -LASER.projectile.speed, 30))
    events = step(fight)
    assert kinds(hits_on(events, "p1")) == ["hit"] and not any(s.move is MOUSE for s in fight.shots)


def test_crt_drop_reaches_wide():
    fight = versus(DOS, ROBERT, 200)
    dos, rival = fight.fighters["p1"], fight.fighters["p2"]
    events = step(fight, FighterInput(up=True))
    for _ in range(8):
        events += step(fight)
    rival.x = dos.x + 50                    # beside him rather than under him: the old box missed
    events += step(fight, FighterInput(x=True))
    for _ in range(40):
        events += step(fight)
    assert kinds(hits_on(events, "p2")) == ["hit"]


# --- COPY: ERWIN's box and BOHR's electricity ------------------------------------------------------


def test_copy_catches_a_falling_box_and_pastes_it_flying_level():
    fight = versus(DOS, ERWIN, 300)
    dos = fight.fighters["p1"]
    fight.shots.append(Shot("p2", BOX_DROP, dos.x + 40, 60.0, -0.5, 90, Z_BASIS, -7.0))
    events = []
    for i in range(COPY.startup + 2):
        events += step(fight, Y if i == 0 else IDLE)
    assert "copy" in kinds(events) and dos.clipboard == (BOX_DROP, Z_BASIS)
    while dos.action == "attack":
        step(fight)
    for i in range(PASTE.startup + 1):
        step(fight, Y if i == 0 else IDLE)
    (shot,) = fight.shots
    assert shot.move is BOX_DROP and shot.vx == PASTE_SPEED and shot.vy == 0


def test_copy_takes_bohrs_electricity_and_paste_crackles_with_it_in_its_colour():
    fight = versus(DOS, BOHR, 60)
    dos, bohr = fight.fighters["p1"], fight.fighters["p2"]
    bohr.basis = X_BASIS                    # purple noise
    events = []
    for i in range(NOISE.startup + 4):
        events += step(fight, Y if i == NOISE.startup - 3 else IDLE, DOWN_X if i == 0 else FighterInput(down=True))
    assert "copy" in kinds(events) and dos.clipboard == (NOISE, X_BASIS)
    assert bohr.phase == "recovery" and hits_on(events, "p1") == []     # his field is gone, unfelt
    while dos.action == "attack" or bohr.action == "attack":
        step(fight)
    events = []
    for i in range(NOISE.startup + 2):
        events += step(fight, Y if i == 0 else IDLE)
    assert dos.move is NOISE and dos.attack_basis == X_BASIS and dos.clipboard is None
    assert "paste" in kinds(events) and kinds(hits_on(events, "p2")) == ["hit"]   # purple hurts purple


def test_crt_drop_stomps_straight_down_and_knocks_down():
    fight = versus(DOS, ROBERT, 200)
    dos, rival = fight.fighters["p1"], fight.fighters["p2"]
    events = step(fight, FighterInput(up=True))
    for _ in range(8):
        events += step(fight)
    rival.x = dos.x + 20                    # walked in under him
    events += step(fight, FighterInput(x=True))
    x0 = dos.x
    for _ in range(40):
        events += step(fight)
        if dos.action == "attack" and dos.phase == "active" and not dos.bounced:
            assert dos.x == x0
    assert kinds(hits_on(events, "p2")) == ["hit"] and rival.action == "knockdown"
    assert "shockwave" not in kinds(events) and "crt_drop" in kinds(events)


def test_a_missed_crt_drop_lands_into_its_recovery():
    fight = versus(DOS, ROBERT, 300)
    dos = fight.fighters["p1"]
    step(fight, FighterInput(up=True))
    for _ in range(8):
        step(fight)
    step(fight, FighterInput(x=True))
    while dos.y > 0:
        step(fight)
    stuck = 0
    while dos.action == "attack":
        step(fight)
        stuck += 1
    assert DROP.recovery - 1 <= stuck <= DROP.recovery


def test_tunnel_past_dos_re_forms_clear_of_his_case():
    fight = versus(PHOEBE, DOS, 100)
    phoebe, dos = fight.fighters["p1"], fight.fighters["p2"]
    step(fight, FighterInput(down=True, x=True))
    for _ in range(TUNNEL_STEPS):
        step(fight, FighterInput(down=True))
    assert phoebe.x - dos.x == body_width(PHOEBE, DOS) == 54
