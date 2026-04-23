import pygame
from config import SCREEN_WIDTH, TIMELINE_HEIGHT
from world import WorldState


def draw_timeline(screen: pygame.Surface, world: WorldState,
                  font_sm: pygame.font.Font, font_md: pygame.font.Font):
    pygame.draw.rect(screen, (30, 30, 50), (0, 0, SCREEN_WIDTH, TIMELINE_HEIGHT))

    with world.lock:
        year = world.sim_year
        day = world.sim_day
        era = world.current_era()
        speed = world.speed
        entries = list(world.book_entries)

    text = f"Year {year}, Day {day}  |  {era}"
    label = font_md.render(text, True, (220, 220, 255))
    screen.blit(label, (10, TIMELINE_HEIGHT // 2 - label.get_height() // 2))

    marker_start = label.get_width() + 20
    marker_end = SCREEN_WIDTH - 130
    marker_width = marker_end - marker_start
    total_days = max(1, year * 365 + day)

    milestone_entries = [e for e in entries if e["tab"] in ("History", "Technology", "Laws", "Culture", "People")]
    for entry in milestone_entries[-20:]:
        entry_day = entry["year"] * 365 + entry["day"]
        frac = min(1.0, entry_day / total_days)
        mx = int(marker_start + frac * marker_width)
        pygame.draw.circle(screen, (255, 200, 50), (mx, TIMELINE_HEIGHT // 2), 4)

    for i, s in enumerate([1, 2, 4]):
        color = (80, 160, 80) if speed == s else (60, 60, 80)
        bx = SCREEN_WIDTH - 120 + i * 38
        by = 6
        pygame.draw.rect(screen, color, (bx, by, 32, TIMELINE_HEIGHT - 12), border_radius=4)
        lbl = font_sm.render(f"{s}x", True, (255, 255, 255))
        screen.blit(lbl, (bx + 8, by + 6))

    mx, my = pygame.mouse.get_pos()
    if 0 < my < TIMELINE_HEIGHT:
        for entry in milestone_entries[-20:]:
            entry_day = entry["year"] * 365 + entry["day"]
            frac = min(1.0, entry_day / total_days)
            emx = int(marker_start + frac * marker_width)
            if abs(mx - emx) < 8:
                tip = font_sm.render(entry["title"], True, (255, 255, 200))
                tip_bg = pygame.Surface((tip.get_width() + 8, tip.get_height() + 4))
                tip_bg.fill((40, 40, 60))
                screen.blit(tip_bg, (emx - 4, TIMELINE_HEIGHT + 2))
                screen.blit(tip, (emx, TIMELINE_HEIGHT + 4))
                break
