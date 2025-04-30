from __future__ import annotations
import random
from renasci.events.base import Event
from renasci.events.house_events import FoundingEvent, HouseChangeEvent
from renasci.events.person_events import BirthEvent, DeathEvent, MarriageEvent, SuccessionEvent, WidowEvent
from renasci.family import Family, Marriage, find_relationship
from renasci.house import House
from renasci.person import Life, Person
from renasci.race import Race
from renasci.utils.helpers import create_person
from renasci.world import World


def create_birth_event(world : World, mother: Person, father: Person, house: House) -> Event:
    if mother.race == father.race:
        race = mother.race
    else:
        race = random.choice([mother.race, father.race])

    child = create_person(
        race,
        life=Life(birth_year=world.current_year),
        house=house,
        family=Family(father=father, mother=mother),
        is_mainline=(mother.is_mainline or father.is_mainline)
    )

    return BirthEvent(
        year=world.current_year,
        type="Birth",
        description=f"{child.name} was born to {mother.name} and {father.name}.",
        world=world,
        mother=mother,
        father=father,
        child=child,
        house=house,
    )

def create_death_event(world : World, person: Person) -> Event:
    return DeathEvent(
        year=world.current_year,
        type="Death",
        description=f"{person.name} died.",
        world=world,
        deceased=person,
    )

def create_marriage_event(world : World, marriage : Marriage) -> Event:
    return MarriageEvent(
        year=world.current_year,
        type="Marriage",
        description=f"{marriage.partner1} and {marriage.partner2} were married.",
        world=world,
        marriage=marriage
    )

def create_widowed_event(world : World, widow: Person, deceased: Person) -> Event:
    return WidowEvent(
        year=world.current_year,
        type="Widowed",
        description=f"{widow.name} became a widow after {deceased.name}'s death.",
        world=world,
        widow=widow
    )

def create_succession_event(world : World, successor: Person, deceased: Person) -> Event:
    return SuccessionEvent(
        year=world.current_year,
        type="Succession",
        description=f"Primarch {deceased} is succeeded by their {find_relationship(deceased.family, successor)} {successor} as the new Primarch of House {deceased.house}",
        world=world,
        successor=successor,
        deceased=deceased
    )


def create_house_change_event(world : World, person: Person, house: House) -> Event:
    return HouseChangeEvent(
        year=world.current_year,
        type="HouseChange",
        description=f"{person.name} joined House {house.name}.",
        world=world,
        house=house,
        person=person,
    )

def create_founding_event(world : World, house_name: str, race: Race, start_year: int, major_house: bool = True, founder: Person | None = None) -> Event:
    return FoundingEvent(
        year=start_year,
        type="Founding",
        description=f"Founding of House {house_name}.",
        world=world,
        house_name=house_name,
        race=race,
        major_house=major_house,
        founder=founder
    )