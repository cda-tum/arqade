"""Dev tool: render every screen headless to PNGs for visual review.

    uv run python tools/snapshot.py OUT_DIR [--scale 3]

Not deployed (lives outside src/). Drives the real scenes with scripted
state, so what you see is what the cabinet draws, upscaled by an integer
factor like the cabinet's SCALED fullscreen does.
"""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from overquqed import game, levels  # noqa: E402
from overquqed.quantum import QState, cnot_merge  # noqa: E402
from overquqed.stations import Item  # noqa: E402


def save(app, out: Path, name: str, scale: int) -> None:
    app.scene.draw(app.surface)
    img = pygame.transform.scale(app.surface, (app.surface.get_width() * scale, app.surface.get_height() * scale))
    pygame.image.save(img, str(out / f"{name}.png"))
    print("wrote", name)


def run(app, seconds: float) -> None:
    for _ in range(int(seconds * 60)):
        app.step(1 / 60, [])


def stock_kitchen(rs) -> None:
    """Put a representative spread of items around a round's kitchen."""
    w = rs.world
    rng = random.Random(4)
    for _ in range(3):
        w.orders.spawn(w.t, None)
    counters = [s for s in w.stations.values() if s.kind == "counter" and s.item is None]
    rng.shuffle(counters)

    def item(ops, age=0.0):
        s = QState.fresh(w.t - age)
        for op in ops:
            s.apply(op)
        it = Item(s)
        w.refresh(it)
        return it

    samples = [item([]), item(["X"]), item(["H"]), item(["X", "H"]), item(["H"], age=14), item(["X"], age=40)]
    plus = QState.fresh(w.t)
    plus.apply("H")
    bell = Item(cnot_merge(plus, QState.fresh(w.t)))
    bell.link_flash = w.t
    w.refresh(bell)
    samples.append(bell)
    for st, it in zip(counters, samples):
        st.item = it
    w.chefs[0].held = item(["H"])
    for st in w.stations.values():
        if st.kind == "h":
            st.item = item(["X"])
            st.progress = 0.5
            break


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "snapshots")
    scale = int(sys.argv[sys.argv.index("--scale") + 1]) if "--scale" in sys.argv else 3
    out.mkdir(parents=True, exist_ok=True)
    pygame.init()
    surface = pygame.display.set_mode((480, 360))
    app = game.App(surface, None, False)

    run(app, 0.6)
    save(app, out, "01_title", scale)

    from overquqed.scenes import JoinScene, LevelSelectScene, ResultsScene
    from overquqed.round_scene import RoundScene

    app.switch(JoinScene(app, 0))
    run(app, 0.5)
    save(app, out, "02_join", scale)
    app.switch(LevelSelectScene(app, [0, 1]))
    run(app, 0.3)
    save(app, out, "03_select", scale)

    for i, lv in enumerate(levels.LEVELS):
        rs = RoundScene(app, lv, [0, 1], seed=7)
        app.switch(rs)
        run(app, 0.2)
        stock_kitchen(rs)
        run(app, 4.5)
        save(app, out, f"1{i}_{lv.key}", scale)

    rs = RoundScene(app, levels.COSMIC_CAFE, [0], seed=3)
    app.switch(rs)
    rs.world.cosmic.next_at = 0.5
    run(app, 1.0)
    save(app, out, "20_cosmic_warning", scale)

    rs = RoundScene(app, levels.SNACK_BAR, [0, 1], seed=5)
    app.switch(rs)
    rs.world.orders.spawn(0.0, "1", "dj")
    rs.world.chefs[0].held = Item(QState.fresh())
    rs.world.chefs[0].held.state.apply("X")
    rs.world.refresh(rs.world.chefs[0].held)
    pas = rs.world.stations_of("pass")[0]
    c = rs.world.chefs[0]
    c.x, c.y, c.facing = (pas.x + 0.5) * 24, (pas.y - 0.5) * 24, (0, 1)
    rs.world._pick(c)
    for ev in rs.world.events:
        rs._on_event(ev)
    rs.world.events.clear()
    run(app, 0.8)
    save(app, out, "21_served_receipt", scale)
    rs.paused = True
    save(app, out, "22_pause", scale)
    rs.paused = False
    app.switch(ResultsScene(app, rs))
    run(app, 2.0)
    save(app, out, "30_results", scale)


if __name__ == "__main__":
    main()
