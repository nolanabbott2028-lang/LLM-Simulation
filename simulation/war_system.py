"""Faction hostility + simple logistics-style pressure (no random battle rolls)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from simulation.ideology import ideology_distance_factions

if TYPE_CHECKING:
    from simulation.factions import FactionManager
    from world import WorldState


HOSTILITY_START = 85.0
GRIEVANCE_ATTACK = 12.0


class WarSystem:
    def __init__(self, world: "WorldState"):
        self.world = world
        self.grievances: dict[str, float] = {}

    def _pair_key(self, a: str, b: str) -> str:
        x, y = sorted([a, b])
        return f"{x}:{y}"

    def add_grievance(self, fid_a: str, fid_b: str, amount: float) -> None:
        k = self._pair_key(fid_a, fid_b)
        self.grievances[k] = min(200.0, self.grievances.get(k, 0.0) + amount)

    def military_power(self, fm: "FactionManager", fid: str) -> float:
        fac = fm.factions.get(fid)
        if not fac:
            return 0.0
        total = 0.0
        with self.world.lock:
            for sid in fac.members:
                s = self.world.sims.get(sid)
                if not s or not s.alive:
                    continue
                inv = sum(float(v) for v in s.inventory.values())
                food = float(s.inventory.get("berry_bush", 0) + s.inventory.get("animal_spawn", 0))
                supply = 0.7 + min(0.3, food * 0.05)
                total += (s.health * 0.02 + inv * 0.01 + 2.0) * supply
        return max(0.5, total)

    def hostility(self, fm: "FactionManager", fa: str, fb: str) -> float:
        a_set = fm.factions.get(fa)
        b_set = fm.factions.get(fb)
        if not a_set or not b_set:
            return 0.0
        ideo_dist = ideology_distance_factions(self.world, a_set.members, b_set.members)
        g = self.grievances.get(self._pair_key(fa, fb), 0.0)
        return ideo_dist * 1.2 + g * 0.15

    def step(self, fm: "FactionManager") -> None:
        from simulation.timeline_engine import TimelineEngine

        tl = TimelineEngine(self.world)
        ids = list(fm.factions.keys())
        for i, fa in enumerate(ids):
            for fb in ids[i + 1 :]:
                h = self.hostility(fm, fa, fb)
                if h < HOSTILITY_START:
                    continue
                pa = self.military_power(fm, fa)
                pb = self.military_power(fm, fb)
                delta = pb - pa
                # Pressure on weaker side's cohesion (status), not RNG outcome
                if delta > 5 and pa < pb:
                    target_fid = fa
                elif delta < -5 and pb < pa:
                    target_fid = fb
                else:
                    continue
                fac = fm.factions.get(target_fid)
                if not fac:
                    continue
                drain = min(8.0, abs(delta) * 0.15)
                with self.world.lock:
                    for sid in list(fac.members):
                        s = self.world.sims.get(sid)
                        if s:
                            s.status = max(0, int(getattr(s, "status", 50) - drain * 0.3))
                tl.log(
                    "war",
                    f"Conflict between bands {fa} and {fb} strains {target_fid}.",
                    {"a": fa, "b": fb, "pressure": round(delta, 2)},
                )

    def snapshot(self) -> dict[str, Any]:
        with self.world.lock:
            wars = list(getattr(self.world, "active_wars", []))
        return {"grievances": dict(self.grievances), "active_wars": wars}

    def restore(self, data: dict[str, Any]) -> None:
        self.grievances = dict(data.get("grievances", {}))
        with self.world.lock:
            self.world.active_wars = list(data.get("active_wars", []))
