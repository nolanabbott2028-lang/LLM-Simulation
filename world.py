import threading
from dataclasses import dataclass, field
from config import WORLD_TILES_W, WORLD_TILES_H, PILLAR_NAMES, ERA_THRESHOLDS
from entities.sim import Sim
from entities.structure import Structure
from entities.resource import ResourceObject


@dataclass
class WorldState:
    terrain: list = field(default_factory=lambda: [
        ["grass"] * WORLD_TILES_W for _ in range(WORLD_TILES_H)
    ])
    sims: dict = field(default_factory=dict)        # id -> Sim
    structures: dict = field(default_factory=dict)  # id -> Structure
    resources: dict = field(default_factory=dict)   # id -> ResourceObject
    pillars: dict = field(default_factory=lambda: {name: 0 for name in PILLAR_NAMES})
    sim_day: int = 0
    sim_year: int = 1
    book_entries: list = field(default_factory=list)
    laws: list = field(default_factory=list)
    technologies: list = field(default_factory=list)
    milestones: set = field(default_factory=set)
    sim_running: bool = False
    paused: bool = False
    speed: int = 1
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add_sim(self, sim: Sim):
        with self.lock:
            self.sims[sim.id] = sim

    def remove_sim(self, sim_id: str):
        with self.lock:
            self.sims.pop(sim_id, None)

    def set_terrain(self, row: int, col: int, terrain_type: str):
        with self.lock:
            self.terrain[row][col] = terrain_type

    def add_resource(self, resource: ResourceObject):
        with self.lock:
            self.resources[resource.id] = resource

    def add_structure(self, structure: Structure):
        with self.lock:
            self.structures[structure.id] = structure

    def raise_pillar(self, name: str, amount: float):
        with self.lock:
            self.pillars[name] = min(100, self.pillars[name] + amount)

    def current_era(self) -> str:
        tech = self.pillars["Technology"]
        era = "Stone Age"
        for threshold, label in ERA_THRESHOLDS:
            if tech >= threshold:
                era = label
        return era

    def add_book_entry(self, tab: str, title: str, body: str):
        with self.lock:
            self.book_entries.append({
                "tab": tab,
                "title": title,
                "body": body,
                "year": self.sim_year,
                "day": self.sim_day,
            })

    def advance_time(self):
        with self.lock:
            self.sim_day += 1
            if self.sim_day >= 365:
                self.sim_day = 0
                self.sim_year += 1
