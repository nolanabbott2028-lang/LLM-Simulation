"""Leader-shaped belief nudges — structured types only, no free LLM here in core tick."""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

from simulation.ideology import BELIEF_KEYS, clamp_beliefs, ensure_beliefs

if TYPE_CHECKING:
    from simulation.factions import FactionManager
    from world import WorldState


PROPAGANDA_CYCLE_DAYS = 60
STRENGTH = 2.5


class PropagandaSystem:
    def __init__(self, world: "WorldState"):
        self.world = world

    def maybe_broadcast(self, fm: "FactionManager", sim_day: int) -> None:
        if sim_day <= 0 or sim_day % PROPAGANDA_CYCLE_DAYS != 0:
            return
        for fid, fac in fm.factions.items():
            lead = fac.leader
            if not lead or lead not in fac.members:
                continue
            charisma = float(getattr(fac, "leader_charisma", 1.2))
            msg_type = random.choice(("unity", "fear", "trade_praise"))
            deltas: dict[str, float] = {}
            if msg_type == "unity":
                deltas = {"cooperation_good": STRENGTH * charisma, "authority_good": STRENGTH * 0.5}
            elif msg_type == "fear":
                deltas = {"outgroup_danger": STRENGTH * charisma, "violence_justified": STRENGTH * 0.4}
            else:
                deltas = {"trade_good": STRENGTH * charisma}
            with self.world.lock:
                for sid in fac.members:
                    sim = self.world.sims.get(sid)
                    if not sim:
                        continue
                    mult = charisma if sid != lead else 1.0
                    b = ensure_beliefs(sim)
                    for k in BELIEF_KEYS:
                        if k in deltas:
                            b[k] += deltas[k] * mult * (0.85 if sid != lead else 0.5)
                    clamp_beliefs(b)
