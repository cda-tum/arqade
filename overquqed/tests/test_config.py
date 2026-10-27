from overquqed.config import GRID_H, GRID_W, INTERNAL_HEIGHT, INTERNAL_WIDTH, TILE
from overquqed.input import ACTION_BUTTONS


def test_resolution_is_4_3_and_tiles_fit_exactly():
    assert INTERNAL_WIDTH * 3 == INTERNAL_HEIGHT * 4
    assert GRID_W * TILE == INTERNAL_WIDTH
    assert GRID_H * TILE == INTERNAL_HEIGHT


def test_each_printed_button_does_one_thing():
    # A picks, B uses a station, Y swaps chef; Start and Select are their own.
    assert ACTION_BUTTONS == {"pick": "a", "use": "b", "swap": "y", "start": "start", "select": "select"}
    assert len(set(ACTION_BUTTONS.values())) == len(ACTION_BUTTONS)
