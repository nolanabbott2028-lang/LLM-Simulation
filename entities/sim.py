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
    energy: float = 100.0
    age: float = 0.0
    role: Optional[str] = None
    relationships: dict = field(default_factory=dict)
    memory: list = field(default_factory=list)
    inventory: dict = field(default_factory=dict)
    skills: dict = field(default_factory=dict)
    speech_bubble: Optional[Bubble] = None
    thought_bubble: Optional[Bubble] = None
    alive: bool = True
