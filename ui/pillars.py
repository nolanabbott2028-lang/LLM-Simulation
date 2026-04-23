import pygame
from config import SCREEN_WIDTH, SCREEN_HEIGHT, TIMELINE_HEIGHT, BOTTOM_BAR_HEIGHT, PILLAR_NAMES
from world import WorldState


PANEL_W = 220
PANEL_H = len(PILLAR_NAMES) * 28 + 40
PANEL_X = SCREEN_WIDTH - PANEL_W - 10
PANEL_Y = TIMELINE_HEIGHT + 10


def draw_pillars(screen: pygame.Surface, world: WorldState, font: pygame.font.Font):
    surface = pygame.Surface((PANEL_W, PANEL_H), pygame.SRCALPHA)
    surface.fill((20, 18, 30, 210))
    screen.blit(surface, (PANEL_X, PANEL_Y))
    pygame.draw.rect(screen, (100, 80, 160), (PANEL_X, PANEL_Y, PANEL_W, PANEL_H), 2, border_radius=6)

    title = font.render("Civilization", True, (200, 180, 255))
    screen.blit(title, (PANEL_X + PANEL_W // 2 - title.get_width() // 2, PANEL_Y + 6))

    with world.lock:
        pillars = dict(world.pillars)

    for i, name in enumerate(PILLAR_NAMES):
        y = PANEL_Y + 28 + i * 28
        val = pillars.get(name, 0)
        bar_w = int((PANEL_W - 90) * val / 100)
        bar_color = (60, 180, 100) if val >= 50 else (180, 120, 40)
        pygame.draw.rect(screen, (40, 40, 60), (PANEL_X + 80, y + 4, PANEL_W - 90, 14), border_radius=3)
        if bar_w > 0:
            pygame.draw.rect(screen, bar_color, (PANEL_X + 80, y + 4, bar_w, 14), border_radius=3)
        lbl = font.render(name[:12], True, (180, 170, 210))
        screen.blit(lbl, (PANEL_X + 4, y + 4))
