import pygame
from config import SCREEN_WIDTH, SCREEN_HEIGHT, TIMELINE_HEIGHT, BOTTOM_BAR_HEIGHT, PILLAR_NAMES
from world import WorldState
from ui import theme


PANEL_W = 230
PANEL_H = len(PILLAR_NAMES) * 28 + 44
PANEL_X = SCREEN_WIDTH - PANEL_W - 10
PANEL_Y = TIMELINE_HEIGHT + 10


def draw_pillars(screen: pygame.Surface, world: WorldState, font: pygame.font.Font):
    surface = pygame.Surface((PANEL_W, PANEL_H), pygame.SRCALPHA)
    surface.fill((*theme.BG_PANEL, 230))
    screen.blit(surface, (PANEL_X, PANEL_Y))
    pygame.draw.rect(screen, theme.BORDER_SUBTLE, (PANEL_X, PANEL_Y, PANEL_W, PANEL_H), 1, border_radius=8)

    title = font.render("Pillars", True, theme.TEXT)
    screen.blit(title, (PANEL_X + PANEL_W // 2 - title.get_width() // 2, PANEL_Y + 8))

    with world.lock:
        pillars = dict(world.pillars)

    for i, name in enumerate(PILLAR_NAMES):
        y = PANEL_Y + 32 + i * 28
        val = pillars.get(name, 0)
        bar_w = int((PANEL_W - 92) * val / 100)
        bar_color = theme.OK if val >= 50 else (251, 191, 36)
        pygame.draw.rect(screen, (40, 44, 58), (PANEL_X + 82, y + 4, PANEL_W - 92, 14), border_radius=4)
        if bar_w > 0:
            pygame.draw.rect(screen, bar_color, (PANEL_X + 82, y + 4, bar_w, 14), border_radius=4)
        short = name[:14] + ("…" if len(name) > 14 else "")
        lbl = font.render(short, True, theme.TEXT_MUTED)
        screen.blit(lbl, (PANEL_X + 6, y + 4))
