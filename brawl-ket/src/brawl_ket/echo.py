"""Bob, ALICE & BOB's second body: an echo of Alice's inputs. Pure logic, no pygame.

The fight (fight.py) gives a player whose character has a `pair` a second Fighter, an Echo, beside
the first one (Alice, whom the player or the bot controls). Every frame Alice's input goes into
the echo's queue and the one from ECHO_DELAY frames ago comes out for Bob, so he does what she
did a beat later, with his own hurtbox and his own hitboxes. What the two share is the pair's:
one health bar and one basis (both always the same colour), both kept on Alice and read and
written through her, so a hit on either costs the bar and anything that switches or collapses
one switches or collapses both.

Bob faces as Alice does and stands ECHO_GAP px behind her: his echo of her walk carries him
along, he never walks past that spot towards her, and once he has nothing left to echo he
walks back to it by himself. He has no push box (the fight pushes only Alice). A knockdown
decoheres him (decohere, called by the fight): he fades out and is gone for DECOHERE_FRAMES,
then comes back on his spot.
"""

from __future__ import annotations

from collections import deque
from dataclasses import replace

from .config import (
    DECOHERE_FRAMES,
    ECHO_DELAY,
    ECHO_GAP,
    ECHO_SLACK,
    REFORM_FRAMES,
    STAGE_LEFT,
    STAGE_RIGHT,
    SWITCH_RECOVERY,
)
from .fighter import IDLE, Fighter, FighterInput
from .moves import Character


class Echo(Fighter):
    def __init__(self, char: Character, lead: Fighter) -> None:
        self.lead = lead                # first: his health and basis are hers (the properties below)
        super().__init__(char, lead.x - lead.facing * ECHO_GAP, lead.facing)
        self.x = self.spot
        self.queue: deque[FighterInput] = deque([IDLE] * ECHO_DELAY)
        self.decohered = 0              # frames since he decohered (0: he is here)
        self.reform = 0                 # frames left of his re-forming, once back (drawn only)
        self.lock_pending = False       # Alice's Y replayed in a hitstop freeze: its lock, next step

    # --- what the pair shares ---------------------------------------------------------------

    @property
    def health(self) -> int:
        return self.lead.health

    @health.setter
    def health(self, value: int) -> None:
        self.lead.health = value

    @property
    def basis(self) -> str:
        return self.lead.basis

    @basis.setter
    def basis(self, value: str) -> None:
        self.lead.basis = value

    # --- where he is --------------------------------------------------------------------------

    @property
    def here(self) -> bool:
        """On the stage: not decohered."""
        return self.decohered == 0

    @property
    def spot(self) -> float:
        """Where he stands: ECHO_GAP px behind Alice, on the stage."""
        return min(max(self.lead.x - self.lead.facing * ECHO_GAP, STAGE_LEFT), STAGE_RIGHT)

    # --- the frame ------------------------------------------------------------------------------

    def replay(self, inp: FighterInput) -> FighterInput:
        """Alice's input this frame goes in; hers from ECHO_DELAY frames ago comes out. The fight
        calls it every frame, hitstop freezes included, so the delay is in the fight's frames."""
        self.queue.append(inp)
        return self.queue.popleft()

    def step(self, inp: FighterInput, rival_x: float) -> list[tuple[str, dict]]:
        """One frame of Bob on Alice's delayed input. Her Y switched the pair already: Bob only
        gets the switch's lock, as she did. Decohered, he only counts the frames until he is back."""
        events: list[tuple[str, dict]] = []
        if not self.here:
            self.decohered += 1
            if self.decohered >= DECOHERE_FRAMES:
                self._come_back()
                events.append(("recohere", {}))
            return events
        if self.reform > 0:
            self.reform -= 1
        if inp.y or self.lock_pending:
            self.lock_pending = False
            self.switch_lock = SWITCH_RECOVERY + 1      # the step counts it down once at its start
            inp = replace(inp, y=False)
        inp = self._walk_back(inp)
        before = self.x
        events += super().step(inp, rival_x)
        self._keep_behind(before)
        return events

    def hold_switch(self, inp: FighterInput) -> None:
        """A Y replayed in a hitstop freeze: the lock comes on the next step (never a switch)."""
        if inp.y:
            self.lock_pending = True

    def _face(self, rival_x: float) -> None:
        self.facing = self.lead.facing      # Bob's facing follows hers

    def _walk_back(self, inp: FighterInput) -> FighterInput:
        """With nothing to echo (a still stick and no button, now and in everything still queued),
        on his feet and free, he walks back to his spot once he is more than ECHO_SLACK px off it."""
        if inp != IDLE or any(q != IDLE for q in self.queue) or self.action not in ("idle", "walk") \
                or self.y > 0:
            return inp
        off = self.spot - self.x
        if off == 0 or (abs(off) <= ECHO_SLACK and self.action != "walk"):    # a walk back goes all the way
            return inp
        return FighterInput(dx=1 if off > 0 else -1)

    def _keep_behind(self, before: float) -> None:
        """Walking, he never passes his spot towards Alice (her echoed walk would carry him into
        her when she is held up, by the rival or a wall), and a walk back stops on it."""
        if self.action != "walk" or self.y > 0:
            return
        f, spot = self.lead.facing, self.spot
        moved, ahead, was = (self.x - before) * f, (self.x - spot) * f, (before - spot) * f
        if moved > 0 and ahead > 0:
            self.x = spot if was <= 0 else before
        elif moved < 0 and was > 0 and ahead < 0:
            self.x = spot

    # --- decoherence ---------------------------------------------------------------------------

    def decohere(self) -> None:
        """Knocked down: he decoheres where he stands, out of the fight until he comes back."""
        self.decohered = 1
        self.move = None
        self.slot = None
        self.chained = False
        self.move_hit = False
        self.bounced = False
        self.buffer = []
        self.crouching = False
        self.stun = 0
        self.vx = self.vy = 0.0
        self.y = 0.0
        self.action = "decohered"
        self.frame = 0

    def _come_back(self) -> None:
        """Back on his spot behind Alice, facing as she does, with nothing of hers still to replay."""
        self.decohered = 0
        self.reform = REFORM_FRAMES
        self.queue = deque([IDLE] * ECHO_DELAY)
        self.x, self.y, self.vx, self.vy = self.spot, 0.0, 0.0, 0.0
        self.facing = self.lead.facing
        self.action = "idle"
        self.frame = 0
        self.wakeup = self.switch_lock = 0
        self.air_used.clear()
