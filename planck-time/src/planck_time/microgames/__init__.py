"""All the microgames. Every module in this package is imported here, so a
new microgame only needs its own file with a @register class: nothing else
has to be edited."""

import importlib
import pkgutil

from planck_time.microgames.base import REGISTRY, Microgame, PlayerInput, play_time, register

for _module in pkgutil.iter_modules(__path__):
    if _module.name != "base":
        importlib.import_module(f"{__name__}.{_module.name}")

__all__ = ["REGISTRY", "Microgame", "PlayerInput", "play_time", "register"]
