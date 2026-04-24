"""Lightweight global event log for history and debugging."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from world import WorldState


class EventLog:
    def __init__(self, world: "WorldState", max_entries: int = 200):
        self.world = world
        self.max_entries = max_entries

    def emit(self, kind: str, payload: dict[str, Any]) -> None:
        entry = {"kind": kind, "payload": payload}
        with self.world.lock:
            self.world.global_events.append(entry)
            if len(self.world.global_events) > self.max_entries:
                self.world.global_events[:] = self.world.global_events[-self.max_entries :]
