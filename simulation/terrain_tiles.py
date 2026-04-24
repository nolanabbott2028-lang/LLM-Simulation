"""
Procedural terrain tiles for dashboard: height + biome from world grid + noise.
Higher `lod` → smaller tiles and finer cell grid (more detail when zoomed in).
"""
from __future__ import annotations

import math
from typing import Any

from config import TILE_SIZE, WORLD_TILES_H, WORLD_TILES_W

# Terrain classification keys (stable for API / frontend)
DEEP_WATER = "deep_water"
SHALLOWS = "shallows"
GRASS = "grassland"
FOREST = "forest"
FOOTHILLS = "foothills"
MOUNTAIN = "mountain"
PEAK = "peak"


def _sin_hash(x: float, y: float) -> float:
    """Deterministic 0–1 noise from coordinates."""
    s = math.sin(x * 12.9898 + y * 78.233) * 43758.5453
    return s - math.floor(s)


def _fbm(x: float, y: float, octaves: int = 4) -> float:
    v = 0.0
    a = 0.5
    f = 1.0
    for _ in range(octaves):
        v += a * _sin_hash(x * f, y * f)
        f *= 2.0
        a *= 0.5
    return v


def _terrain_height(world: Any, wx: float, wy: float) -> float:
    """Normalized height 0–1 combining world cell + multi-scale noise (mountains / basins)."""
    col = int(wx // TILE_SIZE)
    row = int(wy // TILE_SIZE)
    col = max(0, min(WORLD_TILES_W - 1, col))
    row = max(0, min(WORLD_TILES_H - 1, row))
    with world.lock:
        cell = world.terrain[row][col]
    base = 0.52
    if cell == "water":
        base = 0.28
    elif cell == "forest":
        base = 0.58
    else:
        base = 0.48
    nx = wx * 0.004
    ny = wy * 0.004
    ridged = abs(_fbm(nx, ny, 5) - 0.5) * 2.0
    mountains = _fbm(nx * 0.6 + 10, ny * 0.6, 4) * 0.42
    basins = (1.0 - _fbm(nx * 0.25, ny * 0.25 + 3, 3)) * 0.18
    h = base + mountains - basins + (ridged - 0.5) * 0.12
    return max(0.0, min(1.0, h))


def _classify(h: float, base_cell: str) -> tuple[str, float]:
    """Return biome key and display height 0–1."""
    if base_cell == "water" and h < 0.38:
        return DEEP_WATER, h
    if h < 0.36:
        return DEEP_WATER, h
    if h < 0.42:
        return SHALLOWS, h
    if h < 0.52:
        return GRASS if base_cell != "forest" else FOREST, h
    if h < 0.62:
        return FOREST, h
    if h < 0.74:
        return FOOTHILLS, h
    if h < 0.86:
        return MOUNTAIN, h
    return PEAK, h


def _cell_at(world: Any, wx: float, wy: float) -> dict[str, Any]:
    col = int(wx // TILE_SIZE)
    row = int(wy // TILE_SIZE)
    col = max(0, min(WORLD_TILES_W - 1, col))
    row = max(0, min(WORLD_TILES_H - 1, row))
    with world.lock:
        base_cell = world.terrain[row][col]
    h = _terrain_height(world, wx, wy)
    biome, _ = _classify(h, base_cell)
    return {"biome": biome, "h": round(h, 3)}


def terrain_tile_payload(world: Any, lod: int, tx: int, ty: int) -> dict[str, Any]:
    """
    One terrain tile: `lod` in [0, 6] — 2^lod tiles span the world per axis.
    More cells per tile when lod is higher (finer sampling).
    """
    lod = max(0, min(6, int(lod)))
    W = float(WORLD_TILES_W * TILE_SIZE)
    H = float(WORLD_TILES_H * TILE_SIZE)
    nt = 2**lod
    tw = W / nt
    th = H / nt
    if tx < 0 or ty < 0 or tx >= nt or ty >= nt:
        return {"error": "tile out of bounds", "lod": lod, "nt": nt, "tx": tx, "ty": ty}

    x0 = tx * tw
    y0 = ty * th
    x1 = x0 + tw
    y1 = y0 + th

    # Cell resolution: coarse at low lod, dense at high lod
    gw = 6 + lod * 6
    gh = 6 + lod * 6
    dx = tw / gw
    dy = th / gh

    rows: list[list[dict[str, Any]]] = []
    for j in range(gh):
        row: list[dict[str, Any]] = []
        for i in range(gw):
            sx = x0 + (i + 0.5) * dx
            sy = y0 + (j + 0.5) * dy
            row.append(_cell_at(world, sx, sy))
        rows.append(row)

    return {
        "lod": lod,
        "tx": tx,
        "ty": ty,
        "nt": nt,
        "world_rect": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
        "grid": {"w": gw, "h": gh},
        "cells": rows,
    }


def fog_of_war_payload(world: Any, grid_w: int = 32, grid_h: int = 32) -> dict[str, Any]:
    """
    Coarse visibility 0–1: full near any alive agent; fades with distance (exploration hook).
    """
    from config import TILE_SIZE as TS

    W = float(WORLD_TILES_W * TS)
    H = float(WORLD_TILES_H * TS)
    gw = max(8, min(64, grid_w))
    gh = max(8, min(64, grid_h))
    cw = W / gw
    ch = H / gh

    agents: list[tuple[float, float]] = []
    with world.lock:
        for s in world.sims.values():
            if s.alive:
                agents.append((float(s.position[0]), float(s.position[1])))

    cells: list[float] = []
    vis_radius = min(W, H) * 0.12
    vis_radius = max(vis_radius, TS * 8)

    for j in range(gh):
        for i in range(gw):
            cx = (i + 0.5) * cw
            cy = (j + 0.5) * ch
            if not agents:
                v = 0.35
            else:
                d = min(math.hypot(cx - ax, cy - ay) for ax, ay in agents)
                # 1 in sight, taper to 0.25 fog
                t = 1.0 - min(1.0, d / vis_radius)
                v = 0.22 + 0.78 * (t * t)
            cells.append(round(v, 3))

    return {
        "grid_w": gw,
        "grid_h": gh,
        "world_bounds": {"width": W, "height": H},
        "cells": cells,
    }
