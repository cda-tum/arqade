"""OpenGL plumbing through PyOpenGL: the window and its context, shaders,
meshes, textures and an off-screen render target.

The context is OpenGL ES 3.0 where the system offers it (the Pi), else
desktop OpenGL 3.3 core (a PC, or SDL's offscreen driver for the tests);
the shaders are written once and get the matching #version line. Every
frame is drawn into a 960x540 target, then scaled onto the window.
"""

from __future__ import annotations

import ctypes

import numpy as np
import pygame
from OpenGL import GL

from qarrera.mesh import STRIDE

ES_HEADER = "#version 300 es\nprecision mediump float;\n"
CORE_HEADER = "#version 330 core\n"


def open_window(size: tuple[int, int], fullscreen: bool) -> tuple[tuple[int, int], bool]:
    """Open the GL window: OpenGL ES 3.0 if possible, else desktop 3.3 core.
    Returns (its size, whether it is ES)."""
    flags = pygame.OPENGL | pygame.DOUBLEBUF | (pygame.FULLSCREEN if fullscreen else 0)
    attempts = ((pygame.GL_CONTEXT_PROFILE_ES, 3, 0, True), (pygame.GL_CONTEXT_PROFILE_CORE, 3, 3, False))
    last = None
    for profile, major, minor, es in attempts:
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, profile)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, major)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, minor)
        pygame.display.gl_set_attribute(pygame.GL_DEPTH_SIZE, 24)
        try:
            surface = pygame.display.set_mode((0, 0) if fullscreen else size, flags)
            GL.glGetString(GL.GL_VERSION)
            return surface.get_size(), es
        except Exception as exc:  # no such context here: try the next
            last = exc
    raise RuntimeError(f"no OpenGL ES 3.0 or OpenGL 3.3 context: {last}")


class Program:
    def __init__(self, es: bool, vertex: str, fragment: str) -> None:
        header = ES_HEADER if es else CORE_HEADER
        self.id = GL.glCreateProgram()
        for kind, src in ((GL.GL_VERTEX_SHADER, vertex), (GL.GL_FRAGMENT_SHADER, fragment)):
            shader = GL.glCreateShader(kind)
            GL.glShaderSource(shader, header + src)
            GL.glCompileShader(shader)
            if not GL.glGetShaderiv(shader, GL.GL_COMPILE_STATUS):
                raise RuntimeError(GL.glGetShaderInfoLog(shader).decode())
            GL.glAttachShader(self.id, shader)
        GL.glLinkProgram(self.id)
        if not GL.glGetProgramiv(self.id, GL.GL_LINK_STATUS):
            raise RuntimeError(GL.glGetProgramInfoLog(self.id).decode())
        self._loc: dict[str, int] = {}

    def use(self) -> None:
        GL.glUseProgram(self.id)

    def loc(self, name: str) -> int:
        if name not in self._loc:
            self._loc[name] = GL.glGetUniformLocation(self.id, name)
        return self._loc[name]

    def mat4(self, name: str, m) -> None:
        GL.glUniformMatrix4fv(self.loc(name), 1, GL.GL_TRUE, np.asarray(m, dtype=np.float32))

    def vec(self, name: str, *v: float) -> None:
        (GL.glUniform1f, GL.glUniform2f, GL.glUniform3f, GL.glUniform4f)[len(v) - 1](self.loc(name), *v)

    def int(self, name: str, v: int) -> None:
        GL.glUniform1i(self.loc(name), v)


# The lit shader: positions, normals, colours, glow, uv (mesh.STRIDE floats).
LIT_VS = """
layout(location = 0) in vec3 a_pos;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec3 a_color;
layout(location = 3) in float a_glow;
layout(location = 4) in vec2 a_uv;
uniform mat4 u_vp;
uniform mat4 u_model;
out vec3 v_normal;
out vec3 v_color;
out float v_glow;
out vec2 v_uv;
out vec3 v_world;
void main() {
    vec4 world = u_model * vec4(a_pos, 1.0);
    v_world = world.xyz;
    v_normal = mat3(u_model) * a_normal;
    v_color = a_color;
    v_glow = a_glow;
    v_uv = a_uv;
    gl_Position = u_vp * world;
}
"""
LIT_FS = """
in vec3 v_normal;
in vec3 v_color;
in float v_glow;
in vec2 v_uv;
in vec3 v_world;
uniform vec3 u_light;
uniform vec3 u_sun;
uniform vec3 u_ambient;
uniform vec3 u_fog;
uniform vec3 u_eye;
uniform vec2 u_fog_range;
uniform vec4 u_tint;
uniform int u_textured;
uniform vec2 u_scroll;
uniform sampler2D u_tex;
layout(location = 0) out vec4 o_color;
void main() {
    vec3 n = normalize(v_normal);
    vec3 base = v_color;
    if (u_textured == 1) base *= texture(u_tex, v_uv + u_scroll).rgb;
    float d = max(dot(n, -u_light), 0.0);
    vec3 lit = base * (u_ambient + u_sun * d);
    vec3 c = mix(lit, base, v_glow);
    c = mix(c, u_tint.rgb, u_tint.a);
    float f = clamp((distance(v_world, u_eye) - u_fog_range.x) / (u_fog_range.y - u_fog_range.x), 0.0, 1.0);
    o_color = vec4(mix(c, u_fog, f * (1.0 - v_glow * 0.5)), 1.0);
}
"""
# Billboards, shadows and rings: positions, uv, rgba; a texture's alpha cuts out.
FLAT_VS = """
layout(location = 0) in vec3 a_pos;
layout(location = 1) in vec2 a_uv;
layout(location = 2) in vec4 a_color;
uniform mat4 u_vp;
out vec2 v_uv;
out vec4 v_color;
void main() {
    v_uv = a_uv;
    v_color = a_color;
    gl_Position = u_vp * vec4(a_pos, 1.0);
}
"""
FLAT_FS = """
in vec2 v_uv;
in vec4 v_color;
uniform sampler2D u_tex;
uniform float u_cut;
layout(location = 0) out vec4 o_color;
void main() {
    vec4 c = texture(u_tex, v_uv) * v_color;
    if (c.a < u_cut) discard;
    o_color = c;
}
"""


