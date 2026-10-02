"""The Shor code, checked against an independent reference: the [[9,1,3]] code
built from its 8 stabilisers in the Pauli (symplectic) formalism, with the
standard decoder (majority inside each block, then across the blocks)."""

from __future__ import annotations

from itertools import product

import pytest

from brawl_ket import shor
from brawl_ket.shor import CANCEL, FLIPPED, HIGH, LOGICAL, LOW, MID, ShorCode

# --- the reference: Paulis on 9 qubits as (x bits, z bits), qubit = 3 * row + col ---


def _x(*qs):
    return (sum(1 << q for q in qs), 0)


def _z(*qs):
    return (0, sum(1 << q for q in qs))


def _mul(a, b):                         # up to a phase
    return (a[0] ^ b[0], a[1] ^ b[1])


def _commute(a, b):
    return (bin(a[0] & b[1]).count("1") + bin(a[1] & b[0]).count("1")) % 2 == 0


I = (0, 0)  # noqa: E741  (the identity)
STABS = [_z(0, 1), _z(1, 2), _z(3, 4), _z(4, 5), _z(6, 7), _z(7, 8),
         _x(0, 1, 2, 3, 4, 5), _x(3, 4, 5, 6, 7, 8)]
GROUP = {I}
for _s in STABS:
    GROUP |= {_mul(g, _s) for g in GROUP}
_MAJ = {(1, 0): 0, (1, 1): 1, (0, 1): 2}     # syndrome pair -> the odd one out


def ref_logical(e) -> bool:
    """True if the standard decoder leaves a logical operator behind."""
    s = [0 if _commute(e, st) else 1 for st in STABS]
    corr = I
    for r in range(3):                          # X errors: majority inside block r
        q = _MAJ.get((s[2 * r], s[2 * r + 1]))
        if q is not None:
            corr = _mul(corr, _x(3 * r + q))
    r = _MAJ.get((s[6], s[7]))                  # Z errors: majority across the blocks
    if r is not None:
        corr = _mul(corr, _z(3 * r))
    residual = _mul(e, corr)
    assert all(_commute(residual, st) for st in STABS)
    return residual not in GROUP


def ref_state(code: ShorCode):
    """The Pauli the game's grid stands for (Z drawn on a row = Z on its first qubit)."""
    e = I
    for r, c in code.x_cells:
        e = _mul(e, _x(3 * r + c))
    for r in code.z_rows:
        e = _mul(e, _z(3 * r))
    return e


# A hit in the reference alphabet: ("X", row, col), ("Z", row, qubit-in-row), ("Y", row, col)
HITS = [(k, r, c) for k in "XZY" for r in range(3) for c in range(3)]


def ref_pauli(hit):
    k, r, c = hit
    q = 3 * r + c
    return {"X": _x(q), "Z": _z(q), "Y": _mul(_x(q), _z(q))}[k]


def game_apply(code: ShorCode, hit) -> str:
    k, r, c = hit
    return code.apply(k, r, c)      # for Z the column is ignored: any qubit of the row


@pytest.mark.parametrize("n", [1, 2, 3])
def test_every_sequence_of_hits_matches_the_reference(n):
    """For every sequence of up to 3 hits: the game reports LOGICAL exactly when the
    accumulated error is one the decoder can't correct (then re-encodes), and otherwise
    its grid stands for the same error, up to stabilisers."""
    for seq in product(HITS, repeat=n):
        code = ShorCode(60)
        acc = I
        for hit in seq:
            acc = _mul(acc, ref_pauli(hit))
            verdict = game_apply(code, hit)
            if ref_logical(acc):
                assert verdict == LOGICAL, seq
                assert code.lights == 0
                acc = I                     # GAME RULE: re-encoded
            else:
                assert verdict in (FLIPPED, CANCEL), seq
                assert _mul(ref_state(code), acc) in GROUP, seq


SPEC_TABLE = [   # spec section 1: errors in one cycle -> logical?
    ([("X", MID, 0), ("X", MID, 0)], False),
    ([("X", MID, 0), ("X", MID, 1)], True),
    ([("X", HIGH, 0), ("X", MID, 1)], False),
    ([("Z", LOW, 0), ("Z", LOW, 1)], False),
    ([("Z", HIGH, 0), ("Z", LOW, 0)], True),
    ([("Y", MID, 2)], False),
    ([("X", MID, 0), ("Y", MID, 2)], True),
    ([("X", HIGH, 0), ("Y", MID, 2)], False),
    ([("X", MID, 0), ("Z", MID, 0)], False),
]


@pytest.mark.parametrize("hits,logical", SPEC_TABLE)
def test_the_spec_table(hits, logical):
    code = ShorCode(60)
    verdicts = [game_apply(code, h) for h in hits]
    assert (verdicts[-1] == LOGICAL) == logical
    acc = I
    for h in hits:
        acc = _mul(acc, ref_pauli(h))
    assert ref_logical(acc) == logical


def test_cancel_is_reported_when_a_hit_undoes_a_light():
    code = ShorCode(60)
    assert code.apply_x(MID, 0) == FLIPPED
    assert code.apply_x(MID, 0) == CANCEL and code.lights == 0
    assert code.apply_z(LOW) == FLIPPED
    assert code.apply_z(LOW) == CANCEL and code.lights == 0


def test_a_throw_on_a_clean_grid_lights_its_cell_and_row():
    code = ShorCode(60)
    assert code.apply_y(MID, shor.THROW_COL) == FLIPPED
    assert code.x_cells == {(MID, shor.THROW_COL)} and code.z_rows == {MID}


def test_the_cycle_clears_correctable_errors_on_its_tick():
    code = ShorCode(3)
    code.apply_x(HIGH, 0)
    code.apply_z(LOW)
    assert [code.tick(), code.tick()] == [False, False]
    assert code.progress == pytest.approx(2 / 3)
    assert code.tick() is True and code.lights == 0 and code.timer == 0
    assert code.tick() is False             # nothing to repair: no correction reported


def test_reencode_is_an_extra_correction_round():
    code = ShorCode(60)
    assert code.reencode() is False
    code.apply_x(HIGH, 1)
    assert code.reencode() is True and code.lights == 0


def test_danger_rows():
    code = ShorCode(60)
    code.apply_x(HIGH, 0)
    assert code.x_danger_rows() == {HIGH}       # one more different X there breaks it
    assert code.z_danger_rows() == set()
    code.apply_z(MID)
    assert code.z_danger_rows() == {HIGH, LOW}  # a Z on either other row breaks it


def test_bad_arguments_are_rejected():
    with pytest.raises(ValueError):
        ShorCode(0)
    code = ShorCode(60)
    with pytest.raises(ValueError):
        code.apply("W", 0, 0)
    with pytest.raises(ValueError):
        code.apply_x(3, 0)
