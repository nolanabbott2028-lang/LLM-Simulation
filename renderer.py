import pygame
import os
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, TILE_SIZE, FPS,
    TIMELINE_HEIGHT, TOOLBAR_WIDTH, BOTTOM_BAR_HEIGHT, UI_MAP_PADDING,
    TERRAIN_COLORS, OBJECT_COLORS,
    SIM_SPRITE_IDLE, SIM_SPRITE_WALK, SIM_SPRITE_SWIM, SIM_SPRITE_BASE_HEIGHT,
)
from world import WorldState
from world_builder import WorldBuilder
from map_context import map_surface_for_render, world_pixel_size
from ui import theme
from ui.bubbles import draw_bubble
from ui.timeline import draw_timeline
from ui.book import BookPanel
from ui.pillars import draw_pillars
from ui.inspector import draw_inspector
from persistence import save_world, load_world
import os as _os


ZOOM_IN_FACTOR = 1.18
ZOOM_OUT_DIVISOR = 1.18
ZOOM_MAX = 2.0
ZOOM_MIN = 0.04  # can zoom out from initial fit; enough to see context


class Camera:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.zoom = 1.0
        # Map is drawn in this screen rectangle (excludes timeline, toolbars, padding)
        self._vx = 0
        self._vy = 0
        self._vw = SCREEN_WIDTH
        self._vh = 600

    def set_viewport(self, vx: int, vy: int, vw: int, vh: int) -> None:
        self._vx = vx
        self._vy = vy
        self._vw = max(1, vw)
        self._vh = max(1, vh)

    def fit_world_map(
        self, world_w: int, world_h: int, view_w: int, view_h: int
    ) -> None:
        if world_w <= 0 or world_h <= 0 or view_w <= 0 or view_h <= 0:
            return
        self.zoom = min(view_w / world_w, view_h / world_h)
        self.x = 0.0
        self.y = 0.0

    def pan(self, dx: float, dy: float):
        self.x += dx
        self.y += dy

    def zoom_in(self):
        self.zoom = min(ZOOM_MAX, self.zoom * ZOOM_IN_FACTOR)

    def zoom_out(self):
        self.zoom = max(ZOOM_MIN, self.zoom / ZOOM_OUT_DIVISOR)

    def world_to_screen(self, wx: float, wy: float) -> tuple[int, int]:
        sx = int((wx - self.x) * self.zoom) + self._vx
        sy = int((wy - self.y) * self.zoom) + self._vy
        return sx, sy

    def screen_to_world(self, sx: int, sy: int) -> tuple[float, float]:
        wx = (sx - self._vx) / self.zoom + self.x
        wy = (sy - self._vy) / self.zoom + self.y
        return wx, wy


