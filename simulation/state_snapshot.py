"""Compact JSON-serializable view for dashboards / WebSocket bridges (Pygame stays main UI)."""
from __future__ import annotations

from typing import Any

from config import TILE_SIZE, WORLD_TILES_H, WORLD_TILES_W
from simulation.ideology import BELIEF_KEYS, aggregate_beliefs, cosine_similarity, ensure_beliefs
from simulation.geo_hierarchy import build_map_lod
from simulation.terrain_tiles import fog_of_war_payload
from simulation.replay_buffer import replay_append, replay_meta
from simulation.materials import combined_resource_totals
from simulation.world_engine import get_world_engine


def _faction_centroid(world: Any, fm: Any, fid: str) -> tuple[float, float]:
    fac = fm.factions.get(fid)
    if not fac or not fac.members:
        return (WORLD_TILES_W * TILE_SIZE * 0.5, WORLD_TILES_H * TILE_SIZE * 0.5)
    sx = sy = 0.0
    n = 0
    for sid in fac.members:
        s = world.sims.get(sid)
        if s and s.alive:
            sx += s.position[0]
            sy += s.position[1]
            n += 1
    if n == 0:
        return (WORLD_TILES_W * TILE_SIZE * 0.5, WORLD_TILES_H * TILE_SIZE * 0.5)
    return (sx / n, sy / n)


def _terrain_sample(world: Any, stride: int = 8) -> list[list[str]]:
    rows: list[list[str]] = []
    with world.lock:
        for r in range(0, WORLD_TILES_H, stride):
            row: list[str] = []
            for c in range(0, WORLD_TILES_W, stride):
                try:
                    row.append(world.terrain[r][c])
                except (IndexError, TypeError):
                    row.append("grass")
            rows.append(row)
    return rows


def _war_overlay(world: Any, fm: Any, ws: Any) -> list[dict[str, Any]]:
    ids = list(fm.factions.keys())
    out: list[dict[str, Any]] = []
    for i, fa in enumerate(ids):
        for fb in ids[i + 1 :]:
            h = ws.hostility(fm, fa, fb)
            if h < 35:
                continue
            pa = ws.military_power(fm, fa)
            pb = ws.military_power(fm, fb)
            ax, ay = _faction_centroid(world, fm, fa)
            bx, by = _faction_centroid(world, fm, fb)
            out.append(
                {
                    "pair": [fa, fb],
                    "hostility": round(h, 1),
                    "power_a": round(pa, 2),
                    "power_b": round(pb, 2),
                    "imbalance": round(pb - pa, 2),
                    "front_a": {"x": round(ax, 1), "y": round(ay, 1)},
                    "front_b": {"x": round(bx, 1), "y": round(by, 1)},
                }
            )
    out.sort(key=lambda x: -x["hostility"])
    return out[:24]


def _stability(world: Any) -> float:
    sts: list[float] = []
    hun: list[float] = []
    with world.lock:
        for s in world.sims.values():
            if not s.alive:
                continue
            sts.append(float(getattr(s, "status", 50)))
            hun.append(min(100.0, float(s.hunger)))
    if not sts:
        return 50.0
    ms = sum(sts) / len(sts)
    mh = sum(hun) / len(hun)
    return round(min(100.0, ms * 0.55 + mh * 0.45), 1)


def _dominant_ideology_labels(world: Any) -> dict[str, str]:
    acc = {k: 0.0 for k in BELIEF_KEYS}
    n = 0
    with world.lock:
        for s in world.sims.values():
            if not s.alive:
                continue
            b = ensure_beliefs(s)
            for k in BELIEF_KEYS:
                acc[k] += b[k]
            n += 1
    if n == 0:
        return {k: "UNKNOWN" for k in BELIEF_KEYS}

    def lvl(v: float) -> str:
        if v > 22:
            return "HIGH"
        if v < -22:
            return "LOW"
        return "MEDIUM"

    avg = {k: acc[k] / n for k in BELIEF_KEYS}
    return {
        "cooperation": lvl(avg["cooperation_good"]),
        "authority": lvl(avg["authority_good"]),
        "trade": lvl(avg["trade_good"]),
        "violence": lvl(avg["violence_justified"]),
        "outgroup": lvl(avg["outgroup_danger"]),
    }


