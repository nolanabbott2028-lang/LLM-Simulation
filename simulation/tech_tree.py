"""Hooks for civilization progression — wraps existing world.technologies."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from world import WorldState


class TechTree:
    """Thin view over WorldState technologies and pillars."""

    def __init__(self, world: "WorldState"):
        self.world = world

    def known(self) -> list[str]:
        with self.world.lock:
            return list(self.world.technologies)

    def unlock(self, name: str) -> bool:
        with self.world.lock:
            if name in self.world.technologies:
                return False
            self.world.technologies.append(name)
            return True
