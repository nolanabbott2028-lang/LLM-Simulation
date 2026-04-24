# Civilization Sandbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python/Pygame autonomous civilization sandbox where two Ollama-powered sims start from nothing, evolve through 10 civilization pillars, and can be observed via free-roam camera, speech/thought bubbles, a timeline, and a Civilization Book.

**Architecture:** Single Python process — Pygame renders on the main thread at 60fps, a background thread fires Ollama calls every ~3 seconds per sim and mutates shared world state under a threading.Lock. World Builder Mode runs before the sim loop starts.

**Tech Stack:** Python 3.11+, pygame 2.x, ollama Python client, threading, dataclasses, json

---

## File Map

| File | Responsibility |
|---|---|
| `main.py` | Entry point — init, start renderer, start sim loop after world-build |
| `config.py` | Constants: model name, tick rate, world size, tile size, colors |
| `world.py` | `WorldState` dataclass + all mutation methods |
| `entities/sim.py` | `Sim` dataclass |
| `entities/structure.py` | `Structure` dataclass |
| `entities/resource.py` | `ResourceObject` dataclass (placed objects on map) |
| `sim_loop.py` | Background thread — prompt builder, Ollama call, action dispatch |
| `renderer.py` | Pygame main loop — camera, input routing, draw calls |
| `world_builder.py` | Terrain paint + object placement input/draw logic |
| `ui/timeline.py` | Top timeline bar draw + milestone markers |
| `ui/book.py` | Civilization Book panel (tabbed, scrollable) |
| `ui/pillars.py` | Pillar scores side panel |
| `ui/bubbles.py` | Speech/thought bubble rendering + fade |
| `ui/inspector.py` | Sim profile panel on click |

---

## Task 1: Project Setup & Config

**Files:**
- Create: `config.py`
- Create: `requirements.txt`
- Create: `main.py` (skeleton only)

- [ ] **Step 1: Create requirements.txt**

```
pygame==2.5.2
ollama==0.2.1
```

- [ ] **Step 2: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: Both packages install without error.

- [ ] **Step 3: Create config.py**

```python
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
TILE_SIZE = 32
WORLD_TILES_W = 100
WORLD_TILES_H = 100
FPS = 60
SIM_TICK_SECONDS = 3.0
OLLAMA_MODEL = "llama3"
TIMELINE_HEIGHT = 40
TOOLBAR_WIDTH = 160
BOTTOM_BAR_HEIGHT = 36

TERRAIN_COLORS = {
    "grass":    (106, 168,  83),
    "forest":   ( 38, 115,  38),
    "water":    ( 64, 164, 223),
    "mountain": (150, 140, 130),
    "desert":   (210, 190, 120),
    "snow":     (230, 240, 255),
}

OBJECT_COLORS = {
    "berry_bush":    (180,  60,  60),
    "stone_deposit": (160, 160, 160),
    "tree":          ( 34,  85,  34),
    "river_source":  ( 30, 144, 255),
    "animal_spawn":  (200, 140,  60),
    "hut":           (139,  90,  43),
    "shrine":        (200, 180,  50),
    "farm_plot":     (210, 180,  90),
}

ERA_THRESHOLDS = [
    (0,  "Stone Age"),
    (11, "Bronze Age"),
    (26, "Iron Age"),
    (41, "Classical Age"),
    (56, "Medieval"),
    (71, "Renaissance"),
    (86, "Modern"),
]

PILLAR_NAMES = [
    "Government", "Economy", "Language", "Social Structure",
    "Culture & Religion", "Technology", "Infrastructure",
    "Food Supply", "Education", "Military",
]
```

- [ ] **Step 4: Create main.py skeleton**

```python
import pygame
from config import SCREEN_WIDTH, SCREEN_HEIGHT, FPS
from world import WorldState
from renderer import Renderer


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Civilization Sandbox")
    clock = pygame.time.Clock()

    world = WorldState()
    renderer = Renderer(screen, world)

    running = True
    while running:
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False
        renderer.handle_input(events)
        renderer.draw()
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Commit**

```bash
git init
git add config.py requirements.txt main.py
git commit -m "feat: project setup and config"
```

---

## Task 2: Entity Dataclasses

**Files:**
- Create: `entities/__init__.py`
- Create: `entities/sim.py`
- Create: `entities/structure.py`
- Create: `entities/resource.py`
- Create: `tests/test_entities.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_entities.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from entities.sim import Sim
from entities.structure import Structure
from entities.resource import ResourceObject


def test_sim_defaults():
    s = Sim(id="s1", name="Adam", position=(50.0, 50.0))
    assert s.health == 100
    assert s.hunger == 100
    assert s.energy == 100
    assert s.age == 0
    assert s.role is None
    assert s.relationships == {}
    assert s.memory == []
    assert s.inventory == {}
    assert s.skills == {}
    assert s.speech_bubble is None
    assert s.thought_bubble is None


def test_structure_defaults():
    st = Structure(id="b1", name="Hut", position=(10.0, 10.0), structure_type="hut")
    assert st.built_by is None
    assert st.resources_stored == {}


def test_resource_defaults():
    r = ResourceObject(id="r1", object_type="berry_bush", position=(20.0, 20.0))
    assert r.quantity > 0
    assert r.depleted is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_entities.py -v`
Expected: ImportError or AttributeError — entities don't exist yet.

- [ ] **Step 3: Create entities/__init__.py**

```python
```
(empty file)

- [ ] **Step 4: Create entities/sim.py**

```python
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Bubble:
    text: str
    timer: float  # seconds remaining


@dataclass
class Sim:
    id: str
    name: str
    position: tuple[float, float]
    health: float = 100.0
    hunger: float = 100.0
    energy: float = 100.0
    age: float = 0.0
    role: Optional[str] = None
    relationships: dict = field(default_factory=dict)
    memory: list = field(default_factory=list)
    inventory: dict = field(default_factory=dict)
    skills: dict = field(default_factory=dict)
    speech_bubble: Optional[Bubble] = None
    thought_bubble: Optional[Bubble] = None
    alive: bool = True
```

- [ ] **Step 5: Create entities/structure.py**

```python
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Structure:
    id: str
    name: str
    position: tuple[float, float]
    structure_type: str
    built_by: Optional[str] = None  # sim id
    resources_stored: dict = field(default_factory=dict)
```

- [ ] **Step 6: Create entities/resource.py**

```python
from dataclasses import dataclass


