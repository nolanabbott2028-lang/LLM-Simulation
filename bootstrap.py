"""Place Adam & Eve when the world starts empty (same IDs as manual world-builder spawn)."""
from __future__ import annotations

from config import TILE_SIZE, WORLD_TILES_H, WORLD_TILES_W
from entities.sim import Sim
from simulation.factions import Faction
from simulation.world_engine import get_world_engine


def spawn_adam_eve_if_empty(world) -> None:
    with world.lock:
        if world.sims:
            return
        cx = (WORLD_TILES_W * TILE_SIZE) / 2
        cy = (WORLD_TILES_H * TILE_SIZE) / 2
        _spawn_pair_at(world, cx, cy)


def spawn_adam_eve_near(world, wx: float, wy: float) -> tuple[bool, str]:
    """Place Adam & Eve offset from (wx, wy). Only when no living sims exist."""
    with world.lock:
        if any(s.alive for s in world.sims.values()):
            return False, "Living population already exists."
        for sid in [k for k, s in world.sims.items() if not s.alive]:
            world.sims.pop(sid, None)
        wx = max(float(TILE_SIZE), min(WORLD_TILES_W * TILE_SIZE - TILE_SIZE, wx))
        wy = max(float(TILE_SIZE), min(WORLD_TILES_H * TILE_SIZE - TILE_SIZE, wy))
        _spawn_pair_at(world, wx, wy)
    try:
        from simulation.timeline_engine import TimelineEngine

        TimelineEngine(world).log(
            "founding",
            "Two founders appear — the story begins anew.",
            {"x": round(wx, 1), "y": round(wy, 1)},
        )
    except Exception:
        pass
    return True, "ok"


def _register_founders_faction(world) -> None:
    """Two-person band for early game (emergent factions need ≥3)."""
    eng = get_world_engine(world)
    fm = eng.faction_manager
    fid = "founders"
    fac = Faction(id=fid, members={"adam", "eve"}, leader="adam")
    fm.factions[fid] = fac
    fm.sim_faction["adam"] = fid
    fm.sim_faction["eve"] = fid
    fm._sync_shared_inventory(fac)


def _spawn_pair_at(world, cx: float, cy: float) -> None:
    adam = Sim(id="adam", name="Adam", position=(cx - TILE_SIZE * 2, cy))
    eve = Sim(id="eve", name="Eve", position=(cx + TILE_SIZE * 2.5, cy))
    world.add_sim(adam)
    world.add_sim(eve)
    _register_founders_faction(world)
    world.sim_running = True
    world.paused = False
