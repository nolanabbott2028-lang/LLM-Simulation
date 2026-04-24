"""LOD map hierarchy geometry."""
from world import WorldState
from simulation.world_engine import WorldEngine
from simulation.geo_hierarchy import build_map_lod


def test_build_map_lod_grid_counts():
    w = WorldState()
    WorldEngine(w)
    fm = w.faction_manager
    lod = build_map_lod(w, fm)
    assert len(lod["regions"]) == 12
    assert len(lod["provinces"]) == 24
    assert len(lod["cities"]) == 24
    assert len(lod["towns"]) == 48
    r0 = lod["regions"][0]
    assert "polygon" in r0 and len(r0["polygon"]) == 4
    assert "ideology" in r0
