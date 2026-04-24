"""Emergent factions from trust clusters — no hardcoded teams."""
from __future__ import annotations

import itertools
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from simulation.ideology import (
    aggregate_beliefs,
    belief_variance_score,
    faction_narrative_line,
)
from simulation.relationships import ensure_edge, mutual_trust_cluster

if TYPE_CHECKING:
    from world import WorldState


MUTUAL_TRUST_SPAWN = 55.0
FACTION_UTILITY_JOIN_BIAS = 50.0
SHARED_EVENTS_FOR_NARRATIVE = 6
IDEOLOGY_VARIANCE_SPLINTER = 750.0


@dataclass
class Faction:
    id: str
    members: set[str] = field(default_factory=set)
    shared_inventory: dict[str, float] = field(default_factory=dict)
    leader: str | None = None
    reputation: int = 0
    rules: list[str] = field(default_factory=list)
    narratives: list[str] = field(default_factory=list)
    shared_event_counts: dict[str, int] = field(default_factory=dict)
    leader_charisma: float = 1.15

    def ideology_vector(self, world: "WorldState") -> dict[str, float]:
        return aggregate_beliefs(world, self.members)


def faction_utility(world: "WorldState", sim_id: str, faction: Faction) -> float:
    sim = world.sims.get(sim_id)
    if not sim:
        return -999.0
    trusts: list[float] = []
    for m in faction.members:
        if m == sim_id:
            continue
        rel = sim.relationships.get(m)
        if rel:
            trusts.append(float(ensure_edge(dict(rel))["trust"]))
    avg_trust = sum(trusts) / len(trusts) if trusts else 0.0
    safety = len(faction.members) * 2.0
    resource_access = len(faction.shared_inventory) * 5.0
    return avg_trust + safety + resource_access - FACTION_UTILITY_JOIN_BIAS


