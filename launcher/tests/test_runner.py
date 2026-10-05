import sys

import pygame

from arqade_launcher import runner
from arqade_launcher.catalog import Game
from arqade_launcher.settings import RAW_BUTTONS, Settings


def test_game_args_follow_the_settings():
    assert runner.game_args(Settings(), (800, 600)) == ["--fullscreen", "--no-keyboard"]
    assert runner.game_args(Settings(fullscreen=False, pads=False, show_fps=True), (800, 600)) == [
        "--window-size", "800x600", "--fps"]


def test_input_config_uses_raw_numbers_and_axes():
    config = runner.input_config(Settings())
    assert config["exit_key"] == pygame.K_ESCAPE
    p1 = {b["key"]: b for b in config["pads"][0]}
    assert p1[pygame.K_n] == {"key": pygame.K_n, "kind": "button", "index": RAW_BUTTONS["a"]}
    assert p1[pygame.K_1]["index"] == 9  # Start
    assert p1[pygame.K_a] == {"key": pygame.K_a, "kind": "axis", "index": 0, "sign": -1}
    assert runner.input_config(Settings(pads=False))["pads"] == []


def test_unbound_actions_are_left_out():
    s = Settings()
    s.keys["p1"]["a"] = None
    assert len(runner.input_config(s)["pads"][0]) == 11


GAME = '''
import json, os, sys
import pygame

def main(argv):
    pygame.display.init()
    pygame.joystick.init()
    pads = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
    print(json.dumps({"argv": argv, "pads": [p.get_name() for p in pads], "cwd": os.getcwd()}),
          file=sys.stderr)
    sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
'''


def test_runs_a_game_in_its_own_process(tmp_path, monkeypatch):
    package = tmp_path / "fake-game" / "src" / "fake_game"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "main.py").write_text(GAME)
    game = Game("fake_game", tmp_path / "fake-game", "Fake", "", None)
    result = runner.run_game(game, Settings(fullscreen=False), (640, 360))
    assert result.code == 0, result.stderr_tail
    out = result.stderr_tail[-1]
    assert '"argv": ["--window-size", "640x360", "--no-keyboard"]' in out
    assert "keyboard pad P1" in out and "keyboard pad P2" in out
    assert str(tmp_path / "fake-game") in out

    monkeypatch.setenv("FAKE_EXIT", "3")
    assert runner.run_game(game, Settings(fullscreen=False), (640, 360)).code == 3


def test_command_uses_this_interpreter():
    game = Game("g", __import__("pathlib").Path("/x/g"), "G", "", None)
    cmd = runner.command(game, Settings(), (1, 1))
    assert cmd[:5] == [sys.executable, "-m", "arqade_launcher.child", "/x/g/src", "g"]
