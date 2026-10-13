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


def test_null_audio_is_a_silent_stand_in():
    a = audio.NullAudio()
    a.play_events([Cue("win", "p1")])
