"""Thin agent brain — perception and act only through world engine."""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from entities.sim import Sim
    from simulation.world_engine import WorldEngine


class AgentController:
    """Coordinates perceive → decide → act for one sim."""

    def __init__(self, sim: "Sim", engine: "WorldEngine"):
        self.sim = sim
        self.engine = engine

    def perceive(self) -> dict[str, Any]:
        return self.engine.get_local_state(self.sim)

    def decide(self, perception: dict[str, Any], llm_fn: Callable[..., dict[str, Any]]) -> dict[str, Any]:
        return llm_fn(self.sim, perception)

    def act(self, structured: dict[str, Any]) -> None:
        self.engine.execute_structured_action(self.sim, structured)

    def update_needs_tick(self) -> None:
        s = self.sim
        s.hunger = min(100.0, getattr(s, "hunger", 50) + 0.5)
        s.energy = max(0.0, getattr(s, "energy", 50) - 0.3)

    def step(self, llm_fn: Callable[..., dict[str, Any]] | None) -> None:
        perception = self.perceive()
        if llm_fn:
            structured = self.decide(perception, llm_fn)
        else:
            structured = {"action": "observe", "target": {"type": "self"}, "intent": "no brain"}
        self.act(structured)
        self.update_needs_tick()
