"""Qarrera: slot-car racing on the wires of a quantum circuit."""

import os
import sys

from arqade_common.runtime import is_browser

# SDL and PyOpenGL each pick an OpenGL platform on their own, and on Linux
# they can disagree: SDL's x11 driver makes a GLX context, while PyOpenGL
# takes EGL whenever WAYLAND_DISPLAY is set (WSLg, any Wayland desktop). It
# then finds no current context and fails the first time it needs one
# ("Attempt to retrieve context when no valid context"). So both use EGL,
# which SDL's wayland, kmsdrm and offscreen drivers use anyway. This sits
# here so it runs before any module imports OpenGL.
if sys.platform.startswith("linux") and "PYOPENGL_PLATFORM" not in os.environ:
    os.environ["PYOPENGL_PLATFORM"] = "egl"
    os.environ.setdefault("SDL_VIDEO_X11_FORCE_EGL", "1")
elif is_browser():
    # The browser (pygbag): there is no libGL, so PyOpenGL gets its GL
    # functions from WebGL through a platform of our own (webgl.py). And it
    # skips glGetError after every call: in WebGL that waits for the GPU,
    # about 0.2 ms each time.
    import OpenGL
    from OpenGL.plugins import PlatformPlugin

    OpenGL.ERROR_CHECKING = False
    PlatformPlugin("emscripten", "qarrera.webgl.WebGLPlatform")
    # Before every texture upload PyOpenGL also sets how pixels are read back
    # (glPixelStorei with GL_PACK_*), some of it settings WebGL doesn't have:
    # each time that only logs WebGL INVALID_ENUMs. Nothing here reads back.
    import OpenGL.images

    OpenGL.images.setupDefaultTransferMode = lambda: None
    OpenGL.images.rankPacking = lambda rank: None
