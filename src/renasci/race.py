from __future__ import annotations
from dataclasses import dataclass, field
import random
from typing import Literal


@dataclass
class Race:
    name: Literal["Human", "Leonin", "Orc", "Dwarf", "Gnome"] #TODO: I should probably make this data driven
    marriage_age_range: tuple[int, int]
    lifespan_range: tuple[int, int]
    childbearing_range: tuple[int, int]
    namebank: list[str] = field(default_factory=list)
    valid_pairings: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name
    
    def generate_first_name(self) -> str:
        return random.choice(self.namebank)
    
    def valid_pairing(self, race : Race) -> bool:
        return race.name in self.valid_pairings

    def death_chance(self, age: int) -> float:
        if age < self.lifespan_range[0]:
            return 0.0
        elif age >= self.lifespan_range[1]:
            return 1.0
        return (age - self.lifespan_range[0]) / (self.lifespan_range[1] - self.lifespan_range[0])

