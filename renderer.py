import pygame
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, TILE_SIZE, FPS,
    TIMELINE_HEIGHT, TOOLBAR_WIDTH, BOTTOM_BAR_HEIGHT,
    TERRAIN_COLORS, OBJECT_COLORS,
)
from world import WorldState
from world_builder import WorldBuilder
from ui.bubbles import draw_bubble
from ui.timeline import draw_timeline
from ui.book import BookPanel


class Camera:
    def __init__(self):
        self.x = 0.0  # world pixel offset
        self.y = 0.0
        self.zoom = 1.0
        self._zoom_levels = [0.5, 1.0, 2.0]
        self._zoom_index = 1

    def pan(self, dx: float, dy: float):
        self.x += dx
        self.y += dy

    def zoom_in(self):
        if self._zoom_index < len(self._zoom_levels) - 1:
            self._zoom_index += 1
            self.zoom = self._zoom_levels[self._zoom_index]

    def zoom_out(self):
        if self._zoom_index > 0:
            self._zoom_index -= 1
            self.zoom = self._zoom_levels[self._zoom_index]

    def world_to_screen(self, wx: float, wy: float) -> tuple[int, int]:
        sx = int((wx - self.x) * self.zoom)
        sy = int((wy - self.y) * self.zoom) + TIMELINE_HEIGHT
        return sx, sy

    def screen_to_world(self, sx: int, sy: int) -> tuple[float, float]:
        wx = sx / self.zoom + self.x
        wy = (sy - TIMELINE_HEIGHT) / self.zoom + self.y
        return wx, wy


class Renderer:
    PAN_SPEED = 8.0

    def __init__(self, screen: pygame.Surface, world: WorldState):
        self.screen = screen
        self.world = world
        self.camera = Camera()
        self.font_sm = pygame.font.SysFont("monospace", 12)
        self.font_md = pygame.font.SysFont("monospace", 14)
        self.world_builder = WorldBuilder(world)
        self._book_open = False
        self._pillars_open = False
        self._book_panel = BookPanel()

    def handle_input(self, events: list):
        keys = pygame.key.get_pressed()
        dx = dy = 0.0
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: dx -= self.PAN_SPEED / self.camera.zoom
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: dx += self.PAN_SPEED / self.camera.zoom
        if keys[pygame.K_UP]    or keys[pygame.K_w]: dy -= self.PAN_SPEED / self.camera.zoom
        if keys[pygame.K_DOWN]  or keys[pygame.K_s]: dy += self.PAN_SPEED / self.camera.zoom
        if dx or dy:
            self.camera.pan(dx, dy)

        for event in events:
            if event.type == pygame.MOUSEWHEEL:
                if event.y > 0:
                    self.camera.zoom_in()
                else:
                    self.camera.zoom_out()
            if not self.world.sim_running:
                self.world_builder.handle_event(event, self.camera)
            else:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_b:
                        self._book_open = not self._book_open
                        self._book_panel.scroll_offset = 0
                    elif event.key == pygame.K_c:
                        self._pillars_open = not self._pillars_open
                    elif event.key == pygame.K_p:
                        self.world.paused = not self.world.paused
                # Speed button clicks
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    for i, s in enumerate([1, 2, 4]):
                        bx = SCREEN_WIDTH - 120 + i * 38
                        if bx < mx < bx + 32 and 6 < my < TIMELINE_HEIGHT - 6:
                            self.world.speed = s
                if self._book_open:
                    self._book_panel.handle_event(event)

    def draw(self):
        self.screen.fill((20, 20, 20))
        self._draw_terrain()
        self._draw_resources()
        self._draw_structures()
        self._draw_sims()
        if not self.world.sim_running:
            self.world_builder.draw_toolbar(self.screen)
        self._draw_timeline()
        self._draw_bottom_bar()
        if self._book_open:
            self._book_panel.draw(self.screen, self.world)

    def _draw_terrain(self):
        ts = int(TILE_SIZE * self.camera.zoom)
        with self.world.lock:
            terrain = [row[:] for row in self.world.terrain]
        rows = len(terrain)
        cols = len(terrain[0]) if rows else 0
        for r in range(rows):
            for c in range(cols):
                wx = c * TILE_SIZE
                wy = r * TILE_SIZE
                sx, sy = self.camera.world_to_screen(wx, wy)
                if -ts < sx < SCREEN_WIDTH and TIMELINE_HEIGHT - ts < sy < SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT:
                    color = TERRAIN_COLORS.get(terrain[r][c], (100, 100, 100))
                    pygame.draw.rect(self.screen, color, (sx, sy, ts, ts))

    def _draw_resources(self):
        ts = int(TILE_SIZE * self.camera.zoom)
        with self.world.lock:
            resources = list(self.world.resources.values())
        for res in resources:
            if res.depleted:
                continue
            sx, sy = self.camera.world_to_screen(res.position[0], res.position[1])
            color = OBJECT_COLORS.get(res.object_type, (200, 200, 200))
            r = max(4, ts // 3)
            pygame.draw.circle(self.screen, color, (sx + ts // 2, sy + ts // 2), r)

    def _draw_structures(self):
        ts = int(TILE_SIZE * self.camera.zoom)
        with self.world.lock:
            structures = list(self.world.structures.values())
        for struct in structures:
            sx, sy = self.camera.world_to_screen(struct.position[0], struct.position[1])
            pygame.draw.rect(self.screen, (139, 90, 43), (sx + 2, sy + 2, ts - 4, ts - 4))
            label = self.font_sm.render(struct.name[:3], True, (255, 255, 255))
            self.screen.blit(label, (sx + 4, sy + 4))

    def _draw_sims(self):
        ts = int(TILE_SIZE * self.camera.zoom)
        with self.world.lock:
            sims = list(self.world.sims.values())
        for sim in sims:
            if not sim.alive:
                continue
            sx, sy = self.camera.world_to_screen(sim.position[0], sim.position[1])
            r = max(6, ts // 2)
            pygame.draw.circle(self.screen, (255, 220, 150), (sx, sy), r)
            name_label = self.font_sm.render(sim.name, True, (255, 255, 255))
            self.screen.blit(name_label, (sx - name_label.get_width() // 2, sy - r - 14))
            if sim.thought_bubble and sim.thought_bubble.timer > 0:
                draw_bubble(self.screen, self.font_sm, sim.thought_bubble.text, sx, sy - r - 16, is_thought=True)
            if sim.speech_bubble and sim.speech_bubble.timer > 0:
                offset = -80 if sim.thought_bubble and sim.thought_bubble.timer > 0 else 0
                draw_bubble(self.screen, self.font_sm, sim.speech_bubble.text, sx, sy - r - 16 + offset, is_thought=False)

    def _draw_timeline(self):
        draw_timeline(self.screen, self.world, self.font_sm, self.font_md)

    def _draw_bottom_bar(self):
        by = SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT
        pygame.draw.rect(self.screen, (30, 30, 50), (0, by, SCREEN_WIDTH, BOTTOM_BAR_HEIGHT))
        hints = "[B] Book  [C] Pillars  [P] Pause  [ESC] Menu"
        lbl = self.font_sm.render(hints, True, (180, 180, 200))
        self.screen.blit(lbl, (10, by + BOTTOM_BAR_HEIGHT // 2 - lbl.get_height() // 2))