@dataclass
class ResourceObject:
    id: str
    object_type: str
    position: tuple[float, float]
    quantity: int = 10
    depleted: bool = False
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/test_entities.py -v`
Expected: 3 PASSED

- [ ] **Step 8: Commit**

```bash
git add entities/ tests/test_entities.py
git commit -m "feat: entity dataclasses for sim, structure, resource"
```

---

## Task 3: WorldState

**Files:**
- Create: `world.py`
- Create: `tests/test_world.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_world.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from world import WorldState
from entities.sim import Sim
from entities.resource import ResourceObject


def test_world_defaults():
    w = WorldState()
    assert len(w.terrain) == 100
    assert len(w.terrain[0]) == 100
    assert w.terrain[0][0] == "grass"
    assert w.sims == {}
    assert w.structures == {}
    assert w.resources == {}
    assert len(w.pillars) == 10
    assert all(v == 0 for v in w.pillars.values())
    assert w.sim_day == 0
    assert w.sim_year == 1
    assert w.book_entries == []
    assert w.laws == []
    assert w.technologies == []
    assert w.milestones == set()
    assert w.sim_running is False
    assert w.paused is False
    assert w.speed == 1


def test_add_and_remove_sim():
    w = WorldState()
    s = Sim(id="s1", name="Adam", position=(50.0, 50.0))
    w.add_sim(s)
    assert "s1" in w.sims
    w.remove_sim("s1")
    assert "s1" not in w.sims


def test_set_terrain():
    w = WorldState()
    w.set_terrain(5, 5, "forest")
    assert w.terrain[5][5] == "forest"


def test_add_resource():
    w = WorldState()
    r = ResourceObject(id="r1", object_type="berry_bush", position=(10.0, 10.0))
    w.add_resource(r)
    assert "r1" in w.resources


def test_raise_pillar():
    w = WorldState()
    w.raise_pillar("Technology", 5)
    assert w.pillars["Technology"] == 5
    w.raise_pillar("Technology", 200)
    assert w.pillars["Technology"] == 100  # capped at 100


def test_current_era():
    w = WorldState()
    assert w.current_era() == "Stone Age"
    w.pillars["Technology"] = 15
    assert w.current_era() == "Bronze Age"
    w.pillars["Technology"] = 90
    assert w.current_era() == "Modern"


def test_add_book_entry():
    w = WorldState()
    w.add_book_entry(tab="History", title="First Fire", body="Fire was discovered.")
    assert len(w.book_entries) == 1
    assert w.book_entries[0]["tab"] == "History"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_world.py -v`
Expected: ImportError — world.py doesn't exist yet.

- [ ] **Step 3: Create world.py**

```python
import threading
from dataclasses import dataclass, field
from config import WORLD_TILES_W, WORLD_TILES_H, PILLAR_NAMES, ERA_THRESHOLDS
from entities.sim import Sim
from entities.structure import Structure
from entities.resource import ResourceObject


