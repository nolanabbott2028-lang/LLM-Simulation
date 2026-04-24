"""Resources, optional prices — mutations only through WorldEngine / sim_loop actions."""
from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from config import TILE_SIZE

if TYPE_CHECKING:
    from entities.sim import Sim
    from world import WorldState


class Economy:
    def __init__(self, world: "WorldState"):
        self.world = world

    def get_local_resources(self, x: float, y: float, radius_px: float = 160.0) -> list[dict]:
        """Nearby resource nodes for perception (matches gather radius scale)."""
        out: list[dict] = []
        with self.world.lock:
            for rid, res in self.world.resources.items():
                if res.depleted:
                    continue
                dist = math.hypot(res.position[0] - x, res.position[1] - y)
                if dist <= radius_px:
                    out.append(
                        {
                            "id": rid,
                            "type": res.object_type,
                            "amount": int(res.quantity),
                            "distance_px": round(dist, 1),
                        }
                    )
        return out

    def step(self) -> None:
        self._regenerate_resources()
        self._update_prices()

    def _regenerate_resources(self) -> None:
        """Slow regrowth on resource nodes (forest-like types)."""
        with self.world.lock:
            for res in self.world.resources.values():
                if res.depleted:
                    continue
                row = int(res.position[1]) // TILE_SIZE
                col = int(res.position[0]) // TILE_SIZE
                if row < 0 or col < 0:
                    continue
                try:
                    cell = self.world.terrain[row][col]
                except (IndexError, TypeError):
                    continue
                if cell != "forest":
                    continue
                if random.random() > 0.03:
                    continue
                if res.object_type in ("wood", "berry_bush"):
                    res.quantity += random.uniform(0.2, 1.0)
                    if res.quantity > 0:
                        res.depleted = False

    def _update_prices(self) -> None:
        """Soft scarcity pressure on optional global prices."""
        with self.world.lock:
            prices = self.world.prices
            stock: dict[str, float] = {}
            n = max(1, len(self.world.sims))
            for sim in self.world.sims.values():
                for k, v in sim.inventory.items():
                    stock[k] = stock.get(k, 0) + float(v)
            tracked = (
                "berries", "wood", "stone", "meat", "grain", "hide", "fresh_water",
                "berry_bush", "animal_spawn", "farm_plot", "tree", "stone_deposit",
            )
            for name in tracked:
                total = stock.get(name, 0.0)
                scarcity = max(0.1, 3.0 - total / n)
                base = prices.get(name, 1.0)
                prices[name] = round(base * 0.96 + scarcity * 0.04, 3)
