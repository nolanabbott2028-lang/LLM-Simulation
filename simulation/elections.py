"""Periodic leadership by trust + ideology alignment (no parties)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.ideology import BELIEF_KEYS, aggregate_beliefs, ensure_beliefs

if TYPE_CHECKING:
    from simulation.factions import FactionManager
    from world import WorldState


ELECTION_CYCLE_DAYS = 45


class ElectionSystem:
    def __init__(self, world: "WorldState"):
        self.world = world

    def maybe_run(self, fm: "FactionManager", sim_day: int) -> None:
        if sim_day <= 0 or sim_day % ELECTION_CYCLE_DAYS != 0:
            return
        mean_by_faction: dict[str, dict] = {}
        for fid, fac in fm.factions.items():
            mean_by_faction[fid] = aggregate_beliefs(self.world, fac.members)

        for fid, fac in list(fm.factions.items()):
            if len(fac.members) < 2:
                continue
            mean = mean_by_faction[fid]
            best_sid = None
            best_score = -1e9
            for sid in fac.members:
                sim = self.world.sims.get(sid)
                if not sim:
                    continue
                b = ensure_beliefs(sim)
                align = sum(1.0 - abs(b[k] - mean[k]) / 100.0 for k in BELIEF_KEYS) / len(BELIEF_KEYS)
                trust_sum = 0.0
                n = 0
                for other in fac.members:
                    if other == sid:
                        continue
                    rel = sim.relationships.get(other, {})
                    trust_sum += float(rel.get("trust", rel.get("bond", 0)) / 2)
                    n += 1
                avg_trust = trust_sum / max(1, n)
                score = avg_trust * 1.5 + align * 40.0
                if score > best_score:
                    best_score = score
                    best_sid = sid
            if best_sid is not None:
                old = fac.leader
                fac.leader = best_sid
                if old != best_sid:
                    from simulation.timeline_engine import TimelineEngine

                    TimelineEngine(self.world).log(
                        "leader_change",
                        f"Band {fid} raised a new voice to lead.",
                        {"faction": fid, "leader": best_sid},
                    )
