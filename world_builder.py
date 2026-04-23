import pygame
from config import (
    TILE_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT,
    TIMELINE_HEIGHT, TOOLBAR_WIDTH, BOTTOM_BAR_HEIGHT,
    TERRAIN_COLORS, OBJECT_COLORS,
)
from world import WorldState
from entities.resource import ResourceObject
import uuid


TERRAIN_BRUSHES = ["grass", "forest", "water", "mountain", "desert", "snow"]
OBJECT_BRUSHES = ["berry_bush", "stone_deposit", "tree", "river_source",
                  "animal_spawn", "hut", "shrine", "farm_plot"]
BRUSH_SIZES = [1, 2, 3, 4, 5]


class WorldBuilder:
    def __init__(self, world: WorldState):
        self.world = world
        self.phase = "terrain"       # "terrain" | "objects" | "spawn"
        self.selected_brush = "grass"
        self.brush_size = 1
        self.font = pygame.font.SysFont("monospace", 13)
        self.spawn_waiting = False   # True after "Begin Civilization" clicked

    def handle_event(self, event: pygame.event.Event, camera) -> bool:
        """Returns True if event was consumed."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            # Toolbar click
            if mx < TOOLBAR_WIDTH:
                self._handle_toolbar_click(mx, my)
                return True
            # Canvas click
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
            if mx >= TOOLBAR_WIDTH and my > TIMELINE_HEIGHT and my < SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT:
                wx, wy = camera.screen_to_world(mx, my)
                if self.phase == "terrain":
                    self._paint_terrain(wx, wy)
                return True
        return False

    def _handle_toolbar_click(self, mx: int, my: int):
        # Phase toggle buttons at top
        if 50 < my < 70:
            self.phase = "terrain"
        elif 75 < my < 95:
            self.phase = "objects"
        # Brush buttons
        brushes = TERRAIN_BRUSHES if self.phase == "terrain" else OBJECT_BRUSHES
        for i, b in enumerate(brushes):
            btn_y = 110 + i * 28
            if btn_y < my < btn_y + 24:
                self.selected_brush = b
        # Brush size
        for i, s in enumerate(BRUSH_SIZES):
            bx = 10 + i * 26
            if bx < mx < bx + 22 and 310 < my < 332:
                self.brush_size = s
        # Begin Civilization button
        if 20 < mx < TOOLBAR_WIDTH - 20 and SCREEN_HEIGHT - 120 < my < SCREEN_HEIGHT - 90:
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

    def draw_toolbar(self, screen: pygame.Surface):
        pygame.draw.rect(screen, (25, 25, 45), (0, TIMELINE_HEIGHT, TOOLBAR_WIDTH, SCREEN_HEIGHT - TIMELINE_HEIGHT))
        f = self.font

        # Phase buttons
        for i, (label, phase) in enumerate([("Terrain", "terrain"), ("Objects", "objects")]):
            color = (60, 120, 60) if self.phase == phase else (50, 50, 70)
            pygame.draw.rect(screen, color, (5, TIMELINE_HEIGHT + 5 + i * 28, TOOLBAR_WIDTH - 10, 22), border_radius=3)
            lbl = f.render(label, True, (220, 220, 220))
            screen.blit(lbl, (10, TIMELINE_HEIGHT + 9 + i * 28))

        # Brush list
        brushes = TERRAIN_BRUSHES if self.phase in ("terrain",) else OBJECT_BRUSHES
        for i, b in enumerate(brushes):
            by = TIMELINE_HEIGHT + 70 + i * 28
            color = (80, 150, 80) if b == self.selected_brush else (40, 40, 60)
            pygame.draw.rect(screen, color, (5, by, TOOLBAR_WIDTH - 10, 22), border_radius=3)
            dot_color = TERRAIN_COLORS.get(b) or OBJECT_COLORS.get(b, (200, 200, 200))
            pygame.draw.circle(screen, dot_color, (18, by + 11), 7)
            lbl = f.render(b.replace("_", " ").title()[:14], True, (220, 220, 220))
            screen.blit(lbl, (30, by + 4))

        # Brush size (terrain only)
        if self.phase == "terrain":
            size_y = TIMELINE_HEIGHT + 70 + len(brushes) * 28 + 10
            screen.blit(f.render("Size:", True, (180, 180, 200)), (10, size_y))
            for i, s in enumerate(BRUSH_SIZES):
                bx = 10 + i * 26
                color = (80, 150, 80) if s == self.brush_size else (50, 50, 70)
                pygame.draw.rect(screen, color, (bx, size_y + 18, 22, 22), border_radius=3)
                lbl = f.render(str(s), True, (255, 255, 255))
                screen.blit(lbl, (bx + 6, size_y + 22))

        # Begin Civilization button
        btn_color = (100, 60, 160) if self.phase == "spawn" else (70, 40, 120)
        pygame.draw.rect(screen, btn_color, (10, SCREEN_HEIGHT - 130, TOOLBAR_WIDTH - 20, 32), border_radius=5)
        lbl = f.render("Begin Civ.", True, (255, 240, 255))
        screen.blit(lbl, (18, SCREEN_HEIGHT - 122))

        if self.spawn_waiting:
            hint = f.render("Click to spawn", True, (200, 255, 200))
            screen.blit(hint, (5, SCREEN_HEIGHT - 90))
