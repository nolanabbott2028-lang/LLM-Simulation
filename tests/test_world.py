# tests/test_world.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from world import WorldState
from entities.sim import Sim
from entities.resource import ResourceObject


def test_world_defaults():
    w = WorldState()
    assert len(w.terrain) == 100
    assert len(w.terrain[0]) == 100
    assert w.terrain[0][0] == "grass"
    assert w.sims == {}
    assert w.structures == {}
    assert w.resources == {}
    assert len(w.pillars) == 10
    assert all(v == 0 for v in w.pillars.values())
    assert w.sim_day == 0
    assert w.sim_year == 1
    assert w.book_entries == []
    assert w.laws == []
    assert w.technologies == []
    assert w.milestones == set()
    assert w.sim_running is False
    assert w.paused is False
    assert w.speed == 1


def test_add_and_remove_sim():
    w = WorldState()
    s = Sim(id="s1", name="Adam", position=(50.0, 50.0))
    w.add_sim(s)
    assert "s1" in w.sims
    w.remove_sim("s1")
    assert "s1" not in w.sims


def test_set_terrain():
    w = WorldState()
    w.set_terrain(5, 5, "forest")
    assert w.terrain[5][5] == "forest"


def test_add_resource():
    w = WorldState()
    r = ResourceObject(id="r1", object_type="berry_bush", position=(10.0, 10.0))
    w.add_resource(r)
    assert "r1" in w.resources


def test_raise_pillar():
    w = WorldState()
    w.raise_pillar("Technology", 5)
    assert w.pillars["Technology"] == 5
    w.raise_pillar("Technology", 200)
    assert w.pillars["Technology"] == 100  # capped at 100


def test_current_era():
    w = WorldState()
    assert w.current_era() == "Stone Age"
    w.pillars["Technology"] = 15
    assert w.current_era() == "Bronze Age"
    w.pillars["Technology"] = 90
    assert w.current_era() == "Modern"


def test_add_book_entry():
    w = WorldState()
    w.add_book_entry(tab="History", title="First Fire", body="Fire was discovered.")
    assert len(w.book_entries) == 1
    assert w.book_entries[0]["tab"] == "History"
