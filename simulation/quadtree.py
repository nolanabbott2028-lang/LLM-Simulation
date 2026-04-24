"""Simple point quadtree for rectangular range queries (agents, map objects)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px <= self.x + self.w and self.y <= py <= self.y + self.h

    def intersects(self, other: "Rect") -> bool:
        return not (
            other.x > self.x + self.w
            or other.x + other.w < self.x
            or other.y > self.y + self.h
            or other.y + other.h < self.y
        )


class QuadTree:
    """Stores (object_id, x, y); queries by axis-aligned rectangle."""

    def __init__(
        self,
        boundary: Rect,
        capacity: int = 8,
        max_depth: int = 12,
        depth: int = 0,
    ) -> None:
        self.boundary = boundary
        self.capacity = capacity
        self.max_depth = max_depth
        self.depth = depth
        self.points: list[tuple[str, float, float]] = []
        self.divided = False
        self.nw: QuadTree | None = None
        self.ne: QuadTree | None = None
        self.sw: QuadTree | None = None
        self.se: QuadTree | None = None

    def _subdivide(self) -> None:
        x, y, w, h = self.boundary.x, self.boundary.y, self.boundary.w, self.boundary.h
        hw, hh = w / 2, h / 2
        d = self.depth + 1
        self.nw = QuadTree(Rect(x, y, hw, hh), self.capacity, self.max_depth, d)
        self.ne = QuadTree(Rect(x + hw, y, hw, hh), self.capacity, self.max_depth, d)
        self.sw = QuadTree(Rect(x, y + hh, hw, hh), self.capacity, self.max_depth, d)
        self.se = QuadTree(
            Rect(x + hw, y + hh, hw, hh), self.capacity, self.max_depth, d
        )
        self.divided = True

    def _insert_child(self, oid: str, px: float, py: float) -> bool:
        assert self.nw and self.ne and self.sw and self.se
        if self.nw.insert(oid, px, py):
            return True
        if self.ne.insert(oid, px, py):
            return True
        if self.sw.insert(oid, px, py):
            return True
        if self.se.insert(oid, px, py):
            return True
        return False

    def insert(self, oid: str, px: float, py: float) -> bool:
        if not self.boundary.contains(px, py):
            return False
        if len(self.points) < self.capacity or self.depth >= self.max_depth:
            self.points.append((oid, px, py))
            return True
        if not self.divided:
            self._subdivide()
            old = self.points
            self.points = []
            for poid, ppx, ppy in old:
                if not self._insert_child(poid, ppx, ppy):
                    self.points.append((poid, ppx, ppy))
        if self._insert_child(oid, px, py):
            return True
        self.points.append((oid, px, py))
        return True

    def query_range(
        self, rng: Rect, found: list[tuple[str, float, float]] | None = None
    ) -> list[tuple[str, float, float]]:
        if found is None:
            found = []
        if not self.boundary.intersects(rng):
            return found
        for oid, px, py in self.points:
            if rng.contains(px, py):
                found.append((oid, px, py))
        if self.divided and self.nw:
            self.nw.query_range(rng, found)
            self.ne.query_range(rng, found)
            self.sw.query_range(rng, found)
            self.se.query_range(rng, found)
        return found


def build_agent_quadtree(world: Any, margin: float = 2.0) -> QuadTree:
    """Index alive sim positions. Boundary from world size."""
    from config import TILE_SIZE, WORLD_TILES_H, WORLD_TILES_W

    W = float(WORLD_TILES_W * TILE_SIZE)
    H = float(WORLD_TILES_H * TILE_SIZE)
    root = QuadTree(Rect(-margin, -margin, W + 2 * margin, H + 2 * margin))
    with world.lock:
        for sid, s in world.sims.items():
            if not s.alive:
                continue
            root.insert(sid, float(s.position[0]), float(s.position[1]))
    return root


def agents_in_rect_quad(
    world: Any,
    tree: QuadTree | None,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    sim_getter: Callable[[str], Any],
) -> list[Any]:
    if x0 > x1:
        x0, x1 = x1, x0
    if y0 > y1:
        y0, y1 = y1, y0
    if tree is None:
        return []
    rng = Rect(x0, y0, x1 - x0, y1 - y0)
    pts = tree.query_range(rng)
    out: list[Any] = []
    seen: set[str] = set()
    for oid, px, py in pts:
        if oid in seen:
            continue
        seen.add(oid)
        if not (x0 <= px <= x1 and y0 <= py <= y1):
            continue
        s = sim_getter(oid)
        if s and getattr(s, "alive", True):
            out.append(s)
    return out
