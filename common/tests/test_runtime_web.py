from arqade_common import runtime, web


def test_frame_time_is_clamped_only_in_the_browser(monkeypatch):
    assert runtime.frame_seconds(2.0) == 2.0
    monkeypatch.setattr(runtime.sys, "platform", "emscripten")
    assert runtime.frame_seconds(2.0) == runtime.MAX_BROWSER_FRAME_SECONDS
    assert runtime.frame_seconds(0.016) == 0.016


def test_post_event_does_nothing_outside_the_browser():
    web.post_event(web.GAME_START, "quantum-pong")  # must not raise or import pygbag's platform
