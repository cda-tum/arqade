import pygame

from ion_surfer.input import (
    Pad,
    axis_to_direction,
    keyboard_enabled,
    read_keys,
    set_keyboard_enabled,
    should_quit,
)


def test_axis_to_direction_respects_deadzone():
    assert axis_to_direction(0.4, 0.5) == 0
    assert axis_to_direction(0.9, 0.5) == 1
    assert axis_to_direction(-0.9, 0.5) == -1


def test_should_quit_requires_start_and_select_on_same_pad():
    assert not should_quit(p1_start=True, p1_select=False, p2_start=False, p2_select=True)
    assert should_quit(p1_start=True, p1_select=True, p2_start=False, p2_select=False)
    assert should_quit(p1_start=False, p1_select=False, p2_start=True, p2_select=True)


def test_pad_action_stays_held_until_every_source_releases():
    pad = Pad()
    pad.set("a", "key", True)
    pad.set("a", "button", True)
    pad.set("a", "key", False)
    assert pad.held("a")
    pad.set("a", "button", False)
    assert not pad.held("a")


def test_pad_registers_press_once_then_auto_repeats_directions():
    pad = Pad()
    pad.set("up", "hat", True)
    assert "up" in pad.pressed
    pad.pressed.clear()
    pad.update(0.2)  # still inside the initial repeat delay
    assert "up" not in pad.pressed
    pad.update(0.1)  # past it
    assert "up" in pad.pressed

def test_read_keys_reports_nothing_held_with_keyboard_disabled():
    set_keyboard_enabled(False)
    try:
        keys = read_keys()
        assert not keys[pygame.K_a]
        assert not keys[pygame.K_UP]
        assert not keyboard_enabled()
    finally:
        set_keyboard_enabled(True)
    assert keyboard_enabled()


def test_pad_knows_every_action_the_config_can_produce():
    """Regression: a "confirm" action existed in the config but not in Pad's
    hand-written action list, so the first press of A raised KeyError and the
    game died mid-play. Pad derives the list from BUTTON_ACTIONS now; this
    asserts the two can never drift apart again."""
    from ion_surfer.input import BUTTON_ACTIONS, PLAYERS, Pad, keymap

    pad = Pad()
    for player in PLAYERS:
        for acts in [*BUTTON_ACTIONS[player].values(), *keymap(player).values()]:
            for act in acts:
                pad.set(act, ("jb", 0), True)   # must not raise
                assert pad.held(act)
                pad.set(act, ("jb", 0), False)
                assert not pad.held(act)


def test_the_shared_keyboard_layout_drives_each_players_pad():
    """P1: W A S D and G C V B steer, B confirms, F/H are L/R. P2: arrows,
    I J K L, L confirms, U/O are L/R."""
    from ion_surfer.input import Controls

    pygame.init()
    c = Controls()
    for key in (pygame.K_b, pygame.K_w, pygame.K_h, pygame.K_l, pygame.K_u):
        c.handle(pygame.event.Event(pygame.KEYDOWN, key=key))
    p1, p2 = c.pads
    assert p1.held("confirm") and p1.held("right") and p1.held("up") and p1.held("add_ion")
    assert p2.held("confirm") and p2.held("right") and p2.held("cool")
    assert not p1.held("cool") and not p2.held("add_ion")


def test_pad_treats_an_unknown_action_as_not_held():
    from ion_surfer.input import Pad
    assert Pad().held("no_such_action") is False
