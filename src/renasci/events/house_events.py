from __future__ import annotations
from dataclasses import dataclass
import random
from renasci.events.base import Event
from renasci.family import Marriage
from renasci.house import House
from renasci.person import Life, Person
from renasci.race import Race
from renasci.utils.helpers import create_person




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
            race=self.race,
            life=Life(age=random.randint(*self.founder_age_range)),
            is_mainline=True,
            is_head=True
        )

        # 2. Create House
        house = House(self.house_name, self.year, founder, self.major_house)
        founder.house = house

        # 3. Create Spouse
        spouse_gender = founder.gender.get_opposite()
        spouse = create_person(
            race=self.race,
            life=Life(age=random.randint(*self.founder_age_range)),
            house=house,
            gender=spouse_gender
        )

        # 4. Quietly marry (no marriage event, just link internally)
        marriage = Marriage(founder, spouse, self.year, house)
        founder.marriage = marriage
        spouse.marriage = marriage

        # 5. Add people to world
        world.add_people([founder, spouse])
        world.add_house(house)