@dataclass
class WorldState:
    terrain: list = field(default_factory=lambda: [
        ["grass"] * WORLD_TILES_W for _ in range(WORLD_TILES_H)
    ])
    sims: dict = field(default_factory=dict)        # id -> Sim
    structures: dict = field(default_factory=dict)  # id -> Structure
    resources: dict = field(default_factory=dict)   # id -> ResourceObject
    pillars: dict = field(default_factory=lambda: {name: 0 for name in PILLAR_NAMES})
    sim_day: int = 0
    sim_year: int = 1
    book_entries: list = field(default_factory=list)
    laws: list = field(default_factory=list)
    technologies: list = field(default_factory=list)
    milestones: set = field(default_factory=set)
    sim_running: bool = False
    paused: bool = False
    speed: int = 1
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add_sim(self, sim: Sim):
        with self.lock:
            self.sims[sim.id] = sim

    def remove_sim(self, sim_id: str):
        with self.lock:
            self.sims.pop(sim_id, None)

    def set_terrain(self, row: int, col: int, terrain_type: str):
        with self.lock:
            self.terrain[row][col] = terrain_type

    def add_resource(self, resource: ResourceObject):
        with self.lock:
            self.resources[resource.id] = resource

    def add_structure(self, structure: Structure):
        with self.lock:
            self.structures[structure.id] = structure

    def raise_pillar(self, name: str, amount: float):
        with self.lock:
            self.pillars[name] = min(100, self.pillars[name] + amount)

    def current_era(self) -> str:
        tech = self.pillars["Technology"]
        era = "Stone Age"
        for threshold, label in ERA_THRESHOLDS:
            if tech >= threshold:
                era = label
        return era

    def add_book_entry(self, tab: str, title: str, body: str):
        with self.lock:
            self.book_entries.append({
                "tab": tab,
                "title": title,
                "body": body,
                "year": self.sim_year,
                "day": self.sim_day,
            })

    def advance_time(self):
        with self.lock:
            self.sim_day += 1
            if self.sim_day >= 365:
                self.sim_day = 0
                self.sim_year += 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_world.py -v`
Expected: 8 PASSED

- [ ] **Step 5: Commit**

```bash
git add world.py tests/test_world.py
git commit -m "feat: WorldState with terrain, sims, pillars, book entries"
```

---

## Task 4: Renderer Skeleton & Camera

**Files:**
- Create: `renderer.py`

- [ ] **Step 1: Create renderer.py**

```python
import pygame
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, TILE_SIZE, FPS,
    TIMELINE_HEIGHT, TOOLBAR_WIDTH, BOTTOM_BAR_HEIGHT,
    TERRAIN_COLORS, OBJECT_COLORS,
)
from world import WorldState


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

    def draw(self):
        self.screen.fill((20, 20, 20))
        self._draw_terrain()
        self._draw_resources()
        self._draw_structures()
        self._draw_sims()
        self._draw_timeline()
        self._draw_bottom_bar()

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

    def _draw_timeline(self):
        pygame.draw.rect(self.screen, (30, 30, 50), (0, 0, SCREEN_WIDTH, TIMELINE_HEIGHT))
        with self.world.lock:
            year = self.world.sim_year
            day = self.world.sim_day
            era = self.world.current_era()
            speed = self.world.speed
        text = f"Year {year}, Day {day}  |  {era}"
        label = self.font_md.render(text, True, (220, 220, 255))
        self.screen.blit(label, (10, TIMELINE_HEIGHT // 2 - label.get_height() // 2))
        # Speed buttons
        for i, s in enumerate([1, 2, 4]):
            color = (80, 160, 80) if speed == s else (60, 60, 80)
            bx = SCREEN_WIDTH - 120 + i * 38
            by = 6
            pygame.draw.rect(self.screen, color, (bx, by, 32, TIMELINE_HEIGHT - 12), border_radius=4)
            lbl = self.font_sm.render(f"{s}x", True, (255, 255, 255))
            self.screen.blit(lbl, (bx + 8, by + 6))

    def _draw_bottom_bar(self):
        by = SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT
        pygame.draw.rect(self.screen, (30, 30, 50), (0, by, SCREEN_WIDTH, BOTTOM_BAR_HEIGHT))
        hints = "[B] Book  [C] Pillars  [P] Pause  [ESC] Menu"
        lbl = self.font_sm.render(hints, True, (180, 180, 200))
        self.screen.blit(lbl, (10, by + BOTTOM_BAR_HEIGHT // 2 - lbl.get_height() // 2))
```

- [ ] **Step 2: Run main.py and verify a black window opens with a dark timeline bar and bottom bar**

Run: `python main.py`
Expected: Window opens, dark blue timeline at top with "Year 1, Day 0 | Stone Age", bottom hint bar, grass-colored tiles visible. WASD pans. Scroll wheel zooms.

- [ ] **Step 3: Commit**

```bash
git add renderer.py
git commit -m "feat: renderer with camera pan/zoom, terrain, timeline, bottom bar"
```

---

## Task 5: World Builder Mode

**Files:**
- Create: `world_builder.py`
- Modify: `renderer.py`
- Modify: `main.py`

- [ ] **Step 1: Create world_builder.py**

```python
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
        import math
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
```

- [ ] **Step 2: Update renderer.py to use WorldBuilder in pre-sim mode**

Add to the top of `renderer.py` imports:
```python
from world_builder import WorldBuilder
```

Add `self.world_builder` to `Renderer.__init__` after existing fields:
```python
self.world_builder = WorldBuilder(world)
self._book_open = False
self._pillars_open = False
```

Replace `handle_input` in `renderer.py`:
```python
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
                elif event.key == pygame.K_c:
                    self._pillars_open = not self._pillars_open
                elif event.key == pygame.K_p:
                    self.world.paused = not self.world.paused
            if event.type == pygame.MOUSEWHEEL:
                pass  # already handled above
            # Speed button clicks
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                for i, s in enumerate([1, 2, 4]):
                    bx = SCREEN_WIDTH - 120 + i * 38
                    if bx < mx < bx + 32 and 6 < my < TIMELINE_HEIGHT - 6:
                        self.world.speed = s
```

Update `draw` method in `renderer.py` to conditionally show toolbar:
```python
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
```

- [ ] **Step 3: Run and verify world builder**

Run: `python main.py`
Expected: Left toolbar shows Terrain/Objects phase buttons and brush list. Painting terrain changes tile colors. Switching to Objects lets you place colored dots. "Begin Civ." button appears at bottom of toolbar. Clicking it shows "Click to spawn" hint. Clicking the canvas spawns two circles labeled Adam and Eve. Toolbar disappears.

- [ ] **Step 4: Commit**

```bash
git add world_builder.py renderer.py
git commit -m "feat: world builder mode with terrain paint and object placement"
```

---

## Task 6: Sim Loop & Ollama Integration

**Files:**
- Create: `sim_loop.py`
- Modify: `main.py`

- [ ] **Step 1: Create sim_loop.py**

```python
import threading
import time
import json
import ollama
from config import OLLAMA_MODEL, SIM_TICK_SECONDS, PILLAR_NAMES
from world import WorldState
from entities.sim import Sim, Bubble
import uuid


BUBBLE_DURATION = 6.0  # seconds speech/thought bubbles stay visible
MEMORY_LIMIT = 20
NEARBY_RADIUS = 5 * 32  # pixels


def _nearby_context(sim: Sim, world: WorldState) -> str:
    lines = []
    for other in world.sims.values():
        if other.id != sim.id and other.alive:
            dist = ((other.position[0] - sim.position[0])**2 +
                    (other.position[1] - sim.position[1])**2) ** 0.5
            if dist < NEARBY_RADIUS:
                lines.append(f"  - {other.name} (distance {int(dist)}px, role: {other.role or 'none'})")
    for res in world.resources.values():
        if not res.depleted:
            dist = ((res.position[0] - sim.position[0])**2 +
                    (res.position[1] - sim.position[1])**2) ** 0.5
            if dist < NEARBY_RADIUS:
                lines.append(f"  - {res.object_type} at ({int(res.position[0])}, {int(res.position[1])}), qty {res.quantity}")
    for struct in world.structures.values():
        dist = ((struct.position[0] - sim.position[0])**2 +
                (struct.position[1] - sim.position[1])**2) ** 0.5
        if dist < NEARBY_RADIUS:
            lines.append(f"  - {struct.name} (structure) nearby")
    return "\n".join(lines) if lines else "  Nothing nearby."


def _relationship_summary(sim: Sim, world: WorldState) -> str:
    lines = []
    for other_id, rel in sim.relationships.items():
        other = world.sims.get(other_id)
        if other:
            lines.append(f"  - {other.name}: trust={rel.get('trust',0)}, bond={rel.get('bond',0)}, romantic={rel.get('romantic',0)}")
    return "\n".join(lines) if lines else "  No relationships yet."


def _build_prompt(sim: Sim, world: WorldState) -> str:
    memories = "\n".join(f"  - {m}" for m in sim.memory[-5:]) or "  None yet."
    nearby = _nearby_context(sim, world)
    rels = _relationship_summary(sim, world)
    pillar_summary = ", ".join(f"{k}: {int(v)}" for k, v in world.pillars.items())
    techs = ", ".join(world.technologies) if world.technologies else "none"

    return f"""You are {sim.name}, age {int(sim.age)}.
Health: {int(sim.health)}/100. Hunger: {int(sim.hunger)}/100. Energy: {int(sim.energy)}/100.
Your role: {sim.role or "none yet"}.
Your memories:
{memories}
Nearby (within sight):
{nearby}
Your relationships:
{rels}
Current era: {world.current_era()}. Known technologies: {techs}.
Civilization progress: {pillar_summary}.

What do you think, say, and do right now?
Respond ONLY as valid JSON with these exact keys:
{{
  "thought": "your inner thought (one sentence)",
  "speech": "what you say aloud, or empty string if silent",
  "action": "move|gather|build|talk|eat|sleep|reproduce|govern|trade|teach|attack|pray|invent|explore",
  "target": "name/id of target or null",
  "detail": "brief extra info"
}}"""


def _apply_action(sim: Sim, response: dict, world: WorldState):
    action = response.get("action", "move")
    detail = response.get("detail", "")
    target_name = response.get("target")

    # Passive stat decay each tick
    sim.hunger = max(0, sim.hunger - 2)
    sim.energy = max(0, sim.energy - 1)
    if sim.hunger == 0:
        sim.health = max(0, sim.health - 5)
    if sim.health <= 0:
        sim.alive = False
        world.add_book_entry("People", f"Death of {sim.name}",
            f"{sim.name} passed away at age {int(sim.age)} in {world.current_era()}.")
        return

    sim.age += 1 / 365  # one tick = one day

    if action == "move" or action == "explore":
        import random
        dx = random.uniform(-2, 2) * 32
        dy = random.uniform(-2, 2) * 32
        sim.position = (sim.position[0] + dx, sim.position[1] + dy)

    elif action == "gather":
        for res in world.resources.values():
            if not res.depleted:
                dist = ((res.position[0] - sim.position[0])**2 +
                        (res.position[1] - sim.position[1])**2) ** 0.5
                if dist < 64:
                    item = res.object_type
                    sim.inventory[item] = sim.inventory.get(item, 0) + 1
                    res.quantity -= 1
                    if res.quantity <= 0:
                        res.depleted = True
                    sim.memory.append(f"Gathered {item}")
                    break

    elif action == "eat":
        food_items = ["berry_bush", "animal_spawn", "farm_plot"]
        for item in food_items:
            if sim.inventory.get(item, 0) > 0:
                sim.inventory[item] -= 1
                sim.hunger = min(100, sim.hunger + 30)
                sim.memory.append("Ate food, felt better")
                break

    elif action == "sleep":
        sim.energy = min(100, sim.energy + 20)
        sim.memory.append("Rested and regained energy")

    elif action == "talk":
        for other in world.sims.values():
            if other.id != sim.id and other.alive:
                dist = ((other.position[0] - sim.position[0])**2 +
                        (other.position[1] - sim.position[1])**2) ** 0.5
                if dist < 96:
                    rel = sim.relationships.setdefault(other.id, {"trust": 0, "bond": 0, "romantic": 0})
                    rel["trust"] = min(100, rel["trust"] + 2)
                    rel["bond"] = min(100, rel["bond"] + 1)
                    other.memory.append(f"{sim.name} said: {response.get('speech', '')[:80]}")
                    world.raise_pillar("Language", 0.5)
                    break

    elif action == "build":
        from entities.structure import Structure
        struct_name = detail or "Shelter"
        struct = Structure(
            id=str(uuid.uuid4())[:8],
            name=struct_name,
            position=(sim.position[0] + 16, sim.position[1] + 16),
            structure_type=struct_name.lower(),
            built_by=sim.id,
        )
        world.add_structure(struct)
        world.raise_pillar("Infrastructure", 2)
        sim.memory.append(f"Built {struct_name}")
        _check_milestone(world, f"first_build", "History",
            f"First Structure: {struct_name}",
            f"{sim.name} built the first {struct_name}, marking a step toward permanent settlement.")

    elif action == "reproduce":
        partner = None
        for other in world.sims.values():
            if other.id != sim.id and other.alive:
                rel = sim.relationships.get(other.id, {})
                if rel.get("romantic", 0) >= 70 and sim.health >= 60 and sim.hunger >= 40:
                    partner = other
                    break
        if partner:
            child_name = detail or f"Child{len(world.sims)+1}"
            child = Sim(
                id=str(uuid.uuid4())[:8],
                name=child_name,
                position=sim.position,
                age=0,
                skills={k: (v + partner.skills.get(k, 0)) / 2
                        for k, v in sim.skills.items()},
            )
            world.add_sim(child)
            world.raise_pillar("Social Structure", 3)
            world.add_book_entry("People", f"Birth of {child_name}",
                f"{sim.name} and {partner.name} welcomed {child_name} into the world.")

    elif action == "govern":
        law = detail or "All must share food"
        world.laws.append({"law": law, "by": sim.name, "year": world.sim_year, "day": world.sim_day})
        world.raise_pillar("Government", 5)
        sim.role = "Leader"
        sim.memory.append(f"Declared law: {law}")
        _check_milestone(world, "first_law", "Laws",
            f"First Law: {law}",
            f"{sim.name} declared the first law: '{law}'. Order had begun.")

    elif action == "trade":
        for other in world.sims.values():
            if other.id != sim.id and other.alive:
                dist = ((other.position[0] - sim.position[0])**2 +
                        (other.position[1] - sim.position[1])**2) ** 0.5
                if dist < 96:
                    world.raise_pillar("Economy", 3)
                    rel = sim.relationships.setdefault(other.id, {"trust": 0, "bond": 0, "romantic": 0})
                    rel["trust"] = min(100, rel["trust"] + 5)
                    sim.memory.append(f"Traded with {other.name}")
                    _check_milestone(world, "first_trade", "History",
                        "First Trade",
                        f"{sim.name} and {other.name} exchanged goods for the first time, laying the seeds of an economy.")
                    break

    elif action == "teach":
        for other in world.sims.values():
            if other.id != sim.id and other.alive:
                dist = ((other.position[0] - sim.position[0])**2 +
                        (other.position[1] - sim.position[1])**2) ** 0.5
                if dist < 96:
                    skill = detail or "survival"
                    other.skills[skill] = other.skills.get(skill, 0) + 1
                    world.raise_pillar("Education", 2)
                    sim.memory.append(f"Taught {other.name} about {skill}")
                    break

    elif action == "attack":
        for other in world.sims.values():
            if other.id != sim.id and other.alive:
                dist = ((other.position[0] - sim.position[0])**2 +
                        (other.position[1] - sim.position[1])**2) ** 0.5
                if dist < 64:
                    other.health = max(0, other.health - 10)
                    world.raise_pillar("Military", 2)
                    sim.memory.append(f"Attacked {other.name}")
                    break

    elif action == "pray":
        world.raise_pillar("Culture & Religion", 3)
        sim.memory.append("Prayed and felt a sense of meaning")
        _check_milestone(world, "first_prayer", "Culture",
            "First Prayer",
            f"{sim.name} knelt and offered words to the unknown — the first stirring of faith.")

    elif action == "invent":
        tech = detail or "stone tool"
        if tech not in world.technologies:
            world.technologies.append(tech)
            world.raise_pillar("Technology", 5)
            sim.memory.append(f"Invented: {tech}")
            _check_milestone(world, f"invent_{tech}", "Technology",
                f"Invention: {tech}",
                f"{sim.name} conceived of {tech} — a leap forward in the story of their people.")

    elif action == "gather" or action == "explore":
        world.raise_pillar("Food Supply", 0.5)

    # Trim memory
    if len(sim.memory) > MEMORY_LIMIT:
        sim.memory = sim.memory[-MEMORY_LIMIT:]

    # Update romantic relationship if sustained high bond
    for other_id, rel in sim.relationships.items():
        if rel.get("bond", 0) >= 50:
            rel["romantic"] = min(100, rel.get("romantic", 0) + 1)


def _check_milestone(world: WorldState, key: str, tab: str, title: str, body: str):
    if key not in world.milestones:
        world.milestones.add(key)
        world.add_book_entry(tab, title, body)


def _tick(world: WorldState):
    with world.lock:
        sim_ids = list(world.sims.keys())

    for sim_id in sim_ids:
        with world.lock:
            sim = world.sims.get(sim_id)
            if sim is None or not sim.alive:
                continue
            prompt = _build_prompt(sim, world)

        try:
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response["message"]["content"].strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)
        except (json.JSONDecodeError, KeyError, Exception):
            # Retry once with explicit reminder
            try:
                retry_prompt = prompt + "\n\nREMINDER: respond ONLY with raw JSON, no markdown."
                response = ollama.chat(
                    model=OLLAMA_MODEL,
                    messages=[{"role": "user", "content": retry_prompt}],
                )
                raw = response["message"]["content"].strip()
                data = json.loads(raw)
            except Exception:
                continue

        with world.lock:
            sim = world.sims.get(sim_id)
            if sim is None:
                continue
            thought = data.get("thought", "")
            speech = data.get("speech", "")
            if thought:
                sim.thought_bubble = Bubble(text=thought[:120], timer=BUBBLE_DURATION)
            if speech:
                sim.speech_bubble = Bubble(text=speech[:120], timer=BUBBLE_DURATION)
            _apply_action(sim, data, world)

    world.advance_time()


def _bubble_tick(world: WorldState, dt: float):
    with world.lock:
        for sim in world.sims.values():
            if sim.thought_bubble:
                sim.thought_bubble.timer -= dt
                if sim.thought_bubble.timer <= 0:
                    sim.thought_bubble = None
            if sim.speech_bubble:
                sim.speech_bubble.timer -= dt
                if sim.speech_bubble.timer <= 0:
                    sim.speech_bubble = None


def run_sim_loop(world: WorldState):
    while True:
        if not world.sim_running or world.paused:
            time.sleep(0.1)
            continue
        tick_interval = SIM_TICK_SECONDS / world.speed
        _tick(world)
        time.sleep(tick_interval)
```

- [ ] **Step 2: Update main.py to start sim loop thread after world is built**

```python
import pygame
import threading
from config import SCREEN_WIDTH, SCREEN_HEIGHT, FPS
from world import WorldState
from renderer import Renderer
from sim_loop import run_sim_loop


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Civilization Sandbox")
    clock = pygame.time.Clock()

    world = WorldState()
    renderer = Renderer(screen, world)

    sim_thread = threading.Thread(target=run_sim_loop, args=(world,), daemon=True)
    sim_thread.start()

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False
        renderer.handle_input(events)
        renderer.draw()
        # Tick bubble fade on render thread
        from sim_loop import _bubble_tick
        _bubble_tick(world, dt)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify Ollama is running**

Run: `ollama list`
Expected: At least one model listed (llama3 or similar). If not: `ollama pull llama3`

- [ ] **Step 4: Run the full sim and watch sims act**

Run: `python main.py`
Steps: Paint terrain, place a few berry bushes, click "Begin Civ.", click canvas to spawn Adam and Eve. Wait ~6 seconds. Expected: Adam and Eve start moving and show thought/speech bubbles above them. Console should show no crash.

- [ ] **Step 5: Commit**

```bash
git add sim_loop.py main.py
git commit -m "feat: sim loop with Ollama LLM, action dispatch, bubble timers"
```

---

## Task 7: Speech & Thought Bubbles

**Files:**
- Create: `ui/bubbles.py`
- Create: `ui/__init__.py`
- Modify: `renderer.py`

- [ ] **Step 1: Create ui/__init__.py**

```python
```
(empty)

- [ ] **Step 2: Create ui/bubbles.py**

```python
import pygame
from entities.sim import Sim, Bubble
from config import TILE_SIZE


def draw_bubble(screen: pygame.Surface, font: pygame.font.Font,
                text: str, sx: int, sy: int, is_thought: bool):
    """Draw a speech or thought bubble at screen coords (sx, sy) above a sim."""
    if not text:
        return
    padding = 6
    max_chars = 30
    # Word-wrap into lines
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
    by = sy - h - 18  # above the sim circle

    # Background
    bg_color = (240, 240, 255) if not is_thought else (220, 255, 220)
    border_color = (100, 100, 180) if not is_thought else (80, 160, 80)
    pygame.draw.rect(screen, bg_color, (bx, by, w, h), border_radius=8)
    pygame.draw.rect(screen, border_color, (bx, by, w, h), 2, border_radius=8)

    # Tail
    tail_x = sx
    tail_y = by + h
    if is_thought:
        # Dotted circles for thought
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

    # Text
    y_offset = by + padding
    for surf in line_surfaces:
        screen.blit(surf, (bx + padding, y_offset))
        y_offset += surf.get_height()
```

- [ ] **Step 3: Update renderer.py _draw_sims to use bubbles**

Add import at top of renderer.py:
```python
from ui.bubbles import draw_bubble
```

Replace the `_draw_sims` method in renderer.py:
```python
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
        # Thought bubble (green, above name)
        if sim.thought_bubble and sim.thought_bubble.timer > 0:
            draw_bubble(self.screen, self.font_sm, sim.thought_bubble.text, sx, sy - r - 16, is_thought=True)
        # Speech bubble (blue, above thought)
        if sim.speech_bubble and sim.speech_bubble.timer > 0:
            offset = -80 if sim.thought_bubble and sim.thought_bubble.timer > 0 else 0
            draw_bubble(self.screen, self.font_sm, sim.speech_bubble.text, sx, sy - r - 16 + offset, is_thought=False)
```

- [ ] **Step 4: Run and verify bubbles appear**

Run: `python main.py`
Expected: After spawning sims and waiting a few ticks, green thought bubbles and white/blue speech bubbles appear above sims, fade after ~6 seconds, and new ones replace them.

- [ ] **Step 5: Commit**

```bash
git add ui/__init__.py ui/bubbles.py renderer.py
git commit -m "feat: speech and thought bubbles with fade timers"
```

---

## Task 8: Timeline Milestones

**Files:**
- Create: `ui/timeline.py`
- Modify: `renderer.py`

- [ ] **Step 1: Create ui/timeline.py**

```python
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

    # Milestone markers — spread across timeline between label and speed buttons
    marker_start = label.get_width() + 20
    marker_end = SCREEN_WIDTH - 130
    marker_width = marker_end - marker_start
    total_days = max(1, year * 365 + day)

    milestone_entries = [e for e in entries if e["tab"] in ("History", "Technology", "Laws", "Culture", "People")]
    for entry in milestone_entries[-20:]:  # show last 20 milestones max
        entry_day = entry["year"] * 365 + entry["day"]
        frac = min(1.0, entry_day / total_days)
        mx = int(marker_start + frac * marker_width)
        pygame.draw.circle(screen, (255, 200, 50), (mx, TIMELINE_HEIGHT // 2), 4)

    # Speed buttons
    for i, s in enumerate([1, 2, 4]):
        color = (80, 160, 80) if speed == s else (60, 60, 80)
        bx = SCREEN_WIDTH - 120 + i * 38
        by = 6
        pygame.draw.rect(screen, color, (bx, by, 32, TIMELINE_HEIGHT - 12), border_radius=4)
        lbl = font_sm.render(f"{s}x", True, (255, 255, 255))
        screen.blit(lbl, (bx + 8, by + 6))

    # Tooltip on hover
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
```

- [ ] **Step 2: Update renderer.py to use ui/timeline.py**

Add import:
```python
from ui.timeline import draw_timeline
```

Replace `_draw_timeline` method:
```python
def _draw_timeline(self):
    draw_timeline(self.screen, self.world, self.font_sm, self.font_md)
```

- [ ] **Step 3: Run and verify timeline**

Run: `python main.py`
Expected: Timeline bar shows year/day/era. After the first few events fire (first talk, first build, etc.), small gold dots appear on the timeline. Hovering a dot shows the event title.

- [ ] **Step 4: Commit**

```bash
git add ui/timeline.py renderer.py
git commit -m "feat: timeline with milestone markers and hover tooltips"
```

---

## Task 9: Civilization Book Panel

**Files:**
- Create: `ui/book.py`
- Modify: `renderer.py`

- [ ] **Step 1: Create ui/book.py**

```python
import pygame
from config import SCREEN_WIDTH, SCREEN_HEIGHT, TIMELINE_HEIGHT, BOTTOM_BAR_HEIGHT
from world import WorldState


TABS = ["History", "Technology", "Laws", "People", "Culture"]
PANEL_W = 500
PANEL_H = SCREEN_HEIGHT - TIMELINE_HEIGHT - BOTTOM_BAR_HEIGHT - 20
PANEL_X = (SCREEN_WIDTH - PANEL_W) // 2
PANEL_Y = TIMELINE_HEIGHT + 10


class BookPanel:
    def __init__(self):
        self.active_tab = "History"
        self.scroll_offset = 0
        self.font_title = pygame.font.SysFont("monospace", 14, bold=True)
        self.font_body = pygame.font.SysFont("monospace", 12)

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
                tx = PANEL_X + 8 + i * 94
                if tx < mx < tx + 88 and tab_y < my < tab_y + 24:
                    self.active_tab = tab
                    self.scroll_offset = 0
                    return True
        return False

    def draw(self, screen: pygame.Surface, world: WorldState):
        # Background
        surface = pygame.Surface((PANEL_W, PANEL_H), pygame.SRCALPHA)
        surface.fill((20, 18, 30, 230))
        screen.blit(surface, (PANEL_X, PANEL_Y))
        pygame.draw.rect(screen, (120, 100, 180), (PANEL_X, PANEL_Y, PANEL_W, PANEL_H), 2, border_radius=8)

        # Title
        title = self.font_title.render("Civilization Book", True, (220, 200, 255))
        screen.blit(title, (PANEL_X + PANEL_W // 2 - title.get_width() // 2, PANEL_Y + 6))

        # Tabs
        for i, tab in enumerate(TABS):
            tx = PANEL_X + 8 + i * 94
            ty = PANEL_Y + 28
            color = (80, 60, 140) if tab == self.active_tab else (40, 35, 70)
            pygame.draw.rect(screen, color, (tx, ty, 88, 22), border_radius=4)
            lbl = self.font_body.render(tab, True, (220, 210, 255))
            screen.blit(lbl, (tx + 4, ty + 4))

        # Entries
        with world.lock:
            entries = [e for e in world.book_entries if e["tab"] == self.active_tab]

        content_y = PANEL_Y + 58 - self.scroll_offset
        clip_rect = pygame.Rect(PANEL_X + 4, PANEL_Y + 58, PANEL_W - 8, PANEL_H - 62)
        screen.set_clip(clip_rect)

        for entry in reversed(entries):
            header = f"Year {entry['year']}, Day {entry['day']} — {entry['title']}"
            h_surf = self.font_title.render(header, True, (200, 180, 255))
            if PANEL_Y + 58 <= content_y < PANEL_Y + PANEL_H:
                screen.blit(h_surf, (PANEL_X + 10, content_y))
            content_y += h_surf.get_height() + 2

            body = entry["body"]
            words = body.split()
            line = ""
            max_chars = 58
            for word in words:
                if len(line) + len(word) + 1 <= max_chars:
                    line = (line + " " + word).strip()
                else:
                    b_surf = self.font_body.render(line, True, (180, 170, 210))
                    if PANEL_Y + 58 <= content_y < PANEL_Y + PANEL_H:
                        screen.blit(b_surf, (PANEL_X + 14, content_y))
                    content_y += b_surf.get_height()
                    line = word
            if line:
                b_surf = self.font_body.render(line, True, (180, 170, 210))
                if PANEL_Y + 58 <= content_y < PANEL_Y + PANEL_H:
                    screen.blit(b_surf, (PANEL_X + 14, content_y))
                content_y += b_surf.get_height()
            content_y += 12  # gap between entries

        screen.set_clip(None)
```

- [ ] **Step 2: Update renderer.py to draw book panel**

Add import:
```python
from ui.book import BookPanel
```

In `Renderer.__init__`, after `self._pillars_open = False`:
```python
self._book_panel = BookPanel()
```

In `handle_input`, replace the `K_b` handler:
```python
if event.key == pygame.K_b:
    self._book_open = not self._book_open
    self._book_panel.scroll_offset = 0
```

Also route events to book panel when open — add inside the `else` (sim running) block of `handle_input`, after the keydown checks:
```python
if self._book_open:
    self._book_panel.handle_event(event)
```

In `draw`, after `self._draw_bottom_bar()`:
```python
if self._book_open:
    self._book_panel.draw(self.screen, self.world)
```

- [ ] **Step 3: Run and verify book**

Run: `python main.py`
Expected: Press `B` opens a dark panel in the center of the screen. As sims act, entries appear under the relevant tabs. Tabs are clickable. Panel scrolls with mouse wheel.

- [ ] **Step 4: Commit**

```bash
git add ui/book.py renderer.py
git commit -m "feat: Civilization Book panel with tabbed entries and scroll"
```

---

## Task 10: Pillar Scores Panel & Sim Inspector

**Files:**
- Create: `ui/pillars.py`
- Create: `ui/inspector.py`
- Modify: `renderer.py`

- [ ] **Step 1: Create ui/pillars.py**

```python
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
```

- [ ] **Step 2: Create ui/inspector.py**

```python
import pygame
from config import TIMELINE_HEIGHT
from entities.sim import Sim
from world import WorldState


PANEL_W = 280
PANEL_X = 10
PANEL_Y_BASE = TIMELINE_HEIGHT + 10


def draw_inspector(screen: pygame.Surface, sim: Sim, world: WorldState,
                   font_sm: pygame.font.Font, font_md: pygame.font.Font):
    lines = [
        f"Name:   {sim.name}",
        f"Age:    {int(sim.age)}",
        f"Health: {int(sim.health)}/100",
        f"Hunger: {int(sim.hunger)}/100",
        f"Energy: {int(sim.energy)}/100",
        f"Role:   {sim.role or 'none'}",
        "",
        "Inventory:",
    ]
    for item, qty in sim.inventory.items():
        lines.append(f"  {item}: {qty}")
    lines.append("")
    lines.append("Skills:")
    for skill, level in sim.skills.items():
        lines.append(f"  {skill}: {int(level)}")
    lines.append("")
    lines.append("Relationships:")
    with world.lock:
        for other_id, rel in sim.relationships.items():
            other = world.sims.get(other_id)
            if other:
                lines.append(f"  {other.name}: bond={rel.get('bond',0)} trust={rel.get('trust',0)}")
    lines.append("")
    lines.append("Recent memories:")
    for m in sim.memory[-5:]:
        lines.append(f"  - {m[:40]}")

    line_h = font_sm.get_height() + 2
    panel_h = len(lines) * line_h + 24
    surface = pygame.Surface((PANEL_W, panel_h), pygame.SRCALPHA)
    surface.fill((20, 18, 30, 220))
    screen.blit(surface, (PANEL_X, PANEL_Y_BASE))
    pygame.draw.rect(screen, (80, 100, 160), (PANEL_X, PANEL_Y_BASE, PANEL_W, panel_h), 2, border_radius=6)

    title = font_md.render(f"[ {sim.name} ]", True, (220, 200, 255))
    screen.blit(title, (PANEL_X + PANEL_W // 2 - title.get_width() // 2, PANEL_Y_BASE + 4))

    for i, line in enumerate(lines):
        color = (200, 190, 230) if not line.startswith("  ") else (160, 155, 190)
        lbl = font_sm.render(line, True, color)
        screen.blit(lbl, (PANEL_X + 8, PANEL_Y_BASE + 22 + i * line_h))
```

- [ ] **Step 3: Update renderer.py for pillars and inspector**

Add imports:
```python
from ui.pillars import draw_pillars
from ui.inspector import draw_inspector
```

In `Renderer.__init__`, add:
```python
self._inspected_sim_id = None
```

In `handle_input`, inside the sim-running block, add click detection for sims:
```python
if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
    mx, my = event.pos
    # Speed buttons (already handled above)
    # Sim click — inspect
    ts = int(32 * self.camera.zoom)
    with self.world.lock:
        sims = list(self.world.sims.values())
    clicked_sim = None
    for sim in sims:
        if not sim.alive:
            continue
        sx, sy = self.camera.world_to_screen(sim.position[0], sim.position[1])
        r = max(6, ts // 2)
        if ((mx - sx)**2 + (my - sy)**2) ** 0.5 < r + 4:
            clicked_sim = sim
            break
    if clicked_sim:
        self._inspected_sim_id = clicked_sim.id if self._inspected_sim_id != clicked_sim.id else None
```

In `draw`, after drawing book panel:
```python
if self._pillars_open:
    draw_pillars(self.screen, self.world, self.font_sm)
if self._inspected_sim_id:
    with self.world.lock:
        sim = self.world.sims.get(self._inspected_sim_id)
    if sim and sim.alive:
        draw_inspector(self.screen, sim, self.world, self.font_sm, self.font_md)
    else:
        self._inspected_sim_id = None
```

- [ ] **Step 4: Run and verify panels**

Run: `python main.py`
Expected: Press `C` shows pillar bar chart on right side. Click a sim shows their full profile panel on the left (health, hunger, memory, relationships, inventory). Click same sim again to dismiss.

- [ ] **Step 5: Commit**

```bash
git add ui/pillars.py ui/inspector.py renderer.py
git commit -m "feat: pillar scores panel and sim inspector panel"
```

---

## Task 11: Save & Load World State

**Files:**
- Create: `persistence.py`
- Modify: `renderer.py`
- Modify: `main.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_persistence.py
import sys, os, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from world import WorldState
from entities.sim import Sim
from entities.resource import ResourceObject
from persistence import save_world, load_world


def test_save_and_load_roundtrip():
    w = WorldState()
    s = Sim(id="adam", name="Adam", position=(10.0, 20.0))
    s.memory = ["Found berries", "Spoke to Eve"]
    s.inventory = {"berry_bush": 3}
    w.add_sim(s)
    r = ResourceObject(id="r1", object_type="berry_bush", position=(50.0, 60.0), quantity=5)
    w.add_resource(r)
    w.raise_pillar("Technology", 15)
    w.add_book_entry("History", "First Fire", "Fire was found.")
    w.technologies.append("stone tool")
    w.sim_year = 3
    w.sim_day = 42

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name

    save_world(w, path)
    w2 = load_world(path)

    assert "adam" in w2.sims
    assert w2.sims["adam"].name == "Adam"
    assert w2.sims["adam"].memory == ["Found berries", "Spoke to Eve"]
    assert w2.sims["adam"].inventory == {"berry_bush": 3}
    assert "r1" in w2.resources
    assert w2.pillars["Technology"] == 15
    assert len(w2.book_entries) == 1
    assert w2.technologies == ["stone tool"]
    assert w2.sim_year == 3
    assert w2.sim_day == 42
    os.unlink(path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_persistence.py -v`
Expected: ImportError — persistence.py doesn't exist yet.

- [ ] **Step 3: Create persistence.py**

```python
import json
import threading
from world import WorldState
from entities.sim import Sim, Bubble
from entities.structure import Structure
from entities.resource import ResourceObject


def _sim_to_dict(sim: Sim) -> dict:
    return {
        "id": sim.id, "name": sim.name,
        "position": list(sim.position),
        "health": sim.health, "hunger": sim.hunger, "energy": sim.energy,
        "age": sim.age, "role": sim.role,
        "relationships": sim.relationships,
        "memory": sim.memory,
        "inventory": sim.inventory,
        "skills": sim.skills,
        "alive": sim.alive,
    }


def _sim_from_dict(d: dict) -> Sim:
    s = Sim(
        id=d["id"], name=d["name"],
        position=tuple(d["position"]),
        health=d["health"], hunger=d["hunger"], energy=d["energy"],
        age=d["age"], role=d.get("role"),
        relationships=d.get("relationships", {}),
        memory=d.get("memory", []),
        inventory=d.get("inventory", {}),
        skills=d.get("skills", {}),
        alive=d.get("alive", True),
    )
    return s


def _structure_to_dict(st: Structure) -> dict:
    return {
        "id": st.id, "name": st.name,
        "position": list(st.position),
        "structure_type": st.structure_type,
        "built_by": st.built_by,
        "resources_stored": st.resources_stored,
    }


def _structure_from_dict(d: dict) -> Structure:
    return Structure(
        id=d["id"], name=d["name"],
        position=tuple(d["position"]),
        structure_type=d["structure_type"],
        built_by=d.get("built_by"),
        resources_stored=d.get("resources_stored", {}),
    )


def _resource_to_dict(r: ResourceObject) -> dict:
    return {
        "id": r.id, "object_type": r.object_type,
        "position": list(r.position),
        "quantity": r.quantity, "depleted": r.depleted,
    }


def _resource_from_dict(d: dict) -> ResourceObject:
    return ResourceObject(
        id=d["id"], object_type=d["object_type"],
        position=tuple(d["position"]),
        quantity=d["quantity"], depleted=d["depleted"],
    )


def save_world(world: WorldState, path: str):
    with world.lock:
        data = {
            "terrain": world.terrain,
            "sims": [_sim_to_dict(s) for s in world.sims.values()],
            "structures": [_structure_to_dict(st) for st in world.structures.values()],
            "resources": [_resource_to_dict(r) for r in world.resources.values()],
            "pillars": world.pillars,
            "sim_day": world.sim_day,
            "sim_year": world.sim_year,
            "book_entries": world.book_entries,
            "laws": world.laws,
            "technologies": world.technologies,
            "milestones": list(world.milestones),
            "sim_running": world.sim_running,
            "speed": world.speed,
        }
    with open(path, "w") as f:
        json.dump(data, f)


def load_world(path: str) -> WorldState:
    with open(path) as f:
        data = json.load(f)
    w = WorldState()
    w.terrain = data["terrain"]
    w.sims = {d["id"]: _sim_from_dict(d) for d in data["sims"]}
    w.structures = {d["id"]: _structure_from_dict(d) for d in data["structures"]}
    w.resources = {d["id"]: _resource_from_dict(d) for d in data["resources"]}
    w.pillars = data["pillars"]
    w.sim_day = data["sim_day"]
    w.sim_year = data["sim_year"]
    w.book_entries = data["book_entries"]
    w.laws = data["laws"]
    w.technologies = data["technologies"]
    w.milestones = set(data["milestones"])
    w.sim_running = data["sim_running"]
    w.speed = data["speed"]
    return w
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_persistence.py -v`
Expected: 1 PASSED

- [ ] **Step 5: Add save/load keybindings to renderer.py**

Add import at top:
```python
from persistence import save_world, load_world
import os
```

In `handle_input`, inside the sim-running keydown block, add:
```python
elif event.key == pygame.K_F5:
    save_world(self.world, "savegame.json")
elif event.key == pygame.K_F9:
    if os.path.exists("savegame.json"):
        loaded = load_world("savegame.json")
        with self.world.lock:
            self.world.__dict__.update({
                k: v for k, v in loaded.__dict__.items()
                if k != "lock"
            })
```

- [ ] **Step 6: Run and test save/load**

Run: `python main.py`
Expected: Press F5 during sim creates `savegame.json`. Press F9 restores state (sims, terrain, entries, pillars).

- [ ] **Step 7: Commit**

```bash
git add persistence.py tests/test_persistence.py renderer.py
git commit -m "feat: save/load world state to JSON with F5/F9"
```

---

## Task 12: Final Integration Test

**Files:**
- No new files

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 2: Run full simulation smoke test**

Run: `python main.py`
Do the following in order:
1. Paint a mix of terrain (grass, forest, water)
2. Place 3 berry bushes, 2 stone deposits, 1 animal spawn
3. Click "Begin Civ." then click canvas to spawn Adam and Eve
4. Wait 30 seconds — verify thought/speech bubbles appear
5. Press `C` — verify pillar bars update
6. Press `B` — verify Civilization Book has entries
7. Click Adam — verify inspector shows health/hunger/memory
8. Press `P` to pause, then resume
9. Press `4x` speed — verify sims act faster
10. Press `F5` to save, then `F9` to reload — verify state restores

- [ ] **Step 3: Commit**

```bash
git add .
git commit -m "chore: final integration verified"
```

---

## Self-Review Notes

**Spec coverage check:**
- ✅ World Builder Mode (terrain paint + object placement + spawn click)
- ✅ Free-roam camera with pan/zoom
- ✅ Sims with all dataclass fields including energy
- ✅ LLM prompt with no simulation meta-references
- ✅ All 14 action types implemented
- ✅ 10 civilization pillars tracked and displayed
- ✅ Era progression from Stone Age to Modern
- ✅ Speech and thought bubbles with fade
- ✅ Timeline with year/day/era/milestones/speed
- ✅ Civilization Book with 5 tabs
- ✅ Sim inspector on click
- ✅ Reproduction with conditions
- ✅ Death handling
- ✅ Save/load

**Type consistency verified:** `Sim`, `Structure`, `ResourceObject`, `Bubble`, `WorldState` — all field names used consistently across tasks.
