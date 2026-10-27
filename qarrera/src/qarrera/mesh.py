"""Meshes for the 3D renderer, as numpy arrays. No GL here, so it is tested.

Every vertex is 12 floats: position (3), normal (3), colour (3, 0..1), glow
(1: 0 is lit by the sun, 1 shines by itself), texture uv (2). Positions are
in gl() coordinates (camera.py): the race's y flipped, z up.

- voxel_mesh: a voxel model (voxels.py) as cubes, only the faces nothing
  covers; in the model's own units (one per voxel, x forward, y to its
  right, z up), placed by camera.model_matrix.
- track_mesh: a track as a slab: each wire's strip of road, the glowing
  wires, kerbs on the curves, the sides, pillars under anything raised,
  the start line, boost pads and kicker lips.
- ground_mesh: the big plane the scene paints, under everything.
"""

from __future__ import annotations

import math

import numpy as np

from qarrera import config
from qarrera.track import Track

STRIDE = 12
SLAB = 8.0  # the track's thickness
WHITE = (1.0, 1.0, 1.0)


def rgb(c) -> tuple[float, float, float]:
    return (c[0] / 255, c[1] / 255, c[2] / 255)


def quads(a, b, c, d, normal, color, glow: float = 0.0) -> np.ndarray:
    """Two triangles per quad a-b-c-d. Corners are (N, 3) arrays (or one
    point each); normal and color one per quad or one for all."""
    a, b, c, d = (np.atleast_2d(np.asarray(p, dtype=np.float32)) for p in (a, b, c, d))
    n = max(len(a), len(b), len(c), len(d))
    normal = np.broadcast_to(np.asarray(normal, dtype=np.float32), (n, 3))
    color = np.broadcast_to(np.asarray(color, dtype=np.float32), (n, 3))
    out = np.zeros((n, 6, STRIDE), dtype=np.float32)
    for i, p in enumerate((a, b, c, a, c, d)):
        out[:, i, 0:3] = p
    out[:, :, 3:6] = normal[:, None, :]
    out[:, :, 6:9] = color[:, None, :]
    out[:, :, 9] = glow
    return out.reshape(-1, STRIDE)


# --- voxels -------------------------------------------------------------------------------

_FACES = (  # direction, the four corners of that face of a unit cube centred on 0
    ((1, 0, 0), ((.5, -.5, -.5), (.5, .5, -.5), (.5, .5, .5), (.5, -.5, .5))),
    ((-1, 0, 0), ((-.5, .5, -.5), (-.5, -.5, -.5), (-.5, -.5, .5), (-.5, .5, .5))),
    ((0, 1, 0), ((.5, .5, -.5), (-.5, .5, -.5), (-.5, .5, .5), (.5, .5, .5))),
    ((0, -1, 0), ((-.5, -.5, -.5), (.5, -.5, -.5), (.5, -.5, .5), (-.5, -.5, .5))),
    ((0, 0, 1), ((-.5, -.5, .5), (.5, -.5, .5), (.5, .5, .5), (-.5, .5, .5))),
    ((0, 0, -1), ((-.5, .5, -.5), (.5, .5, -.5), (.5, -.5, -.5), (-.5, -.5, -.5))),
)


def voxel_mesh(model: dict) -> np.ndarray:
    """The model's visible cube faces. Its voxels sit on z = 0 (a voxel at
    height 0 fills 0..1)."""
    corners, normals, colors = [], [], []
    for (x, y, z), c in model.items():
        col = rgb(c)
        for (dx, dy, dz), quad in _FACES:
            if (x + dx, y + dy, z + dz) in model:
                continue
            corners.append([(x + qx, y + qy, z + 0.5 + qz) for qx, qy, qz in quad])
            normals.append((dx, dy, dz))
            colors.append(col)
    if not corners:
        return np.zeros((0, STRIDE), dtype=np.float32)
    q = np.asarray(corners, dtype=np.float32)
    return quads(q[:, 0], q[:, 1], q[:, 2], q[:, 3], normals, colors)


def place(mesh: np.ndarray, x: float, y: float, z: float, heading: float, scale: float) -> np.ndarray:
    """A model-space mesh moved into the world, as camera.model_matrix does."""
    out = mesh.copy()
    c, s = math.cos(heading), math.sin(heading)
    rot = np.array([[c, -s, 0], [-s, -c, 0], [0, 0, 1]], dtype=np.float32)
    out[:, 0:3] = mesh[:, 0:3] @ (rot * scale).T + np.array([x, -y, z], dtype=np.float32)
    out[:, 3:6] = mesh[:, 3:6] @ rot.T
    return out


