"""Training Day script (placeholder until the tutorial milestone)."""

from __future__ import annotations


class Tutorial:
    wants_start = False
    show_hints = True

    def __init__(self, scene) -> None:
        self.scene = scene
        scene.world.orders.auto_spawn = True

    def filter_inputs(self, inputs, inp):
        return inputs

    def on_event(self, ev) -> None:
        pass

    def update(self, dt, inp) -> None:
        pass

    def draw(self, surf, t) -> None:
        pass
