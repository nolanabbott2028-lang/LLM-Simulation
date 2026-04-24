"""Shared colors and fonts for a modern dark UI."""
import pygame

# Background & surfaces
BG_APP = (15, 17, 24)
BG_PANEL = (24, 27, 38)
BG_PANEL_ELEV = (32, 36, 50)
BG_CANVAS = (18, 20, 28)
BORDER_SUBTLE = (45, 52, 72)
# Accents
ACCENT = (99, 102, 241)
ACCENT_DIM = (67, 71, 180)
ACCENT_MUTED = (79, 84, 200)
OK = (52, 211, 153)
DANGER = (248, 113, 113)
# Text
TEXT = (226, 232, 240)
TEXT_MUTED = (148, 163, 184)
# Timeline / bar
TL_BG_TOP = (22, 25, 35)
TL_BG_BOTTOM = (18, 20, 30)
ACCENT_GLOW = (79, 70, 230)


def try_font(sizes: tuple[int, ...], names: tuple[str, ...]) -> pygame.font.Font:
    for size in sizes:
        for n in names:
            try:
                f = pygame.font.SysFont(n, size)
                m = f.render("Mm", True, (255, 255, 255))
                if m.get_width() > 0:
                    return f
            except (OSError, AttributeError, TypeError, ValueError):
                continue
    return pygame.font.Font(None, 16)


def load_ui_fonts() -> tuple[pygame.font.Font, pygame.font.Font, pygame.font.Font]:
    """(small, body, title) with sensible cross-platform font fallbacks."""
    names = (
        "Helvetica Neue",
        "Helvetica",
        "Segoe UI",
        "Arial",
    )
    sm = try_font((12, 13), names)
    md = try_font((14, 15), names)
    lg = try_font((16, 18), names)
    return sm, md, lg
