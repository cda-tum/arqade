from qurves.main import parse_args


def test_defaults_are_a_windowed_dev_run():
    args = parse_args([])
    assert not args.fullscreen and not args.no_keyboard and not args.input_test
    assert args.window_size == "1440x810"


def test_the_cabinet_loader_flags_parse():
    args = parse_args(["--fullscreen", "--no-keyboard"])
    assert args.fullscreen and args.no_keyboard


def test_quit_on_the_title_ends_the_game_loop(monkeypatch):
    from qurves import game
    from qurves.match import FrameInput

    script = iter([FrameInput(), FrameInput(nav=(0, 1), activity=True), FrameInput(confirm=True, pick=True)])

    class ScriptedInput:
        select_held_time = 0.0
        keyboard_quit = False

        def handle(self, event):
            pass

        def update(self, dt):
            pass

        def quit_combo(self):
            return False

        def frame_input(self):
            return next(script)  # running past the script would raise StopIteration

    monkeypatch.setattr(game, "Input", ScriptedInput)
    game.run(fullscreen=False, window_size="320x180", show_fps=False)  # returns: the loop exited
