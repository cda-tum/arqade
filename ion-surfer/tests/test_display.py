from ion_surfer.display import compute_scaled_rect


def test_scaled_rect_matches_window_when_aspect_ratio_equal():
    rect = compute_scaled_rect((480, 270), (960, 540))
    assert (rect.width, rect.height) == (960, 540)
    assert (rect.x, rect.y) == (0, 0)


def test_scaled_rect_letterboxes_top_and_bottom_on_wider_window():
    # Window is wider than 16:9 (e.g. an ultrawide-ish display) -> bars top/bottom.
    rect = compute_scaled_rect((480, 270), (1200, 540))
    assert (rect.width, rect.height) == (960, 540)
    assert rect.x == 120  # (1200 - 960) / 2
    assert rect.y == 0


def test_scaled_rect_letterboxes_left_and_right_on_taller_window():
    # Window is taller/narrower than 16:9 (e.g. a 4:3 cabinet monitor) -> bars left/right.
    rect = compute_scaled_rect((480, 270), (640, 480))
    assert (rect.width, rect.height) == (640, 360)
    assert rect.x == 0
    assert rect.y == 60  # (480 - 360) / 2
