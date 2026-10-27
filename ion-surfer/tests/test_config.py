from ion_surfer.input import BUTTON_ACTIONS, DIRECTIONS

SANDBOX_ONLY = ("remove_ion", "add_ion", "cool", "passive_cool")  # L/R, only active in SANDBOX


def test_the_face_buttons_are_a_dpad():
    # Printed L X R / Y B A: X up, Y left, B down, A right, like W A S D.
    for player in ("p1", "p2"):
        faces = {b: BUTTON_ACTIONS[player][b][0] for b in ("x", "y", "b", "a")}
        assert faces == {"x": "up", "y": "left", "b": "down", "a": "right"}
        assert set(faces.values()) == set(DIRECTIONS)


def test_confirm_and_back_are_the_printed_A_and_B():
    # Cabinet convention (see "Button convention" in ../AGENTS.md): A confirms,
    # B goes back, in every game. They deliberately share the movement
    # buttons: the menu code tests confirm/back first and returns, so a single
    # press never both scrolls and confirms.
    for player in ("p1", "p2"):
        assert BUTTON_ACTIONS[player]["a"] == ("right", "confirm")
        assert BUTTON_ACTIONS[player]["b"] == ("down", "back")


def test_sandbox_buttons_sit_on_L_and_R_clear_of_everything_else():
    for player, acts in (("p1", ("remove_ion", "add_ion")), ("p2", ("cool", "passive_cool"))):
        assert (BUTTON_ACTIONS[player]["l"], BUTTON_ACTIONS[player]["r"]) == tuple((a,) for a in acts)
        others = {a for b, bacts in BUTTON_ACTIONS[player].items() if b not in "lr" for a in bacts}
        assert not set(acts) & others


def test_start_and_select_are_only_themselves():
    for player in ("p1", "p2"):
        assert BUTTON_ACTIONS[player]["start"] == ("start",)
        assert BUTTON_ACTIONS[player]["select"] == ("select",)
