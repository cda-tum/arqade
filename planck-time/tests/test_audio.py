import inspect
import re

import random

from planck_time import audio, session
from planck_time.microgames import BOSSES, REGISTRY
from planck_time.session import Cue, Session


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
    assert "boss" in audio.TRACKS


def test_every_track_has_a_tune_and_a_wave():
    for bpm, lead, tune in audio.TRACKS.values():
        assert bpm > 0 and tune in audio.TUNES
        audio._wave(lead, 0.3)
        assert lead in ("square", "pulse", "triangle", "saw")


def test_the_boss_track_is_faster_and_renders_a_whole_loop():
    bpm, lead, tune = audio.TRACKS["boss"]
    assert bpm > max(audio.GAME_BPM[:3]) and lead == "saw"
    samples = audio.render_track(bpm, lead, audio.TUNES[tune])
    loop = len(audio.BOSS_MELODY) * 4 * 60 / bpm * audio.SAMPLE_RATE
    assert abs(len(samples) - loop) < audio.SAMPLE_RATE * 0.01
    assert max(map(abs, samples)) > audio.AMP // 4


def test_the_boss_music_plays_through_a_boss_and_only_then():
    s = Session(random.Random(0), registry=REGISTRY[:2], bosses=BOSSES)
    assert audio.music_for(s) == "title"
    s.state = session.PLAY
    s.game_cls = REGISTRY[0]
    assert audio.music_for(s) == "game"
    s.state = session.BOSS_CARD  # the card: the last microgame is still current
    assert audio.music_for(s) == "boss"
    s.game_cls = BOSSES[0]
    for state in (session.INTRO, session.PLAY, session.RESULT):
        s.state = state
        assert audio.music_for(s) == "boss"
    for state in (session.GAME_OVER, session.MATCH_RESULT):
        s.state = state
        assert audio.music_for(s) == "game"
    for name in ("title", "game", "boss"):  # every key music_for gives has a track
        key = f"game{min(3, len(audio.GAME_BPM) - 1)}" if name == "game" else name
        assert key in audio.TRACKS


def test_null_audio_is_a_silent_stand_in():
    a = audio.NullAudio()
    a.music("game")
    a.tempo(3)
    a.update()
    a.play_events([Cue("win", "p1")])
