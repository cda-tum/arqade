"""Tests for the HOW TO PLAY scene: a real fight, played from its script."""

from __future__ import annotations

from brawl_ket import basis
from brawl_ket.tutorial import LOOP, SCRIPT, Lesson


def play(lesson: Lesson, frames: int) -> list:
    events = []
    for _ in range(frames):
        events += [(lesson.t, e) for e in lesson.step()]
    return events


def test_the_scene_teaches_the_colour_rule_in_order() -> None:
    """A green jab hurts green, the rival switches, the same jab bounces, B hurts purple."""
    lesson = Lesson()
    events = [e for _t, e in play(lesson, LOOP) if e.kind in ("hit", "block", "switch")]
    assert [(e.kind, e.player, e.error) for e in events] == [
        ("hit", "p2", basis.X), ("switch", "p2", None), ("block", "p2", basis.X), ("hit", "p2", basis.Z),
    ]


def test_the_captions_follow_the_script() -> None:
    lesson = Lesson()
    seen = []
    for _ in range(LOOP):
        lesson.step()
        if not seen or seen[-1] != lesson.caption:
            seen.append(lesson.caption)
    assert seen == [index for *_rest, index in SCRIPT]


def test_the_scene_loops_with_a_fresh_fight() -> None:
    lesson = Lesson()
    first = lesson.fight
    play(lesson, LOOP)
    assert lesson.fight is first
    play(lesson, 1)
    assert lesson.fight is not first and lesson.t == 1
    hurt = first.fighters["p2"]
    assert hurt.health < hurt.char.health and hurt.basis == basis.X_BASIS
    assert not first.over                   # nobody is knocked out: it only teaches


def test_nobody_is_thrown_by_accident() -> None:
    """ROBERT walks in between presses, but never while pressing B (that would throw)."""
    lesson = Lesson()
    for _ in range(LOOP):
        inputs = lesson.inputs()
        assert not (inputs["p1"].b and inputs["p1"].dx)
        lesson.step()
