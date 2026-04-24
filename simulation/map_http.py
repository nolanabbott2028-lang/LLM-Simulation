"""Shared map tile / LOD HTTP payloads (FastAPI + stdlib dashboard)."""
from __future__ import annotations

from typing import Any

from simulation.geo_hierarchy import build_map_lod
from simulation.terrain_tiles import fog_of_war_payload, terrain_tile_payload
from simulation.world_engine import get_world_engine


def _bbox_polygon(poly: list[list[float]]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _aabb_intersects(
    ax0: float,
    ay0: float,
    ax1: float,
    ay1: float,
    bx0: float,
    by0: float,
    bx1: float,
    by1: float,
) -> bool:
    if ax0 > ax1:
        ax0, ax1 = ax1, ax0
    if ay0 > ay1:
        ay0, ay1 = ay1, ay0
    if bx0 > bx1:
        bx0, bx1 = bx1, bx0
    if by0 > by1:
        by0, by1 = by1, by0
    return not (ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0)


def map_terrain(world: Any, lod: int, tx: int, ty: int) -> dict[str, Any]:
    return terrain_tile_payload(world, lod, tx, ty)


def map_regions_bbox(
    world: Any,
    min_x: float | None,
    min_y: float | None,
    max_x: float | None,
    max_y: float | None,
) -> dict[str, Any]:
    eng = get_world_engine(world)
    fm = eng.faction_manager
    lod = build_map_lod(world, fm)
    regions = lod["regions"]
    if min_x is None or min_y is None or max_x is None or max_y is None:
        return {"regions": regions, "count": len(regions)}
    out = []
    for r in regions:
        x0, y0, x1, y1 = _bbox_polygon(r["polygon"])
        if _aabb_intersects(x0, y0, x1, y1, min_x, min_y, max_x, max_y):
            out.append(r)
    return {"regions": out, "count": len(out), "bbox": [min_x, min_y, max_x, max_y]}


def map_provinces_bbox(
    world: Any,
    min_x: float | None,
    min_y: float | None,
    max_x: float | None,
    max_y: float | None,
) -> dict[str, Any]:
    eng = get_world_engine(world)
    fm = eng.faction_manager
    lod = build_map_lod(world, fm)
    provinces = lod["provinces"]
    if min_x is None or min_y is None or max_x is None or max_y is None:
        return {"provinces": provinces, "count": len(provinces)}
    out = []
    for p in provinces:
        x0, y0, x1, y1 = _bbox_polygon(p["polygon"])
        if _aabb_intersects(x0, y0, x1, y1, min_x, min_y, max_x, max_y):
            out.append(p)
    return {"provinces": out, "count": len(out), "bbox": [min_x, min_y, max_x, max_y]}


def map_cities_bbox(
    world: Any,
    min_x: float | None,
    min_y: float | None,
    max_x: float | None,
    max_y: float | None,
) -> dict[str, Any]:
    eng = get_world_engine(world)
    fm = eng.faction_manager
    lod = build_map_lod(world, fm)
    cities = lod["cities"]
    if min_x is None or min_y is None or max_x is None or max_y is None:
        return {"cities": cities, "count": len(cities)}
    out = [
        c
        for c in cities
        if min_x <= c["x"] <= max_x and min_y <= c["y"] <= max_y
    ]
    return {"cities": out, "count": len(out), "bbox": [min_x, min_y, max_x, max_y]}


def map_towns_bbox(
    world: Any,
    min_x: float | None,
    min_y: float | None,
    max_x: float | None,
    max_y: float | None,
) -> dict[str, Any]:
    eng = get_world_engine(world)
    fm = eng.faction_manager
    lod = build_map_lod(world, fm)
    towns = lod["towns"]
    if min_x is None or min_y is None or max_x is None or max_y is None:
        return {"towns": towns, "count": len(towns)}
    out = [
        t
        for t in towns
        if min_x <= t["x"] <= max_x and min_y <= t["y"] <= max_y
    ]
    return {"towns": out, "count": len(out), "bbox": [min_x, min_y, max_x, max_y]}


def map_fog(world: Any) -> dict[str, Any]:
    return {"fog": fog_of_war_payload(world)}