class FactionManager:
    def __init__(self, world: "WorldState"):
        self.world = world
        self.factions: dict[str, Faction] = {}
        self.sim_faction: dict[str, str] = {}

    def _sync_shared_inventory(self, fac: Faction) -> None:
        total: dict[str, float] = {}
        with self.world.lock:
            for m in fac.members:
                inv = self.world.sims[m].inventory if m in self.world.sims else {}
                for k, v in inv.items():
                    total[k] = total.get(k, 0) + float(v)
        fac.shared_inventory = {k: round(v, 2) for k, v in total.items()}

    def try_spawn_from_high_trust(self) -> None:
        ids = list(self.world.sims.keys())
        if len(ids) < 3:
            return
        rels = {sid: self.world.sims[sid].relationships for sid in ids}
        for combo in itertools.combinations(sorted(ids), 3):
            mt = mutual_trust_cluster(rels, list(combo))
            if mt < MUTUAL_TRUST_SPAWN:
                continue
            fids = {self.sim_faction.get(x) for x in combo}
            if len(fids) == 1 and None not in fids:
                continue
            fid = str(uuid.uuid4())[:8]
            fac = Faction(id=fid, members=set(combo))
            fac.leader = combo[0]
            self.factions[fid] = fac
            for m in combo:
                self.sim_faction[m] = fid
            self._sync_shared_inventory(fac)

    def evaluate_membership(self) -> None:
        """Pick independent vs best faction by utility."""
        with self.world.lock:
            n_alive = sum(1 for s in self.world.sims.values() if s.alive)
        for sid, sim in list(self.world.sims.items()):
            if n_alive <= 2 and self.sim_faction.get(sid):
                continue
            solo_u = float(getattr(sim, "status", 50)) * 0.5
            best_fid: str | None = None
            best_u = solo_u
            for fid, fac in self.factions.items():
                u = faction_utility(self.world, sid, fac)
                if u > best_u:
                    best_u = u
                    best_fid = fid

            cur = self.sim_faction.get(sid)
            if best_fid is None:
                if cur and cur in self.factions:
                    self.factions[cur].members.discard(sid)
                    if not self.factions[cur].members:
                        del self.factions[cur]
                    self.sim_faction.pop(sid, None)
                continue

            if cur != best_fid:
                if cur and cur in self.factions:
                    self.factions[cur].members.discard(sid)
                    if not self.factions[cur].members:
                        del self.factions[cur]
                fac = self.factions.setdefault(best_fid, Faction(id=best_fid))
                fac.members.add(sid)
                self.sim_faction[sid] = best_fid
                self._sync_shared_inventory(fac)

        for fac in self.factions.values():
            self._sync_shared_inventory(fac)

    def step(self) -> None:
        self.try_spawn_from_high_trust()
        self.evaluate_membership()

    def record_shared_trade(self, sim_a: str, sim_b: str) -> None:
        fa = self.sim_faction.get(sim_a)
        fb = self.sim_faction.get(sim_b)
        if not fa or fa != fb:
            return
        fac = self.factions.get(fa)
        if not fac:
            return
        fac.shared_event_counts["mutual_trade"] = fac.shared_event_counts.get("mutual_trade", 0) + 1

    def maybe_emergent_narratives(self, world: "WorldState") -> None:
        from simulation.timeline_engine import TimelineEngine

        tl = TimelineEngine(world)
        for fid, fac in list(self.factions.items()):
            n = fac.shared_event_counts.get("mutual_trade", 0)
            tier = n // SHARED_EVENTS_FOR_NARRATIVE
            added = 0
            while len(fac.narratives) < tier and added < 2:
                line = faction_narrative_line(world, fac)
                fac.narratives.append(line[:200])
                tl.log("shared_narrative", line[:240], {"faction": fid})
                added += 1

    def maybe_ideological_splinter(self, world: "WorldState") -> None:
        from simulation.ideology import ensure_beliefs
        from simulation.timeline_engine import TimelineEngine

        tl = TimelineEngine(world)

        for fid, fac in list(self.factions.items()):
            if len(fac.members) < 4:
                continue
            var_score = belief_variance_score(world, fac.members)
            if var_score < IDEOLOGY_VARIANCE_SPLINTER:
                continue
            ids = sorted(
                fac.members,
                key=lambda i: ensure_beliefs(world.sims[i])["cooperation_good"],
            )
            mid = len(ids) // 2
            if mid < 1 or mid >= len(ids):
                continue
            low_c = set(ids[:mid])
            high_c = set(ids[mid:])
            if len(high_c) < 2:
                continue
            new_id = str(uuid.uuid4())[:8]
            new_fac = Faction(id=new_id, members=set(high_c), leader=next(iter(high_c)))
            self.factions[new_id] = new_fac
            for sid in high_c:
                self.sim_faction[sid] = new_id
                fac.members.discard(sid)
            if not fac.members:
                del self.factions[fid]
                for k in list(self.sim_faction.keys()):
                    if self.sim_faction.get(k) == fid:
                        self.sim_faction.pop(k, None)
            else:
                self._sync_shared_inventory(fac)
            self._sync_shared_inventory(new_fac)
            tl.log(
                "splinter",
                f"Band {fid} split as views diverged; some formed {new_id}.",
                {"old": fid, "new": new_id},
            )
            try:
                from simulation.world_engine import get_world_engine

                ws = get_world_engine(world).war_system
                for other_id in self.factions:
                    if other_id not in (fid, new_id):
                        ws.add_grievance(fid, other_id, 3.0)
            except Exception:
                pass

    def snapshot(self) -> dict:
        return {
            "factions": {
                fid: {
                    "members": list(f.members),
                    "leader": f.leader,
                    "reputation": f.reputation,
                    "rules": list(f.rules),
                    "narratives": list(f.narratives),
                    "shared_event_counts": dict(f.shared_event_counts),
                    "leader_charisma": f.leader_charisma,
                }
                for fid, f in self.factions.items()
            },
            "sim_faction": dict(self.sim_faction),
        }

    def restore(self, data: dict) -> None:
        self.factions.clear()
        self.sim_faction.clear()
        for fid, fd in (data or {}).get("factions", {}).items():
            fac = Faction(
                id=fid,
                members=set(fd.get("members", [])),
                leader=fd.get("leader"),
                reputation=int(fd.get("reputation", 0)),
                rules=list(fd.get("rules", [])),
                narratives=list(fd.get("narratives", [])),
                shared_event_counts=dict(fd.get("shared_event_counts", {})),
                leader_charisma=float(fd.get("leader_charisma", 1.15)),
            )
            self.factions[fid] = fac
        self.sim_faction.update((data or {}).get("sim_faction", {}))
        for fac in self.factions.values():
            self._sync_shared_inventory(fac)
