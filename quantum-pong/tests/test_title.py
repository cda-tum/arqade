from quantum_pong.title import QUIT, START, STAY, TITLE_ITEMS, TitleInput, TitleMenu


def test_quit_is_the_last_item():
    assert TITLE_ITEMS[-1] == "QUIT"
    assert TITLE_ITEMS[0] == "PLAY"


def test_play_is_preselected_and_nothing_happens_without_input():
    menu = TitleMenu()
    assert TITLE_ITEMS[menu.index] == "PLAY"
    for _ in range(10):
        assert menu.update(TitleInput()) == STAY


def test_a_on_play_starts():
    assert TitleMenu().update(TitleInput(confirm=True)) == START


def test_stick_down_then_a_quits():
    menu = TitleMenu()
    assert menu.update(TitleInput(nav=1)) == STAY
    assert TITLE_ITEMS[menu.index] == "QUIT"
    assert menu.update(TitleInput(confirm=True)) == QUIT


def test_start_starts_even_with_quit_selected():
    menu = TitleMenu(index=TITLE_ITEMS.index("QUIT"))
    assert menu.update(TitleInput(start=True)) == START


def test_start_wins_over_a_pressed_on_quit_in_the_same_frame():
    menu = TitleMenu(index=TITLE_ITEMS.index("QUIT"))
    assert menu.update(TitleInput(start=True, confirm=True)) == START


def test_b_does_not_quit_or_start():
    menu = TitleMenu(index=TITLE_ITEMS.index("QUIT"))
    assert menu.update(TitleInput(back=True)) == STAY
    assert TITLE_ITEMS[menu.index] == "QUIT"


def test_stick_wraps_round():
    menu = TitleMenu()
    menu.update(TitleInput(nav=-1))
    assert TITLE_ITEMS[menu.index] == "QUIT"
    menu.update(TitleInput(nav=1))
    assert TITLE_ITEMS[menu.index] == "PLAY"
