# tests/test_entities.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from entities.sim import Sim
from entities.structure import Structure
from entities.resource import ResourceObject


def test_sim_defaults():
    s = Sim(id="s1", name="Adam", position=(50.0, 50.0))
    assert s.health == 100
    assert s.hunger == 100
    assert s.energy == 100
    assert s.age == 0
    assert s.role is None
    assert s.relationships == {}
    assert s.memory == []
    assert s.inventory == {}
    assert s.skills == {}
    assert s.speech_bubble is None
    assert s.thought_bubble is None


def test_structure_defaults():
    st = Structure(id="b1", name="Hut", position=(10.0, 10.0), structure_type="hut")
    assert st.built_by is None
    assert st.resources_stored == {}


def test_resource_defaults():
    r = ResourceObject(id="r1", object_type="berry_bush", position=(20.0, 20.0))
    assert r.quantity > 0
    assert r.depleted is False
