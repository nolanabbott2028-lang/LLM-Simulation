"""Single coordinator: perception, structured actions, subsystem steps."""
from __future__ import annotations

from typing import Any

from config import TILE_SIZE
from entities.sim import Sim
from simulation.economy import Economy
from simulation.elections import ElectionSystem
from simulation.events import EventLog
from simulation.factions import FactionManager
from simulation.government import Government
from simulation.ideology import (
    BELIEF_KEYS,
    aggregate_beliefs,
    beliefs_prompt_block,
    compressed_belief_summary,
    ensure_beliefs,
)
from simulation.propaganda import PropagandaSystem
from simulation.relationships import ensure_edge
from simulation.timeline_engine import TimelineEngine
from simulation.war_system import WarSystem
from simulation.crafting import RECIPES, perception_crafting
from world import WorldState

NEARBY_RADIUS = 5 * TILE_SIZE

_ENGINES: dict[int, "WorldEngine"] = {}


class WorldEngine:
    def __init__(self, world: WorldState):
        self.world = world
        self.economy = Economy(world)
        self.government = Government(world)
        self.events = EventLog(world)
        self.faction_manager = FactionManager(world)
        self.timeline = TimelineEngine(world)
        self.war_system = WarSystem(world)
        self.election_system = ElectionSystem(world)
        self.propaganda_system = PropagandaSystem(world)
        world.faction_manager = self.faction_manager

    def get_local_state(self, sim: Sim) -> dict[str, Any]:
        x, y = sim.position
        nearby_agents: list[dict[str, Any]] = []
        with self.world.lock:
            for other in self.world.sims.values():
                if other.id == sim.id or not other.alive:
                    continue
                dist = ((other.position[0] - x) ** 2 + (other.position[1] - y) ** 2) ** 0.5
                if dist > NEARBY_RADIUS:
                    continue
                rel = sim.relationships.get(other.id)
                if rel is None:
                    rel = {}
                ensure_edge(rel)
                nearby_agents.append(
                    {
                        "id": other.id,
                        "name": other.name,
                        "distance_px": round(dist, 1),
                        "trust": rel.get("trust", 0),
                        "fear": rel.get("fear", 0),
                        "familiarity": rel.get("familiarity", 0),
                    }
                )
            laws = self.government.get_laws()
            resources = self.economy.get_local_resources(x, y)

        fid = self.faction_manager.sim_faction.get(sim.id)
        faction_status: dict[str, Any] = {}
        if fid and fid in self.faction_manager.factions:
            fac = self.faction_manager.factions[fid]
            trusts = []
            for m in fac.members:
                if m == sim.id:
                    continue
                r = sim.relationships.get(m)
                if r:
                    trusts.append(float(ensure_edge(dict(r))["trust"]))
            faction_status = {
                "id": fid,
                "members": len(fac.members),
                "trust_avg": round(sum(trusts) / len(trusts), 1) if trusts else 0.0,
                "resources_summary": dict(list(fac.shared_inventory.items())[:8]),
                "aggregated_beliefs": aggregate_beliefs(self.world, fac.members),
                "shared_stories": list(getattr(fac, "narratives", [])[-4:]),
            }

        return {
            "nearby_agents": nearby_agents,
            "resources": resources,
            "laws": laws,
            "faction_status": faction_status,
            "crafting": perception_crafting(sim, self.world),
            "beliefs_numeric": {k: round(ensure_beliefs(sim)[k], 1) for k in BELIEF_KEYS},
            "beliefs_summary_line": compressed_belief_summary(sim),
            "beliefs_prompt": beliefs_prompt_block(sim),
        }

    def execute_structured_action(self, sim: Sim, structured: dict[str, Any]) -> None:
        """Translate strict schema → legacy sim_loop response and apply."""
        from sim_loop import apply_sim_action

        legacy = structured_to_legacy(structured, sim, self.world)
        apply_sim_action(sim, legacy, self.world)

    def step_subsystems(self) -> None:
        self.economy.step()
        self.government.step()
        self.faction_manager.step()
        self.election_system.maybe_run(self.faction_manager, self.world.sim_day)
        self.propaganda_system.maybe_broadcast(self.faction_manager, self.world.sim_day)
        self.war_system.step(self.faction_manager)
        self.faction_manager.maybe_emergent_narratives(self.world)
        self.faction_manager.maybe_ideological_splinter(self.world)
        hint = self.timeline.maybe_update_era_label()
        if hint:
            self.world.era_pressure_label = hint


def get_world_engine(world: WorldState) -> WorldEngine:
    wid = id(world)
    if wid not in _ENGINES:
        _ENGINES[wid] = WorldEngine(world)
    return _ENGINES[wid]


def structured_to_legacy(structured: dict[str, Any], sim: Sim, world: WorldState) -> dict[str, Any]:
    """Map new JSON schema to existing thought/speech/action/target/detail format."""
    thought = (structured.get("thought") or "")[:120]
    intent = (structured.get("intent") or "")[:120]
    action = structured.get("action", "observe")
    allowed = {"move", "gather", "trade", "talk", "rest", "observe", "craft"}
    if action not in allowed:
        action = "observe"
    target = structured.get("target") if isinstance(structured.get("target"), dict) else {}

    legacy: dict[str, Any] = {
        "thought": thought,
        "speech": "",
        "action": "explore",
        "target": target.get("id"),
        "detail": "",
    }

    if action == "observe":
        legacy["action"] = "explore"
        if not legacy["thought"]:
            legacy["thought"] = intent or "I watch and wait."
        return legacy

    if action == "rest":
        legacy["action"] = "sleep"
        if intent:
            legacy["thought"] = intent
        return legacy

    if action == "move":
        legacy["action"] = "move"
        if target.get("type") == "location" and target.get("x") is not None and target.get("y") is not None:
            legacy["detail"] = f"{target['x']},{target['y']}"
        return legacy

    if action == "gather":
        legacy["action"] = "gather"
        rid = target.get("id")
        if rid:
            legacy["detail"] = str(rid)
        return legacy

    if action == "craft":
        rid: str | None = None
        raw_id = target.get("id")
        if isinstance(raw_id, str) and raw_id.strip() in RECIPES:
            rid = raw_id.strip()
        else:
            alt = structured.get("recipe") or structured.get("recipe_id")
            if isinstance(alt, str) and alt.strip() in RECIPES:
                rid = alt.strip()
        if rid:
            legacy["action"] = "craft"
            legacy["detail"] = rid
        else:
            legacy["action"] = "explore"
            if not legacy["thought"]:
                legacy["thought"] = intent or "I lack a clear plan for what to make."
        return legacy

    if action == "trade":
        legacy["action"] = "trade"
        legacy["speech"] = intent[:120] if intent else "Let us trade."
        return legacy

    if action == "talk":
        legacy["action"] = "talk"
        legacy["speech"] = intent[:120] if intent else "Hello."
        return legacy

    return legacy
