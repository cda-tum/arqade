"""The match flow. Pure (no pygame): one FrameInput per 60 Hz frame in, events out.

  title -> select -> tutorial -> round intro -> fight -> round end -> (round intro ...)
        -> match result -> rematch (round intro) or title

The title is a menu, PLAY / QUIT: the stick picks, A takes it, and Start always plays.
QUIT ends the game (`quit` is set and the main loop exits, as Start + Select does).
The tutorial is the HOW TO PLAY card, before every match from the select screen (not
a rematch); any button pressed after its first TUTORIAL_LOCK frames goes on.

Rounds are first to ROUNDS_TO_WIN; a draw round counts for nobody. Start pauses
the round intro, the fight and the round end (RESUME / QUIT TO TITLE). Left
untouched, the title runs a bot-against-bot demo; IDLE_TIMEOUT frames without
input anywhere else returns to the title.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import config
from .bot import Bot
from .fight import Fight
from .fighter import IDLE
from .moves import CHARACTERS
from .tutorial import Lesson

PLAYERS = ("p1", "p2")
ROSTER = tuple(CHARACTERS.values())     # the select screen's order: TRIO, QUINT

TITLE = "title"
SELECT = "select"
TUTORIAL = "tutorial"
ROUND_INTRO = "round_intro"
FIGHT = "fight"
ROUND_END = "round_end"
MATCH_RESULT = "match_result"
TITLE_ITEMS = ("PLAY", "QUIT")
PAUSE_ITEMS = ("RESUME", "QUIT TO TITLE")
PAUSABLE = (ROUND_INTRO, FIGHT, ROUND_END)
FIGHT_CALL = config.ROUND_INTRO_FRAMES // 2     # "ROUND n" until here, then "FIGHT!"


@dataclass(frozen=True)
class Cue:
    """A match-level event, for the sound and the renderer."""

    kind: str   # blip confirm pause round fight ko timeout perfect draw match_won
    player: str | None = None


def _per_player(make):
    return lambda: {p: make() for p in PLAYERS}


@dataclass
class FrameInput:
    fighters: dict = field(default_factory=_per_player(lambda: IDLE))   # in the fight
    nav: dict = field(default_factory=_per_player(lambda: (0, 0)))      # menus: stick pushes (edges)
    confirms: dict = field(default_factory=_per_player(bool))  # A or Start pressed
    backs: dict = field(default_factory=_per_player(bool))     # B pressed
    pauses: dict = field(default_factory=_per_player(bool))    # Start pressed
    any_button: bool = False    # any button at all went down, on either pad (the tutorial)
    activity: bool = False      # any input at all (the idle timeout, stopping the demo)
    held: bool = False          # any button still down (the title waits for it to clear)

    @property
    def confirm(self) -> bool:
        return any(self.confirms.values())

    @property
    def back(self) -> bool:
        return any(self.backs.values())

    @property
    def pause(self) -> bool:
        return any(self.pauses.values())


class Match:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.state = TITLE
        self.t = 0                  # frames in the current state
        self.idle = 0               # frames without input
        self.picks = {"p1": 0, "p2": 1}     # indices into ROSTER, kept from match to match
        self.ready = {p: False for p in PLAYERS}
        self.fight: Fight | None = None
        self.round_no = 1
        self.wins = {p: 0 for p in PLAYERS}
        self.round_winner: str | None = None    # of the round just ended (None: a draw)
        self.perfect = False
        self.ko = False                         # the round just ended on a K.O. (not on time)
        self.winner: str | None = None          # of the match
        self.paused = False
        self.pause_index = 0
        self.wait_release = False   # the title ignores buttons until all are let go
        self.title_index = 0        # PLAY / QUIT
        self.quit = False           # QUIT was picked: the main loop ends the game
        self.lesson: Lesson | None = None   # the tutorial's scene
        self.attract: Fight | None = None
        self.card = False           # the title shows the COLOUR MUST MATCH card (between demos)
        self.hint = False           # this round intro shows the rules hint (a match's first)
        self._title_phase = 0       # frames into the current demo or card
        self.bots: dict[str, Bot] = {}
        self._attract_over = 0

    # --- the frame -------------------------------------------------------------------------

    def update(self, inp: FrameInput) -> list:
        self.idle = 0 if inp.activity else self.idle + 1
        if self.state != TITLE and self.idle >= config.IDLE_TIMEOUT:
            self._to_title()
            return []
        events: list = []
        if self.state in PAUSABLE and (self.paused or inp.pause):
            self._on_pause(inp, events)
            return events
        self.t += 1
        getattr(self, f"_on_{self.state}")(inp, events)
        return events

    def _on_pause(self, inp: FrameInput, events: list) -> None:
        """Start pauses (either pad). In the menu the stick moves, A picks, and
        Start or B resumes. Nothing moves meanwhile, the round clock included."""
        if not self.paused:
            self.paused = True
            self.pause_index = 0
            events.append(Cue("pause"))
            return
        if inp.pause or inp.back:
            self.paused = False
            events.append(Cue("blip"))
            return
        dy = next((d[1] for d in inp.nav.values() if d[1]), 0)
        if dy:
            self.pause_index = (self.pause_index + dy) % len(PAUSE_ITEMS)
            events.append(Cue("blip"))
        if inp.confirm:         # A (Start resumed above)
            events.append(Cue("blip"))
            if PAUSE_ITEMS[self.pause_index] == "RESUME":
                self.paused = False
            else:
                self._to_title()
                self.wait_release = True

    def _on_title(self, inp: FrameInput, events: list) -> None:
        if self.wait_release:
            if inp.held:
                return
            self.wait_release = False
        if self.attract is not None or self.card:
            if inp.activity:        # any input ends the demo or the card, and does nothing else
                self.card = False
                self._stop_attract()
                return
            self._title_phase += 1
            if self.card:
                if self._title_phase >= config.CARD_FRAMES:     # the card's done: the demo again
                    self.card = False
                    self._start_attract()
                return
            if self._title_phase >= config.DEMO_FRAMES:          # the demo's done: the card
                self._stop_attract()
                self.card = True
                self._title_phase = 0
                return
            self._step_attract()
            return
        dy = next((d[1] for d in inp.nav.values() if d[1]), 0)
        if inp.pause or (inp.confirm and TITLE_ITEMS[self.title_index] == "PLAY"):
            self.ready = {p: False for p in PLAYERS}
            self._set_state(SELECT)
            events.append(Cue("confirm"))
        elif inp.confirm:           # A on QUIT: no questions asked
            self.quit = True
        elif dy:
            self.title_index = (self.title_index + dy) % len(TITLE_ITEMS)
            events.append(Cue("blip"))
        elif self.t >= config.ATTRACT_DELAY and not inp.activity:
            self._start_attract()

    def _on_select(self, inp: FrameInput, events: list) -> None:
        for p in PLAYERS:
            if inp.backs[p]:
                if not self.ready[p]:
                    self._to_title()
                    events.append(Cue("blip"))
                    return
                self.ready[p] = False
                events.append(Cue("blip"))
            elif self.ready[p]:
                continue
            elif inp.confirms[p]:
                self.ready[p] = True
                events.append(Cue("confirm"))
            elif inp.nav[p][0]:
                self.picks[p] = (self.picks[p] + inp.nav[p][0]) % len(ROSTER)
                events.append(Cue("blip"))
        if all(self.ready.values()):
            self.lesson = Lesson()
            self._set_state(TUTORIAL)

    def _on_tutorial(self, inp: FrameInput, events: list) -> None:
        """HOW TO PLAY: its scene plays until any button, pressed once the card has been up
        TUTORIAL_LOCK frames (the A that readied, or its bounce, must not skip it unseen).
        Only edges count, so the press that goes on does nothing in the round."""
        if self.t > config.TUTORIAL_LOCK and inp.any_button:
            self.lesson = None
            events.append(Cue("confirm"))
            self._start_match(events)
            return
        events += self.lesson.step()

    def _on_round_intro(self, inp: FrameInput, events: list) -> None:
        if self.t == FIGHT_CALL:
            events.append(Cue("fight"))
        if self.t >= config.ROUND_INTRO_FRAMES:
            self._set_state(FIGHT)

    def _on_fight(self, inp: FrameInput, events: list) -> None:
        fight = self.fight
        events += fight.step(inp.fighters)
        if not fight.over:
            return
        self.round_winner = fight.winner
        if fight.winner is None:
            events.append(Cue("draw"))
            self.perfect = False
        else:
            self.wins[fight.winner] += 1
            f = fight.fighters[fight.winner]
            self.perfect = f.health >= f.char.health
            if self.perfect:
                events.append(Cue("perfect", fight.winner))
        # the fight's own "ko" / "timeout" event is passed on as a cue too
        self.ko = any(f.health <= 0 for f in fight.fighters.values())
        events.append(Cue("ko" if self.ko else "timeout", fight.winner))
        self._set_state(ROUND_END)

    def _on_round_end(self, inp: FrameInput, events: list) -> None:
        # the bodies play out: in slow motion for the first moments of a K.O.
        slow = self.ko and self.t <= config.KO_SLOW_FRAMES
        if not slow or self.t % config.KO_SLOW_RATE == 0:
            self.fight.step({p: IDLE for p in PLAYERS})
        if self.t < config.ROUND_END_FRAMES:
            return
        leader = max(self.wins, key=self.wins.get)
        if self.wins[leader] >= config.ROUNDS_TO_WIN:
            self.winner = leader
            self._set_state(MATCH_RESULT)
            events.append(Cue("match_won", leader))
        else:
            self.round_no += 1
            self.hint = False
            self._start_round(events)

    def _on_match_result(self, inp: FrameInput, events: list) -> None:
        if self.t < config.MATCH_RESULT_LOCK:
            return
        if inp.confirm:
            events.append(Cue("blip"))
            self._start_match(events)
        elif inp.back:
            events.append(Cue("blip"))
            self._to_title()

    # --- the attract demo ------------------------------------------------------------------

    def _start_attract(self) -> None:
        self.title_index = 0    # whoever stops the demo finds PLAY, never QUIT, under A
        chars = {p: self.rng.choice(ROSTER) for p in PLAYERS}
        self.attract = Fight(chars)
        self._title_phase = 0
        seed = self.rng.randrange(1 << 30)
        self.bots = {p: Bot(p, seed + i) for i, p in enumerate(PLAYERS)}
        self._attract_over = 0

    def _step_attract(self) -> None:
        fight = self.attract
        if fight.over:
            self._attract_over += 1
            if self._attract_over >= config.ROUND_END_FRAMES:
                self._start_attract()
            elif self._attract_over % config.KO_SLOW_RATE == 0 or self._attract_over > config.KO_SLOW_FRAMES:
                fight.step({p: IDLE for p in PLAYERS})      # the bodies play out, as in a match
            return
        fight.step({p: bot.input(fight) for p, bot in self.bots.items()})

    def _stop_attract(self) -> None:
        self.attract = None
        self.bots = {}
        self.t = 0

    # --- transitions -------------------------------------------------------------------------

    def _set_state(self, state: str) -> None:
        self.state = state
        self.t = 0

    def _to_title(self) -> None:
        self.fight = None
        self.lesson = None
        self.paused = False
        self.card = False
        self.title_index = 0
        self._stop_attract()
        self._set_state(TITLE)

    def _start_match(self, events: list) -> None:
        self.wins = {p: 0 for p in PLAYERS}
        self.winner = None
        self.round_no = 1
        self.hint = True            # a match's first round intro teaches the rule
        self._start_round(events)

    def _start_round(self, events: list) -> None:
        self.fight = Fight({p: ROSTER[self.picks[p]] for p in PLAYERS})
        self.round_winner = None
        self.perfect = False
        self.ko = False
        self._set_state(ROUND_INTRO)
        events.append(Cue("round"))

    @property
    def shown_fight(self) -> Fight | None:
        """The fight on screen: the match's own, or the title's demo."""
        return self.fight if self.fight is not None else self.attract
