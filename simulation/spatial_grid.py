"""Simple uniform grid for spatial queries (agents / entities by world position)."""
from __future__ import annotations

from typing import Any, Callable, Iterator


class SpatialGrid:
    """Cells keyed by (ix, iy) where ix = floor(x / cell_size)."""

    def __init__(self, cell_size: float = 128.0) -> None:
        self.cell_size = max(8.0, float(cell_size))
        self.cells: dict[tuple[int, int], list[str]] = {}

    def clear(self) -> None:
        self.cells.clear()

    def insert(self, obj_id: str, x: float, y: float) -> None:
        cs = self.cell_size
        key = (int(x // cs), int(y // cs))
        self.cells.setdefault(key, []).append(obj_id)

    def _cell_range(
        self, x0: float, y0: float, x1: float, y1: float
    ) -> Iterator[tuple[int, int]]:
        cs = self.cell_size
        ix0 = int(x0 // cs)
        iy0 = int(y0 // cs)
        ix1 = int(x1 // cs)
        iy1 = int(y1 // cs)
        for ix in range(ix0, ix1 + 1):
            for iy in range(iy0, iy1 + 1):
                yield (ix, iy)

    def query_rect_ids(self, x0: float, y0: float, x1: float, y1: float) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for key in self._cell_range(x0, y0, x1, y1):
            for oid in self.cells.get(key, []):
                if oid not in seen:
                    seen.add(oid)
                    out.append(oid)
        return out


def build_agent_grid(world: Any, cell_size: float = 128.0) -> SpatialGrid:
    """Index alive sims for fast rectangular queries."""
    g = SpatialGrid(cell_size=cell_size)
    with world.lock:
        for sid, s in world.sims.items():
            if not s.alive:
                continue
            g.insert(sid, float(s.position[0]), float(s.position[1]))
    return g


def agents_in_rect(
    world: Any,
    grid: SpatialGrid | None,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    sim_getter: Callable[[str], Any],
) -> list[Any]:
    """Return Sim objects whose positions lie in axis-aligned rect (inclusive)."""
    if x0 > x1:
        x0, x1 = x1, x0
    if y0 > y1:
        y0, y1 = y1, y0
    out: list[Any] = []
    if grid is not None:
        for sid in grid.query_rect_ids(x0, y0, x1, y1):
            s = sim_getter(sid)
            if not s or not getattr(s, "alive", True):
                continue
            x, y = float(s.position[0]), float(s.position[1])
            if x0 <= x <= x1 and y0 <= y <= y1:
                out.append(s)
        return out
    with world.lock:
        for sid, s in world.sims.items():
            if not s.alive:
                continue
            x, y = float(s.position[0]), float(s.position[1])
            if x0 <= x <= x1 and y0 <= y <= y1:
                out.append(s)
    return out
