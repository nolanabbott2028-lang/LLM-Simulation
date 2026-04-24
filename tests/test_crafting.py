"""Crafting recipes and gather yields."""
import pytest

from entities.resource import ResourceObject
from entities.sim import Sim
from simulation.crafting import has_shelter_nearby, perception_crafting, suggested_recipe_ids, try_craft
from simulation.world_engine import structured_to_legacy
from simulation.materials import combined_resource_totals, gather_yields_for_node
from world import WorldState


@pytest.fixture
def world():
    return WorldState()


def test_gather_yields_use_materials_not_only_node_types():
    assert gather_yields_for_node("tree") == [("wood", 1.0)]
    assert gather_yields_for_node("berry_bush")[0][0] == "berries"
    assert gather_yields_for_node("hut") == []


def test_try_craft_tool_and_totals(world: WorldState):
    s = Sim(id="s1", name="A", position=(100.0, 100.0))
    s.inventory = {"wood": 5.0, "stone": 2.0}
    world.add_sim(s)
    ok = try_craft(s, world, "stone_axe")
    assert ok
    assert s.inventory.get("stone_axe", 0) >= 1
    assert s.inventory.get("wood", 0) == 3.0
    assert s.inventory.get("stone", 0) == 1.0


def test_combined_totals_include_map_stock(world: WorldState):
    world.add_resource(
        ResourceObject(id="r1", object_type="tree", position=(10.0, 10.0), quantity=5)
    )
    s = Sim(id="s2", name="B", position=(50.0, 50.0))
    s.inventory = {"berries": 2.0}
    world.add_sim(s)
    totals = combined_resource_totals(world)
    assert totals.get("berries") == 2.0
    assert totals.get("wood") == 5.0


def test_suggested_recipes_prioritize_tools(world: WorldState):
    s = Sim(id="s3", name="C", position=(200.0, 200.0))
    s.inventory = {"wood": 10.0, "stone": 5.0}
    world.add_sim(s)
    ids = suggested_recipe_ids(s, world)
    assert ids and ids[0] == "stone_axe"


def test_perception_crafting_includes_ready_and_catalog(world: WorldState):
    s = Sim(id="s5", name="E", position=(400.0, 400.0))
    s.inventory = {"wood": 6.0, "stone": 2.0}
    world.add_sim(s)
    p = perception_crafting(s, world)
    assert "stone_axe" in p["ready_now"]
    assert any(r["id"] == "cottage" for r in p["recipes"])


def test_structured_to_legacy_craft(world: WorldState):
    s = Sim(id="s6", name="F", position=(10.0, 10.0))
    leg = structured_to_legacy(
        {"action": "craft", "target": {"type": "recipe", "id": "wooden_hammer"}, "intent": "need a hammer"},
        s,
        world,
    )
    assert leg["action"] == "craft"
    assert leg["detail"] == "wooden_hammer"


def test_structured_to_legacy_invalid_recipe_becomes_explore(world: WorldState):
    s = Sim(id="s7", name="G", position=(10.0, 10.0))
    leg = structured_to_legacy(
        {"action": "craft", "target": {"type": "recipe", "id": "fake_recipe"}},
        s,
        world,
    )
    assert leg["action"] == "explore"


def test_cottage_blocked_when_sheltered(world: WorldState):
    from entities.structure import Structure

    s = Sim(id="s4", name="D", position=(300.0, 300.0))
    s.inventory = {"wood": 20.0, "stone": 10.0}
    world.add_sim(s)
    world.add_structure(
        Structure(id="x1", name="H", position=(310.0, 310.0), structure_type="hut")
    )
    assert has_shelter_nearby(s, world)
    ids = suggested_recipe_ids(s, world)
    assert "cottage" not in ids
