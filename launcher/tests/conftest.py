import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402
import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def no_video(monkeypatch):
    """No ffmpeg in the tests: the menu behaves as without imageio-ffmpeg.
    Tests of the attract mode put a stand-in player back."""
    from arqade_launcher import video

    monkeypatch.setattr(video, "available", lambda path: False)


@pytest.fixture(autouse=True)
def pygame_display():
    pygame.display.init()
    pygame.font.init()
    yield
    pygame.display.quit()
