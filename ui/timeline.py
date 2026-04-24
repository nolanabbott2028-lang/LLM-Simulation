import pygame
from config import SCREEN_WIDTH, TIMELINE_HEIGHT
from world import WorldState
from ui import theme


def draw_timeline(
    screen: pygame.Surface, world: WorldState,
    font_sm: pygame.font.Font, font_md: pygame.font.Font,
) -> None:
    h = TIMELINE_HEIGHT
    for y in range(h):
        t = y / max(1, h - 1)
        c1 = theme.TL_BG_TOP
        c2 = theme.TL_BG_BOTTOM
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g_ = int(c1[1] + (c2[1] - c1[1]) * t)
        b_ = int(c1[2] + (c2[2] - c1[2]) * t)
        pygame.draw.line(screen, (r, g_, b_), (0, y), (SCREEN_WIDTH, y))
    pygame.draw.line(screen, theme.BORDER_SUBTLE, (0, h - 1), (SCREEN_WIDTH, h - 1), 1)

    with world.lock:
        year = world.sim_year
        day = world.sim_day
        era = world.current_era()
        speed = world.speed
        entries = list(world.book_entries)

    text = f"Year {year}  ·  Day {day}   {era}"
    label = font_md.render(text, True, theme.TEXT)
    screen.blit(label, (16, h // 2 - label.get_height() // 2))

    marker_start = label.get_width() + 28
    marker_end = SCREEN_WIDTH - 128
    marker_width = max(1, marker_end - marker_start)
    total_days = max(1, year * 365 + day)

    milestone_entries = [e for e in entries if e["tab"] in (
        "History", "Technology", "Laws", "Culture", "People", "Language",
    )]
    for entry in milestone_entries[-20:]:
        entry_day = entry["year"] * 365 + entry["day"]
        frac = min(1.0, entry_day / total_days)
        mx = int(marker_start + frac * marker_width)
        pygame.draw.circle(screen, (251, 191, 36), (mx, h // 2), 3)
        pygame.draw.circle(screen, (120, 90, 20), (mx, h // 2), 3, 1)

    for i, s in enumerate((1, 2, 4)):
        on = speed == s
        bx = SCREEN_WIDTH - 116 + i * 38
        by = 7
        rect = pygame.Rect(bx, by, 32, h - 14)
        col = theme.ACCENT if on else theme.BG_PANEL_ELEV
        pygame.draw.rect(screen, col, rect, border_radius=6)
        if on:
            pygame.draw.rect(screen, theme.ACCENT_MUTED, rect, 1, border_radius=6)
        lbl = font_sm.render(f"{s}×", True, theme.TEXT if on else theme.TEXT_MUTED)
        screen.blit(lbl, (bx + 9, by + 3))

    mx, my = pygame.mouse.get_pos()
    if 0 < my < h:
        for entry in milestone_entries[-20:]:
            entry_day = entry["year"] * 365 + entry["day"]
            frac = min(1.0, entry_day / total_days)
            emx = int(marker_start + frac * marker_width)
            if abs(mx - emx) < 8:
                tip = font_sm.render(entry["title"], True, theme.TEXT)
                tw, th = tip.get_width() + 10, tip.get_height() + 6
                pad = pygame.Rect(emx - tw // 2, h + 2, tw, th)
                pygame.draw.rect(screen, theme.BG_PANEL_ELEV, pad, border_radius=4)
                pygame.draw.rect(screen, theme.BORDER_SUBTLE, pad, 1, border_radius=4)
                screen.blit(tip, (pad.x + 5, pad.y + 3))
                break
