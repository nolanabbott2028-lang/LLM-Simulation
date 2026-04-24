from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Bubble:
    text: str
    timer: float  # seconds remaining


@dataclass
class Sim:
    id: str
    name: str
    position: tuple[float, float]
    health: float = 100.0
    hunger: float = 100.0
    thirst: float = 100.0
    energy: float = 100.0
    age: float = 0.0
    role: Optional[str] = None
    relationships: dict = field(default_factory=dict)
    memory: list = field(default_factory=list)
    inventory: dict = field(default_factory=dict)
    skills: dict = field(default_factory=dict)
    language_fluency: float = 0.0  # personal exposure to the shared tongue (0–100)
    traits: dict = field(default_factory=lambda: {"aggression": 50, "intelligence": 50, "sociability": 50})
    safety: float = 50.0
    status: int = 50
    beliefs: dict = field(default_factory=dict)  # cooperation_good, authority_good, … (−100..100)
    speech_bubble: Optional[Bubble] = None
    thought_bubble: Optional[Bubble] = None
    alive: bool = True
    # Per-frame state for rendering (not persisted except facing optional)
    facing: float = 1.0  # 1 = right, -1 = left
    moving: bool = False
    in_water: bool = False
    walk_cycle: float = 0.0  # 0-1, toggles walk vs idle pose while moving
