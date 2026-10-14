"""Tests for the chiptune effects: every cue and fight event is mapped."""

from __future__ import annotations

import inspect
import re

from brawl_ket import audio, fight, fighter, match
from brawl_ket.fight import Event
from brawl_ket.match import Cue


def test_every_match_cue_has_a_sound() -> None:
    kinds = set(re.findall(r'Cue\("(\w+)"', inspect.getsource(match)))
    kinds |= {"ko", "timeout"}          # passed on from the fight as cues too
    assert kinds <= set(audio.CUE_SOUNDS)
    assert {s for s in audio.CUE_SOUNDS.values() if s} <= set(audio.build_sfx())


def test_every_fight_event_is_mapped() -> None:
    """A sound, or None for the ones deliberately silent (a stance switch, a landing)."""
    kinds = set(re.findall(r'Event\("(\w+)"', inspect.getsource(fight)))
    kinds |= set(re.findall(r'events\.append\(\("(\w+)"', inspect.getsource(fighter)))
    assert kinds <= set(audio.EVENT_SOUNDS), kinds - set(audio.EVENT_SOUNDS)
    assert {s for s in audio.EVENT_SOUNDS.values() if s} <= set(audio.build_sfx())
    assert {"hit", "block", "switch", "measure"} <= {k for k, s in audio.EVENT_SOUNDS.items() if s}


def test_sounds_for_plays_each_sound_once_per_frame() -> None:
    events = [Event("hit", "p2", "X"), Event("hit", "p1", "Z"), Cue("blip"), Event("land", "p1")]
    assert audio.sounds_for(events) == ["hit", "blip"]


def test_a_block_pings_and_a_switch_whooshes() -> None:
    assert audio.sounds_for([Event("block", "p2", "Z")]) == ["ping"]
    assert audio.sounds_for([Event("switch", "p1")]) == ["whoosh"]


def test_measure_replaces_its_own_throws_thump() -> None:
    assert audio.sounds_for([Event("hit", "p2", "Y"), Event("measure", "p2")]) == ["measure"]


def test_null_audio_is_a_silent_stand_in() -> None:
    a = audio.NullAudio()
    a.play_events([Cue("blip"), Event("hit", "p1", "X")])
