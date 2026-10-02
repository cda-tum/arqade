from quantum_pong.pause import (
    PAUSE_ITEMS,
    PAUSED,
    PLAY,
    QUIT_TO_TITLE,
    PauseInput,
    PauseMenu,
    nav_edge,
)


def _paused_menu() -> PauseMenu:
    menu = PauseMenu()
    menu.update(PauseInput(pause=True))
    return menu


def test_menu_plays_until_start_is_pressed():
    menu = PauseMenu()
    assert menu.update(PauseInput()) == PLAY
    assert menu.update(PauseInput(confirm=True, back=True, nav=1)) == PLAY
    assert not menu.paused


def test_start_pauses_and_play_stays_frozen_without_input():
    menu = PauseMenu()
    assert menu.update(PauseInput(pause=True)) == PAUSED
    assert menu.paused
    for _ in range(10):
        assert menu.update(PauseInput()) == PAUSED


def test_pausing_always_starts_on_resume():
    menu = _paused_menu()
    menu.update(PauseInput(nav=1))
    menu.update(PauseInput(pause=True))  # resume
    menu.update(PauseInput(pause=True))  # pause again
    assert PAUSE_ITEMS[menu.index] == "RESUME"


def test_start_resumes():
    menu = _paused_menu()
    assert menu.update(PauseInput(pause=True)) == PLAY
    assert not menu.paused


def test_b_resumes():
    menu = _paused_menu()
    assert menu.update(PauseInput(back=True)) == PLAY
    assert not menu.paused


def test_start_resumes_even_with_quit_to_title_selected():
    menu = _paused_menu()
    menu.update(PauseInput(nav=1))
    assert menu.update(PauseInput(pause=True)) == PLAY


def test_a_on_resume_resumes():
    menu = _paused_menu()
    assert menu.update(PauseInput(confirm=True)) == PLAY
    assert not menu.paused


def test_a_on_quit_to_title_goes_to_the_title():
    menu = _paused_menu()
    menu.update(PauseInput(nav=1))
    assert PAUSE_ITEMS[menu.index] == "QUIT TO TITLE"
    assert menu.update(PauseInput(confirm=True)) == QUIT_TO_TITLE
    assert not menu.paused


def test_selection_moves_with_the_stick_and_wraps():
    menu = _paused_menu()
    assert menu.index == 0
    assert menu.update(PauseInput(nav=1)) == PAUSED
    assert menu.index == 1
    menu.update(PauseInput(nav=1))
    assert menu.index == 0  # wrapped past the last item
    menu.update(PauseInput(nav=-1))
    assert menu.index == len(PAUSE_ITEMS) - 1


def test_nav_edge_moves_once_per_push():
    assert nav_edge(previous=0, current=1) == 1
    assert nav_edge(previous=0, current=-1) == -1
    assert nav_edge(previous=1, current=1) == 0  # still held
    assert nav_edge(previous=1, current=0) == 0  # released
    assert nav_edge(previous=1, current=-1) == -1  # flicked straight across


def test_pause_input_any_counts_every_button_and_the_stick():
    assert not PauseInput().any
    assert PauseInput(pause=True).any
    assert PauseInput(back=True).any
    assert PauseInput(confirm=True).any
    assert PauseInput(nav=-1).any