def get_world_snapshot(world: Any, *, record_replay: bool = True) -> dict[str, Any]:
    """Single snapshot for external observers — canvas + overlays."""
    eng = get_world_engine(world)
    fm = eng.faction_manager
    ws = eng.war_system

    agents: list[dict[str, Any]] = []
    with world.lock:
        sim_day = world.sim_day
        sim_year = world.sim_year
        for sid, s in world.sims.items():
            if not s.alive:
                continue
            fid = fm.sim_faction.get(sid)
            b = ensure_beliefs(s)
            ix = b["cooperation_good"] - b["violence_justified"]
            iy = b["authority_good"] - b["outgroup_danger"]
            agents.append(
                {
                    "id": sid,
                    "name": s.name,
                    "x": round(s.position[0], 1),
                    "y": round(s.position[1], 1),
                    "hunger": round(s.hunger, 1),
                    "energy": round(s.energy, 1),
                    "faction": fid,
                    "beliefs": dict(b),
                    "ideology_xy": {"x": round(ix, 1), "y": round(iy, 1)},
                    "status": getattr(s, "status", 50),
                    "in_water": bool(getattr(s, "in_water", False)),
                    "moving": bool(getattr(s, "moving", False)),
                    "facing": float(getattr(s, "facing", 1.0)),
                }
            )

        factions_out: list[dict[str, Any]] = []
        for fid, fac in fm.factions.items():
            agg = aggregate_beliefs(world, fac.members)
            lx, ly = (0.0, 0.0)
            if fac.leader and fac.leader in world.sims:
                ls = world.sims[fac.leader]
                lx, ly = ls.position[0], ls.position[1]
            ch = float(getattr(fac, "leader_charisma", 1.15))
            propaganda = round(ch * (len(fac.members) ** 0.5) * 12.0, 1)
            factions_out.append(
                {
                    "id": fid,
                    "size": len(fac.members),
                    "leader": fac.leader,
                    "leader_x": round(lx, 1),
                    "leader_y": round(ly, 1),
                    "ideology": agg,
                    "military_power": round(ws.military_power(fm, fid), 2),
                    "narratives": list(getattr(fac, "narratives", [])[-4:]),
                    "propaganda_power": propaganda,
                    "centroid_x": round(_faction_centroid(world, fm, fid)[0], 1),
                    "centroid_y": round(_faction_centroid(world, fm, fid)[1], 1),
                }
            )

        te = getattr(world, "timeline_events", []) or []
        tail = te[-18:]
        off = len(te) - len(tail)
        timeline = [{**e, "event_index": off + i} for i, e in enumerate(tail)]
        terrain_cells = _terrain_sample(world)

        resources_out: list[dict[str, Any]] = []
        for rid, res in world.resources.items():
            if res.depleted:
                continue
            resources_out.append(
                {
                    "id": rid,
                    "type": res.object_type,
                    "x": round(res.position[0], 1),
                    "y": round(res.position[1], 1),
                    "amount": float(res.quantity),
                }
            )

        structures_out: list[dict[str, Any]] = []
        for sid, st in world.structures.items():
            structures_out.append(
                {
                    "id": sid,
                    "name": st.name,
                    "type": st.structure_type,
                    "x": round(st.position[0], 1),
                    "y": round(st.position[1], 1),
                }
            )

    total_inv = 0.0
    with world.lock:
        for s in world.sims.values():
            total_inv += sum(float(v) for v in s.inventory.values())

    war_ov = _war_overlay(world, fm, ws)

    resource_totals: dict[str, float] = {}
    raw_totals = combined_resource_totals(world)
    for k, v in sorted(raw_totals.items()):
        resource_totals[k] = round(float(v), 1)

    trade_tail = []
    with world.lock:
        tf = getattr(world, "trade_flow_events", None)
        if tf:
            trade_tail = list(tf)[-40:]
    bm = getattr(world, "dashboard_bookmark", None)

    map_lod = build_map_lod(world, fm)
    fog = fog_of_war_payload(world, grid_w=28, grid_h=28)

    snap = {
        "time": {
            "year": sim_year,
            "day": sim_day,
            "era": world.current_era(),
        },
        "paused": getattr(world, "paused", False),
        "speed": getattr(world, "speed", 1),
        "sim_running": getattr(world, "sim_running", False),
        "world_bounds": {
            "width": WORLD_TILES_W * TILE_SIZE,
            "height": WORLD_TILES_H * TILE_SIZE,
        },
        "terrain_sample": terrain_cells,
        "agents": agents,
        "factions": factions_out,
        "resources": resources_out[:400],
        "structures": structures_out,
        "economy": {
            "total_inventory_mass": round(total_inv, 1),
            "prices": dict(getattr(world, "prices", {})),
            "resource_totals": resource_totals,
        },
        "wars": list(getattr(world, "active_wars", [])),
        "war_overlay": war_ov,
        "timeline": timeline,
        "era_hint": getattr(world, "era_pressure_label", None),
        "bookmark": bm,
        "trade_flow": trade_tail,
        "replay": replay_meta(),
        "stats": {
            "population": len(agents),
            "faction_count": len(factions_out),
            "active_war_signals": len(war_ov),
            "stability": _stability(world),
            "dominant_ideology": _dominant_ideology_labels(world),
        },
        "map_lod": map_lod,
        "fog_of_war": fog,
    }
    if record_replay and getattr(world, "dashboard_replay_enabled", True):
        replay_append(snap)
    return snap


