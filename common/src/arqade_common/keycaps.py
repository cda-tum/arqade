"""Keyboard keys drawn as little keycaps, for hints read by keyboard players.

Where a pad player sees the stick or a lit button, a keyboard player sees the
keys they press instead: a rounded cap with the key's name on it (an arrow
for the arrow keys). A cap makes "B" read as the B key, not the pad's B button.
"""

import pygame


class Plain(str):
    """A name among a hint's keys that is written, not drawn as a key: a pad
    button ("A") or a group of keys ("WASD"), e.g. for a player on a pad
    while the other is on the keyboard."""


ARROWS = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}
EDGE = 2  # the cap's side, showing under its face
GAP = 2  # between two caps
ACTION_GAP = 5  # between the last cap and its action
ITEM_GAP = 14  # between one "keys action" pair and the next
SEPARATORS = ("/", "+")  # written between keys: either key, or both together


def keycap_size(font: pygame.font.Font, name: str) -> tuple[int, int]:
    h = font.get_height() + 4 + EDGE
    if name in ARROWS:
        return h, h
    return max(h, font.size(name)[0] + 8), h


def draw_keycap(
    surface: pygame.Surface, font: pygame.font.Font, name: str, topleft: tuple[int, int],
    face, edge, ink,
) -> pygame.Rect:
    """One key, its top-left at `topleft`; returns the space it took."""
    w, h = keycap_size(font, name)
    rect = pygame.Rect(topleft, (w, h))
    pygame.draw.rect(surface, edge, rect, border_radius=3)
    top = pygame.Rect(rect.x, rect.y, w, h - EDGE)
    pygame.draw.rect(surface, face, top, border_radius=3)
    pygame.draw.rect(surface, edge, top, 1, border_radius=3)
    if name in ARROWS:
        dx, dy = ARROWS[name]
        cx, cy = top.center
        r = max(2, (top.height - 6) // 2)
        tip = (cx + dx * r, cy + dy * r)
        side = (dy * r, dx * r)  # perpendicular to the arrow
        base = (cx - dx * r, cy - dy * r)
        pygame.draw.polygon(surface, ink, [tip, (base[0] + side[0], base[1] + side[1]),
                                           (base[0] - side[0], base[1] - side[1])])
    else:
        text = font.render(name, False, ink)
        surface.blit(text, text.get_rect(center=(top.centerx + 1, top.centery + 1)))
    return rect


def _parts(font, items):
    for i, (keys, action) in enumerate(items):
        if i:
            yield "gap", ITEM_GAP
        for j, key in enumerate(keys):
            if key in SEPARATORS or isinstance(key, Plain):
                yield "text", key
                continue
            if j and keys[j - 1] not in SEPARATORS:
                yield "gap", GAP
            yield "key", key
        if action:
            yield "gap", ACTION_GAP
            yield "text", action


def key_hint_size(font: pygame.font.Font, items) -> tuple[int, int]:
    width = 0
    for kind, value in _parts(font, items):
        if kind == "gap":
            width += value
        elif kind == "key":
            width += keycap_size(font, value)[0]
        else:
            width += font.size(value)[0] + (2 * GAP if value in SEPARATORS else 0)
    return width, keycap_size(font, "W")[1]


def draw_key_hint(
    surface: pygame.Surface, font: pygame.font.Font, items, midleft: tuple[int, int],
    face, edge, ink, text_color, name_color=None,
) -> pygame.Rect:
    """A row of hints, each a few keycaps then what they do, e.g.
    items = ((("B",), "PICK"), (("SPACE",), "RESUME")). A "/" among the keys
    is written between them, for "either key" ("+": both together), and a
    Plain name is written too, in `name_color` (end it with ":" if it is the
    last before the action). Vertically centred on midleft[1]; returns the
    space it took."""
    w, h = key_hint_size(font, items)
    x, top = midleft[0], midleft[1] - h // 2
    for kind, value in _parts(font, items):
        if kind == "gap":
            x += value
        elif kind == "key":
            x = draw_keycap(surface, font, value, (x, top), face, edge, ink).right
        else:
            pad = 2 * GAP if value in SEPARATORS else 0
            color = name_color if name_color and isinstance(value, Plain) else text_color
            text = font.render(value, False, color)
            surface.blit(text, (x + pad // 2, top + (h - EDGE - text.get_height()) // 2 + 1))
            x += text.get_width() + pad
    return pygame.Rect(midleft[0], top, w, h)


def key_hint_surface(font: pygame.font.Font, items, face, edge, ink, text_color, name_color=None) -> pygame.Surface:
    """draw_key_hint on a transparent surface of its own size, to place like
    rendered text."""
    w, h = key_hint_size(font, items)
    img = pygame.Surface((w, h), pygame.SRCALPHA)
    draw_key_hint(img, font, items, (0, h // 2), face, edge, ink, text_color, name_color)
    return img


def hint_items(parts, players, name) -> tuple:
    """draw_key_hint's items for hints that name each player's own controls:
    parts = ((controls, action), ...), and name(control, player) gives
    (on-screen name, is a keyboard key). Keys become caps, everything else
    (pad buttons, "WASD") is written, so a key never passes for a button."""
    items = []
    for controls, action in parts:
        names = list(dict.fromkeys(name(c, p) for c in controls for p in players))
        keys: list[str] = []
        for i, (text, is_key) in enumerate(names):
            if i:
                keys.append("/")
            last = i == len(names) - 1
            keys.append(text if is_key else Plain(text + (":" if last else "")))
        items.append((tuple(keys), action))
    return tuple(items)
