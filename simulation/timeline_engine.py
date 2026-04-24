"""Macro event log + optional era label from recent pressures."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from world import WorldState


class TimelineEngine:
    def __init__(self, world: "WorldState", max_entries: int = 400):
        self.world = world
        self.max_entries = max_entries

    def log(self, kind: str, summary: str, payload: dict[str, Any] | None = None) -> None:
        entry = {
            "kind": kind,
            "summary": summary[:300],
            "payload": payload or {},
            "year": self.world.sim_year,
            "day": self.world.sim_day,
        }
        with self.world.lock:
            self.world.timeline_events.append(entry)
            if len(self.world.timeline_events) > self.max_entries:
                self.world.timeline_events[:] = self.world.timeline_events[-self.max_entries :]

    def recent(self, n: int = 12) -> list[dict[str, Any]]:
        with self.world.lock:
            return list(self.world.timeline_events[-n:])

    def maybe_update_era_label(self) -> str | None:
        """Cheap heuristic label from recent macro events (not predefined civ eras)."""
        with self.world.lock:
            tail = self.world.timeline_events[-80:]
        if not tail:
            return None
        kinds = [e["kind"] for e in tail]
        war_n = sum(1 for k in kinds if k == "war")
        split_n = sum(1 for k in kinds if k == "splinter")
        trade_n = sum(1 for k in kinds if k == "trade_boom")
        if war_n >= 5:
            return "time of many clashes"
        if split_n >= 4:
            return "time of breaking bands"
        if trade_n >= 6:
            return "time of growing exchange"
        return None
