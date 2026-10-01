import random

from qurves.fx import Fx


def test_burst_particles_fade_out():
    fx = Fx(random.Random(0))
    fx.burst((10, 10), (255, 0, 0), count=20, life=0.5)
    assert len(fx.particles) == 20
    for _ in range(40):
        fx.update(1 / 60)
    assert fx.particles == []


def test_shake_decays_to_nothing():
    fx = Fx(random.Random(0))
    fx.kick(5)
    fx.update(1.0)
    assert fx.shake == 0 and fx.offset() == (0, 0)


def test_a_dissolve_caps_its_particle_count():
    fx = Fx(random.Random(0))
    fx.dissolve([(i, 0) for i in range(500)], (0, 255, 0))
    assert 0 < len(fx.particles) <= 48


def test_rings_expire():
    fx = Fx(random.Random(0))
    fx.ring((5, 5), (255, 255, 255), life=0.2)
    fx.update(0.3)
    assert fx.rings == []
