"""Laws, crime log, enforcement, political power map."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from entities.sim import Sim
    from world import WorldState


def _law_strings(world: "WorldState") -> list[str]:
    out: list[str] = []
    for L in world.laws:
        if isinstance(L, dict):
            out.append(str(L.get("law", L)))
        else:
            out.append(str(L))
    return out


class Government:
    def __init__(self, world: "WorldState"):
        self.world = world

    def get_laws(self, _location: tuple[float, float] | None = None) -> list[str]:
        with self.world.lock:
            return _law_strings(self.world)

    def report_crime(self, agent: "Sim", crime_type: str, detail: str = "") -> None:
        with self.world.lock:
            self.world.crime_log.append(
                {"agent": agent.id, "agent_name": agent.name, "type": crime_type, "detail": detail}
            )

    def enforce(self) -> None:
        with self.world.lock:
            crimes = list(self.world.crime_log)
            self.world.crime_log.clear()
        for c in crimes:
            sid = c.get("agent")
            sim = self.world.sims.get(sid)
            if not sim:
                continue
            ctype = c.get("type", "")
            if ctype in ("theft", "assault", "raid"):
                sim.status = max(0, getattr(sim, "status", 50) - 10)
                sim.memory.append(f"Punished by law for {ctype}.")
                try:
                    from simulation.ideology import on_public_punishment

                    on_public_punishment(sim, self.world)
                except Exception:
                    pass
            elif ctype == "vandalism":
                sim.status = max(0, getattr(sim, "status", 50) - 5)

    def update_politics(self) -> None:
        with self.world.lock:
            fm = getattr(self.world, "faction_manager", None)
            for sid, sim in self.world.sims.items():
                inv = sim.inventory
                wealth = sum(float(v) for v in inv.values())
                bonus = 0.0
                if fm:
                    fid = fm.sim_faction.get(sid)
                    if fid and fid in fm.factions:
                        bonus = len(fm.factions[fid].members) * 3.0
                self.world.power_map[sid] = min(100.0, wealth * 0.5 + bonus)

    def step(self) -> None:
        self.enforce()
        self.update_politics()
