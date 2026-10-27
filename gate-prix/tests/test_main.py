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
              Event("check", "p1", 4), Event("warp", "p1", (1.0, 6.0)), Event("lap", "p1", 2), Event("finish", "p1", 1),
              Event("bump", "p1", "cpu1"), Event("box", "p1", "QEC"), Event("box", "p1", None),
              Event("box_full", "p1", "SPLIT"), Event("item", "p1", "SPLIT"),
              Event("item", "p1", "QEC"), Event("split_end", "p1"),
              Event("item", "p1", "MEASURE"), Event("item", "p1", "TUNNEL"),
              Event("item", "p1", "DECOHERENCE"), Event("turbo", "p1", 1),
              Event("turbo", "p1", 2), Event("drift", "p1", 1), Event("hazard", "p1", "cloud"),
              Event("hazard", "p1", "mine"), Event("collapse", "p1", "cpu1"),
              Event("decohered", "p1", "cpu1"), Event("fizzle", "p1"),
              Event("immune", "p1", "shot"), Event("tunnel_end", "p1")]:
        name = audio.sound_for(e)
        assert name in sfx, e
    assert audio.sounds_for([Event("bump", "p1", "a"), Event("bump", "p1", "b")]) == ["bump"]
    assert audio.sound_for(Event("warp", "p1", (1.0, 6.0))) == "warp"
    # a whoosh you can hear: the warp's is the longest sound there is
    assert len(sfx["warp"]) == max(len(v) for v in sfx.values())


def test_the_shooter_and_the_victim_of_a_hit_hear_different_sounds():
    hit = Event("collapse", "cpu1", "p1")  # P1's MEASURE collapsed a CPU
    assert audio.sound_for(hit, ("p1",)) == "scored"
    assert audio.sound_for(Event("collapse", "p1", "cpu1"), ("p1",)) == "collapsed"
    assert audio.sound_for(Event("decohered", "cpu2", "p2"), ("p1", "p2")) == "deco_scored"
    assert audio.sound_for(Event("decohered", "p2", "cpu2"), ("p1", "p2")) == "static"
    # P1 measures P2: both sounds, once each
    both = audio.sounds_for([Event("collapse", "p2", "p1")], ("p1", "p2"))
    assert set(both) == {"collapsed", "scored"}
    # P1 measures a bot: the bot's zap, as a person's, and P1's ring
    assert set(audio.sounds_for([hit], ("p1",))) == {"collapsed", "scored"}
    # what happens between two bots (passed on by the match when a player sees it)
    assert audio.sounds_for([Event("collapse", "cpu1", "cpu2")], ("p1",)) == ["collapsed"]
    assert audio.sounds_for([Event("bump", "cpu1", "cpu2"), Event("bump", "cpu2", "cpu1")],
                            ("p1",)) == ["bump"]
    # every item has a sound of its own
    names = {audio.sound_for(Event("item", "p1", item)) for item in config.ITEMS}
    assert len(names) == len(config.ITEMS)
    assert audio.sound_for(Event("hazard", "p1", "mine")) != audio.sound_for(Event("hazard", "p1", "cloud"))


def test_there_is_no_engine_only_a_nitro_hiss_while_boosting():
    assert not hasattr(audio, "engine_loop")
    assert audio.nitro_volume(0.0) == 0.0
    assert 0 < audio.nitro_volume(0.2) < audio.nitro_volume(0.5) <= audio.nitro_volume(2.0) == 1.0
    loop = audio.nitro_loop()
    assert len(loop) == int(audio.SAMPLE_RATE * 0.6)
    assert max(abs(v) for v in loop) < audio.AMP // 2 + 1


def test_the_audio_plays_or_stays_silent_without_crashing():
    pygame.init()
    a = audio.make_audio()
    deadline = time.time() + 20
    while not a.ready() and time.time() < deadline:
        time.sleep(0.05)
    a.play_events([Cue("go"), Event("right", "p1", 2)])
    a.nitro({"p1": 0.3, "p2": 0.7})
    a.nitro({"p1": 0.3})
    a.nitro({})
    a.menu_music(True)
    a.menu_music(False)
    assert config.MASTER_VOLUME > 0
