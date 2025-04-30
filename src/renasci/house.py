from __future__ import annotations
from dataclasses import dataclass, field

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from renasci.person import Person


@dataclass
class House:
    name: str
    start_year: int
    founder: Person
    major_house: bool = True
    people: dict[str, Person] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return str(self)
    
    def __post_init__(self):
        self.add_person(self.founder)

    def add_person(self, person: Person):
        self.people[person.id] = person