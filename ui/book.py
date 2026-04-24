import pygame
from config import SCREEN_WIDTH, SCREEN_HEIGHT, TIMELINE_HEIGHT, BOTTOM_BAR_HEIGHT
from world import WorldState


TABS = ["History", "Technology", "Laws", "People", "Culture", "Language"]
TAB_W = 88
PANEL_W = min(560, SCREEN_WIDTH - 40)
PANEL_H = SCREEN_HEIGHT - TIMELINE_HEIGHT - BOTTOM_BAR_HEIGHT - 20
PANEL_X = (SCREEN_WIDTH - PANEL_W) // 2
PANEL_Y = TIMELINE_HEIGHT + 10


class BookPanel:
    def __init__(self):
        self.active_tab = "History"
        self.scroll_offset = 0
        self.font_title = pygame.font.SysFont("helveticaneue", 14, bold=True)
        self.font_body = pygame.font.SysFont("helveticaneue", 12)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            if PANEL_X < mx < PANEL_X + PANEL_W and PANEL_Y < my < PANEL_Y + PANEL_H:
                self.scroll_offset = max(0, self.scroll_offset - event.y * 20)
                return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            tab_y = PANEL_Y + 8
            for i, tab in enumerate(TABS):
                tx = PANEL_X + 8 + i * TAB_W
                if tx < mx < tx + TAB_W - 4 and tab_y < my < tab_y + 24:
                    self.active_tab = tab
                    self.scroll_offset = 0
                    return True
        return False

    def draw(self, screen: pygame.Surface, world: WorldState):
        surface = pygame.Surface((PANEL_W, PANEL_H), pygame.SRCALPHA)
        surface.fill((24, 27, 38, 235))
        screen.blit(surface, (PANEL_X, PANEL_Y))
        pygame.draw.rect(screen, (99, 102, 241), (PANEL_X, PANEL_Y, PANEL_W, PANEL_H), 2, border_radius=10)

        title = self.font_title.render("Civilization Book", True, (226, 232, 240))
        screen.blit(title, (PANEL_X + PANEL_W // 2 - title.get_width() // 2, PANEL_Y + 6))

        for i, tab in enumerate(TABS):
            tx = PANEL_X + 8 + i * TAB_W
            ty = PANEL_Y + 28
            color = (67, 71, 180) if tab == self.active_tab else (40, 44, 62)
            pygame.draw.rect(screen, color, (tx, ty, TAB_W - 4, 22), border_radius=5)
            lbl = self.font_body.render(tab, True, (226, 232, 240))
            screen.blit(lbl, (tx + 6, ty + 4))

        with world.lock:
            entries = [e for e in world.book_entries if e["tab"] == self.active_tab]

        content_y = PANEL_Y + 58 - self.scroll_offset
        clip_rect = pygame.Rect(PANEL_X + 4, PANEL_Y + 58, PANEL_W - 8, PANEL_H - 62)
        screen.set_clip(clip_rect)

        for entry in reversed(entries):
            header = f"Year {entry['year']}, Day {entry['day']} — {entry['title']}"
            h_surf = self.font_title.render(header, True, (199, 210, 254))
            if PANEL_Y + 58 <= content_y < PANEL_Y + PANEL_H:
                screen.blit(h_surf, (PANEL_X + 10, content_y))
            content_y += h_surf.get_height() + 2

            body = entry["body"]
            words = body.split()
            line = ""
            max_chars = 62
            for word in words:
                if len(line) + len(word) + 1 <= max_chars:
                    line = (line + " " + word).strip()
                else:
                    b_surf = self.font_body.render(line, True, (180, 190, 210))
                    if PANEL_Y + 58 <= content_y < PANEL_Y + PANEL_H:
                        screen.blit(b_surf, (PANEL_X + 14, content_y))
                    content_y += b_surf.get_height()
                    line = word
            if line:
                b_surf = self.font_body.render(line, True, (180, 190, 210))
                if PANEL_Y + 58 <= content_y < PANEL_Y + PANEL_H:
                    screen.blit(b_surf, (PANEL_X + 14, content_y))
                content_y += b_surf.get_height()
            content_y += 12

        screen.set_clip(None)
