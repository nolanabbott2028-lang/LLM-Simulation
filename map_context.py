"""
Map image sampling: classify terrain from pixels, describe surroundings for LLM prompts.
Falls back to world.terrain grid when no image is loaded.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Optional

try:
    import pygame
except ImportError:  # dashboard-only install without a pygame binary
    pygame = None  # type: ignore[assignment, misc]

if TYPE_CHECKING:
    from world import WorldState

from config import TILE_SIZE, WORLD_TILES_W, WORLD_TILES_H

_world_px_w = WORLD_TILES_W * TILE_SIZE
_world_px_h = WORLD_TILES_H * TILE_SIZE

# Original image and scaled copy matching world size (set only when pygame loads a map)
_map_original: Any = None
_map_scaled: Any = None
_map_path: Optional[str] = None


def world_pixel_size() -> tuple[int, int]:
    return _world_px_w, _world_px_h


def has_map_image() -> bool:
    return _map_scaled is not None


def map_surface_for_render() -> Optional[pygame.Surface]:
    return _map_scaled


def get_map_path() -> Optional[str]:
    return _map_path


def _classify_pixel(r: int, g: int, b: int) -> str:
    """Map RGB to a terrain key used in-world (must match TERRAIN_COLORS / world.terrain)."""
    s = r + g + b
    # Light sky / UI backdrop on overworld art — not swimmable; treat as open grassland
    if s > 480 and b > 170 and r > 80 and g > 100 and (b - r) < 100:
        return "grass"
    # Water: blue clearly leads red (lakes/rivers, not bright sky)
    if b > 70 and (b - r) > 12 and b > g - 30:
        return "water"
    # Snow: very bright, low contrast
    if r > 200 and g > 200 and b > 200 and abs(int(r) - g) < 30:
        return "snow"
    # Desert: sandy, warm, not water
    if r > 180 and g > 160 and b < 150 and r > b + 20:
        return "desert"
    # Mountain / rock: grey
    if 100 < r < 190 and abs(r - g) < 30 and abs(g - b) < 35:
        return "mountain"
    # Forest: dark greens
    if g > 60 and g > r and g > b and (r + g + b) < 420 and g < 150:
        return "forest"
    # Default: grass
    return "grass"


def try_load_map(path: str) -> bool:
    """Load a map image from disk, scale to world size. Returns True if successful."""
    global _map_original, _map_scaled, _map_path
    if pygame is None:
        return False
    if not os.path.isfile(path):
        return False
    try:
        surf = pygame.image.load(path)
    except (OSError, Exception):
        return False
    try:
        surf = surf.convert()
    except Exception:
        pass  # no display surface yet; unconverted image still works for smoothscale
    _map_original = surf
    _map_path = path
    _map_scaled = pygame.transform.smoothscale(surf, (_world_px_w, _world_px_h))
    return True


def _sample_rgba(surf: Any, x: int, y: int) -> tuple[int, int, int, int]:
    w, h = surf.get_size()
    x = max(0, min(w - 1, x))
    y = max(0, min(h - 1, y))
    c = surf.get_at((x, y))
    if len(c) >= 3:
        return int(c[0]), int(c[1]), int(c[2]), int(c[3]) if len(c) > 3 else 255
    return 128, 128, 128, 255


def terrain_at_image(x: float, y: float) -> str:
    if _map_scaled is None:
        return "grass"
    ix = int(x)
    iy = int(y)
    r, g, b, _ = _sample_rgba(_map_scaled, ix, iy)
    return _classify_pixel(r, g, b)


def terrain_at_world(x: float, y: float, world: WorldState) -> str:
    if _map_scaled is not None:
        return terrain_at_image(x, y)
    col = int(x // TILE_SIZE)
    row = int(y // TILE_SIZE)
    with world.lock:
        if 0 <= row < len(world.terrain) and 0 <= col < len(world.terrain[0]):
            return world.terrain[row][col]
    return "grass"


def in_water(x: float, y: float, world: WorldState) -> bool:
    return terrain_at_world(x, y, world) == "water"


def adjacent_to_water(x: float, y: float, world: WorldState) -> bool:
    """True if in water or any nearby sample is water (shore drinking)."""
    if in_water(x, y, world):
        return True
    for dx, dy in _dirs():
        if in_water(x + dx, y + dy, world):
            return True
    return False


def _dirs():
    d = 48
    return [(0, 0), (d, 0), (-d, 0), (0, d), (0, -d), (d, d), (d, -d), (-d, d), (-d, -d)]


def nearest_water_direction(x: float, y: float, world: WorldState) -> Optional[str]:
    """Return a short compass note if any sample point is water (you are on shore or near a lake/river)."""
    best = None
    best_d = 1e9
    for dx, dy in _dirs():
        tx, ty = x + dx, y + dy
        if 0 <= tx < _world_px_w and 0 <= ty < _world_px_h:
            if in_water(tx, ty, world):
                dist = (dx * dx + dy * dy) ** 0.5
                if dist < best_d:
                    best_d = dist
                    if dy < -10:
                        best = "north"
                    elif dy > 10:
                        best = "south"
                    elif dx < -10:
                        best = "west"
                    elif dx > 10:
                        best = "east"
                    else:
                        best = "here"
    return best


def environment_paragraph(x: float, y: float, world: WorldState) -> str:
    """Rich situational line for the LLM (no mention of games/simulation in caller)."""
    t = terrain_at_world(x, y, world)
    wdir = nearest_water_direction(x, y, world)
    parts = [f"Underfoot: {t}."]
    if t == "water":
        parts.append(
            "You are in open water. If you are thirsty, you may drink. "
            "If you are not thirsty, you may swim, play in the water, or cross carefully."
        )
    elif wdir:
        parts.append(
            f"Fresh water lies to the {wdir} — you can go there to drink if thirsty, "
            "or to cool off; if you are not thirsty, you might still wade or swim for pleasure."
        )
    if t in ("forest", "grass") and wdir is None and _map_scaled is not None:
        # Darker / greener regions often read as forage
        r, g, b, _ = _sample_rgba(_map_scaled, int(x), int(y))
        if g > r and g > b and (r + g + b) < 400:
            parts.append("Vegetation is rich here; foraging for food is plausible.")
    if t == "mountain":
        parts.append("The ground is rocky and high; good for stone, harder travel.")
    if t in ("desert", "snow"):
        parts.append("This environment is harsh; shelter and water matter more than usual.")
    return " ".join(parts)


def import_map_to_terrain(world: "WorldState") -> None:
    """Overwrite the logical terrain grid from the loaded map (for builder + pathfinding)."""
    if _map_scaled is None:
        return
    with world.lock:
        for r in range(WORLD_TILES_H):
            for c in range(WORLD_TILES_W):
                cx = c * TILE_SIZE + TILE_SIZE // 2
                cy = r * TILE_SIZE + TILE_SIZE // 2
                world.terrain[r][c] = terrain_at_image(float(cx), float(cy))
