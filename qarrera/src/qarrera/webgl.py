"""PyOpenGL's platform in the browser (pygbag), registered in __init__.py.

pygbag's Python is CPython compiled to WebAssembly by Emscripten, and its
ctypes works. There is no libGL to load, but the running module itself
exports the GL functions SDL's WebGL backend is built on (glClear,
glDrawArrays, ...), so ctypes.CDLL(None) finds them by name, as it would in
a libGL. With that, PyOpenGL and every GL call in the game are the same as
on the cabinet: SDL makes a WebGL 2 context when gfx.open_window asks for
OpenGL ES 3.0, and the ES shaders run on it unchanged.

PyOpenGL imports this module itself, the first time OpenGL.platform is
loaded; nothing else should.
"""

from __future__ import annotations

import ctypes

from OpenGL.platform import baseplatform


class WebGLPlatform(baseplatform.BasePlatform):
    DEFAULT_FUNCTION_TYPE = staticmethod(ctypes.CFUNCTYPE)
    EXTENSIONS_USE_BASE_FUNCTIONS = True  # extension functions are exported by name as well

    @baseplatform.lazy_property
    def GL(self):
        return ctypes.CDLL(None)  # the running module

    @baseplatform.lazy_property
    def GLES2(self):
        return self.GL

    @baseplatform.lazy_property
    def GLES3(self):
        return self.GL

    @baseplatform.lazy_property
    def OpenGL(self):
        return self.GL

    GLES1 = GLU = GLUT = GLE = None

    @baseplatform.lazy_property
    def getExtensionProcedure(self):
        get = self.GL.SDL_GL_GetProcAddress
        get.restype = ctypes.c_void_p
        get.argtypes = [ctypes.c_char_p]
        return get

    @baseplatform.lazy_property
    def GetCurrentContext(self):
        try:
            current = self.GL.emscripten_webgl_get_current_context
        except AttributeError:  # not exported: the page has the one context SDL made
            return lambda: 1
        current.restype = ctypes.c_void_p
        return current
