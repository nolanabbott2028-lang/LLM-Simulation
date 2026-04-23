import pygame
from entities.sim import Sim, Bubble
from config import TILE_SIZE


def draw_bubble(screen: pygame.Surface, font: pygame.font.Font,
                text: str, sx: int, sy: int, is_thought: bool):
    if not text:
        return
    padding = 6
    max_chars = 30
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = (current + " " + word).strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    line_surfaces = [font.render(l, True, (20, 20, 20)) for l in lines]
    w = max(s.get_width() for s in line_surfaces) + padding * 2
    h = sum(s.get_height() for s in line_surfaces) + padding * 2

    bx = sx - w // 2
    by = sy - h - 18

    bg_color = (240, 240, 255) if not is_thought else (220, 255, 220)
    border_color = (100, 100, 180) if not is_thought else (80, 160, 80)
    pygame.draw.rect(screen, bg_color, (bx, by, w, h), border_radius=8)
    pygame.draw.rect(screen, border_color, (bx, by, w, h), 2, border_radius=8)

    tail_x = sx
    tail_y = by + h
    if is_thought:
        for i in range(3):
            pygame.draw.circle(screen, bg_color, (tail_x, tail_y + 4 + i * 5), 3)
            pygame.draw.circle(screen, border_color, (tail_x, tail_y + 4 + i * 5), 3, 1)
    else:
        pygame.draw.polygon(screen, bg_color, [
            (tail_x - 6, tail_y), (tail_x + 6, tail_y), (tail_x, tail_y + 10)
        ])
        pygame.draw.lines(screen, border_color, False, [
            (tail_x - 6, tail_y), (tail_x, tail_y + 10), (tail_x + 6, tail_y)
        ], 2)

    y_offset = by + padding
    for surf in line_surfaces:
        screen.blit(surf, (bx + padding, y_offset))
        y_offset += surf.get_height()
