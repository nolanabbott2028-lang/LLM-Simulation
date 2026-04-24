import os

_SCREEN_DIR = os.path.dirname(os.path.abspath(__file__))

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
TILE_SIZE = 32
WORLD_TILES_W = 100
WORLD_TILES_H = 100
FPS = 60
SIM_TICK_SECONDS = 3.0
OLLAMA_MODEL = "llama3"
# Local Ollama server (set OLLAMA_HOST in env to override, e.g. http://127.0.0.1:11434)
OLLAMA_HOST = "http://127.0.0.1:11434"
# HTTP timeouts: connect fails fast if `ollama serve` is not running; read can stay long for big models
OLLAMA_CONNECT_TIMEOUT = 8.0
OLLAMA_READ_TIMEOUT = 300.0
# Log at most one Ollama connection warning per this many seconds (avoids terminal spam offline)
OLLAMA_WARN_INTERVAL_SEC = 30.0

# Place map + character sprites in assets/ (see assets/README.txt)
ASSETS_DIR = os.path.join(_SCREEN_DIR, "assets")
MAP_IMAGE_FILE = "map.png"
MAP_IMAGE_PATH = os.path.join(ASSETS_DIR, MAP_IMAGE_FILE)
# Three character frames: standing / walking / in water
SIM_SPRITE_IDLE = os.path.join(ASSETS_DIR, "sims", "idle.png")
SIM_SPRITE_WALK = os.path.join(ASSETS_DIR, "sims", "walk.png")
SIM_SPRITE_SWIM = os.path.join(ASSETS_DIR, "sims", "swim.png")
# Display height in world units (scaled by camera zoom in renderer)
SIM_SPRITE_BASE_HEIGHT = 40
TIMELINE_HEIGHT = 44
TOOLBAR_WIDTH = 184
BOTTOM_BAR_HEIGHT = 40
# Inner margin around the map (fixes labels cut off at edges, clears toolbar overlap)
UI_MAP_PADDING = 10

# Browser dashboard (started alongside pygame; see dashboard_server.py)
DASHBOARD_HOST = os.environ.get("DASHBOARD_HOST", "127.0.0.1")
DASHBOARD_PORT = int(os.environ.get("DASHBOARD_PORT", "8765"))

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
