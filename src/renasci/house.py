from __future__ import annotations
from dataclasses import dataclass, field

from typing import TYPE_CHECKING

from renasci.stats import StatBlock, StatMixin
if TYPE_CHECKING:
    from renasci.person import Person


DEFAULT_HOUSE_STATS = {
            "prestige": (10, 0, 100),
            "influence": (5, 0, 100),
            "unrest": (0, 0, 100),
            "wealth": (20, 0, 100),
        }

@dataclass
class House():
    name: str
    start_year: int
    founder: Person
    major_house: bool = True
    people: dict[str, Person] = field(default_factory=dict)
    stats : StatBlock = field(default_factory=lambda : StatBlock.from_dict(DEFAULT_HOUSE_STATS))

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return str(self)
    
    def __post_init__(self):
        self.add_person(self.founder)

    def add_person(self, person: Person):
        self.people[person.id] = person