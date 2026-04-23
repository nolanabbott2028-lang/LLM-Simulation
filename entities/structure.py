from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Structure:
    id: str
    name: str
    position: tuple[float, float]
    structure_type: str
    built_by: Optional[str] = None  # sim id
    resources_stored: dict = field(default_factory=dict)
