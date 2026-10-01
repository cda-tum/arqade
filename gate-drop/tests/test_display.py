from gate_drop.display import compute_scaled_rect


def test_scaled_rect_matches_window_when_aspect_ratio_equal():
    rect = compute_scaled_rect((480, 270), (1920, 1080))
    assert (rect.width, rect.height, rect.x, rect.y) == (1920, 1080, 0, 0)


def test_scaled_rect_letterboxes_a_taller_window():
    rect = compute_scaled_rect((480, 270), (1280, 960))
    assert (rect.width, rect.height) == (1280, 720)
    assert (rect.x, rect.y) == (0, 120)