class Mesh:
    """A vertex buffer and how to read it: attrs is ((location, size), ...)
    in order, all float32."""

    def __init__(self, data: np.ndarray, attrs, dynamic: bool = False) -> None:
        self.vao = GL.glGenVertexArrays(1)
        self.vbo = GL.glGenBuffers(1)
        self.stride = sum(size for _, size in attrs)
        self.dynamic = dynamic
        GL.glBindVertexArray(self.vao)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo)
        offset = 0
        for loc, size in attrs:
            GL.glEnableVertexAttribArray(loc)
            GL.glVertexAttribPointer(loc, size, GL.GL_FLOAT, GL.GL_FALSE, self.stride * 4, ctypes.c_void_p(offset * 4))
            offset += size
        self.count = 0
        self.set(data)
        GL.glBindVertexArray(0)

    def set(self, data: np.ndarray) -> None:
        data = np.ascontiguousarray(data, dtype=np.float32)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo)
        usage = GL.GL_STREAM_DRAW if self.dynamic else GL.GL_STATIC_DRAW
        GL.glBufferData(GL.GL_ARRAY_BUFFER, max(4, data.nbytes), data if data.size else None, usage)
        self.count = len(data) if data.ndim > 1 else data.size // self.stride

    def draw(self, mode=GL.GL_TRIANGLES) -> None:
        if self.count:
            GL.glBindVertexArray(self.vao)
            GL.glDrawArrays(mode, 0, self.count)

    def delete(self) -> None:
        GL.glDeleteBuffers(1, [self.vbo])
        GL.glDeleteVertexArrays(1, [self.vao])


LIT_ATTRS = ((0, 3), (1, 3), (2, 3), (3, 1), (4, 2))
FLAT_ATTRS = ((0, 3), (1, 2), (2, 4))
assert sum(s for _, s in LIT_ATTRS) == STRIDE


class Texture:
    def __init__(self, surface: pygame.Surface, smooth: bool = False, repeat: bool = False) -> None:
        self.id = GL.glGenTextures(1)
        self.size = surface.get_size()
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.id)
        filt = GL.GL_LINEAR if smooth else GL.GL_NEAREST
        wrap = GL.GL_REPEAT if repeat else GL.GL_CLAMP_TO_EDGE
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, filt)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, filt)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, wrap)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, wrap)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, self.size[0], self.size[1], 0, GL.GL_RGBA,
                        GL.GL_UNSIGNED_BYTE, pygame.image.tostring(surface, "RGBA"))

    def update(self, surface: pygame.Surface, rect: pygame.Rect | None = None) -> None:
        """Upload the surface again; with rect, just that part of it."""
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.id)
        if rect is None:
            rect = pygame.Rect((0, 0), self.size)
        rect = rect.clip(pygame.Rect((0, 0), self.size))
        if rect.w and rect.h:
            data = pygame.image.tostring(surface.subsurface(rect), "RGBA")
            GL.glTexSubImage2D(GL.GL_TEXTURE_2D, 0, rect.x, rect.y, rect.w, rect.h, GL.GL_RGBA,
                               GL.GL_UNSIGNED_BYTE, data)

    def bind(self, unit: int = 0) -> None:
        GL.glActiveTexture(GL.GL_TEXTURE0 + unit)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.id)


class Target:
    """An off-screen framebuffer with a colour texture and a depth buffer."""

    def __init__(self, w: int, h: int) -> None:
        self.size = (w, h)
        self.fbo = GL.glGenFramebuffers(1)
        self.tex = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.tex)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, w, h, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, None)
        for p in (GL.GL_TEXTURE_MIN_FILTER, GL.GL_TEXTURE_MAG_FILTER):
            GL.glTexParameteri(GL.GL_TEXTURE_2D, p, GL.GL_NEAREST)
        for p in (GL.GL_TEXTURE_WRAP_S, GL.GL_TEXTURE_WRAP_T):
            GL.glTexParameteri(GL.GL_TEXTURE_2D, p, GL.GL_CLAMP_TO_EDGE)
        self.depth = GL.glGenRenderbuffers(1)
        GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, self.depth)
        GL.glRenderbufferStorage(GL.GL_RENDERBUFFER, GL.GL_DEPTH_COMPONENT24, w, h)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.fbo)
        GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, GL.GL_TEXTURE_2D, self.tex, 0)
        GL.glFramebufferRenderbuffer(GL.GL_FRAMEBUFFER, GL.GL_DEPTH_ATTACHMENT, GL.GL_RENDERBUFFER, self.depth)
        if GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER) != GL.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError("the off-screen target is incomplete")
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)

    def bind(self) -> None:
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.fbo)
        GL.glViewport(0, 0, *self.size)

    def read(self) -> pygame.Surface:
        """What is in it, as a pygame surface (for screenshots and the reels)."""
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.fbo)
        data = GL.glReadPixels(0, 0, self.size[0], self.size[1], GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
        return pygame.image.fromstring(bytes(data), self.size, "RGBA", True)
