from entities.sim import Sim
from simulation.ideology import (
    BELIEF_KEYS,
    belief_variance_score,
    blend_child_beliefs,
    default_beliefs,
    on_trade_success,
)
from world import WorldState


def test_belief_drift_trade():
    w = WorldState()
    a = Sim(id="a", name="A", position=(0.0, 0.0))
    b = Sim(id="b", name="B", position=(10.0, 0.0))
    w.sims = {"a": a, "b": b}
    on_trade_success(a, b, w)
    assert a.beliefs["trade_good"] > 0
    assert all(k in a.beliefs for k in BELIEF_KEYS)


def test_variance_and_child_blend():
    w = WorldState()
    p1 = Sim(id="p1", name="P1", position=(0.0, 0.0), beliefs=dict(default_beliefs()))
    p2 = Sim(id="p2", name="P2", position=(1.0, 0.0), beliefs=dict(default_beliefs()))
    p1.beliefs["cooperation_good"] = 80.0
    p2.beliefs["cooperation_good"] = -60.0
    w.sims = {"p1": p1, "p2": p2}
    v = belief_variance_score(w, {"p1", "p2"})
    assert v > 100
    c = blend_child_beliefs(p1, p2)
    assert -100 <= c["cooperation_good"] <= 100
