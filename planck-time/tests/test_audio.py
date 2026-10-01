import inspect
import re

from planck_time import audio, session
from planck_time.session import Cue


def test_every_session_cue_has_a_sound():
    kinds = set(re.findall(r'Cue\("(\w+)"', inspect.getsource(session)))
    assert kinds <= set(audio._CUE_SOUNDS)
    assert set(audio._CUE_SOUNDS.values()) <= set(audio.build_sfx())


def test_sounds_for_plays_each_sound_once_per_frame():
    events = [Cue("win", "p1"), Cue("win", "p2"), Cue("blip")]
    assert audio.sounds_for(events) == ["win", "blip"]


def test_every_tempo_tier_has_a_track():
    for level in range(10):
        tier = min(level, len(audio.GAME_BPM) - 1)
        assert f"game{tier}" in audio.TRACKS
    assert "title" in audio.TRACKS


def test_null_audio_is_a_silent_stand_in():
    a = audio.NullAudio()
    a.music("game")
    a.tempo(3)
    a.update()
    a.play_events([Cue("win", "p1")])
