"""The extended logos as round 50 mm pin badges on an A4 print sheet: logos_print.pdf.

    python print_sheet.py    # with any of the games' venvs (only pygame is needed)

Each <rom>-logo.png here (generate_logos.py writes them) is cut to its 50 mm punch circle
and placed at exactly 50 mm on a white A4 page, in the menu's order, 3 across, the spare
space spread evenly between the badges and the paper's edges. Nothing else is printed: no
cut lines, no ring for the 38 mm face. Print it at "Actual size" / 100 %.

Every badge is its own image in the PDF at the PNG's full resolution (1792 px over 50 mm,
about 910 dpi), its corners outside the circle made white. The PDF is written by hand
(zlib, no PDF library), so nothing beyond pygame is needed.
"""

from __future__ import annotations

import os
import sys
import zlib
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from generate_logos import ROMS  # noqa: E402

OUT = HERE / "logos_print.pdf"
MM = 72 / 25.4  # PDF points per millimetre
PAGE = (210.0, 297.0)  # A4, mm
BADGE = 50.0  # the punch diameter, mm
COLS = 3
EDGE_AA = 4  # the circle's edge is drawn this many times bigger, then smoothscaled down


def disc(path: Path) -> pygame.Surface:
    """The logo cut to the circle that fits it, on white."""
    img = pygame.image.load(str(path)).convert()
    n = img.get_width()
    big = pygame.Surface((n * EDGE_AA, n * EDGE_AA), pygame.SRCALPHA)
    pygame.draw.circle(big, (255, 255, 255, 255), (n * EDGE_AA / 2,) * 2, n * EDGE_AA / 2)
    mask = pygame.transform.smoothscale(big, (n, n))
    cut = img.convert_alpha()
    cut.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    out = pygame.Surface((n, n))
    out.fill((255, 255, 255))
    out.blit(cut, (0, 0))
    return out


def layout(count: int) -> list[tuple[float, float]]:
    """Each badge's lower-left corner in mm (PDF coordinates: y up), page by page."""
    rows = int((PAGE[1] - 10) // (BADGE + 5))  # at least 5 mm between badges and to the edge
    per_page = COLS * rows
    spots = []
    for i in range(count):
        on_page = min(per_page, count - i // per_page * per_page)
        used_rows = -(-on_page // COLS)
        gx = (PAGE[0] - COLS * BADGE) / (COLS + 1)
        gy = (PAGE[1] - used_rows * BADGE) / (used_rows + 1)
        k = i % per_page
        col, row = k % COLS, k // COLS
        spots.append((i // per_page, gx + col * (BADGE + gx), PAGE[1] - (gy + row * (BADGE + gy) + BADGE)))
    return spots


def write_pdf(images: list[pygame.Surface], spots) -> bytes:
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    pages = sorted({p for p, _, _ in spots})
    image_ids = []
    for img in images:
        w, h = img.get_size()
        data = zlib.compress(pygame.image.tostring(img, "RGB"), 9)
        image_ids.append(add(b"<< /Type /XObject /Subtype /Image /Width %d /Height %d "
                             b"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode "
                             b"/Length %d >>\nstream\n" % (w, h, len(data)) + data + b"\nendstream"))
    pages_id = len(objects) + 2 * len(pages) + 1  # after every page and its content
    page_ids = []
    for page in pages:
        on = [(i, x, y) for i, (p, x, y) in enumerate(spots) if p == page]
        ops = b"".join(b"q %.3f 0 0 %.3f %.3f %.3f cm /Im%d Do Q\n"
                       % (BADGE * MM, BADGE * MM, x * MM, y * MM, i) for i, x, y in on)
        content = add(b"<< /Length %d >>\nstream\n" % len(ops) + ops + b"endstream")
        xobjects = b" ".join(b"/Im%d %d 0 R" % (i, image_ids[i]) for i, _, _ in on)
        page_ids.append(add(b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.3f %.3f] "
                            b"/Resources << /XObject << %s >> >> /Contents %d 0 R >>"
                            % (pages_id, PAGE[0] * MM, PAGE[1] * MM, xobjects, content)))
    assert add(b"<< /Type /Pages /Kids [%s] /Count %d >>"
               % (b" ".join(b"%d 0 R" % p for p in page_ids), len(page_ids))) == pages_id
    catalog = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for n, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % n + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, catalog, xref)
    return bytes(out)


def main() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    paths = [HERE / f"{rom}-logo.png" for rom in ROMS if (HERE / f"{rom}-logo.png").is_file()]
    images = [disc(p) for p in paths]
    OUT.write_bytes(write_pdf(images, layout(len(images))))
    print(f"wrote {OUT.name}: {len(images)} badges")


if __name__ == "__main__":
    main()