def box(x0, y0, z0, x1, y1, z1, color, glow: float = 0.0) -> np.ndarray:
    """An axis-aligned box in world coordinates (y as the race has it)."""
    gy0, gy1 = -y1, -y0
    pts = {
        "000": (x0, gy0, z0), "100": (x1, gy0, z0), "110": (x1, gy1, z0), "010": (x0, gy1, z0),
        "001": (x0, gy0, z1), "101": (x1, gy0, z1), "111": (x1, gy1, z1), "011": (x0, gy1, z1),
    }
    faces = (("100", "110", "111", "101", (1, 0, 0)), ("010", "000", "001", "011", (-1, 0, 0)),
             ("110", "010", "011", "111", (0, 1, 0)), ("000", "100", "101", "001", (0, -1, 0)),
             ("001", "101", "111", "011", (0, 0, 1)))
    return np.concatenate([quads(pts[a], pts[b], pts[c], pts[d], n, color, glow) for a, b, c, d, n in faces])


# --- the track ------------------------------------------------------------------------------

def _edges(track: Track, lane: int, offset: float, ks: np.ndarray, lift: float = 0.0) -> np.ndarray:
    """(N, 3) gl() points at `offset` to the right of wire `lane`'s centre."""
    cx, cy, ch = (np.asarray(a, dtype=np.float32)[ks] for a in (track.cx, track.cy, track.ch))
    off = np.asarray(track.off[lane], dtype=np.float32)[ks] + offset
    z = np.asarray(track.elev, dtype=np.float32)[ks] + lift
    return np.stack([cx - np.sin(ch) * off, -(cy + np.cos(ch) * off), z], axis=1)


def _strip(track: Track, lane: int, a: float, b: float, ks: np.ndarray, color, glow: float = 0.0,
           lift: float = 0.0, mask: np.ndarray | None = None) -> np.ndarray:
    """A flat band along wire `lane` from offset a to b, segment by segment."""
    left, right = _edges(track, lane, a, ks, lift), _edges(track, lane, b, ks, lift)
    l0, l1, r0, r1 = left[:-1], left[1:], right[:-1], right[1:]
    color = np.asarray(color, dtype=np.float32)
    if mask is not None:
        l0, l1, r0, r1 = l0[mask], l1[mask], r0[mask], r1[mask]
        if color.ndim == 2:
            color = color[mask]
    if len(l0) == 0:
        return np.zeros((0, STRIDE), dtype=np.float32)
    return quads(l0, r0, r1, l1, (0, 0, 1), color, glow)


def _wall(track: Track, lane: int, offset: float, outward: float, ks: np.ndarray, color, depth: float,
          mask: np.ndarray | None = None) -> np.ndarray:
    """The slab's side along an edge, from the road down `depth`."""
    top = _edges(track, lane, offset, ks)
    bottom = top.copy()
    bottom[:, 2] -= depth
    t0, t1, b0, b1 = top[:-1], top[1:], bottom[:-1], bottom[1:]
    ch = np.asarray(track.ch, dtype=np.float32)[ks][:-1]
    normal = np.stack([-np.sin(ch) * outward, -np.cos(ch) * outward, np.zeros_like(ch)], axis=1)
    if mask is not None:
        t0, t1, b0, b1, normal = t0[mask], t1[mask], b0[mask], b1[mask], normal[mask]
    if len(t0) == 0:
        return np.zeros((0, STRIDE), dtype=np.float32)
    return quads(t0, t1, b1, b0, normal, color)


def _across(track: Track, s: float, a: float, b: float, d0: float, d1: float, lift: float):
    """Corners of a band across the whole track at station s: from a to b
    across (-1 the left edge, 1 the right), from d0 to d1 along."""
    x, y, h = track.pose(1.5, s)
    z = track.height(s) + lift
    nx, ny, tx, ty = -math.sin(h), math.cos(h), math.cos(h), math.sin(h)
    half = config.LANES * config.LANE_W / 2

    def pt(u, d):
        return (x + nx * half * u + tx * d, -(y + ny * half * u + ty * d), z)

    return pt(a, d0), pt(b, d0), pt(b, d1), pt(a, d1)


