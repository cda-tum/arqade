"""Qircuit: slot-car racing on the wires of a quantum circuit."""

import os
import sys

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
