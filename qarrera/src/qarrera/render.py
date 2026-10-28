"""Drawing, in 3D with OpenGL (gfx.py), into a 960x540 frame that is then
scaled onto the window.

Each track becomes a World once: the scene's ground plane (scenes.py), the
track as a slab with its props baked in (mesh.py). Every frame then draws,
from the race's isometric camera (camera.py):

- the ground (the sea drifts), the track and the props;
- each racer as a lit voxel mesh, turned into a corner when it drifts,
  wiggling when bumped, spinning when spun out, tinted red while its spin
  meter fills and cyan after a Zeno trap, blinking just after a reset;
- on the track: soft shadows, a ring in a person's colour under their
  racer, Zeno traps, and the dots ahead of a hovering bug that show where
  it will go;
- standing up (billboards): Gate Drop's error bugs, the gates' glyphs, the
  item boxes, smoke, boost flames and slipstream streaks;
- and the HUD layer (hud.py) over it all, with the marker over the leader.

The racer select draws its racers turning in 3D in the boxes hud.py lays
out, and the HOW TO PLAY card its demo race (tutorial.py) in its box, through
the demo's own, narrower camera.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pygame
from arqade_common.input import LastDevice
from OpenGL import GL

from qarrera import camera, config, gfx, mesh, voxels
from qarrera.art import Atlas
from qarrera.camera import gl
from qarrera.fonts import load_font
from qarrera.gfx import FLAT_ATTRS, FLAT_FS, FLAT_VS, LIT_ATTRS, LIT_FS, LIT_VS, Mesh, Program, Target, Texture
from qarrera.hud import Hud, panel_model_box, select_layout, tutorial_box
from qarrera.match import SELECT, TITLE, TUTORIAL, Match, Pack
from qarrera.racers import ROSTER
from qarrera.scenes import Scene, scene_for
from qarrera.track import Track

W, H = config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT
MODELS = dict(voxels.RACERS)
MODELS.update({f"prop_jelly_{k}": (lambda k=k: voxels.jelly(k)) for k in "XZY"})
MODELS["prop_xmon"] = voxels.xmon
GOLD = (255, 220, 80)
POPUPS = {  # only over people's racers: eight racers' worth would be clutter
    "copy": ("COPY!", (255, 255, 255)),
    "swap": ("SWAP!", config.CNOT_COLOR),
    "bitflip": ("BIT FLIP!", config.GATE_COLORS["X"]),
    "phaseflip": ("PHASE FLIP!", config.GATE_COLORS["Z"]),
    "zeno": ("ZENO!", config.COLOR_ZENO),
    "decohered": ("DECOHERED", config.COLOR_DIM),
    "spin": ("SPUN OUT!", config.COLOR_WARN),
    "reset": ("BACK IN!", config.COLOR_TEXT),
    "lead": ("LEAD!", GOLD),
    "copy_lost": ("COPY LOST", config.COLOR_DIM),
    "boost": ("BOOST!", (255, 168, 40)),
}
STREAK = (0.75, 0.9, 1.0)  # the slipstream's speed streaks
SMOKE = (1.0, 1.0, 1.0)


def rgba(c, a: float = 1.0) -> tuple[float, float, float, float]:
    return (c[0] / 255, c[1] / 255, c[2] / 255, a)


class World:
    """One track in GL: its ground and its track with the props baked in."""

    def __init__(self, track: Track, models: dict) -> None:
        self.track = track
        self.scene: Scene = scene_for(track)
        sc = self.scene
        parts = [mesh.track_mesh(track, sc.palette, sc.ground_z)]
        for key, x, y, z, heading, scale in sc.props:
            parts.append(mesh.place(models[key], x, y, z, heading, config.VOXEL_SIZE * scale))
        self.solid = Mesh(np.concatenate(parts), LIT_ATTRS)
        self.ground = Mesh(mesh.ground_mesh(track, sc.ground_z, sc.ground_color, sc.ground_tile), LIT_ATTRS)
        self.ground_tex = Texture(sc.ground_picture(), repeat=True)


class Renderer:
    def __init__(self, window_size: tuple[int, int], es: bool, devices: LastDevice | None = None) -> None:
        self.window_size = window_size
        self.target = Target(W, H)
        self.lit = Program(es, LIT_VS, LIT_FS)
        self.flat = Program(es, FLAT_VS, FLAT_FS)
        self.atlas = Atlas(load_font(8))
        self.atlas_tex = Texture(self.atlas.surface)
        white = pygame.Surface((1, 1), pygame.SRCALPHA)
        white.fill((255, 255, 255, 255))
        self.white = Texture(white)
        self.models: dict[str, np.ndarray] = {}
        self.meshes: dict[str, Mesh] = {}
        self.worlds: dict[str, World] = {}
        self.decals = Mesh(np.zeros((0, 9), np.float32), FLAT_ATTRS, dynamic=True)
        self.boards = Mesh(np.zeros((0, 9), np.float32), FLAT_ATTRS, dynamic=True)
        self.soft = Mesh(np.zeros((0, 9), np.float32), FLAT_ATTRS, dynamic=True)
        self.beams = Mesh(np.zeros((0, mesh.STRIDE), np.float32), LIT_ATTRS, dynamic=True)
        quad = np.array([[-1, -1, 0, 0, 1, 1, 1, 1, 1], [1, -1, 0, 1, 1, 1, 1, 1, 1], [1, 1, 0, 1, 0, 1, 1, 1, 1],
                         [-1, -1, 0, 0, 1, 1, 1, 1, 1], [1, 1, 0, 1, 0, 1, 1, 1, 1], [-1, 1, 0, 0, 0, 1, 1, 1, 1]],
                        dtype=np.float32)
        self.screen = Mesh(quad, FLAT_ATTRS)
        flipped = quad.copy()
        flipped[:, 4] = 1 - flipped[:, 4]
        self.screen_flipped = Mesh(flipped, FLAT_ATTRS)
        self.hud = Hud(devices)  # devices: what each side last used, for the button hints
        # in RGBA byte order, so the texture upload can take its pixels as they are (gfx.Texture.update)
        self.layer = pygame.Surface((W, H), pygame.SRCALPHA, 32, gfx.RGBA_MASKS)
        self.layer_tex = Texture(self.layer)
        self.popups: list[list] = []  # [x, y, z, text, color, age] in the world
        self.smoke: list[list] = []  # [x, y, z, age, rgb, size]
        self.time = 0.0
        self.rng = random.Random(7)
        self.show_fps: float | None = None
        self._in_tutorial = False
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_CULL_FACE)

    # --- resources ------------------------------------------------------------------------

    def model(self, key: str) -> np.ndarray:
        if key not in self.models:
            self.models[key] = mesh.voxel_mesh(MODELS[key]())
        return self.models[key]

    def racer(self, key: str) -> Mesh:
        if key not in self.meshes:
            self.meshes[key] = Mesh(self.model(key), LIT_ATTRS)
        return self.meshes[key]

    def world(self, track: Track) -> World:
        if track.name not in self.worlds:
            self.worlds[track.name] = World(track, {k: self.model(k) for k in MODELS if k.startswith("prop")})
        return self.worlds[track.name]

    # --- a frame ---------------------------------------------------------------------------

    def draw(self, match: Match, events: list, dt: float) -> None:
        self.time += dt
        self.target.bind()
        if (match.state == TUTORIAL) != self._in_tutorial:  # the demo's popups and smoke stay in the demo
            self._in_tutorial = not self._in_tutorial
            self.popups.clear()
            self.smoke.clear()
        if match.state == SELECT:
            self.popups.clear()
            self.smoke.clear()
            self._select(match)
            self.hud.draw(self.layer, match, [], [], dt)
        elif match.state == TUTORIAL:
            self._tutorial(match, dt)
        else:
            pack = match.demo if match.state == TITLE else match.pack
            if match.state == TITLE:
                self.popups.clear()
            elif not match.paused:
                self._apply(events, pack)
            if not match.paused:
                self._age(dt)
            world = self.world(match.track)
            if pack is not None:
                self._scene(world, pack)
            popups = []
            warnings = []
            mark = None
            if pack is not None and match.state != TITLE:
                cam = pack.camera
                for x, y, z, text, color, age in self.popups:
                    px, py = cam.to_pixels(x, y, z + 14)
                    popups.append((px, py, text, color, age))
                warnings = self._warnings(pack)
                mark = self._lead_mark(pack)
            self.hud.draw(self.layer, match, popups, warnings, dt, mark)
        if self.show_fps is not None:
            img = self.hud.text(f"{self.show_fps:.0f} FPS", self.hud.font8, config.COLOR_FPS)
            self.layer.blit(img, (W - img.get_width() - 6, H - 14))
        self._layer()

    def present(self) -> None:
        """The 960x540 frame onto the window, as large as fits, letterboxed."""
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        ww, wh = self.window_size
        scale = min(ww / W, wh / H)
        w, h = round(W * scale), round(H * scale)
        GL.glViewport(0, 0, ww, wh)
        GL.glClearColor(0, 0, 0, 1)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        GL.glViewport((ww - w) // 2, (wh - h) // 2, w, h)
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_BLEND)
        self.flat.use()
        self.flat.mat4("u_vp", [1.0 if i % 5 == 0 else 0.0 for i in range(16)])
        self.flat.vec("u_cut", -1.0)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.target.tex)
        self.flat.int("u_tex", 0)
        self.screen_flipped.draw()
        # Unbound again: drawing into the target while its own texture is bound
        # is an error in WebGL ("feedback loop"), even where nothing samples it.
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        GL.glEnable(GL.GL_DEPTH_TEST)

    def snapshot(self) -> pygame.Surface:
        return self.target.read()

    # --- the 3D scene ---------------------------------------------------------------------

    def _lights(self, sc: Scene, vp, eye, fog: bool = True) -> None:
        p = self.lit
        p.use()
        p.mat4("u_vp", vp)
        n = math.sqrt(sum(v * v for v in sc.light))
        p.vec("u_light", *(v / n for v in sc.light))
        p.vec("u_sun", *sc.sun)
        p.vec("u_ambient", *sc.ambient)
        p.vec("u_fog", *(c / 255 for c in sc.fog))
        p.vec("u_eye", *eye)
        p.vec("u_fog_range", *(sc.fog_range if fog else (1e6, 2e6)))
        p.vec("u_tint", 0, 0, 0, 0)
        p.vec("u_scroll", 0, 0)
        p.int("u_textured", 0)
        p.int("u_tex", 0)

    def _scene(self, world: World, pack: Pack) -> None:
        sc = world.scene
        cam = pack.camera
        GL.glClearColor(*(c / 255 for c in sc.clear), 1)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDepthMask(GL.GL_TRUE)
        GL.glDisable(GL.GL_BLEND)
        self._lights(sc, cam.vp, cam.eye)
        identity = [1.0 if i % 5 == 0 else 0.0 for i in range(16)]
        self.lit.mat4("u_model", identity)
        world.ground_tex.bind(0)
        self.lit.int("u_textured", 1)
        self.lit.vec("u_scroll", sc.scroll[0] * self.time, sc.scroll[1] * self.time)
        world.ground.draw()
        self.lit.int("u_textured", 0)
        self.lit.vec("u_scroll", 0, 0)
        world.solid.draw()
        race = pack.race
        self._gate_beams(race)
        self.lit.mat4("u_model", identity)
        self.beams.draw()
        for b in race.bodies:
            if b.ghost > 0 and int(b.ghost * 12) % 2:
                continue  # just put back in: it blinks while it passes through everything
            self._body(race, b)
        self.lit.vec("u_tint", 0, 0, 0, 0)
        self._flat_pass(race, cam)

    def _body(self, race, b) -> None:
        key = race.racer_keys.get(b.player, "colorcode")
        x, y, h = race.pose(b)
        nx, ny = -math.sin(h), math.cos(h)
        if b.load > config.DRIFT_LOAD:
            side = 1.0 if b.curve > 0 else -1.0
            over = b.load - config.DRIFT_LOAD
            h += side * min(0.6, over * 1.2)  # the nose turns into the corner
            slide = -side * min(4.0, over * 8)  # and it slides out of it
            x, y = x + nx * slide, y + ny * slide
            if self.rng.random() < 0.5:
                self.smoke.append([x - math.cos(h) * 12, y - math.sin(h) * 12, b.z + 2, 0.0, SMOKE, 1.0])
        if b.wiggle > 0:
            w = math.sin(self.time * 50) * 3 * b.wiggle / config.WIGGLE_TIME
            x, y = x + nx * w, y + ny * w
        if b.spin > 0:
            h += b.spin * 18
        tint = (0, 0, 0, 0)
        if b.measured > 0:
            tint = (0.35, 0.92, 0.92, 0.55 * b.measured / config.ZENO_GLOW)
        elif b.load > config.WARN_LOAD or b.slip > 0.05:
            tint = (1.0, 0.1, 0.1, 0.25 + 0.35 * (int(self.time * 12) % 2))
        self.lit.vec("u_tint", *tint)
        roll = 0.0
        if key in voxels.RIDERS:  # on the wire itself: it leans into the corner, and sways
            lean = min(config.RIDER_LEAN_MAX, config.RIDER_LEAN * b.load)
            roll = math.copysign(lean, b.curve) + config.RIDER_SWAY * math.sin(
                self.time * config.RIDER_SWAY_RATE + b.id * 1.7)
        self.lit.mat4("u_model", camera.model_matrix(x, y, b.z, h, config.VOXEL_SIZE, roll))
        self.racer(key).draw()
        if b.boost > 0 and self.rng.random() < 0.8:
            self.smoke.append([x - math.cos(h) * 14, y - math.sin(h) * 14, b.z + 4, 0.25, SMOKE, 1.0])
        if b.draft > 0.5 and self.rng.random() < 0.6 * b.draft:  # slipstream (and DRS): streaks off its sides
            side = self.rng.choice((-1, 1)) * 7
            self.smoke.append([x + nx * side - math.cos(h) * 6, y + ny * side - math.sin(h) * 6, b.z + 5, 0.15,
                               STREAK, 0.4])

    def _gate_beams(self, race) -> None:
        """A glowing bar between a SWAP's or CNOT's two wires, hovering. All
        gates' bars in one mesh.quads: each numpy call has its overhead."""
        corners = []
        for g in race.gates:
            if self._hidden(g.age, g.life):
                continue
            grow = min(1.0, g.age / config.ITEM_POP)
            (x0, y0, _), (x1, y1, _) = (race.track.pose(lane, g.s) for lane in g.lanes)
            z = race.track.height(g.s) + 9 * grow
            dx, dy = x1 - x0, y1 - y0
            n = math.hypot(dx, dy) or 1
            tx, ty = -dy / n * 1.2, dx / n * 1.2
            a, b = gl(x0 + tx, y0 + ty, z), gl(x1 + tx, y1 + ty, z)
            c, d = gl(x1 - tx, y1 - ty, z), gl(x0 - tx, y0 - ty, z)
            corners.append((a, b, c, d))
        if corners:
            q = np.asarray(corners, dtype=np.float32)
            self.beams.set(mesh.quads(q[:, 0], q[:, 1], q[:, 2], q[:, 3], (0, 0, 1), mesh.rgb(config.CNOT_COLOR),
                                      glow=0.7))
        else:
            self.beams.set(np.zeros((0, mesh.STRIDE), np.float32))

    def _hidden(self, age: float, life: float) -> bool:
        """A gate in its last GATE_FADE seconds blinks."""
        left = life - age
        return left < config.GATE_FADE and int(self.time * (6 if left > 0.6 else 12)) % 2 == 1

    # --- things on the track and standing on it ---------------------------------------------

    def _flat_pass(self, race, cam) -> None:
        track = race.track
        right = (cam.view[0], cam.view[1], cam.view[2])
        up = (cam.view[4], cam.view[5], cam.view[6])
        decals, boards, soft = [], [], []

        def decal(x, y, z, r, name, color):
            u0, v0, u1, v1 = self.atlas.uv[name]
            gx, gy, gz = gl(x, y, z + 0.4)
            pts = ((gx - r, gy - r, u0, v1), (gx + r, gy - r, u1, v1), (gx + r, gy + r, u1, v0),
                   (gx - r, gy + r, u0, v0))
            for i in (0, 1, 2, 0, 2, 3):
                px, py, u, v = pts[i]
                decals.append((px, py, gz, u, v, *color))

        def board(x, y, z, w, h, name, color, out):
            u0, v0, u1, v1 = self.atlas.uv[name]
            cx, cy, cz = gl(x, y, z)
            corners = []
            for su, sv, u, v in ((-0.5, 0, u0, v1), (0.5, 0, u1, v1), (0.5, 1, u1, v0), (-0.5, 1, u0, v0)):
                corners.append((cx + right[0] * su * w + up[0] * sv * h, cy + right[1] * su * w + up[1] * sv * h,
                                cz + right[2] * su * w + up[2] * sv * h, u, v))
            for i in (0, 1, 2, 0, 2, 3):
                out.append((*corners[i][:3], corners[i][3], corners[i][4], *color))

        for b in race.bodies:
            x, y, _ = race.pose(b)
            ground = track.height(race.s_of(b.p))
            r = 12 * (1 - min(0.5, (b.z - ground) / 80))
            decal(x, y, ground, r, "shadow", (1, 1, 1, 0.7))
            if b.player in race.humans:
                decal(x, y, ground, 15, "ring", rgba(config.color_of(b.player), 0.95))
        for g in race.gates:
            if self._hidden(g.age, g.life):
                continue
            grow = min(1.0, g.age / config.ITEM_POP)
            bob = 1.2 * math.sin(self.time * 3 + g.id)
            for lane in g.lanes:
                x, y, _ = track.pose(lane, g.s)
                z = track.height(g.s)
                decal(x, y, z, 5, "shadow", (1, 1, 1, 0.5))
                name = "swap" if g.kind == "SWAP" else ("control" if lane == g.lanes[0] else "target")
                board(x, y, z + 6 + bob, 11 * grow, 11 * grow, name, (1, 1, 1, 1), boards)
        for it in race.items:
            x, y, _ = track.pose(it.lane, it.s)
            z = track.height(it.s)
            grow = min(1.0, it.age / config.ITEM_POP)
            decal(x, y, z, 6, "shadow", (1, 1, 1, 0.5))
            turn = abs(math.cos(self.time * 2.5 + it.id)) * 0.7 + 0.3  # a box turning round
            name = "item_err" if it.kind == "ERR" else "item_zeno"
            board(x, y, z + 5 + 2 * math.sin(self.time * 4 + it.id), 13 * grow * turn, 13 * grow, name,
                  (1, 1, 1, 1), boards)
        for bug in race.bugs:
            x, y = race.lane_point(bug.u, bug.p)
            z = track.height(race.s_of(bug.p))
            decal(x, y, z, 6, "shadow", (1, 1, 1, 0.5))
            lift = 0.0
            if bug.hold > 0:  # hovering in front of its racer: dots down the wire it will take
                lift = 6 + 2 * math.sin(self.time * 10)
                color = rgba(config.GATE_COLORS[bug.kind], 0.9)
                for k in range(1, 6):
                    ax, ay = race.lane_point(bug.u, bug.p + k * 22)
                    decal(ax, ay, track.height(race.s_of(bug.p + k * 22)), 2.5, "ring", color)
            board(x, y, z + lift, 15, 15, f"bug_{bug.kind}_{int(self.time * 8) % 2}", (1, 1, 1, 1), boards)
        for t in race.traps:
            if t.arm > 0 and int(self.time * 10) % 2:
                continue
            x, y = race.lane_point(t.lane, t.p)
            z = track.height(race.s_of(t.p))
            decal(x, y, z, 9 + (0 if t.arm > 0 else 1.5 * math.sin(self.time * 6)), "ring", rgba(config.COLOR_ZENO, 0.9))
            board(x, y, z + 2, 9, 9, "item_zeno", (1, 1, 1, 1), boards)
        for x, y, z, age, color, size in self.smoke:
            k = min(1.0, age / 0.5)
            w = (6 + 10 * k) * size
            board(x, y, z + k * 6 * size, w, w, "smoke", (*color, 0.6 * (1 - k)), soft)

        self.flat.use()
        self.flat.mat4("u_vp", cam.vp)
        self.atlas_tex.bind(0)
        self.flat.int("u_tex", 0)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glDepthMask(GL.GL_FALSE)
        self.flat.vec("u_cut", 0.01)
        self.decals.set(np.asarray(decals, np.float32).reshape(-1, 9))
        self.decals.draw()
        GL.glDepthMask(GL.GL_TRUE)
        self.flat.vec("u_cut", 0.5)
        self.boards.set(np.asarray(boards, np.float32).reshape(-1, 9))
        self.boards.draw()
        GL.glDepthMask(GL.GL_FALSE)
        self.flat.vec("u_cut", 0.01)
        self.soft.set(np.asarray(soft, np.float32).reshape(-1, 9))
        self.soft.draw()
        GL.glDepthMask(GL.GL_TRUE)
        GL.glDisable(GL.GL_BLEND)

    # --- the racer select ----------------------------------------------------------------------

    def _select(self, match: Match) -> None:
        GL.glClearColor(8 / 255, 9 / 255, 22 / 255, 1)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        tiles, panels = select_layout(len(match.people))
        sc = scene_for(match.track)
        boxes = [(rect, racer.key, 1.0) for rect, racer in zip(tiles, ROSTER)]
        for p, rect in zip(match.people, panels):
            boxes.append((panel_model_box(rect), ROSTER[match.picks.get(p, 0)].key, 1.0))
        GL.glEnable(GL.GL_SCISSOR_TEST)
        for rect, key, _ in boxes:
            x, y, w, h = rect.x, H - rect.bottom, rect.w, rect.h
            GL.glViewport(x, y, w, h)
            GL.glScissor(x, y, w, h)
            GL.glClear(GL.GL_DEPTH_BUFFER_BIT)
            eye = (34.0, -34.0, 30.0)
            proj = camera.perspective(30.0, w / h, 1.0, 400.0)
            vp = camera.mul(proj, camera.look_at(eye, (0.0, 0.0, 6.0)))
            self._lights(sc, vp, eye, fog=False)
            self.lit.mat4("u_model", camera.model_matrix(0, 0, 0, self.time * 1.2, 1.0))
            self.racer(key).draw()
        GL.glDisable(GL.GL_SCISSOR_TEST)
        GL.glViewport(0, 0, W, H)

    # --- the HOW TO PLAY card ---------------------------------------------------------------------

    def _tutorial(self, match: Match, dt: float) -> None:
        """The card's demo race in its box, in 3D like the race itself, and
        the card over it."""
        GL.glClearColor(*(c / 255 for c in config.COLOR_PANEL), 1)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        demo = match.tutorial
        popups, mark = [], None
        if demo is not None:
            box = tutorial_box()
            self._apply(demo.events, demo.pack)
            self._age(dt)
            GL.glEnable(GL.GL_SCISSOR_TEST)
            GL.glViewport(box.x, H - box.bottom, box.w, box.h)
            GL.glScissor(box.x, H - box.bottom, box.w, box.h)
            self._scene(self.world(match.track), demo.pack)
            GL.glDisable(GL.GL_SCISSOR_TEST)
            GL.glViewport(0, 0, W, H)
            cam = demo.pack.camera
            for x, y, z, text, color, age in self.popups:
                px, py = cam.to_pixels(x, y, z + 14, box.size)
                popups.append((box.x + px, box.y + py, text, color, age))
            mark = self._lead_mark(demo.pack, box)
        self.hud.draw(self.layer, match, popups, [], dt, mark)

    # --- the 2D layer -----------------------------------------------------------------------------

    def _layer(self) -> None:
        self.layer_tex.update(self.layer)
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        self.flat.use()
        self.flat.mat4("u_vp", [1.0 if i % 5 == 0 else 0.0 for i in range(16)])
        self.flat.vec("u_cut", 0.0)
        self.layer_tex.bind(0)
        self.flat.int("u_tex", 0)
        self.screen.draw()
        GL.glDisable(GL.GL_BLEND)
        GL.glEnable(GL.GL_DEPTH_TEST)

    # --- popups, smoke, warnings ---------------------------------------------------------------

    def _apply(self, events: list, pack: Pack | None) -> None:
        if pack is None:
            return
        people = pack.race.humans or pack.race.players  # the title's demo has nobody: show them all
        for e in events:
            if e.kind not in POPUPS or e.player not in people:
                continue
            text, color = POPUPS[e.kind]
            if any(p[3] == text and p[5] < 0.4 and math.hypot(p[0] - e.x, p[1] - e.y) < 30 for p in self.popups):
                continue  # a racer and its copy through the same gate: say it once
            self.popups.append([e.x, e.y, e.z, text, color, 0.0])

    def _age(self, dt: float) -> None:
        for p in self.popups:
            p[5] += dt
        self.popups = [p for p in self.popups if p[5] < 1.2]
        for s in self.smoke:
            s[3] += dt
        self.smoke = [s for s in self.smoke if s[3] < 0.5]

    def _warnings(self, pack: Pack) -> list:
        """A person's racer close to the screen's edge: where, and who."""
        out = []
        race = pack.race
        for player in race.humans:
            best = race.front(player)
            if best.ghost > 0 or player == pack.holder:
                continue
            x, y, _ = race.pose(best)
            nx, ny, _ = pack.camera.project(x, y, best.z)
            if abs(nx) > 0.8 or ny < -0.75 or ny > camera.TOP - 0.2:
                px, py = pack.camera.to_pixels(x, y, best.z)
                out.append((px, py - 30, config.color_of(player), config.label_of(player)))
        return out

    def _lead_mark(self, pack: Pack, box: pygame.Rect | None = None) -> tuple | None:
        """Where the marker over the leader goes, and whose colour and name
        (in a box of the screen, for the HOW TO PLAY card's demo)."""
        if pack.holder is None:
            return None
        b = pack.race.front(pack.holder)
        x, y, _ = pack.race.pose(b)
        if box is None:
            px, py = pack.camera.to_pixels(x, y, b.z + 16)
        else:
            px, py = pack.camera.to_pixels(x, y, b.z + 16, box.size)
            px, py = box.x + px, box.y + py
        return px, py, config.color_of(pack.holder), config.label_of(pack.holder)
