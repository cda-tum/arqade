"""All the microgames and bosses. Every module in this package is imported
here, so a new one only needs its own file with a @register (or
@register_boss) class: nothing else has to be edited."""

import importlib
import pkgutil

from planck_time.microgames.base import (
    BOSSES,
    REGISTRY,
    Boss,
    Microgame,
    PlayerInput,
    play_time,
    register,
    register_boss,
)

for _module in pkgutil.iter_modules(__path__):
    if _module.name != "base":
        importlib.import_module(f"{__name__}.{_module.name}")

__all__ = ["BOSSES", "REGISTRY", "Boss", "Microgame", "PlayerInput", "play_time", "register", "register_boss"]
