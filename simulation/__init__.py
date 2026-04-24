"""Core simulation architecture: Agent, WorldEngine, Economy, Government, Factions."""
from simulation.agent import AgentController
from simulation.economy import Economy
from simulation.events import EventLog
from simulation.factions import Faction, FactionManager
from simulation.government import Government
from simulation.ideology import BELIEF_KEYS, default_beliefs, ensure_beliefs
from simulation.memory_system import compress_memory_lines
from simulation.state_snapshot import get_world_snapshot, ideology_graph_snapshot
from simulation.tech_tree import TechTree
from simulation.timeline_engine import TimelineEngine
from simulation.world_engine import WorldEngine, get_world_engine, structured_to_legacy

__all__ = [
    "BELIEF_KEYS",
    "AgentController",
    "Economy",
    "EventLog",
    "Faction",
    "FactionManager",
    "Government",
    "TechTree",
    "TimelineEngine",
    "WorldEngine",
    "compress_memory_lines",
    "default_beliefs",
    "ensure_beliefs",
    "get_world_engine",
    "get_world_snapshot",
    "ideology_graph_snapshot",
    "structured_to_legacy",
]
