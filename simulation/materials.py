"""Map resource nodes → inventory materials and world stock accounting."""
from __future__ import annotations

from typing import Any

# Primary material produced when a sim gathers from this node type (one gather tick).
# Nodes not listed are not gatherable (or fall back to legacy key = object_type).
# Placed as map objects but not harvested like deposits.
NON_GATHERABLE_NODES = frozenset({"hut", "shrine"})

NODE_GATHER_YIELDS: dict[str, list[tuple[str, float]]] = {
    "berry_bush": [("berries", 1.0)],
    "tree": [("wood", 1.0)],
    "stone_deposit": [("stone", 1.0)],
    "river_source": [("fresh_water", 1.0)],
    "animal_spawn": [("meat", 1.0), ("hide", 0.35)],
    "farm_plot": [("grain", 1.0)],
}


def gather_yields_for_node(object_type: str) -> list[tuple[str, float]]:
    """Return (material, expected_amount) for one gather action."""
    if object_type in NON_GATHERABLE_NODES:
        return []
    if object_type in NODE_GATHER_YIELDS:
        return list(NODE_GATHER_YIELDS[object_type])
    # Legacy / unknown objects: use type name as material key
    return [(object_type, 1.0)]


def primary_material_for_node(object_type: str) -> str | None:
    """Single bucket key for undiscovered map stock (one material per node)."""
    if object_type in NON_GATHERABLE_NODES:
        return None
    ys = gather_yields_for_node(object_type)
    return ys[0][0] if ys else None


def world_stock_from_nodes(world: Any) -> dict[str, float]:
    """Sum quantities still in the ground, keyed by primary material type."""
    out: dict[str, float] = {}
    with world.lock:
        for res in world.resources.values():
            if res.depleted:
                continue
            pm = primary_material_for_node(res.object_type)
            if pm is None:
                continue
            q = float(res.quantity)
            out[pm] = out.get(pm, 0.0) + q
    return out


def inventory_totals(world: Any) -> dict[str, float]:
    out: dict[str, float] = {}
    with world.lock:
        for s in world.sims.values():
            if not s.alive:
                continue
            for k, v in s.inventory.items():
                out[k] = out.get(k, 0.0) + float(v)
    return out


def combined_resource_totals(world: Any) -> dict[str, float]:
    """Carried goods plus material still available at map nodes."""
    combined = dict(inventory_totals(world))
    for k, v in world_stock_from_nodes(world).items():
        combined[k] = combined.get(k, 0.0) + v
    return combined
