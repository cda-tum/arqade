"""The camera, and who is on the screen. Pure (no pygame, no GL), so it is
tested.

The race's world has x east, y south (down the map) and z up; for 3D maths
that becomes the right-handed (x, -y, z) of gl(). The Director is a fixed
isometric camera: it looks along CAM_YAW from CAM_PITCH above, with an
orthographic projection CAM_VIEW units wide, and never turns. It only
slides after the leader (a little ahead of it, CAM_AHEAD), so the leader
drives across the screen and whoever trails falls off an edge. The same
view-projection matrix is the renderer's camera and the race's judge.

Matrices are 16 floats, row-major (upload with transpose).
"""

from __future__ import annotations

import math

from qircuit import config

Vec = tuple[float, float, float]


def gl(x: float, y: float, z: float = 0.0) -> Vec:
    return (x, -y, z)


def _sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a: Vec) -> Vec:
    n = math.sqrt(_dot(a, a)) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


def perspective(fovy: float, aspect: float, near: float, far: float) -> list[float]:
    f = 1 / math.tan(math.radians(fovy) / 2)
    return [f / aspect, 0, 0, 0,
            0, f, 0, 0,
            0, 0, (far + near) / (near - far), 2 * far * near / (near - far),
            0, 0, -1, 0]


def ortho(left: float, right: float, bottom: float, top: float, near: float, far: float) -> list[float]:
    return [2 / (right - left), 0, 0, -(right + left) / (right - left),
            0, 2 / (top - bottom), 0, -(top + bottom) / (top - bottom),
            0, 0, -2 / (far - near), -(far + near) / (far - near),
            0, 0, 0, 1]


def look_at(eye: Vec, target: Vec, up: Vec = (0.0, 0.0, 1.0)) -> list[float]:
    f = _norm(_sub(target, eye))
    s = _norm(_cross(f, up))
    u = _cross(s, f)
    return [s[0], s[1], s[2], -_dot(s, eye),
            u[0], u[1], u[2], -_dot(u, eye),
            -f[0], -f[1], -f[2], _dot(f, eye),
            0, 0, 0, 1]


def mul(a: list[float], b: list[float]) -> list[float]:
    return [sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4)) for r in range(4) for c in range(4)]


def apply(m: list[float], p: Vec) -> tuple[float, float, float, float]:
    x, y, z = p
    return tuple(m[r * 4] * x + m[r * 4 + 1] * y + m[r * 4 + 2] * z + m[r * 4 + 3] for r in range(4))


def model_matrix(x: float, y: float, z: float, heading: float, scale: float = 1.0,
                 roll: float = 0.0) -> list[float]:
    """Place a model (x forward, y to its right, z up, in voxels) at world
    (x, y, z) facing heading (world radians, 0 east, turning towards south).
    roll leans it about its own x axis at its feet (z = 0): positive tips
    its top to its right."""
    c, s = math.cos(heading), math.sin(heading)
    # model x -> world (c, s); model y (its right) -> world (-s, c); then gl() flips y
    if not roll:
        return [c * scale, -s * scale, 0, x,
                -s * scale, -c * scale, 0, -y,
                0, 0, scale, z,
                0, 0, 0, 1]
    cr, sr = math.cos(roll), math.sin(roll)
    # its right tips down and its up towards its right
    return [c * scale, -s * scale * cr, -s * scale * sr, x,
            -s * scale, -c * scale * cr, -c * scale * sr, -y,
            0, -scale * sr, scale * cr, z,
            0, 0, 0, 1]


# The HUD band covers the top of the screen: under it counts as off.
TOP = 1 - 2 * config.HUD_BAND / config.INTERNAL_HEIGHT


class Director:
    """The camera. snap() puts it in place at once; update() follows. The
    tutorial's demo uses a narrower one (view: world units across)."""

    def __init__(self, aspect: float = config.INTERNAL_WIDTH / config.INTERNAL_HEIGHT,
                 view: float = config.CAM_VIEW) -> None:
        self.aspect = aspect
        self.focus: Vec = (0.0, 0.0, 0.0)  # gl() coordinates
        self.yaw = math.radians(config.CAM_YAW)  # the world heading it looks along, for good
        half_w = view / 2
        half_h = half_w / aspect
        # an orthographic box around the eye: near is negative so that nothing
        # between the eye and the far ground is ever clipped
        self.proj = ortho(-half_w, half_w, -half_h, half_h, -3000.0, 3000.0)
        self.vp = [1.0 if i % 5 == 0 else 0.0 for i in range(16)]
        self.view = list(self.vp)
        self.eye: Vec = (0.0, 0.0, 0.0)
        self._compute()

    @staticmethod
    def _aim(x: float, y: float, z: float, heading: float) -> Vec:
        return gl(x + math.cos(heading) * config.CAM_AHEAD, y + math.sin(heading) * config.CAM_AHEAD, z)

    def snap(self, x: float, y: float, z: float, heading: float) -> None:
        self.focus = self._aim(x, y, z, heading)
        self._compute()

    def update(self, dt: float, x: float, y: float, z: float, heading: float) -> None:
        target = self._aim(x, y, z, heading)
        k = 1 - math.exp(-dt / config.CAM_FOLLOW)
        self.focus = tuple(f + (t - f) * k for f, t in zip(self.focus, target))
        self._compute()

    def _compute(self) -> None:
        pitch = math.radians(config.CAM_PITCH)
        fx, fy = math.cos(self.yaw), -math.sin(self.yaw)  # where it looks, in gl() coordinates
        d = config.CAM_DISTANCE
        self.eye = (self.focus[0] - fx * d * math.cos(pitch), self.focus[1] - fy * d * math.cos(pitch),
                    self.focus[2] + d * math.sin(pitch))
        self.view = look_at(self.eye, self.focus)
        self.vp = mul(self.proj, self.view)

    def project(self, x: float, y: float, z: float = 0.0) -> tuple[float, float, float]:
        """World point to normalised device coordinates: x and y run -1..1
        across the screen (y up), the third is depth."""
        cx, cy, cz, cw = apply(self.vp, gl(x, y, z))
        return cx / cw, cy / cw, cz / cw

    def to_pixels(self, x: float, y: float, z: float = 0.0,
                  size: tuple[int, int] = (config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT)) -> tuple[float, float]:
        nx, ny, _ = self.project(x, y, z)
        return (nx + 1) / 2 * size[0], (1 - ny) / 2 * size[1]

    def on_screen(self, x: float, y: float, z: float = 0.0, margin: float = config.OUT_MARGIN) -> bool:
        """Inside the picture below the HUD band, give or take margin (a
        negative margin asks for that far inside the edges)."""
        nx, ny, _ = self.project(x, y, z)
        return abs(nx) <= 1 + margin and -1 - margin <= ny <= TOP + margin
