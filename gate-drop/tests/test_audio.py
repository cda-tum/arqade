from gate_drop import audio
from gate_drop.board import Event
from gate_drop.match import BoardEvent, Cue


def test_note_frequencies():
    assert audio.note_freq("A4") == 440.0
    assert round(audio.note_freq("A5")) == 880
    assert audio.note_freq("-") == 0.0


def test_tones_have_the_right_length_and_range():
    s = audio.tone(440, 0.1, 0.5)
    assert len(s) == int(audio.SAMPLE_RATE * 0.1)
    assert max(abs(v) for v in s) <= audio.AMP


def test_every_event_sound_exists():
    events = [
        Cue("beep"), Cue("go"), Cue("round_won", "p1"), Cue("draw"), Cue("match_won", "p1"),
        Cue("blip"), Cue("level_clear"), Cue("game_over"),
        *(BoardEvent("p1", Event(k)) for k in ("move", "rotate", "land", "attack", "noise", "topout")),
        BoardEvent("p1", Event("errors", value=1)),
        *(BoardEvent("p1", Event("clear", value=n)) for n in range(1, 9)),
    ]
    sfx = audio.build_sfx()
    for name in audio.sounds_for(events):
        assert name in sfx, name


def test_chains_raise_the_pitch_and_each_sound_plays_once_per_frame():
    names = audio.sounds_for([BoardEvent("p1", Event("clear", value=1)), BoardEvent("p2", Event("clear", value=7)),
                              BoardEvent("p1", Event("move")), BoardEvent("p2", Event("move"))])
    assert names == ["clear1", "clear5", "move"]


def test_audio_never_raises_without_a_sound_card():
    a = audio.make_audio()
    a.play_events([Cue("beep")])
    a.music("title")
    a.tempo(True)
    a.update()
