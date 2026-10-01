import pygame

from superconductor import config

CABINET_P1_LETTERS = {"l", "x", "r", "b", "y", "a"}


def test_p1_dev_keys_avoid_the_letters_the_cabinet_encoder_types():
    for names in config.KEYS["p1"].values():
        for name in names:
            assert pygame.key.name(getattr(pygame, name)) not in CABINET_P1_LETTERS


def test_pad_buttons_are_distinct():
    for p in ("p1", "p2"):
        used = [b for idxs in config.INPUT_CONFIG[p]["buttons"].values() for b in idxs]
        assert len(used) == len(set(used))
