import sys, os, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from world import WorldState
from entities.sim import Sim
from entities.resource import ResourceObject
from persistence import save_world, load_world


def test_save_and_load_roundtrip():
    w = WorldState()
    s = Sim(id="adam", name="Adam", position=(10.0, 20.0))
    s.memory = ["Found berries", "Spoke to Eve"]
    s.inventory = {"berry_bush": 3}
    w.add_sim(s)
    r = ResourceObject(id="r1", object_type="berry_bush", position=(50.0, 60.0), quantity=5)
    w.add_resource(r)
    w.raise_pillar("Technology", 15)
    w.add_book_entry("History", "First Fire", "Fire was found.")
    w.technologies.append("stone tool")
    w.sim_year = 3
    w.sim_day = 42

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name

    save_world(w, path)
    w2 = load_world(path)

    assert "adam" in w2.sims
    assert w2.sims["adam"].name == "Adam"
    assert w2.sims["adam"].memory == ["Found berries", "Spoke to Eve"]
    assert w2.sims["adam"].inventory == {"berry_bush": 3}
    assert "r1" in w2.resources
    assert w2.pillars["Technology"] == 15
    assert len(w2.book_entries) == 1
    assert w2.technologies == ["stone tool"]
    assert w2.sim_year == 3
    assert w2.sim_day == 42
    os.unlink(path)
