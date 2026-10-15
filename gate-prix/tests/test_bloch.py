"""The qubit on show: which states the race's gates reach, and their pictures."""

import pygame

from gate_prix import bloch, circuit, config, sprites


def test_the_gates_reach_exactly_the_four_named_states_and_each_lands_on_its_axis():
    seen, frontier = set(), [()]
    for _ in range(6):  # every circuit of up to 6 gates
        frontier = [c + (g,) for c in frontier for g in circuit.GATES]
        for c in frontier:
            v = circuit.bloch(circuit.run(list(c)))
            name = bloch.state_of(c)
            axis = bloch.STATES[name][0]
            assert all(abs(a - b) < 1e-9 for a, b in zip(v, axis)), (c, v)
            seen.add(name)
    assert seen == set(bloch.NAMES) == {"+z", "-z", "+x", "-x"}


def test_a_cars_state_follows_its_slots_so_far():
    assert bloch.state_of(()) == "+z"
    assert bloch.state_of((None,) * config.SLOTS) == "+z"  # empty slots do nothing
    assert bloch.state_of(("X",)) == "-z"
    assert bloch.state_of(("H",)) == "+x"
    assert bloch.state_of(("H", "Z")) == "-x"
    assert bloch.state_of(("H", None, "Z", "H")) == "-z"


def test_the_states_colours_are_apart_and_never_a_players():
    cols = [col for _, _, col in bloch.STATES.values()]
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            assert sum(abs(x - y) for x, y in zip(a, b)) > 120
        for p in config.PLAYER_COLORS.values():
            assert sum(abs(x - y) for x, y in zip(a, p)) > 120


def test_every_state_has_an_orb_on_the_cars_engine_cover():
    pygame.font.init()
    for name in bloch.NAMES:
        img, ax, ay = sprites.render_sprite(f"orb:{name}", 800.0)
        # its centre is ORB_Y above the car's foot, and it is about the orb's size
        assert abs((ay - img.get_height() / 2) - sprites.ORB_Y * 800) <= 2
        assert 2 * sprites.ORB_R * 800 <= img.get_width() <= 2 * (sprites.ORB_GLOW + 0.005) * 800 + 4
    # the arrows differ: four different pictures
    pics = {pygame.image.tobytes(sprites.render_sprite(f"orb:{n}", 800.0)[0], "RGBA")
            for n in bloch.NAMES}
    assert len(pics) == len(bloch.NAMES)


def test_the_sphere_points_its_arrow_where_the_state_is():
    pygame.font.init()
    for name in bloch.NAMES:
        img = bloch.sphere(name, 90)
        dx, dy = bloch.project(bloch.STATES[name][0], 90 * 0.36 * 0.92)
        tip = (round(45 + dx), round(45 + dy))
        r, g, b, a = img.get_at(tip)
        assert a > 200 and r + g + b > 560, (name, tip)  # the bright tip
        near = [sum(img.get_at((45 + i, 45 + j))[:3]) for i in (-1, 0, 1) for j in (-1, 0, 1)]
        assert max(near) > 560  # the arrow starts at the centre
