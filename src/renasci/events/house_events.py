from __future__ import annotations
from dataclasses import dataclass
import random
import uuid
from renasci.events.base import Event
from renasci.family import Marriage
from renasci.house import House
from renasci.person import Life, Person
from renasci.race import Race
from renasci.utils.helpers import create_person, create_house


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from renasci.world import World

@dataclass
class HouseChangeEvent(Event):
    person : Person
    house : House

    @classmethod
    def create(cls, world: World, person: Person, house: House) -> HouseChangeEvent:
        return cls(
            year=world.current_year,
            type="HouseChange",
            description=f"{person.name} joined House {house.name}.",
            world=world,
            house=house,
            person=person,
        )

    def apply(self):
        super().apply()

        self.person.maiden_house = self.person.house
        self.person.house = self.house
        self.house.stats["prestige"] += 1


@dataclass
class FoundingEvent(Event):
    house_name: str
    race: Race
    major_house: bool = True
    founder: Person | None = None  # Optionally pre-specified
    founder_age_range: tuple[int, int] = (18, 40)  # Default range for founder/spouse ages

    @classmethod
    def create(cls, world: World, house_name: str, race: Race, start_year: int, major_house: bool = True, founder: Person | None = None) -> FoundingEvent:
        return cls(
            year=start_year,
            type="Founding",
            description=f"Founding of House {house_name}.",
            world=world,
            house_name=house_name,
            race=race,
            major_house=major_house,
            founder=founder
        )

    def apply(self):
        super().apply()

        world = self.world

        founder = self.founder or create_person(
            world=world,
            race=self.race,
            life=Life(age=random.randint(*self.founder_age_range)),
            is_mainline=True,
            is_head=True
        )

        house = create_house(world=world, name=self.house_name, start_year=self.year, founder=founder, is_major_house=self.major_house)

        spouse_gender = founder.gender.get_opposite()
        spouse = create_person(
            world=world,
            race=self.race,
            life=Life(age=random.randint(*self.founder_age_range)),
            house=house,
            gender=spouse_gender
        )

        marriage = Marriage(founder, spouse, self.year, house)
        founder.marriage = marriage
        spouse.marriage = marriage

        # 5. Add people to world
        world.add_people([founder, spouse])
        world.add_house(house)

@dataclass
class GrumblingEvent(Event):
    house : House

    @classmethod
    def create(cls, world: World, house: House) -> GrumblingEvent:
        return cls(
            year=world.current_year,
            type="Grumbling",
            description=f"House {house} is experiencing growing unrest among its members {house.stats["unrest"]}",
            world=world,
            house=house,
        )