import json
from world import WorldState
from entities.sim import Sim
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
    return Sim(
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
