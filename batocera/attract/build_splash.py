"""Make the cabinet's ARQADE artwork: loading screens and the menu logos.

    uv run --project launcher --with resvg-py batocera/attract/build_splash.py

(resvg-py renders the logo SVG; it is only needed here, so it is not one of
the launcher's dependencies.)

Two sources, written into the theme installer's folders
(quantum-pong/batocera/arqade-theme/), which install.py then puts in place on
the cabinet. From the 3D logo render, logos/animation/arqade_loading_v3_1080p.webm
(a seamless 4 s, 120-frame, 1920x1080 turn on black):

  splash/arqade_splash.mp4  the boot splash: the logo turning three times
  splash/arqade_splash.png  its first frame, front on: the still that every
  art/mqt_splash.png        screen which cannot play video shows instead

and from the flat logo, logos/Arqade_logo.svg, rendered on transparency into
the same places the old purple logo sat:

  art/logos/{mqt,pygame}[-w].png  the system's logo in the menu carousel
  art/consoles/{mqt,pygame}.png   its "console" picture beside it

A boot splash video should run about as long as Batocera's own (~10 s):
S28splash is killed when EmulationStation takes over, and a shorter clip
leaves the screen black for the rest of the boot. Three turns are 12 s.

The stills are where the spin comes to rest: the same logo, face on, so the
boot video, the framebuffer logo, sway's wallpaper and EmulationStation's
start-up and game-launch splashes all show one picture. Every PNG here is
8-bit -- fbv and EmulationStation cannot read 16-bit ones (see AGENTS.md,
"Artwork must be 8-bit PNG").
"""

from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
import pygame

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SPIN = REPO / "logos" / "animation" / "arqade_loading_v3_1080p.webm"
LOGO_SVG = REPO / "logos" / "Arqade_logo.svg"
THEME = REPO / "quantum-pong" / "batocera" / "arqade-theme"
TURNS = 3
TURN_SECONDS = 4.0
# Canvas size and the box the logo is fitted into, as the theme's originals had it.
MENU_LOGOS = {
    ("art/logos/mqt.png", "art/logos/mqt-w.png", "art/logos/pygame.png", "art/logos/pygame-w.png"):
        ((1300, 520), pygame.Rect(36, 37, 1228, 445)),
    ("art/consoles/mqt.png", "art/consoles/pygame.png"): ((600, 600), pygame.Rect(20, 198, 560, 203)),
}


def ffmpeg(*args: str) -> None:
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-y", *args], check=True)


def bit_depth(png: Path) -> int:
    return png.read_bytes()[24]


def flat_logo() -> pygame.Surface:
    """The logo SVG without its black background layer, cropped to the logo."""
    import resvg_py

    svg = LOGO_SVG.read_text(encoding="utf-8")
    svg, found = re.subn(r'<rect\s+id="background-fill"[^>]*/>', "", svg)
    assert found == 1, "the SVG's background rect has moved; update flat_logo()"
    png = bytes(resvg_py.svg_to_bytes(svg_string=svg, width=2800, height=2800))
    img = pygame.image.load(io.BytesIO(png), "logo.png")
    return img.subsurface(img.get_bounding_rect()).copy()


def menu_logos() -> None:
    logo = flat_logo()
    for paths, (canvas, box) in MENU_LOGOS.items():
        scale = min(box.w / logo.get_width(), box.h / logo.get_height())
        fitted = pygame.transform.smoothscale(
            logo, (round(logo.get_width() * scale), round(logo.get_height() * scale)))
        out = pygame.Surface(canvas, pygame.SRCALPHA)
        out.blit(fitted, fitted.get_rect(center=box.center))
        for path in paths:
            pygame.image.save(out, str(THEME / path))
            assert bit_depth(THEME / path) == 8, f"{path} is not an 8-bit PNG"
            print(f"wrote {(THEME / path).relative_to(REPO)}")


def main() -> None:
    if not SPIN.is_file():
        sys.exit(f"missing {SPIN}")
    video = THEME / "splash" / "arqade_splash.mp4"
    ffmpeg("-stream_loop", str(TURNS - 1), "-i", str(SPIN),
           "-t", str(TURNS * TURN_SECONDS), "-vf", "fade=t=in:st=0:d=0.6",
           "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p",
           "-profile:v", "high", "-level", "4.1", "-movflags", "+faststart", "-an", str(video))
    print(f"wrote {video.relative_to(REPO)}")
    for still in (THEME / "splash" / "arqade_splash.png", THEME / "art" / "mqt_splash.png"):
        ffmpeg("-i", str(SPIN), "-frames:v", "1", "-pix_fmt", "rgb24", str(still))
        assert bit_depth(still) == 8, f"{still} is not an 8-bit PNG"
        print(f"wrote {still.relative_to(REPO)}")
    menu_logos()


if __name__ == "__main__":
    main()
