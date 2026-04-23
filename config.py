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
