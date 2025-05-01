from __future__ import annotations
from dataclasses import dataclass, field
from renasci.stats import StatBlock

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from renasci.person import Person
    from renasci.world import World


DEFAULT_HOUSE_STATS = {
            "prestige": (10, 0, 100),
            "influence": (5, 0, 100),
            "unrest": (0, 0, 100),
            "wealth": (20, 0, 100),
        }

@dataclass
class House():
    id: str
    world : World
    name: str
    start_year: int
    founder: Person
    is_major_house: bool = True
    people: dict[str, Person] = field(default_factory=dict)
    stats : StatBlock = field(init=False)

    def __post_init__(self):
        self.add_person(self.founder)
        self.founder.house = self
        self.stats = StatBlock.from_dict(self, self.world, DEFAULT_HOUSE_STATS)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return str(self)
        
    def add_person(self, person: Person):
        self.people[person.id] = person

    def __hash__(self) -> int:
        return hash(self.id)