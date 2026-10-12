from qircuit.main import parse_args


def test_defaults_are_a_windowed_dev_run():
    args = parse_args([])
    assert not args.fullscreen and not args.no_keyboard and not args.input_test
    assert args.window_size == "1440x810"


def test_the_cabinet_loader_flags_parse():
    args = parse_args(["--fullscreen", "--no-keyboard"])
    assert args.fullscreen and args.no_keyboard