def track_mesh(track: Track, pal, ground_z: float, step: int = 3) -> np.ndarray:
    n = track.n
    ks = np.arange(0, n + step, step) % n
    hw = config.LANE_W / 2 + 0.6
    lk0 = np.asarray(track.lk[0], dtype=np.float32)[ks][:-1]
    lk3 = np.asarray(track.lk[config.LANES - 1], dtype=np.float32)[ks][:-1]
    curved = (np.abs(lk0) + np.abs(lk3)) > 0.0015
    stripes = (np.arange(len(ks) - 1) // 3) % 2 == 0
    kerb = np.where(stripes[:, None], np.array(rgb(pal.kerb)), np.array(rgb(pal.kerb_alt)))
    kerb = np.where(curved[:, None], kerb, np.array(rgb(pal.edge)))
    split = np.asarray(track.split, dtype=np.float32)[ks][:-1] > 0.05
    parts = []
    for i in range(config.LANES):
        parts.append(_strip(track, i, -hw, hw, ks, rgb(pal.bed)))
        parts.append(_strip(track, i, -0.55, 0.55, ks, rgb(pal.wire), glow=0.85, lift=0.12))
    last = config.LANES - 1
    mid = config.LANES // 2
    for lane, a, b, out, mask in ((0, -hw - 2.6, -hw, -1, None), (last, hw, hw + 2.6, 1, None),
                                   (mid - 1, hw, hw + 2.6, 1, split), (mid, -hw - 2.6, -hw, -1, split)):
        parts.append(_strip(track, lane, a, b, ks, kerb, lift=0.06, mask=mask))
        edge = b if out > 0 else a
        parts.append(_wall(track, lane, edge, out, ks, rgb(pal.side), SLAB, mask=mask))
    elev = np.asarray(track.elev)
    for k in range(0, n, max(1, int(60 / track.ds))):  # pillars under anything raised (not in space)
        if elev[k] > SLAB + 2 and ground_z > -100:
            x, y, _ = track.pose(1.5, k * track.ds)
            parts.append(box(x - 3, y - 3, ground_z, x + 3, y + 3, elev[k] - SLAB, rgb(pal.side)))
    s0 = track.d.start_s
    cells = 8
    for j in range(cells):
        for row in (0, 1):
            a, b = -1 + 2 * j / cells, -1 + 2 * (j + 1) / cells
            c = _across(track, s0, a, b, -4 + 4 * row, 4 * row, 0.2)
            parts.append(quads(*c, (0, 0, 1), WHITE if (j + row) % 2 else rgb(config.COLOR_INK)))
    for lip in track.d.kickers:
        for j in range(8):
            a, b = -1 + j / 4, -1 + (j + 1) / 4
            c = _across(track, lip - 3, a, b, 0, 3, 0.2)
            parts.append(quads(*c, (0, 0, 1), rgb(pal.lip) if j % 2 else rgb(config.COLOR_INK)))
        top = _across(track, lip, -1.05, 1.05, 0, 0.01, 0)
        drop = [top[0], top[1], (top[1][0], top[1][1], top[1][2] - config.KICKER_HEIGHT - SLAB),
                (top[0][0], top[0][1], top[0][2] - config.KICKER_HEIGHT - SLAB)]
        x, y, h = track.pose(1.5, lip)
        parts.append(quads(*drop, (math.cos(h), -math.sin(h), 0), rgb(pal.side)))
    for s, lanes in track.d.boosts:
        z = track.height(s) + 0.25
        for lane in lanes:
            x, y, h = track.pose(lane, s)
            tx, ty, nx, ny = math.cos(h), math.sin(h), -math.sin(h), math.cos(h)
            w = config.LANE_W * 0.42
            for c in range(3):  # three chevrons pointing the way
                d = -10 + 8 * c

                def P(u, v):
                    return (x + tx * u + nx * v, -(y + ty * u + ny * v), z)
                parts.append(quads(P(d + 5, 0), P(d, w), P(d - 3, w), P(d + 2, 0), (0, 0, 1),
                                   rgb(BOOST), glow=1.0))
                parts.append(quads(P(d + 5, 0), P(d + 2, 0), P(d - 3, -w), P(d, -w), (0, 0, 1),
                                   rgb(BOOST), glow=1.0))
    return np.concatenate([p for p in parts if len(p)])


BOOST = (255, 168, 40)


def ground_mesh(track: Track, z: float, color, tile: float, margin: float = 900.0) -> np.ndarray:
    """One big plane under the track, uv in tiles of `tile` units."""
    x0, x1 = min(track.cx) - margin, max(track.cx) + margin
    y0, y1 = min(track.cy) - margin, max(track.cy) + margin
    q = quads((x0, -y1, z), (x1, -y1, z), (x1, -y0, z), (x0, -y0, z), (0, 0, 1), rgb(color))
    q[:, 10] = q[:, 0] / tile
    q[:, 11] = q[:, 1] / tile
    return q
