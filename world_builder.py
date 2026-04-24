import pygame
from config import (
    TILE_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT,
    TIMELINE_HEIGHT, TOOLBAR_WIDTH, BOTTOM_BAR_HEIGHT,
    TERRAIN_COLORS, OBJECT_COLORS,
)
from world import WorldState
from entities.resource import ResourceObject
from ui import theme
import uuid


TERRAIN_BRUSHES = ["grass", "forest", "water", "mountain", "desert", "snow"]
OBJECT_BRUSHES = [
    "berry_bush", "stone_deposit", "tree", "river_source",
    "animal_spawn", "hut", "shrine", "farm_plot",
]
BRUSH_SIZES = [1, 2, 3, 4, 5]


def _rrect(surf, r: pygame.Rect, color, rad: int, width: int = 0) -> None:
    pygame.draw.rect(surf, color, r, width, border_radius=rad)


class WorldBuilder:
    def __init__(self, world: WorldState, font_sm, font_md):
        self.world = world
        self.font = font_sm
        self.font_md = font_md
        self.phase = "terrain"
        self.selected_brush = "grass"
        self.brush_size = 1
        self.spawn_waiting = False

    def _phase_rects(self) -> tuple[pygame.Rect, pygame.Rect]:
        t0 = TIMELINE_HEIGHT + 8
        w = TOOLBAR_WIDTH - 20
        r0 = pygame.Rect(10, t0, w, 28)
        r1 = pygame.Rect(10, t0 + 34, w, 28)
        return r0, r1

    def handle_event(self, event: pygame.event.Event, camera) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if mx < TOOLBAR_WIDTH:
                self._handle_toolbar_click(mx, my)
                return True
            if my > TIMELINE_HEIGHT and my < SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT:
                wx, wy = camera.screen_to_world(mx, my)
                if self.phase == "terrain":
                    self._paint_terrain(wx, wy)
                elif self.phase == "objects":
                    self._place_object(wx, wy)
                elif self.phase == "spawn":
                    self._spawn_sims(wx, wy)
                return True
        if event.type == pygame.MOUSEMOTION and pygame.mouse.get_pressed()[0]:
            mx, my = event.pos
            if (
                mx >= TOOLBAR_WIDTH
                and my > TIMELINE_HEIGHT
                and my < SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT
            ):
                wx, wy = camera.screen_to_world(mx, my)
                if self.phase == "terrain":
                    self._paint_terrain(wx, wy)
                return True
        return False

    def _handle_toolbar_click(self, mx: int, my: int) -> None:
        r0, r1 = self._phase_rects()
        if r0.collidepoint(mx, my):
            self.phase = "terrain"
            return
        if r1.collidepoint(mx, my):
            self.phase = "objects"
            return

        brushes = TERRAIN_BRUSHES if self.phase == "terrain" else OBJECT_BRUSHES
        row_h = 30
        start_y = r1.bottom + 12
        for i, b in enumerate(brushes):
            by = start_y + i * row_h
            br = pygame.Rect(8, by, TOOLBAR_WIDTH - 16, 26)
            if br.collidepoint(mx, my):
                self.selected_brush = b
                return

        if self.phase == "terrain":
            list_bottom = start_y + len(brushes) * row_h
            size_y = list_bottom + 6
            for i, s in enumerate(BRUSH_SIZES):
                bx = 10 + i * 30
                if (
                    bx < mx < bx + 28
                    and size_y + 16 < my < size_y + 16 + 28
                ):
                    self.brush_size = s
                    return

        begin = pygame.Rect(12, SCREEN_HEIGHT - 128, TOOLBAR_WIDTH - 24, 36)
        if begin.collidepoint(mx, my):
            self.phase = "spawn"
            self.spawn_waiting = True

    def _paint_terrain(self, wx: float, wy: float):
        col = int(wx / TILE_SIZE)
        row = int(wy / TILE_SIZE)
        half = self.brush_size // 2
        from config import WORLD_TILES_W, WORLD_TILES_H
        for dr in range(-half, half + 1):
            for dc in range(-half, half + 1):
                r, c = row + dr, col + dc
                if 0 <= r < WORLD_TILES_H and 0 <= c < WORLD_TILES_W:
                    self.world.set_terrain(r, c, self.selected_brush)

    def _place_object(self, wx: float, wy: float):
        obj = ResourceObject(
            id=str(uuid.uuid4())[:8],
            object_type=self.selected_brush,
            position=(wx, wy),
            quantity=10,
        )
        self.world.add_resource(obj)

    def _spawn_sims(self, wx: float, wy: float):
        from entities.sim import Sim
        s1 = Sim(id="adam", name="Adam", position=(wx, wy))
        s2 = Sim(id="eve",  name="Eve",  position=(wx + TILE_SIZE * 1.5, wy))
        self.world.add_sim(s1)
        self.world.add_sim(s2)
        self.world.sim_running = True
        self.phase = "done"
        self.spawn_waiting = False

    def draw_toolbar(self, screen: pygame.Surface) -> None:
        panel = pygame.Rect(0, TIMELINE_HEIGHT, TOOLBAR_WIDTH, SCREEN_HEIGHT - TIMELINE_HEIGHT)
        _rrect(screen, panel, theme.BG_PANEL, 0, 0)
        pygame.draw.line(
            screen, theme.BORDER_SUBTLE, (TOOLBAR_WIDTH - 1, TIMELINE_HEIGHT), (TOOLBAR_WIDTH - 1, SCREEN_HEIGHT)
        )
        f, fm = self.font, self.font_md
        hlabel = fm.render("Build", True, theme.TEXT)
        screen.blit(hlabel, (14, TIMELINE_HEIGHT + 4))

        r0, r1 = self._phase_rects()
        for rect, (label, phase) in (
            (r0, ("Terrain", "terrain")),
            (r1, ("Objects", "objects")),
        ):
            on = self.phase == phase
            _rrect(
                screen, rect,
                theme.ACCENT if on else theme.BG_PANEL_ELEV, 6, 0
            )
            if on:
                _rrect(screen, rect, theme.ACCENT_MUTED, 6, 2)
            t = f.render(label, True, theme.TEXT)
            screen.blit(t, (rect.x + 10, rect.y + rect.h // 2 - t.get_height() // 2))

        brushes = TERRAIN_BRUSHES if self.phase == "terrain" else OBJECT_BRUSHES
        row_h = 30
        start_y = r1.bottom + 12
        for i, b in enumerate(brushes):
            by = start_y + i * row_h
            rect = pygame.Rect(8, by, TOOLBAR_WIDTH - 16, 26)
            on = b == self.selected_brush
            _rrect(screen, rect, theme.ACCENT_DIM if on else theme.BG_PANEL_ELEV, 5, 0)
            if on:
                _rrect(screen, rect, theme.ACCENT, 5, 1)
            dot = TERRAIN_COLORS.get(b) or OBJECT_COLORS.get(b, (200, 200, 200))
            pygame.draw.circle(screen, dot, (rect.x + 16, rect.centery), 6)
            lbl = f.render(b.replace("_", " ").title()[:14], True, theme.TEXT)
            screen.blit(lbl, (rect.x + 28, rect.y + 5))

        if self.phase == "terrain":
            list_bottom = start_y + len(brushes) * row_h
            size_y = list_bottom + 4
            screen.blit(f.render("Brush size", True, theme.TEXT_MUTED), (10, size_y))
            for i, s in enumerate(BRUSH_SIZES):
                bx = 10 + i * 30
                brect = pygame.Rect(bx, size_y + 18, 28, 28)
                on = s == self.brush_size
                _rrect(screen, brect, theme.OK if on else theme.BG_PANEL_ELEV, 4, 0)
                t = f.render(str(s), True, theme.TEXT)
                screen.blit(
                    t,
                    (
                        brect.centerx - t.get_width() // 2,
                        brect.centery - t.get_height() // 2,
                    ),
                )

        begin = pygame.Rect(12, SCREEN_HEIGHT - 128, TOOLBAR_WIDTH - 24, 36)
        _rrect(
            screen, begin,
            theme.ACCENT if self.phase == "spawn" else theme.ACCENT_MUTED, 7, 0
        )
        t = f.render("Begin civ.", True, (255, 255, 255))
        screen.blit(
            t,
            (begin.centerx - t.get_width() // 2, begin.centery - t.get_height() // 2),
        )

        if self.spawn_waiting:
            hint = f.render("Click on the map to place both people", True, theme.OK)
            screen.blit(hint, (10, SCREEN_HEIGHT - 84))
