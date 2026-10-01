from brawl_ket.qec import BIT, FLIPPED, LOGICAL, PHASE, Code, X, Y, Z


def test_distance_sets_how_many_errors_are_corrected():
    assert Code(3, 120).t == 1
    assert Code(5, 180).t == 2


def test_the_bit_flip_code_corrects_x_and_cannot_see_z():
    c = Code(3, 120)
    assert c.basis == BIT and c.corrects(X) and not c.corrects(Z) and not c.corrects(Y)


def test_the_phase_flip_code_corrects_z_and_cannot_see_x():
    c = Code(3, 120)
    c.switch()
    assert c.basis == PHASE and c.corrects(Z) and not c.corrects(X) and not c.corrects(Y)


def test_one_error_on_distance_3_flips_a_light_and_the_cycle_repairs_it():
    c = Code(3, 120)
    assert c.hit(X) == FLIPPED and len(c.flipped) == 1
    repaired = [c.tick() for _ in range(120)]
    assert repaired.count(True) == 1 and repaired[-1] is True
    assert c.flipped == set()


def test_two_errors_within_one_cycle_beat_distance_3():
    c = Code(3, 120)
    assert c.hit(X) == FLIPPED
    assert c.hit(X) == LOGICAL
    assert c.flipped == set()  # re-encoded


def test_errors_in_different_cycles_are_each_corrected():
    c = Code(3, 120)
    c.hit(X)
    for _ in range(120):
        c.tick()
    assert c.hit(X) == FLIPPED


def test_distance_5_needs_three_errors_within_a_cycle():
    c = Code(5, 180)
    assert [c.hit(X) for _ in range(3)] == [FLIPPED, FLIPPED, LOGICAL]


def test_an_error_the_code_cannot_see_is_a_logical_error_at_once():
    c = Code(5, 180)
    assert c.hit(Z) == LOGICAL
    c.switch()
    assert c.hit(X) == LOGICAL


def test_a_y_error_is_always_logical():
    for switch in (False, True):
        c = Code(5, 180)
        if switch:
            c.switch()
        assert c.hit(Y) == LOGICAL


def test_transversal_h_carries_pending_errors_over():
    # H maps X errors to Z errors, and the new code corrects Z: the lights stay flipped
    c = Code(3, 120)
    c.hit(X)
    c.switch()
    assert len(c.flipped) == 1
    assert c.hit(Z) == LOGICAL  # the second correctable error in this cycle


def test_reencode_repairs_early():
    c = Code(5, 180)
    c.hit(X)
    c.hit(X)
    assert c.reencode() is True and c.flipped == set()
    assert c.reencode() is False


def test_labels():
    c = Code(3, 120)
    assert c.label() == "|000>"
    c.switch()
    assert c.label() == "|+++>"
    assert Code(5, 180).label() == "|00000>"


def test_progress_runs_through_the_cycle():
    c = Code(3, 120)
    for _ in range(60):
        c.tick()
    assert abs(c.progress - 0.5) < 1e-9
