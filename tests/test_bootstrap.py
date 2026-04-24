"""Adam & Eve bootstrap helpers."""
from bootstrap import spawn_adam_eve_if_empty, spawn_adam_eve_near
from world import WorldState


def test_spawn_adam_eve_if_empty():
    w = WorldState()
    spawn_adam_eve_if_empty(w)
    assert len(w.sims) == 2
    assert w.sim_running is True


def test_spawn_adam_eve_near_places_and_blocks_second():
    w = WorldState()
    ok, msg = spawn_adam_eve_near(w, 400.0, 300.0)
    assert ok and msg == "ok"
    assert "adam" in w.sims and "eve" in w.sims
    assert w.sim_running is True
    assert w.paused is False
    ok2, msg2 = spawn_adam_eve_near(w, 500.0, 500.0)
    assert not ok2


def test_spawn_after_dead_removes_corpses():
    w = WorldState()
    spawn_adam_eve_near(w, 100.0, 100.0)
    for s in w.sims.values():
        s.alive = False
    ok, _ = spawn_adam_eve_near(w, 200.0, 200.0)
    assert ok
    living = [s for s in w.sims.values() if s.alive]
    assert len(living) == 2
