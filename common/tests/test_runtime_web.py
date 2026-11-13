from arqade_common import runtime, web


def test_frame_time_is_clamped_only_in_the_browser(monkeypatch):
    assert runtime.frame_seconds(2.0) == 2.0
    monkeypatch.setattr(runtime.sys, "platform", "emscripten")
    assert runtime.frame_seconds(2.0) == runtime.MAX_BROWSER_FRAME_SECONDS
    assert runtime.frame_seconds(0.016) == 0.016


def test_post_event_does_nothing_outside_the_browser():
    web.post_event(web.GAME_START, "quantum-pong")  # must not raise or import pygbag's platform


def test_post_score_does_nothing_outside_the_browser(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def no_platform(name, *args, **kwargs):
        if name == "platform":
            raise AssertionError("post_score imported platform outside the browser")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_platform)
    assert web.post_score("gate-drop", "default", 1234, "ABC") is None


def test_post_score_never_raises_in_the_browser_without_a_page(monkeypatch):
    monkeypatch.setattr(web, "is_browser", lambda: True)
    web.post_score("gate-drop", "default", 1234, "ABC")  # no platform.window here


def test_post_score_sends_only_initials_the_site_accepts(monkeypatch):
    sent = []
    monkeypatch.setattr(web, "is_browser", lambda: True)
    monkeypatch.setattr(web, "_post", sent.append)
    web.post_score("overquqed", "snackbar", 12.0, "a-*")
    web.post_score("overquqed", "snackbar", 12, "-*-")  # nothing left: not sent
    assert sent == [{"type": web.SCORE, "id": "overquqed", "mode": "snackbar", "score": 12, "initials": "A"}]