class Renderer:
    PAN_SPEED = 8.0

    def __init__(self, screen: pygame.Surface, world: WorldState):
        self.screen = screen
        self.world = world
        self.font_sm, self.font_md, self.font_lg = theme.load_ui_fonts()
        self.camera = Camera()
        self._canvas_rect = pygame.Rect(0, 0, 1, 1)
        self._sync_viewport()
        self.world_builder = WorldBuilder(world, self.font_sm, self.font_md)
        self._book_open = False
        self._pillars_open = False
        self._book_panel = BookPanel()
        self._inspected_sim_id = None
        self._spr_idle, self._spr_walk, self._spr_swim = self._load_sim_sprites()
        self._fit_camera_to_map()

    def _sync_viewport(self) -> None:
        """Map content lives in a padded region to the right of the builder toolbar (or full width in sim)."""
        p = UI_MAP_PADDING
        top = TIMELINE_HEIGHT + p
        bottom_pad = p
        if not self.world.sim_running:
            left = TOOLBAR_WIDTH + p
            vw = SCREEN_WIDTH - TOOLBAR_WIDTH - 2 * p
        else:
            left = p
            vw = SCREEN_WIDTH - 2 * p
        vh = SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT - top - bottom_pad
        vw = max(1, int(vw))
        vh = max(1, int(vh))
        self._canvas_rect = pygame.Rect(left, top, vw, vh)
        self.camera.set_viewport(left, top, vw, vh)

    def _fit_camera_to_map(self) -> None:
        self._sync_viewport()
        W, H = world_pixel_size()
        self.camera.fit_world_map(W, H, self._canvas_rect.w, self._canvas_rect.h)

    def _load_sim_sprites(self) -> tuple:
        out = []
        for path in (SIM_SPRITE_IDLE, SIM_SPRITE_WALK, SIM_SPRITE_SWIM):
            if os.path.isfile(path):
                s = pygame.image.load(path).convert_alpha()
                out.append(s)
            else:
                out.append(None)
        return (out[0], out[1], out[2])

    def handle_input(self, events: list):
        self._sync_viewport()
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
                mx, my = pygame.mouse.get_pos()
                if self._canvas_rect.collidepoint(mx, my):
                    if event.y > 0:
                        self.camera.zoom_in()
                    else:
                        self.camera.zoom_out()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_HOME:
                self._fit_camera_to_map()
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
                    elif event.key == pygame.K_F5:
                        save_world(self.world, "savegame.json")
                    elif event.key == pygame.K_F9:
                        if _os.path.exists("savegame.json"):
                            loaded = load_world("savegame.json")
                            with self.world.lock:
                                for k, v in loaded.__dict__.items():
                                    if k != "lock":
                                        setattr(self.world, k, v)
                # Speed button clicks
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    for i, s in enumerate([1, 2, 4]):
                        bx = SCREEN_WIDTH - 116 + i * 38
                        if bx < mx < bx + 32 and 6 < my < TIMELINE_HEIGHT - 6:
                            self.world.speed = s
                    hpx = int(SIM_SPRITE_BASE_HEIGHT * self.camera.zoom)
                    r_hit = max(14, hpx * 0.28)
                    with self.world.lock:
                        sims = list(self.world.sims.values())
                    clicked_sim = None
                    for sim in sims:
                        if not sim.alive:
                            continue
                        sx, sy = self.camera.world_to_screen(sim.position[0], sim.position[1])
                        mcx, mcy = sx, sy - hpx // 2
                        if ((mx - mcx) ** 2 + (my - mcy) ** 2) ** 0.5 < r_hit + 10:
                            clicked_sim = sim
                            break
                    if clicked_sim:
                        self._inspected_sim_id = clicked_sim.id if self._inspected_sim_id != clicked_sim.id else None
                if self._book_open:
                    self._book_panel.handle_event(event)

    def draw(self):
        self._sync_viewport()
        self.screen.fill(theme.BG_APP)
        pygame.draw.rect(self.screen, theme.BG_CANVAS, self._canvas_rect, border_radius=10)
        pygame.draw.rect(self.screen, theme.BORDER_SUBTLE, self._canvas_rect, 1, border_radius=10)
        prev = self.screen.get_clip()
        self.screen.set_clip(self._canvas_rect)
        self._draw_terrain()
        self._draw_resources()
        self._draw_structures()
        self._draw_sims()
        self.screen.set_clip(prev)
        if not self.world.sim_running:
            self.world_builder.draw_toolbar(self.screen)
        self._draw_timeline()
        self._draw_bottom_bar()
        if self._book_open:
            self._book_panel.draw(self.screen, self.world)
        if self._pillars_open:
            draw_pillars(self.screen, self.world, self.font_sm)
        if self._inspected_sim_id:
            with self.world.lock:
                sim = self.world.sims.get(self._inspected_sim_id)
            if sim and sim.alive:
                draw_inspector(self.screen, sim, self.world, self.font_sm, self.font_md)
            else:
                self._inspected_sim_id = None

    def _draw_terrain(self):
        map_surf = map_surface_for_render()
        cr = self._canvas_rect
        if map_surf is not None and cr.h > 0 and cr.w > 0:
            W, H = world_pixel_size()
            zw = cr.w / self.camera.zoom
            zh = cr.h / self.camera.zoom
            x0 = max(0, int(self.camera.x))
            y0 = max(0, int(self.camera.y))
            subw = min(int(zw), W - x0)
            subh = min(int(zh), H - y0)
            if subw > 0 and subh > 0:
                sub = map_surf.subsurface((x0, y0, subw, subh))
                scaled = pygame.transform.scale(sub, (cr.w, cr.h))
                self.screen.blit(scaled, (cr.x, cr.y))
                return
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
                tile = pygame.Rect(sx, sy, ts, ts)
                if not cr.colliderect(tile):
                    continue
                color = TERRAIN_COLORS.get(terrain[r][c], (100, 100, 100))
                pygame.draw.rect(self.screen, color, tile)

    def _draw_resources(self):
        ts = int(TILE_SIZE * self.camera.zoom)
        with self.world.lock:
            resources = list(self.world.resources.values())
        for res in resources:
            if res.depleted:
                continue
            sx, sy = self.camera.world_to_screen(res.position[0], res.position[1])
            cx, cy = sx + ts // 2, sy + ts // 2
            r = max(4, ts // 3)
            ot = res.object_type
            if ot == "berry_bush":
                pygame.draw.circle(self.screen, (34, 100, 34), (cx, cy + r // 2), r)
                for bx, bby in [(-r//2, -r//3), (r//2, -r//3), (0, -r//2), (-r//3, r//4), (r//3, r//4)]:
                    pygame.draw.circle(self.screen, (200, 40, 80), (cx + bx, cy + bby), max(2, r // 3))
            elif ot == "tree":
                pygame.draw.rect(self.screen, (100, 60, 20), (cx - max(2, r//4), cy, max(3, r//2), r))
                pygame.draw.circle(self.screen, (30, 120, 30), (cx, cy - r // 2), r)
                pygame.draw.circle(self.screen, (50, 160, 50), (cx - r//3, cy - r//3), r // 2)
            elif ot == "stone_deposit":
                pygame.draw.ellipse(self.screen, (130, 130, 140), (cx - r, cy - r//2, r*2, r))
                pygame.draw.ellipse(self.screen, (160, 160, 170), (cx - r//2, cy - r, r, r//2))
            elif ot == "river_source":
                pygame.draw.ellipse(self.screen, (40, 120, 210), (cx - r, cy - r//2, r*2, r))
                pygame.draw.ellipse(self.screen, (80, 160, 240), (cx - r//2, cy - r//3, r, r//2))
            elif ot == "animal_spawn":
                pygame.draw.ellipse(self.screen, (160, 110, 60), (cx - r, cy - r//2, r*2, r))
                pygame.draw.circle(self.screen, (140, 90, 40), (cx + r//2, cy - r//3), r//2)
            elif ot == "hut":
                pygame.draw.rect(self.screen, (139, 90, 43), (cx - r, cy - r//2, r*2, r))
                pygame.draw.polygon(self.screen, (160, 60, 40), [(cx - r, cy - r//2), (cx + r, cy - r//2), (cx, cy - r - r//2)])
            elif ot == "shrine":
                pygame.draw.rect(self.screen, (180, 160, 60), (cx - r//2, cy - r//2, r, r))
                pygame.draw.polygon(self.screen, (220, 200, 80), [(cx - r//2, cy - r//2), (cx + r//2, cy - r//2), (cx, cy - r - r//3)])
            elif ot == "farm_plot":
                pygame.draw.rect(self.screen, (160, 120, 60), (cx - r, cy - r//2, r*2, r))
                for row in range(3):
                    for col in range(3):
                        pygame.draw.circle(self.screen, (80, 180, 60),
                            (cx - r + col * r//1 + r//3, cy - r//3 + row * r//3), max(2, r//5))
            else:
                pygame.draw.circle(self.screen, OBJECT_COLORS.get(ot, (200, 200, 200)), (cx, cy), r)

    def _draw_structures(self):
        ts = int(TILE_SIZE * self.camera.zoom)
        with self.world.lock:
            structures = list(self.world.structures.values())
        for struct in structures:
            sx, sy = self.camera.world_to_screen(struct.position[0], struct.position[1])
            # Wall
            pygame.draw.rect(self.screen, (160, 110, 60), (sx + 2, sy + ts // 3, ts - 4, ts * 2 // 3 - 2))
            # Roof
            pygame.draw.polygon(self.screen, (180, 70, 50),
                [(sx + 2, sy + ts // 3), (sx + ts - 2, sy + ts // 3), (sx + ts // 2, sy + 2)])
            # Door
            dw = max(4, ts // 4)
            dh = max(5, ts // 3)
            pygame.draw.rect(self.screen, (80, 50, 20), (sx + ts // 2 - dw // 2, sy + ts - dh - 2, dw, dh))
            # Label
            label = self.font_sm.render(struct.name[:8], True, (255, 240, 200))
            self.screen.blit(label, (sx, sy - 14))

    # Role -> (body_color, accent_color)
    ROLE_COLORS = {
        None:        ((210, 180, 140), (160, 130, 100)),
        "Leader":    ((220,  60,  60), (160,  30,  30)),
        "Hunter":    ((120, 160,  60), ( 70, 110,  30)),
        "Gatherer":  ((100, 190, 100), ( 60, 140,  60)),
        "Builder":   ((160, 120,  60), (110,  80,  30)),
        "Merchant":  ((200, 170,  40), (150, 120,  20)),
        "Priest":    ((180, 120, 220), (120,  70, 170)),
        "Soldier":   ((100, 100, 160), ( 60,  60, 120)),
        "Teacher":   ( (80, 180, 200), ( 40, 130, 160)),
    }

    def _draw_sim_character(self, sx: int, sy: int, sim, scale: float):
        """Draw a detailed pixel-art style character at screen position (sx, sy)."""
        s = max(0.5, scale)
        body_color, accent = self.ROLE_COLORS.get(sim.role, self.ROLE_COLORS[None])

        # Skin tone: slightly varied per sim id hash
        h = hash(sim.id) % 40
        skin = (220 + h // 4, 175 + h // 3, 130 + h // 5)

        # --- body (torso) ---
        bw = int(14 * s)
        bh = int(16 * s)
        bx = sx - bw // 2
        by = sy - bh // 2 + int(6 * s)
        pygame.draw.rect(self.screen, body_color, (bx, by, bw, bh), border_radius=int(3 * s))
        # collar / chest detail
        pygame.draw.rect(self.screen, accent, (bx + bw // 4, by, bw // 2, int(5 * s)), border_radius=int(2 * s))

        # --- legs ---
        lw = int(5 * s)
        lh = int(10 * s)
        ly = by + bh - int(2 * s)
        pygame.draw.rect(self.screen, accent, (bx + int(1 * s), ly, lw, lh), border_radius=int(2 * s))
        pygame.draw.rect(self.screen, accent, (bx + bw - lw - int(1 * s), ly, lw, lh), border_radius=int(2 * s))
        # feet
        pygame.draw.ellipse(self.screen, (60, 40, 20), (bx + int(0 * s), ly + lh - int(2 * s), lw + int(3 * s), int(4 * s)))
        pygame.draw.ellipse(self.screen, (60, 40, 20), (bx + bw - lw - int(2 * s), ly + lh - int(2 * s), lw + int(3 * s), int(4 * s)))

        # --- arms ---
        aw = int(4 * s)
        ah = int(12 * s)
        ay = by + int(2 * s)
        pygame.draw.rect(self.screen, body_color, (bx - aw + int(1 * s), ay, aw, ah), border_radius=int(2 * s))
        pygame.draw.rect(self.screen, body_color, (bx + bw - int(1 * s), ay, aw, ah), border_radius=int(2 * s))

        # --- head ---
        hr = int(9 * s)
        hx = sx
        hy = by - hr + int(2 * s)
        pygame.draw.circle(self.screen, skin, (hx, hy), hr)
        # eyes
        eye_y = hy - int(2 * s)
        eye_off = int(3 * s)
        pygame.draw.circle(self.screen, (30, 20, 10), (hx - eye_off, eye_y), max(1, int(2 * s)))
        pygame.draw.circle(self.screen, (30, 20, 10), (hx + eye_off, eye_y), max(1, int(2 * s)))
        # eye shine
        pygame.draw.circle(self.screen, (255, 255, 255), (hx - eye_off + 1, eye_y - 1), max(1, int(s)))
        pygame.draw.circle(self.screen, (255, 255, 255), (hx + eye_off + 1, eye_y - 1), max(1, int(s)))
        # mouth: smile or neutral
        mouth_y = hy + int(3 * s)
        pygame.draw.arc(self.screen, (160, 80, 60),
                        (hx - int(3 * s), mouth_y - int(2 * s), int(6 * s), int(4 * s)),
                        3.14, 6.28, max(1, int(s)))

        # hair — color varies by sim id
        hair_colors = [(80, 50, 20), (180, 140, 60), (30, 30, 30), (160, 80, 40), (200, 200, 200)]
        hair = hair_colors[hash(sim.id) % len(hair_colors)]
        pygame.draw.arc(self.screen, hair,
                        (hx - hr, hy - hr, hr * 2, hr * 2),
                        2.8, 6.0, max(2, int(3 * s)))

        # --- role badge (small icon above head) ---
        badge_icons = {
            "Leader": "♛", "Hunter": "🏹", "Gatherer": "🌿",
            "Builder": "🔨", "Merchant": "💰", "Priest": "✝",
            "Soldier": "⚔", "Teacher": "📖",
        }
        if sim.role and sim.role in badge_icons:
            badge = self.font_sm.render(sim.role[:3], True, accent)
            self.screen.blit(badge, (sx - badge.get_width() // 2, hy - hr - int(14 * s)))

        head_for_layout = hy - hr
        self._draw_sim_bars_name(sx, head_for_layout, sim, s)
        return head_for_layout

    def _draw_sim_bars_name(self, sx: int, head_top: int, sim, z: float):
        s = max(0.5, z)
        bar_w = int(24 * s)
        bar_h = max(2, int(3 * s))
        bar_x = sx - bar_w // 2
        bar_y = head_top - int(8 * s)
        pygame.draw.rect(self.screen, (80, 0, 0), (bar_x, bar_y, bar_w, bar_h))
        filled = int(bar_w * sim.health / 100)
        hp_color = (60, 200, 60) if sim.health > 60 else (220, 180, 0) if sim.health > 30 else (220, 40, 40)
        if filled > 0:
            pygame.draw.rect(self.screen, hp_color, (bar_x, bar_y, filled, bar_h))
        name_surf = self.font_sm.render(sim.name, True, (255, 255, 255))
        shadow = self.font_sm.render(sim.name, True, (0, 0, 0))
        nx = sx - name_surf.get_width() // 2
        ny = head_top - int(18 * s)
        self.screen.blit(shadow, (nx + 1, ny + 1))
        self.screen.blit(name_surf, (nx, ny))

    def _blit_sim_sprite(self, sx: int, sy: int, sim, z: float) -> int:
        """Image-based sim; returns y of top of head for bubbles."""
        hpx = max(4, int(SIM_SPRITE_BASE_HEIGHT * z))
        src = None
        if sim.in_water and self._spr_swim is not None:
            src = self._spr_swim
        elif sim.moving and self._spr_walk is not None and self._spr_idle is not None:
            src = self._spr_walk if sim.walk_cycle < 0.5 else self._spr_idle
        elif sim.moving and self._spr_walk is not None:
            src = self._spr_walk
        else:
            src = self._spr_idle
        if src is None:
            return self._draw_sim_character(sx, sy, sim, z)
        ow, oh = src.get_size()
        if oh <= 0:
            return self._draw_sim_character(sx, sy, sim, z)
        dw = max(1, int(ow * hpx / oh))
        scaled = pygame.transform.scale(src, (dw, hpx))
        if sim.facing < 0 and not sim.in_water:
            scaled = pygame.transform.flip(scaled, True, False)
        rect = scaled.get_rect(midbottom=(sx, sy))
        self.screen.blit(scaled, rect)
        self._draw_sim_bars_name(sx, rect.top, sim, z)
        return rect.top

    def _draw_sims(self):
        with self.world.lock:
            sims = list(self.world.sims.values())
        for sim in sims:
            if not sim.alive:
                continue
            sx, sy = self.camera.world_to_screen(sim.position[0], sim.position[1])
            scale = self.camera.zoom
            head_top = self._blit_sim_sprite(sx, sy, sim, scale)
            bubble_y = head_top - 4
            if sim.thought_bubble and sim.thought_bubble.timer > 0:
                draw_bubble(self.screen, self.font_sm, sim.thought_bubble.text, sx, bubble_y, is_thought=True)
                bubble_y -= 70
            if sim.speech_bubble and sim.speech_bubble.timer > 0:
                draw_bubble(self.screen, self.font_sm, sim.speech_bubble.text, sx, bubble_y, is_thought=False)

    def _draw_timeline(self):
        draw_timeline(self.screen, self.world, self.font_sm, self.font_md)

    def _draw_bottom_bar(self):
        by = SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT
        pygame.draw.rect(self.screen, theme.TL_BG_TOP, (0, by, SCREEN_WIDTH, BOTTOM_BAR_HEIGHT))
        pygame.draw.line(
            self.screen, theme.BORDER_SUBTLE, (0, by), (SCREEN_WIDTH, by), 1
        )
        hints = "  [B] Book   [C] Pillars   [P] Pause   [Home] Fit map   [F5] Save   [F9] Load  "
        lbl = self.font_sm.render(hints, True, theme.TEXT_MUTED)
        self.screen.blit(lbl, (12, by + BOTTOM_BAR_HEIGHT // 2 - lbl.get_height() // 2))