def get_agent_focus(world: Any, agent_id: str) -> dict[str, Any] | None:
    """Detail payload for dashboard focus mode."""
    eng = get_world_engine(world)
    fm = eng.faction_manager
    with world.lock:
        s = world.sims.get(agent_id)
        if not s or not s.alive:
            return None
        fid = fm.sim_faction.get(agent_id)
        rel_summary = []
        for oid, rel in list(s.relationships.items())[:12]:
            o = world.sims.get(oid)
            if o:
                rel_summary.append(
                    {
                        "id": oid,
                        "name": o.name,
                        "trust": rel.get("trust", 0),
                        "fear": rel.get("fear", 0),
                    }
                )
        fac_block = None
        if fid and fid in fm.factions:
            fac = fm.factions[fid]
            fac_block = {
                "id": fid,
                "leader": fac.leader,
                "narratives": list(getattr(fac, "narratives", [])[-5:]),
                "mates": len(fac.members),
            }
        fears = [float(rel.get("fear", 0)) for rel in s.relationships.values()]
        bonds = [float(rel.get("bond", 0)) for rel in s.relationships.values()]
        avg_fear = sum(fears) / len(fears) if fears else 0.0
        avg_bond = sum(bonds) / len(bonds) if bonds else 0.0
        safety = float(getattr(s, "safety", 50.0))
        stress = max(0.0, min(100.0, 100.0 - safety))
        return {
            "id": s.id,
            "name": s.name,
            "beliefs": dict(ensure_beliefs(s)),
            "memory_recent": list(s.memory[-8:]),
            "relationships": rel_summary,
            "faction": fac_block,
            "status": getattr(s, "status", 50),
            "hunger": s.hunger,
            "inventory": dict(s.inventory),
            "occupation": s.role or "Traveler",
            "vitals": {
                "stress": round(stress, 1),
                "fear": round(min(100.0, avg_fear), 1),
                "loyalty": round(min(100.0, avg_bond), 1),
                "health": round(float(s.health), 1),
            },
        }


def ideology_graph_snapshot(world: Any) -> dict[str, Any]:
    """Nodes = agents with belief vectors; edges = cosine similarity above threshold."""
    eng = get_world_engine(world)
    nodes = []
    edges = []
    with world.lock:
        ids = [s.id for s in world.sims.values() if s.alive]
        vecs = {sid: {k: ensure_beliefs(world.sims[sid])[k] for k in BELIEF_KEYS} for sid in ids}
        fid_of = dict(eng.faction_manager.sim_faction)
        for sid in ids:
            nodes.append({"id": sid, "group": fid_of.get(sid), "beliefs": vecs[sid]})
        for i, a in enumerate(ids):
            for b in ids[i + 1 :]:
                sim_ab = cosine_similarity(vecs[a], vecs[b])
                if sim_ab >= 0.35:
                    edges.append({"source": a, "target": b, "value": round(sim_ab, 3)})
    return {"nodes": nodes, "links": edges}
