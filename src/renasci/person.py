from __future__ import annotations
from dataclasses import dataclass, field
from renasci.family import Family, Marriage
from renasci.house import House
from renasci.orientation import Gender, Sexuality
from renasci.race import Race
from renasci.stats import StatBlock

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from renasci.world import World

@dataclass
class PersonView:
    is_head : bool
    gender : str
    house : House

@dataclass
class Life:
    birth_year: int | None = None
    age : int = 0
    is_alive : bool = True
    death_year: int | None = None

    def __str__(self) -> str:
        return str(self.age)

    def __repr__(self) -> str:
        return str(self.age)

    def die(self, year: int):
        self.death_year = year
        self.is_alive = False


DEFAULT_PERSON_STATS = {
            "reputation": (0, -100, 100),
            "loyalty": (50, 0, 100),
            "ambition": (30, 0, 100),
        }   

@dataclass
class Person():
    id: str
    world : World
    first_name: str
    gender: Gender
    house: House
    race: Race
    life: Life
    sexuality: Sexuality = field(default_factory=Sexuality)
    family: Family = field(default_factory=Family)
    marriage: Marriage | None = None
    is_mainline: bool = False
    is_head: bool = False
    is_immortal: bool = False
    maiden_house: House | None = None  # for marriage name changes
    stats : StatBlock = field(init=False)

    def __post_init__(self):
        self.stats = StatBlock.from_dict(self,self.world,DEFAULT_PERSON_STATS)

    @property
    def name(self) -> str:
        return f"{self.first_name} {self.house.name}"

    @property
    def is_married(self) -> bool:
        return self.marriage is not None

    @property
    def is_alive(self) -> bool:
        return self.life.is_alive 
            
    @property
    def age(self) -> int:
        return self.life.age
    
    @property
    def spouse(self) -> Person | None:
        return self.marriage.get_spouse(self) if self.is_married else None
    
    @property
    def can_have_children(self) -> bool:
        return self.is_married and self.gender == Gender.FEMALE and self.marriage.get_spouse(self).gender == self.gender.get_opposite()
    
    def die(self, year: int):
        self.life.die(year)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return str(self)

    def __hash__(self) -> int:
        return hash(self.id)
    
    def to_view(self, overrides: dict = None) -> PersonView:
        overrides = overrides or {}

        return PersonView(
            house=overrides.get('house', self.house),
            is_head=overrides.get('is_head', self.is_head),
            gender=overrides.get('gender', self.gender),
        )