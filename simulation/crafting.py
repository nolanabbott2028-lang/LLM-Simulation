"""Crafting: recipes, validation, and applying crafts (tools, QoL, structures)."""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from typing import Any

from entities.structure import Structure


@dataclass(frozen=True)
class Recipe:
    id: str
    name: str
    inputs: dict[str, float]
    outputs: dict[str, float]  # inventory items only
    structure: tuple[str, str] | None = None  # (structure_type, display_name) placed at sim


RECIPES: dict[str, Recipe] = {
    "stone_axe": Recipe(
        "stone_axe",
        "Stone axe",
        {"wood": 2.0, "stone": 1.0},
        {"stone_axe": 1.0},
    ),
    "wooden_hammer": Recipe(
        "wooden_hammer",
        "Wooden hammer",
        {"wood": 3.0},
        {"wooden_hammer": 1.0},
    ),
    "bedroll": Recipe(
        "bedroll",
        "Bedroll",
        {"wood": 2.0, "hide": 2.0},
        {"bedroll": 1.0},
    ),
    "pottery": Recipe(
        "pottery",
        "Pottery",
        {"stone": 3.0, "wood": 1.0},
        {"pottery": 1.0},
    ),
    "cottage": Recipe(
        "cottage",
        "Cottage",
        {"wood": 8.0, "stone": 4.0},
        {},
        structure=("cottage", "Cottage"),
    ),
    "shrine": Recipe(
        "shrine",
        "Shrine",
        {"stone": 6.0, "wood": 2.0},
        {},
        structure=("shrine", "Shrine"),
    ),
    "leather_wrap": Recipe(
        "leather_wrap",
        "Leather wraps",
        {"hide": 3.0, "wood": 1.0},
        {"leather_wrap": 1.0},
    ),
}


def _has_inputs(sim: Any, recipe: Recipe) -> bool:
    inv = sim.inventory
    for k, need in recipe.inputs.items():
        if inv.get(k, 0) < need - 1e-6:
            return False
    return True


def _consume(sim: Any, recipe: Recipe) -> None:
    for k, need in recipe.inputs.items():
        sim.inventory[k] = sim.inventory.get(k, 0) - need
        if sim.inventory[k] <= 1e-6:
            sim.inventory.pop(k, None)


def _grant_outputs(sim: Any, recipe: Recipe) -> None:
    for k, amt in recipe.outputs.items():
        sim.inventory[k] = sim.inventory.get(k, 0) + amt


def _dist(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def has_shelter_nearby(sim: Any, world: Any, radius: float = 200.0) -> bool:
    x, y = sim.position
    with world.lock:
        for st in world.structures.values():
            if _dist(x, y, st.position[0], st.position[1]) < radius:
                return True
    return False


def has_structure_type_nearby(sim: Any, world: Any, structure_type: str, radius: float = 260.0) -> bool:
    x, y = sim.position
    with world.lock:
        for st in world.structures.values():
            if st.structure_type != structure_type:
                continue
            if _dist(x, y, st.position[0], st.position[1]) < radius:
                return True
    return False


def try_craft(sim: Any, world: Any, recipe_id: str) -> bool:
    recipe = RECIPES.get(recipe_id)
    if not recipe or not _has_inputs(sim, recipe):
        return False
    _consume(sim, recipe)
    _grant_outputs(sim, recipe)
    if recipe.structure:
        stype, sname = recipe.structure
        struct = Structure(
            id=str(uuid.uuid4())[:8],
            name=sname,
            position=(sim.position[0] + 12, sim.position[1] + 12),
            structure_type=stype,
            built_by=sim.id,
        )
        world.add_structure(struct)
        world.raise_pillar("Infrastructure", 4)
    else:
        world.raise_pillar("Technology", 1.5)
    return True


def suggested_recipe_ids(sim: Any, world: Any) -> list[str]:
    """Ordered list of crafts worth attempting (first = highest priority)."""
    order: list[str] = []
    inv = sim.inventory

    def want(rid: str) -> bool:
        r = RECIPES.get(rid)
        return bool(r) and _has_inputs(sim, r)

    # Skip home recipes if already sheltered
    sheltered = has_shelter_nearby(sim, world)

    if want("stone_axe") and inv.get("stone_axe", 0) < 1:
        order.append("stone_axe")
    if want("wooden_hammer") and inv.get("wooden_hammer", 0) < 1:
        order.append("wooden_hammer")
    if want("cottage") and not sheltered:
        order.append("cottage")
    if want("shrine") and not has_structure_type_nearby(sim, world, "shrine"):
        order.append("shrine")
    if want("bedroll") and inv.get("bedroll", 0) < 1:
        order.append("bedroll")
    if want("leather_wrap") and inv.get("leather_wrap", 0) < 1:
        order.append("leather_wrap")
    if want("pottery") and inv.get("pottery", 0) < 1:
        order.append("pottery")

    # Filter to actually craftable (clay may be missing for pottery)
    return [rid for rid in order if want(rid)]


def perception_crafting(sim: Any, world: Any) -> dict[str, Any]:
    """LLM-facing summary: what can be built now and full recipe list."""
    ready = suggested_recipe_ids(sim, world)
    all_recipes: list[dict[str, Any]] = []
    for rid, r in RECIPES.items():
        entry: dict[str, Any] = {
            "id": rid,
            "name": r.name,
            "inputs": dict(r.inputs),
            "kind": "structure" if r.structure else "items",
        }
        if r.structure:
            entry["builds"] = r.structure[1]
        all_recipes.append(entry)
    return {"ready_now": ready, "recipes": all_recipes}
