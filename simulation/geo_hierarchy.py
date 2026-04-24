"""
Hierarchical map geometry for LOD dashboards: regions → provinces → cities → towns.
Vector polygons in world coordinates; ideology/population aggregated from agents in bounds.
"""
from __future__ import annotations

from typing import Any

from config import TILE_SIZE, WORLD_TILES_H, WORLD_TILES_W
from simulation.ideology import BELIEF_KEYS, ensure_beliefs
from simulation.quadtree import agents_in_rect_quad, build_agent_quadtree


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


_REGION_NAMES = [
    "Frostpeak Marches",
    "Stonehall Reach",
    "Ironridge Expanse",
    "Ashton Vale",
    "Greenvale Basin",
    "Northwatch Frontier",
    "Sundervale Coast",
    "Wildhold Deep",
    "Darkmere Sink",
    "Silverstep Ridge",
    "Emberfen Lowlands",
    "Stormglass Isles",
]

_PROVINCE_SUFFIXES = ("Upper", "Lower", "Inner", "Outer")


def _rect_polygon(x0: float, y0: float, x1: float, y1: float) -> list[list[float]]:
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def _avg_ideology(sims: list[Any]) -> dict[str, float]:
    if not sims:
        return {k: 0.0 for k in BELIEF_KEYS}
    acc = {k: 0.0 for k in BELIEF_KEYS}
    for s in sims:
        b = ensure_beliefs(s)
        for k in BELIEF_KEYS:
            acc[k] += float(b.get(k, 0.0))
    n = float(len(sims))
    return {k: round(acc[k] / n, 1) for k in BELIEF_KEYS}


def _region_label(ri: int, ci: int, rf: int, cf: int) -> str:
    idx = ri * cf + ci
    if idx < len(_REGION_NAMES):
        return _REGION_NAMES[idx]
    return f"Region {ri}-{ci}"


def _province_label(region_name: str, side: int) -> str:
    suf = _PROVINCE_SUFFIXES[side % len(_PROVINCE_SUFFIXES)]
    return f"{suf} {region_name.split()[0]}"


def build_map_lod(world: Any, fm: Any) -> dict[str, Any]:
    """
    Build regions (coarse grid), provinces (split each region), cities & towns (points).
    Faction on a region is chosen by dominant population or round-robin if empty.
    """
    W = float(WORLD_TILES_W * TILE_SIZE)
    H = float(WORLD_TILES_H * TILE_SIZE)
    rf, cf = 3, 4
    cell_w = W / cf
    cell_h = H / rf

    faction_ids = list(fm.factions.keys()) if getattr(fm, "factions", None) else []

    tree = build_agent_quadtree(world)

    def get_sim(sid: str) -> Any:
        return world.sims.get(sid)

    def agents_rect(xa: float, ya: float, xb: float, yb: float) -> list[Any]:
        return agents_in_rect_quad(world, tree, xa, ya, xb, yb, get_sim)

    regions_out: list[dict[str, Any]] = []
    provinces_out: list[dict[str, Any]] = []
    cities_out: list[dict[str, Any]] = []
    towns_out: list[dict[str, Any]] = []

    for ri in range(rf):
        for ci in range(cf):
            x0 = ci * cell_w
            y0 = ri * cell_h
            x1 = x0 + cell_w
            y1 = y0 + cell_h
            rid = f"reg_{ri}_{ci}"
            rname = _region_label(ri, ci, rf, cf)
            rsims = agents_rect(x0, y0, x1, y1)

            fac_id = None
            if rsims:
                counts: dict[str | None, int] = {}
                for s in rsims:
                    fid = fm.sim_faction.get(s.id) if fm else None
                    counts[fid] = counts.get(fid, 0) + 1
                fac_id = max(counts, key=lambda k: counts[k])
            elif faction_ids:
                fac_id = faction_ids[(ri * cf + ci) % len(faction_ids)]

            regions_out.append(
                {
                    "id": rid,
                    "name": rname,
                    "polygon": _rect_polygon(x0, y0, x1, y1),
                    "faction_id": fac_id,
                    "population": len(rsims),
                    "ideology": _avg_ideology(rsims),
                }
            )

            mid_x = (x0 + x1) * 0.5
            for side, (px0, px1) in enumerate([(x0, mid_x), (mid_x, x1)]):
                pid = f"prov_{ri}_{ci}_{side}"
                pname = _province_label(rname, side)
                psims = agents_rect(px0, y0, px1, y1)
                provinces_out.append(
                    {
                        "id": pid,
                        "name": pname,
                        "polygon": _rect_polygon(px0, y0, px1, y1),
                        "region_id": rid,
                        "faction_id": fac_id,
                        "population": len(psims),
                        "ideology": _avg_ideology(psims),
                    }
                )

                cx = (px0 + px1) * 0.5
                cy = (y0 + y1) * 0.5
                city_id = f"city_{ri}_{ci}_{side}"
                cities_out.append(
                    {
                        "id": city_id,
                        "name": f"{pname.split()[-1]} Mark",
                        "x": round(cx, 1),
                        "y": round(cy, 1),
                        "province_id": pid,
                        "region_id": rid,
                        "faction_id": fac_id,
                        "population": max(1, len(psims) + 1),
                        "ideology": _avg_ideology(psims),
                    }
                )

                tw = (px1 - px0) * 0.22
                th = (y1 - y0) * 0.22
                for ti, (dx, dy) in enumerate(
                    [(-tw, -th), (tw * 0.6, th * 0.7)], start=1
                ):
                    tx, ty = cx + dx, cy + dy
                    tx = _clamp(tx, px0 + 8, px1 - 8)
                    ty = _clamp(ty, y0 + 8, y1 - 8)
                    towns_out.append(
                        {
                            "id": f"town_{ri}_{ci}_{side}_{ti}",
                            "name": f"Hamlet {ri}{ci}{side}{ti}",
                            "x": round(tx, 1),
                            "y": round(ty, 1),
                            "province_id": pid,
                            "city_id": city_id,
                            "population": max(0, len(psims) // 3),
                        }
                    )

    return {
        "regions": regions_out,
        "provinces": provinces_out,
        "cities": cities_out,
        "towns": towns_out,
        "spatial_index": "quadtree",
    }
