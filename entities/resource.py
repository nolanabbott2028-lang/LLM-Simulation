from dataclasses import dataclass


@dataclass
class ResourceObject:
    id: str
    object_type: str
    position: tuple[float, float]
    quantity: int = 10
    depleted: bool = False
