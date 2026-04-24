"""Terrain tiles + map HTTP helpers."""
from world import WorldState
from simulation.map_http import map_terrain
from simulation.quadtree import build_agent_quadtree
from simulation.world_engine import WorldEngine


def test_terrain_tile_payload_shape():
    w = WorldState()
    WorldEngine(w)
    p = map_terrain(w, lod=1, tx=0, ty=0)
    assert "cells" in p and p["cells"]
    assert p["grid"]["w"] > 0
    assert len(p["world_rect"]) == 4


def test_terrain_tile_oob():
    w = WorldState()
    WorldEngine(w)
    p = map_terrain(w, lod=0, tx=99, ty=99)
    assert "error" in p


def test_quadtree_builds():
    w = WorldState()
    WorldEngine(w)
    q = build_agent_quadtree(w)
    assert q.boundary.w > 0
