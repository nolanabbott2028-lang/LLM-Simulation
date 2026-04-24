import json
from collections import deque
from world import WorldState
from entities.sim import Sim
from entities.structure import Structure
from entities.resource import ResourceObject


def _sim_to_dict(sim: Sim) -> dict:
    return {
        "id": sim.id, "name": sim.name,
        "position": list(sim.position),
        "health": sim.health, "hunger": sim.hunger, "thirst": sim.thirst, "energy": sim.energy,
        "age": sim.age, "role": sim.role,
        "relationships": sim.relationships,
        "memory": sim.memory,
        "inventory": sim.inventory,
        "skills": sim.skills,
        "language_fluency": sim.language_fluency,
        "traits": getattr(sim, "traits", {"aggression": 50, "intelligence": 50, "sociability": 50}),
        "safety": getattr(sim, "safety", 50.0),
        "status": getattr(sim, "status", 50),
        "beliefs": dict(getattr(sim, "beliefs", {}) or {}),
        "alive": sim.alive,
    }


def _sim_from_dict(d: dict) -> Sim:
    return Sim(
        id=d["id"], name=d["name"],
        position=tuple(d["position"]),
        health=d["health"], hunger=d["hunger"], thirst=d.get("thirst", 100.0), energy=d["energy"],
        age=d["age"], role=d.get("role"),
        relationships=d.get("relationships", {}),
        memory=d.get("memory", []),
        inventory=d.get("inventory", {}),
        skills=d.get("skills", {}),
        language_fluency=d.get("language_fluency", 0.0),
        traits=d.get("traits", {"aggression": 50, "intelligence": 50, "sociability": 50}),
        safety=d.get("safety", 50.0),
        status=d.get("status", 50),
        beliefs=d.get("beliefs", {}),
        alive=d.get("alive", True),
    )


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
        faction_snap = {}
        war_snap = {}
        try:
            from simulation.world_engine import get_world_engine

            eng = get_world_engine(world)
            faction_snap = eng.faction_manager.snapshot()
            war_snap = eng.war_system.snapshot()
        except Exception:
            pass
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
            "language_progress": world.language_progress,
            "sim_running": world.sim_running,
            "speed": world.speed,
            "global_events": list(getattr(world, "global_events", [])[-200:]),
            "crime_log": list(getattr(world, "crime_log", [])),
            "prices": dict(getattr(world, "prices", {})),
            "power_map": dict(getattr(world, "power_map", {})),
            "factions": faction_snap,
            "timeline_events": list(getattr(world, "timeline_events", [])[-400:]),
            "era_pressure_label": getattr(world, "era_pressure_label", None),
            "war_state": war_snap,
            "trade_flow_events": list(getattr(world, "trade_flow_events", []) or []),
            "dashboard_bookmark": getattr(world, "dashboard_bookmark", None),
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
    w.language_progress = data.get("language_progress", 0.0)
    w.sim_running = data["sim_running"]
    w.speed = data["speed"]
    w.global_events = data.get("global_events", [])
    w.crime_log = data.get("crime_log", [])
    w.prices = data.get("prices", {})
    w.power_map = data.get("power_map", {})
    fac = data.get("factions") or {}
    if fac:
        try:
            from simulation.world_engine import get_world_engine

            get_world_engine(w).faction_manager.restore(fac)
        except Exception:
            pass
    w.timeline_events = data.get("timeline_events", [])
    w.era_pressure_label = data.get("era_pressure_label")
    wsnap = data.get("war_state") or {}
    try:
        from simulation.world_engine import get_world_engine

        get_world_engine(w).war_system.restore(wsnap)
    except Exception:
        pass
    w.trade_flow_events = deque(data.get("trade_flow_events", []), maxlen=120)
    w.dashboard_bookmark = data.get("dashboard_bookmark")
    return w
