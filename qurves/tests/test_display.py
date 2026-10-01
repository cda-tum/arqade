from qurves.display import compute_scaled_rect


def test_scaled_rect_matches_window_when_aspect_ratio_equal():
    rect = compute_scaled_rect((960, 540), (1920, 1080))
    assert (rect.width, rect.height) == (1920, 1080)
    assert (rect.x, rect.y) == (0, 0)


def test_scaled_rect_letterboxes_top_and_bottom_on_wider_window():
    rect = compute_scaled_rect((960, 540), (2400, 1080))
    assert (rect.width, rect.height) == (1920, 1080)
    assert (rect.x, rect.y) == (240, 0)


def test_scaled_rect_letterboxes_left_and_right_on_taller_window():
    rect = compute_scaled_rect((960, 540), (1280, 960))
    assert (rect.width, rect.height) == (1280, 720)
    assert (rect.x, rect.y) == (0, 120)
