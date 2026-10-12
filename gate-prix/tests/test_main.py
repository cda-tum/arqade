"""The command line, the input test, the audio and a short scripted session of the real
loop (the full one is `--selftest 600`)."""

import time

import pygame
import pytest

from gate_prix import audio, config
from gate_prix.main import main, parse_args
from gate_prix.match import Cue
from gate_prix.race import Event


def test_defaults_are_a_windowed_dev_run():
    args = parse_args([])
    assert not args.fullscreen and not args.no_keyboard and not args.input_test
    assert args.window_size == "1440x810" and args.selftest is None


def test_the_cabinet_loader_and_launcher_flags_parse():
    args = parse_args(["--fullscreen", "--no-keyboard", "--fps", "--window-size", "960x540"])
    assert args.fullscreen and args.no_keyboard and args.fps and args.window_size == "960x540"


def test_the_input_test_screen_runs_and_leaves_on_quit():
    from gate_prix.input_test import run_input_test

    pygame.init()
    surface = pygame.Surface((960, 540))
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    run_input_test(surface, None)


def test_a_short_scripted_session_runs_through_the_real_loop(tmp_path, capsys):
    with pytest.raises(SystemExit) as done:
        main(["--selftest", "20", "--window-size", "960x540", "--shots", str(tmp_path),
              "--seed", "3"])
    assert done.value.code == 0
    out = capsys.readouterr().out
    assert "selftest ok" in out
    assert len(list(tmp_path.glob("*.png"))) >= 3  # the title, the attract race, the countdown


def test_every_cue_has_a_sound_and_the_effects_build():
    sfx = audio.build_sfx()
    for e in [Cue("blip"), Cue("select"), Cue("count", value=3), Cue("go"), Cue("pause"),
              Cue("result"), Event("right", "p1", 1), Event("right", "p1", 30),
              Event("wrong", "p1", 0), Event("miss", "p1", 0), Event("check", "p1", 0),
              Event("check", "p1", 4), Event("lap", "p1", 2), Event("finish", "p1", 1),
              Event("bump", "p1", "green"), Event("box", "p1", "QEC"), Event("box", "p1", None),
              Event("box_full", "p1", "SPLIT"), Event("item", "p1", "SPLIT"),
              Event("item", "p1", "QEC"), Event("split_end", "p1")]:
        name = audio.sound_for(e)
        assert name in sfx, e
    assert audio.sounds_for([Event("bump", "p1", "a"), Event("bump", "p1", "b")]) == ["bump"]


def test_the_engine_rises_with_speed_and_loops_whole_periods():
    assert audio.engine_step(0.0) == 0 and audio.engine_step(5.0) == audio.ENGINE_STEPS - 1
    assert audio.engine_step(1.0) < audio.engine_step(1.5)
    freqs = [audio.engine_freq(i) for i in range(audio.ENGINE_STEPS)]
    assert freqs == sorted(freqs)
    loop = audio.engine_loop(3)
    period = 2 * round(audio.SAMPLE_RATE / audio.engine_freq(3))
    assert len(loop) % period == 0


def test_the_audio_plays_or_stays_silent_without_crashing():
    pygame.init()
    a = audio.make_audio()
    deadline = time.time() + 20
    while not a.ready() and time.time() < deadline:
        time.sleep(0.05)
    a.play_events([Cue("go"), Event("right", "p1", 2)])
    a.engines({"p1": 1.0, "p2": 0.3})
    a.engines({"p1": 1.2})
    a.engines({})
    assert config.MASTER_VOLUME > 0
