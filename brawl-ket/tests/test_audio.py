"""Tests for the chiptune effects: every cue and fight event is mapped."""

from __future__ import annotations

import inspect
import re

from brawl_ket import audio, echo, fight, fighter, match
from brawl_ket.fight import Event
from brawl_ket.match import Cue
from brawl_ket.moves import CHARACTERS


def test_every_match_cue_has_a_sound() -> None:
    kinds = set(re.findall(r'Cue\("(\w+)"', inspect.getsource(match)))
    kinds |= {"ko", "timeout"}          # passed on from the fight as cues too
    assert kinds <= set(audio.CUE_SOUNDS)
    assert {s for s in audio.CUE_SOUNDS.values() if s} <= set(audio.build_sfx())


def test_every_fight_event_is_mapped() -> None:
    """A sound, or None for the ones deliberately silent (a stance switch, a landing)."""
    kinds = set(re.findall(r'Event\("(\w+)"', inspect.getsource(fight)))
    for module in (fighter, echo):
        kinds |= set(re.findall(r'events\.append\(\("(\w+)"', inspect.getsource(module)))
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


NEW_SOUNDS = ("box_split", "box_collapse", "pounce", "box_drop", "floppy", "mouse", "crt_drop", "copy", "paste")


def test_erwin_and_dos_have_their_sounds() -> None:
    sfx = audio.build_sfx()
    for kind in NEW_SOUNDS:
        assert audio.EVENT_SOUNDS.get(kind) in sfx, kind


def test_every_moves_cue_has_a_sound() -> None:
    moves = [m for c in CHARACTERS.values() for m in (*c.moves.values(), *c.extra.values())]
    assert {m.cue for m in moves if m.cue} <= {k for k, s in audio.EVENT_SOUNDS.items() if s}


def test_a_floppy_and_a_paste_replace_the_photons_sound() -> None:
    assert audio.sounds_for([Event("projectile", "p1"), Event("floppy", "p1")]) == ["floppy"]
    assert audio.sounds_for([Event("projectile", "p1"), Event("paste", "p1")]) == ["paste"]


CUTIE_SOUNDS = (*(f"charge{n}" for n in range(1, 7)), *(f"wave{n}" for n in range(1, 7)), "trap_set", "trap_close",
                "spin")


def test_m_cutie_has_her_sounds() -> None:
    sfx = audio.build_sfx()
    for kind in CUTIE_SOUNDS:
        assert audio.EVENT_SOUNDS.get(kind) == kind and kind in sfx, kind
    assert audio.EVENT_SOUNDS["trap"] is None          # the fighter's own: the fight makes it a trap


def crossings(samples) -> int:
    return sum(1 for a, b in zip(samples, samples[1:]) if (a < 0) != (b < 0))


def test_each_charge_step_blips_higher_and_a_bigger_wave_whooshes_deeper() -> None:
    sfx = audio.build_sfx()
    blips = [crossings(sfx[f"charge{n}"]) for n in range(1, 7)]
    assert blips == sorted(blips) and len(set(blips)) == 6
    tones = [audio.tone(900 - 100 * n, 0.2, 0.16, "triangle", decay=7, slide=0.5) for n in range(1, 7)]
    whoosh = [crossings(t) for t in tones]              # the whoosh's tone, without its noise
    assert whoosh == sorted(whoosh, reverse=True)


KIDS_SOUNDS = ("toss", "catch", "key_shot", "teleport", "bell_dive", "decohere", "recohere")


def test_alice_and_bob_have_their_sounds() -> None:
    sfx = audio.build_sfx()
    for kind in KIDS_SOUNDS:
        assert audio.EVENT_SOUNDS.get(kind) == kind and kind in sfx, kind
    assert audio.EVENT_SOUNDS["pass"] is None and audio.EVENT_SOUNDS["swap"] is None     # the fighter's own
    assert audio.EVENT_SOUNDS["intercept"] == "sizzle"


def test_bobs_shot_replaces_the_photons_sound() -> None:
    assert audio.sounds_for([Event("projectile", "p1"), Event("key_shot", "p1")]) == ["key_shot"]


def test_teleport_shimmers_at_both_ends() -> None:
    """Down at one end and up at the other: its first half falls, its second rises."""
    sfx = audio.build_sfx()["teleport"]
    half = len(sfx) // 2
    a, b = sfx[:half], sfx[half:]
    assert crossings(a[: half // 3]) > crossings(a[-half // 3:]) and crossings(b[: half // 3]) < crossings(b[-half // 3:])


def test_her_wave_replaces_the_photons_sound() -> None:
    assert audio.sounds_for([Event("projectile", "p1"), Event("wave3", "p1")]) == ["wave3"]


def test_the_super_has_its_sounds() -> None:
    sfx = audio.build_sfx()
    for kind in ("super_half", "super_full"):
        assert audio.EVENT_SOUNDS.get(kind) in sfx, kind
